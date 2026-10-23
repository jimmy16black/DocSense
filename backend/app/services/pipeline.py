"""Document ingestion pipeline + pluggable background worker (ISSUE-003).

Replaces the old synchronous, mock-page "processing" that ran inside the HTTP
request. Now:

  * ``POST /documents/{id}/process`` only enqueues a job and returns ACCEPTED
    (HTTP 202); it never touches storage/AI itself.
  * The real pipeline runs in a background worker with its OWN database
    session, advancing the document through the state machine
    (EXTRACTING -> CHUNKING -> EMBEDDING -> COMPLETED/FAILED) durably at
    every transition (ISSUE-001 commit discipline).
  * Progress events are recorded per-document so clients poll
    ``GET /documents/{id}/status`` — the mobile app renders REAL server
    progress instead of fabricating it (Document_8 §8.4).

Transport seam: ``AsyncJobWorker`` is the default single-process asyncio
transport (zero new infra, deterministic in CI). For multi-instance
production deployments a Redis/arq transport implementing the same
``enqueue`` interface drops in without touching pipeline logic — tracked as
a follow-up in REVIEW_FINDINGS.md.

Crash recovery: the pipeline deletes and rebuilds all derived rows on every
run, so re-enqueuing a document stuck mid-pipeline (e.g. after a process
restart) is idempotent. ``recover_stale_jobs`` performs that sweep.
"""

import asyncio
import time
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import async_session_factory, commit_now
from app.models.document import (
    Citation,
    Document,
    DocumentChunk,
    DocumentPage,
    DocumentStatus,
    Extraction,
)
from app.services.extractor import pdf_extractor_service
from app.services.storage import storage_service

logger = get_logger("pipeline")

# Stages as reported to clients (coarse-grained view of the full state machine).
STAGES: dict[str, int] = {
    "QUEUED": 0,
    "EXTRACTING": 25,
    "CHUNKING": 50,
    "EMBEDDING": 75,
    "COMPLETED": 100,
    "FAILED": 100,
}

# Job callable signature: async fn(document_id, session_factory) -> None
JobFn = Callable[..., Coroutine[Any, Any, None]]


class AsyncJobWorker:
    """Single-process asyncio job runner with bounded concurrency."""

    def __init__(self, job_fn: JobFn, concurrency: int = 2) -> None:
        self._job_fn = job_fn
        self._queue: asyncio.Queue[UUID] = asyncio.Queue()
        self._tasks: set[asyncio.Task] = set()
        self._concurrency = concurrency
        # Injectable so tests can point jobs at their ephemeral DB.
        self.session_factory: Callable[[], Any] = async_session_factory

    def enqueue(self, document_id: UUID) -> None:
        self._queue.put_nowait(document_id)
        self._ensure_consumers()
        logger.info("Pipeline job enqueued", document_id=str(document_id))

    def _ensure_consumers(self) -> None:
        running = sum(1 for t in self._tasks if not t.done())
        needed = min(self._concurrency, self._queue.qsize())
        while running < needed:
            task = asyncio.create_task(self._consume(), name="pipeline-worker")
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            running += 1

    async def _consume(self) -> None:
        while not self._queue.empty():
            document_id = await self._queue.get()
            try:
                await self._job_fn(document_id, self.session_factory)
            except Exception as exc:  # noqa: BLE001 - worker must never die
                logger.error(
                    "Unhandled pipeline error",
                    document_id=str(document_id),
                    error=str(exc),
                )
            finally:
                self._queue.task_done()

    async def drain(self, timeout: float = 30.0) -> None:
        """Wait until the queue is empty and all jobs finished.

        Used by tests and by graceful shutdown. Raises TimeoutError rather
        than hanging forever.
        """
        deadline = time.monotonic() + timeout
        while (not self._queue.empty()) or any(not t.done() for t in self._tasks):
            if time.monotonic() > deadline:
                raise TimeoutError("Pipeline worker did not drain in time")
            await asyncio.sleep(0.01)

    async def shutdown(self) -> None:
        await self.drain(timeout=10.0)


def record_progress(document: Document, stage: str, message: str | None = None) -> None:
    """Append a durable progress event on the document row (polled via
    /status). metadata_json is REASSIGNED so SQLAlchemy detects the change
    (in-place mutation of a JSON dict column is not tracked)."""
    meta = dict(document.metadata_json or {})
    events = list(meta.get("progress_events", []))[-20:]
    events.append({"stage": stage, "progressPercentage": STAGES.get(stage, 0), "message": message})
    meta["progress_events"] = events
    document.metadata_json = meta


async def run_ingestion_pipeline(
    document_id: UUID,
    session_factory: Callable[[], Any] = async_session_factory,
) -> None:
    """Real end-to-end ingestion for one document. Owns its own session.

    ``session_factory`` is injectable so tests can point the background
    worker at their ephemeral DB without monkeypatching globals.
    """
    async with session_factory() as session:
        document = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if document is None:
            logger.warning("Pipeline job for missing document", document_id=str(document_id))
            return

        try:
            await _run(session, document)
        except Exception as exc:
            # Error-state machine: FAILED must be durable even though the rest
            # of the transaction is rolled back (ISSUE-001 discipline).
            await session.rollback()
            fresh = (
                await session.execute(select(Document).where(Document.id == document_id))
            ).scalar_one_or_none()
            if fresh is not None:
                fresh.status = DocumentStatus.FAILED
                fresh.error_message = str(exc)[:2000]
                record_progress(fresh, "FAILED", "Processing failed. You can retry.")
                await commit_now(session)
            logger.error("Ingestion pipeline failed", document_id=str(document_id), error=str(exc))


pipeline_worker = AsyncJobWorker(job_fn=run_ingestion_pipeline, concurrency=2)


async def _run(session, document: Document) -> None:
    # Guard against double-processing races (duplicate enqueues).
    if document.status == DocumentStatus.COMPLETED:
        return

    # ---- Stage 1: EXTRACTING — read the REAL verified bytes from storage ----
    document.status = DocumentStatus.EXTRACTING
    record_progress(document, "EXTRACTING", "Reading document pages")
    await commit_now(session)

    data = storage_service.download_file(document.storage_path)
    pages = pdf_extractor_service.extract_text_from_pdf_bytes(data)
    document.page_count = len(pages)

    if not any(text for _, text in pages):
        raise ValueError(
            "No readable text found in this PDF. It may be a scanned image — "
            "OCR support is required before this document can be processed."
        )

    # Persist page text (per-page raw_text powers provenance & FTS later).
    await session.execute(
        DocumentPage.__table__.delete().where(DocumentPage.document_id == document.id)
    )
    for page_num, text in pages:
        session.add(
            DocumentPage(
                document_id=document.id,
                user_id=document.user_id,
                page_number=page_num,
                raw_text=text[:100_000],
            )
        )
    await commit_now(session)

    # Structured envelope from the AI gateway (deterministic mock offline).
    envelope = await pdf_extractor_service.extract_structured_envelope(
        pages=pages,
        document_type_hint=document.document_type or "OTHER",
    )

    # Replace prior derived rows so re-processing is idempotent.
    await session.execute(
        Citation.__table__.delete().where(Citation.document_id == document.id)
    )
    await session.execute(
        Extraction.__table__.delete().where(Extraction.document_id == document.id)
    )
    extraction = Extraction(
        document_id=document.id,
        user_id=document.user_id,
        document_type=envelope.document_type,
        confidence_score=envelope.confidence_score,
        title=envelope.title,
        summary_bullets=envelope.summary_bullets,
        important_alerts=envelope.important_alerts,
        suggested_questions=envelope.suggested_questions,
        recommended_actions=envelope.recommended_actions,
        payload=envelope.payload,
    )
    session.add(extraction)
    await session.flush()  # need extraction.id for citation FK (same txn OK)
    for c in envelope.citations:
        session.add(
            Citation(
                document_id=document.id,
                extraction_id=extraction.id,
                user_id=document.user_id,
                page_number=c.page_number,
                section_heading=c.section_heading,
                exact_quote=c.exact_quote,
                bounding_box=c.bounding_box,
            )
        )
    document.document_type = envelope.document_type
    document.confidence_score = envelope.confidence_score
    await commit_now(session)

    # ---- Stage 2: CHUNKING ----
    document.status = DocumentStatus.CHUNKING
    record_progress(document, "CHUNKING", "Splitting into searchable chunks")
    await commit_now(session)

    chunks_data = pdf_extractor_service.chunk_text(pages)
    await session.execute(
        DocumentChunk.__table__.delete().where(DocumentChunk.document_id == document.id)
    )
    chunk_rows: list[DocumentChunk] = []
    for ch in chunks_data:
        row = DocumentChunk(
            document_id=document.id,
            user_id=document.user_id,
            page_number=ch["page_number"],
            chunk_index=ch["chunk_index"],
            content=ch["content"],
        )
        chunk_rows.append(row)
        session.add(row)
    await commit_now(session)

    # ---- Stage 3: EMBEDDING (hybrid-RAG vector leg, ISSUE-004) ----
    document.status = DocumentStatus.EMBEDDING
    record_progress(document, "EMBEDDING", "Generating embeddings for semantic search")
    await commit_now(session)

    if chunk_rows:
        from app.services.ai_gateway import ai_gateway_service

        vectors = await ai_gateway_service.generate_embeddings([c.content for c in chunk_rows])
        for row, vec in zip(chunk_rows, vectors, strict=True):
            row.embedding = vec
        await commit_now(session)

    # ---- Done ----
    document.status = DocumentStatus.COMPLETED
    document.error_message = None
    record_progress(document, "COMPLETED", "Document processed and indexed")
    await commit_now(session)
    logger.info(
        "Ingestion pipeline completed",
        document_id=str(document.id),
        pages=document.page_count,
        chunks=len(chunks_data),
    )


async def recover_stale_jobs(
    stale_seconds: int = 15 * 60,
    session_factory: Callable[[], Any] = async_session_factory,
    worker: AsyncJobWorker | None = None,
) -> int:
    """Re-enqueue documents left mid-pipeline by a crash/restart.

    Any document in a transient state whose row hasn't advanced for
    ``stale_seconds`` is picked back up; pipeline re-execution is idempotent.
    Swept periodically from the FastAPI lifespan.
    """
    worker = worker or pipeline_worker
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_seconds)
    query = select(Document.id).where(
        Document.status.in_(
            [
                DocumentStatus.EXTRACTING,
                DocumentStatus.CHUNKING,
                DocumentStatus.EMBEDDING,
                DocumentStatus.RETRYING,
            ]
        ),
        Document.updated_at < cutoff,
    )
    async with session_factory() as session:
        result = await session.execute(query)
        ids = list(result.scalars().all())
    for doc_id in ids:
        worker.enqueue(doc_id)
    if ids:
        logger.warning("Recovered stale pipeline jobs", count=len(ids))
    return len(ids)


async def start_periodic_recovery(interval_seconds: int = 300) -> None:
    """Background loop that sweeps for stale jobs (crash recovery)."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await recover_stale_jobs()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - sweep must not kill app
            logger.error("Stale-job recovery sweep failed", error=str(exc))
