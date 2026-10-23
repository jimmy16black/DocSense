import hashlib
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    DocSenseException,
    ErrorClassification,
    PermissionDeniedError,
    ResourceNotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import CurrentUser, get_current_user
from app.db.session import commit_now, get_db_session
from app.models.document import Citation, Document, DocumentStatus, Extraction
from app.schemas.citation import CitationSchema
from app.schemas.common import APIResponse, PagedData, PageMeta
from app.schemas.document import (
    DocumentEvent,
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
)
from app.schemas.extraction import ExtractionEnvelope
from app.schemas.qa import AskRequest, AskResponse, CompareRequest, CompareResponse, ComparisonItem
from app.services import audit
from app.services.extractor import pdf_extractor_service
from app.services.idempotency import idempotency_guard, save_idempotent_response
from app.services.pipeline import STAGES, pipeline_worker, record_progress
from app.services.rag import rag_service
from app.services.storage import storage_service

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = get_logger("routes.documents")
settings = get_settings()

# ISSUE-002: only ever place objects we can identify by content magic.
_MAGIC_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def _sniff_mime(data: bytes) -> str | None:
    """Return the MIME type implied by the object's leading magic bytes."""
    for magic, mime in _MAGIC_SIGNATURES:
        if data.startswith(magic):
            return mime
    # RIFF....WEBP
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _safe_file_name(raw_name: str) -> str:
    """Strip directory components and path-traversal from a client file name.

    ISSUE-002: `file_name` used to be interpolated raw into `storage_path`,
    allowing "../" segments to escape the per-user prefix.
    """
    name = raw_name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = re.sub(r"[^A-Za-z0-9 ._-]", "_", name)
    if not name or name in {".", ".."}:
        raise ValidationError("Invalid file name.")
    return name[:255]


@router.post("/upload-init", response_model=APIResponse[DocumentUploadInitResponse])
async def init_upload(
    req: DocumentUploadInitRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Initialize secure presigned document upload to Cloudflare R2 vault.
    Validates file extension, size, and MIME type; sanitizes the file name so
    it cannot escape the per-user storage prefix (ISSUE-002). The document is
    created in PENDING_UPLOAD state and may only advance after the server has
    verified the bytes that actually landed via /upload-complete.
    """
    if req.file_size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise ValidationError(
            f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB"
        )

    if req.mime_type not in settings.ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"MIME type '{req.mime_type}' is not supported. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}"
        )

    safe_name = _safe_file_name(req.file_name)
    doc_id = uuid.uuid4()
    storage_path = f"users/{current_user.id}/documents/{doc_id}/{safe_name}"

    upload_url, expires_at = storage_service.generate_upload_url(
        storage_path=storage_path,
        mime_type=req.mime_type,
        expected_size_bytes=req.file_size_bytes,
    )

    document = Document(
        id=doc_id,
        user_id=current_user.id,
        title=safe_name.rsplit(".", 1)[0],
        file_name=safe_name,
        file_size_bytes=req.file_size_bytes,
        mime_type=req.mime_type,
        storage_path=storage_path,
        status=DocumentStatus.PENDING_UPLOAD,
        document_type=req.document_type,
    )
    db.add(document)
    await audit.record(
        db,
        user_id=current_user.id,
        event_type="document.upload_init",
        document_id=doc_id,
        details={"file_name": safe_name, "size_bytes": req.file_size_bytes},
        ip_address=audit.client_ip(request),
    )
    # Commit immediately so the document row is durable BEFORE handing the
    # client a presigned URL (ISSUE-001). Otherwise an upload could reference
    # a document row that never persisted.
    await commit_now(db)

    return APIResponse(
        success=True,
        data=DocumentUploadInitResponse(
            document_id=doc_id,
            upload_url=upload_url,
            storage_path=storage_path,
            expires_at=expires_at,
        ),
        message="Upload initialized successfully.",
    )


@router.post("/{document_id}/upload-complete", response_model=APIResponse[UploadCompleteResponse])
async def complete_upload(
    document_id: uuid.UUID,
    req: UploadCompleteRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Verify uploaded bytes server-side before the lifecycle advances (ISSUE-002).

    Checks, against the object that ACTUALLY landed in storage:
      1. existence (client must finish the presigned PUT first),
      2. declared vs real size (quota accounting integrity),
      3. max-size cap,
      4. magic-byte sniffing — content must match its declared MIME type,
      5. optional client-supplied SHA-256 checksum.

    On any mismatch the document transitions UPLOADED -> FAILED with a
    USER_ACTION_REQUIRED classification and no processing is possible.
    Repeating this call after success is idempotent.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document with ID {document_id} was not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("You do not have access to this document.")

    # Idempotent replay: already verified — report the stored truth.
    # (UPLOADED with a recorded checksum means verification already passed;
    # re-verifying is harmless but we short-circuit for determinism.)
    if document.status not in (DocumentStatus.PENDING_UPLOAD,) and (
        document.metadata_json or {}
    ).get("checksum_sha256"):
        return APIResponse(
            success=True,
            data=UploadCompleteResponse(
                document_id=document.id,
                status=document.status,
                verified_size_bytes=document.file_size_bytes,
                checksum_sha256=(document.metadata_json or {}).get("checksum_sha256"),
                message="Upload already verified.",
            ),
        )

    if document.status not in (DocumentStatus.PENDING_UPLOAD, DocumentStatus.UPLOADED):
        raise ValidationError(
            f"Document is in state {document.status} and cannot accept upload completion."
        )

    async def _fail(reason: str) -> None:
        document.status = DocumentStatus.FAILED
        document.error_message = reason[:2000]
        await commit_now(db)
        logger.warning("Upload verification failed", document_id=str(document_id), reason=reason)
        raise ValidationError(reason)

    stat = storage_service.head_object(document.storage_path)
    if not stat.exists:
        await _fail(
            "No object found at the expected storage location. "
            "Complete the presigned PUT upload before calling upload-complete."
        )

    if stat.size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        await _fail(
            f"Uploaded file exceeds the maximum allowed size of "
            f"{settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
        )

    if stat.size_bytes != document.file_size_bytes:
        await _fail(
            "Uploaded file size does not match the size declared at upload-init "
            f"(declared {document.file_size_bytes} bytes, stored {stat.size_bytes} bytes)."
        )

    data = storage_service.download_file(document.storage_path)
    detected = _sniff_mime(data)
    if detected is None:
        await _fail("Uploaded content is not a recognized PDF/JPEG/PNG/WEBP file.")
    if detected != document.mime_type:
        await _fail(
            f"Declared MIME type '{document.mime_type}' does not match the actual "
            f"content type '{detected}' detected from file signature."
        )

    # For PDFs, additionally require that the object actually parses and its
    # page count is within limits — blocks crafted/corrupt files reaching the
    # ingestion pipeline (ISSUE-002).
    if detected == "application/pdf":
        try:
            parsed_pages = pdf_extractor_service.extract_text_from_pdf_bytes(data)
        except Exception as exc:
            await _fail(f"Uploaded PDF could not be parsed: {str(exc)[:300]}")
        if len(parsed_pages) > settings.MAX_PAGE_COUNT:
            await _fail(
                f"PDF has {len(parsed_pages)} pages; maximum supported is {settings.MAX_PAGE_COUNT}."
            )

    computed = hashlib.sha256(data).hexdigest()
    if req.checksum_sha256 and req.checksum_sha256.lower() != computed:
        await _fail("SHA-256 checksum mismatch between uploaded bytes and client-declared value.")

    document.status = DocumentStatus.UPLOADED
    document.metadata_json = {
        **(document.metadata_json or {}),
        "checksum_sha256": computed,
        "verified_size_bytes": stat.size_bytes,
        "etag": stat.etag,
    }
    await audit.record(
        db,
        user_id=current_user.id,
        event_type="document.upload_verified",
        document_id=document_id,
        details={"checksum_sha256": computed, "size_bytes": stat.size_bytes},
        ip_address=audit.client_ip(request),
    )
    await commit_now(db)

    return APIResponse(
        success=True,
        data=UploadCompleteResponse(
            document_id=document.id,
            status=DocumentStatus.UPLOADED,
            verified_size_bytes=stat.size_bytes,
            checksum_sha256=computed,
            message="Upload verified successfully.",
        ),
    )


@router.post(
    "/{document_id}/process",
    response_model=APIResponse[DocumentProcessResponse],
    status_code=202,
    dependencies=[Depends(idempotency_guard)],
)
async def process_document(
    document_id: uuid.UUID,
    req: DocumentProcessRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Enqueue real background ingestion for a document (ISSUE-003).

    The HTTP handler ONLY validates ownership/lifecycle state and enqueues a
    job; extraction, chunking and embedding happen in the background worker
    against the actual verified bytes in storage. Clients track progress via
    GET /documents/{id}/status. This replaces the previous synchronous
    mock-page pipeline that fabricated results inside the request.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document with ID {document_id} was not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("You do not have access to process this document.")

    # ISSUE-002: processing may only start on server-verified bytes. A client
    # that skipped (or failed) /upload-complete cannot advance the lifecycle.
    if document.status == DocumentStatus.PENDING_UPLOAD:
        raise ValidationError(
            "Upload has not been verified yet. Call POST /documents/"
            f"{document_id}/upload-complete after the PUT finishes."
        )
    if document.status == DocumentStatus.FAILED and not req.force_reprocess:
        raise ValidationError(
            "Document is in FAILED state. Reprocess with forceReprocess=true "
            "after correcting the upload."
        )

    # Idempotency: already completed -> no new job.
    if document.status == DocumentStatus.COMPLETED and not req.force_reprocess:
        resp: APIResponse[DocumentProcessResponse] = APIResponse(
            success=True,
            data=DocumentProcessResponse(
                job_id=f"job-{document.id}-cached",
                document_id=document.id,
                status=document.status,
                message="Document is already processed.",
            ),
        )
        await save_idempotent_response(db, request, current_user.id, resp)
        return resp

    # Already queued/running -> don't double-enqueue (unless forced reprocess,
    # which the pipeline handles idempotently by rebuilding derived rows).
    in_flight = document.status in (
        DocumentStatus.EXTRACTING,
        DocumentStatus.CHUNKING,
        DocumentStatus.EMBEDDING,
        DocumentStatus.RETRYING,
    )
    if in_flight and not req.force_reprocess:
        resp = APIResponse(
            success=True,
            data=DocumentProcessResponse(
                job_id=f"job-{document.id}-inflight",
                document_id=document.id,
                status=document.status,
                message="Processing already in progress.",
            ),
        )
        await save_idempotent_response(db, request, current_user.id, resp)
        return resp

    # Mark QUEUED-equivalent (VALIDATING) durably BEFORE enqueue so a crash
    # between response and job start still leaves a recoverable row
    # (ISSUE-001 + stale-job recovery sweep).
    document.status = DocumentStatus.VALIDATING
    document.error_message = None
    record_progress(document, "QUEUED", "Queued for processing")
    await audit.record(
        db,
        user_id=current_user.id,
        event_type="document.process_enqueued",
        document_id=document_id,
        details={"force_reprocess": req.force_reprocess},
        ip_address=audit.client_ip(request),
    )
    await commit_now(db)

    job_id = f"job-{document.id}-{uuid.uuid4().hex[:8]}"
    pipeline_worker.enqueue(document.id)

    resp = APIResponse(
        success=True,
        data=DocumentProcessResponse(
            job_id=job_id,
            document_id=document.id,
            status="ACCEPTED",
            message=f"Processing started. Poll /documents/{document.id}/status for progress.",
        ),
    )
    await save_idempotent_response(db, request, current_user.id, resp, status_code=202)
    return resp


@router.get("/{document_id}/status", response_model=APIResponse[DocumentStatusResponse])
async def get_document_status(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Lightweight progress endpoint for the processing UX (ISSUE-003).

    Returns the authoritative server-side stage + progress percentage and the
    recent event trail. Mobile renders THIS — never a locally invented
    progress bar (Document_8 §8.4).
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document {document_id} not found.")
    if document.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    events = (document.metadata_json or {}).get("progress_events", [])
    latest = events[-1] if events else None
    progress = STAGES.get(document.status, 0)
    if latest:
        progress = max(progress, int(latest.get("progressPercentage", 0)))

    return APIResponse(
        success=True,
        data=DocumentStatusResponse(
            document_id=document.id,
            status=document.status,
            progress_percentage=progress,
            stage=latest.get("stage", document.status) if latest else document.status,
            message=(latest.get("message") if latest else None) or document.error_message,
            events=[DocumentEvent.model_validate(e) for e in events[-10:]],
        ),
    )


@router.get("/{document_id}", response_model=APIResponse[DocumentResponse])
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get full document metadata, status, extraction envelope, and citations.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document {document_id} not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    # Fetch latest extraction
    ext_query = (
        select(Extraction)
        .where(Extraction.document_id == document.id)
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    ext_res = await db.execute(ext_query)
    extraction = ext_res.scalar_one_or_none()

    # Fetch citations
    cit_query = select(Citation).where(Citation.document_id == document.id)
    cit_res = await db.execute(cit_query)
    citations = list(cit_res.scalars().all())

    latest_envelope = None
    if extraction:
        latest_envelope = ExtractionEnvelope(
            document_type=extraction.document_type,
            confidence_score=extraction.confidence_score,
            title=extraction.title,
            summary_bullets=extraction.summary_bullets,
            important_alerts=extraction.important_alerts,
            suggested_questions=extraction.suggested_questions,
            recommended_actions=extraction.recommended_actions,
            payload=extraction.payload,
            citations=[
                CitationSchema(
                    page_number=c.page_number,
                    section_heading=c.section_heading,
                    exact_quote=c.exact_quote,
                    bounding_box=c.bounding_box,
                )
                for c in citations
            ],
        )

    doc_resp = DocumentResponse(
        id=document.id,
        user_id=document.user_id,
        title=document.title,
        file_name=document.file_name,
        file_size_bytes=document.file_size_bytes,
        mime_type=document.mime_type,
        status=document.status,
        document_type=document.document_type,
        confidence_score=document.confidence_score,
        page_count=document.page_count,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        latest_extraction=latest_envelope,
        citations=[
            CitationSchema(
                page_number=c.page_number,
                section_heading=c.section_heading,
                exact_quote=c.exact_quote,
                bounding_box=c.bounding_box,
            )
            for c in citations
        ],
    )

    return APIResponse(success=True, data=doc_resp)


@router.get("", response_model=APIResponse[PagedData[DocumentResponse]])
async def list_documents(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(
        20, ge=1, le=100, alias="pageSize", description="Items per page (max 100)"
    ),
    status: str | None = Query(None, description="Filter by lifecycle status (e.g. COMPLETED)"),
    document_type: str | None = Query(
        None, alias="documentType", description="Filter by extracted document type"
    ),
    search: str | None = Query(
        None, max_length=200, description="Case-insensitive title/file-name search"
    ),
    sort: str = Query(
        "-created_at",
        description="Sort key: created_at | -created_at | title | -title | confidence_score | -confidence_score",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List documents with pagination, filtering, search and sorting (ISSUE-013).

    Previously returned the user's ENTIRE library unpaginated — O(n) payload
    growth that breaks mobile performance as vaults scale. Now bounded to
    ``page_size`` items plus a pagination envelope so the client can render
    infinite scroll / paged lists correctly.
    """
    conds = [Document.user_id == current_user.id]
    if status:
        conds.append(Document.status == status.upper())
    if document_type:
        conds.append(Document.document_type == document_type.lower())
    if search:
        # Substring match with LIKE wildcards escaped (LIKE-injection safe) and
        # an explicit ESCAPE clause so the pattern works identically on
        # Postgres and SQLite. Lower-cased for portability (Postgres ILIKE ->
        # we normalize both sides instead).
        term = search.strip().lower()
        if term:
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            conds.append(
                or_(
                    func.lower(Document.title).like(pattern, escape="\\"),
                    func.lower(Document.file_name).like(pattern, escape="\\"),
                )
            )

    sort_map = {
        "created_at": Document.created_at.asc(),
        "-created_at": Document.created_at.desc(),
        "title": Document.title.asc(),
        "-title": Document.title.desc(),
        "confidence_score": Document.confidence_score.asc(),
        "-confidence_score": Document.confidence_score.desc(),
    }
    order: Any = sort_map.get(sort, Document.created_at.desc())

    total = (
        await db.execute(select(func.count()).select_from(Document).where(*conds))
    ).scalar_one()

    result = await db.execute(
        select(Document)
        .where(*conds)
        .order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    docs = list(result.scalars().all())

    total_pages = (total + page_size - 1) // page_size
    items = [
        DocumentResponse(
            id=d.id,
            user_id=d.user_id,
            title=d.title,
            file_name=d.file_name,
            file_size_bytes=d.file_size_bytes,
            mime_type=d.mime_type,
            status=d.status,
            document_type=d.document_type,
            confidence_score=d.confidence_score,
            page_count=d.page_count,
            error_message=d.error_message,
            created_at=d.created_at,
            updated_at=d.updated_at,
            latest_extraction=None,
            citations=[],
        )
        for d in docs
    ]

    return APIResponse(
        success=True,
        data=PagedData(
            items=items,
            pagination=PageMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
                has_next=page < total_pages,
            ),
        ),
    )


@router.post(
    "/{document_id}/ask",
    response_model=APIResponse[AskResponse],
    dependencies=[Depends(idempotency_guard)],
)
async def ask_question(
    document_id: uuid.UUID,
    req: AskRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Grounded Q&A over document with citations.

    ISSUE-016: pass ``Idempotency-Key`` to dedupe retried questions — a replay
    returns the original answer without paying for another AI-gateway call.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document {document_id} not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    ans = await rag_service.answer_question(
        db=db,
        document_id=document.id,
        user_id=current_user.id,
        question=req.question,
    )

    resp: APIResponse[AskResponse] = APIResponse(success=True, data=ans)
    await save_idempotent_response(db, request, current_user.id, resp)
    return resp


@router.post(
    "/compare",
    response_model=APIResponse[CompareResponse],
    dependencies=[Depends(idempotency_guard)],
)
async def compare_documents(
    req: CompareRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Compares 2-5 documents side-by-side on critical terms/clauses (ISSUE-012).
    """
    query = select(Document).where(
        Document.id.in_(req.document_ids),
        Document.user_id == current_user.id,
    )
    result = await db.execute(query)
    documents = list(result.scalars().all())

    if len(documents) != len(req.document_ids):
        raise ValidationError("One or more documents could not be found or do not belong to you.")

    # 1. State machine validation: documents must be COMPLETED
    incomplete = [d.title for d in documents if d.status != DocumentStatus.COMPLETED]
    if incomplete:
        raise ValidationError(
            f"Cannot compare documents that are not fully processed. Pending: {', '.join(incomplete)}"
        )

    # 2. Category compatibility check
    doc_types = {d.document_type for d in documents if d.document_type}
    if len(doc_types) > 1:
        raise ValidationError(
            f"Invalid comparison: cannot compare different document types ({', '.join(doc_types)}). "
            "Please select documents of the same category."
        )

    # 3. Fetch latest extractions for term-level alignment
    ext_query = (
        select(Extraction)
        .where(Extraction.document_id.in_(req.document_ids))
        .order_by(Extraction.created_at.desc())
    )
    ext_res = await db.execute(ext_query)
    extractions_map: dict[uuid.UUID, Extraction] = {}
    for ext in ext_res.scalars().all():
        if ext.document_id not in extractions_map:
            extractions_map[ext.document_id] = ext

    # 4. Construct term comparison matrix
    def get_term_val(doc: Document, keys: list[str]) -> Any:
        ext = extractions_map.get(doc.id)
        if not ext or not ext.payload:
            return "[Not specified in document]"
        for k in keys:
            val = ext.payload.get(k)
            if val is not None and str(val).strip():
                return val
        return "[Not specified in document]"

    term_specs = [
        ("Document Classification", ["document_type"], "Extracted document category"),
        (
            "Coverage / Sum Insured",
            ["sum_insured", "coverage_amount", "limit"],
            "Maximum coverage liability",
        ),
        ("Premium / Cost", ["premium", "annual_premium", "total_premium"], "Cost to policyholder"),
        ("Deductible / Co-pay", ["deductible", "copay", "co_pay"], "Out-of-pocket obligation"),
        (
            "Policy Term / Validity",
            ["policy_term", "validity_period", "expiry_date"],
            "Effective duration",
        ),
        (
            "Waiting Period",
            ["waiting_period", "pre_existing_waiting"],
            "Duration before pre-existing coverage",
        ),
        ("Key Exclusions", ["exclusions", "exclusion_count"], "Non-covered events or treatments"),
    ]

    matrix: list[ComparisonItem] = []
    for attr, keys, notes in term_specs:
        values: dict[str, Any] = {}
        for d in documents:
            if attr == "Document Classification":
                values[str(d.id)] = d.document_type or "Unknown"
            elif attr == "Key Exclusions":
                doc_ext = extractions_map.get(d.id)
                ex_val = doc_ext.payload.get("exclusions") if doc_ext and doc_ext.payload else None
                if isinstance(ex_val, list) and ex_val:
                    values[str(d.id)] = f"{len(ex_val)} exclusions noted"
                else:
                    values[str(d.id)] = "[Not specified in document]"
            else:
                values[str(d.id)] = get_term_val(d, keys)

        # Rule-based winner detection
        winner_id: str | None = None
        if attr == "Coverage / Sum Insured":
            best_val = -1.0
            for d in documents:
                raw_str = str(values.get(str(d.id), ""))
                nums = re.findall(r"\d[\d,]*", raw_str)
                if nums:
                    val_clean = float(nums[0].replace(",", ""))
                    if val_clean > best_val:
                        best_val = val_clean
                        winner_id = str(d.id)
        elif attr == "Deductible / Co-pay":
            lowest_val = float("inf")
            for d in documents:
                raw_str = str(values.get(str(d.id), ""))
                nums = re.findall(r"\d[\d,]*", raw_str)
                if nums:
                    val_clean = float(nums[0].replace(",", ""))
                    if val_clean < lowest_val:
                        lowest_val = val_clean
                        winner_id = str(d.id)

        matrix.append(
            ComparisonItem(
                attribute=attr,
                values=values,
                winnerDocumentId=winner_id,
                notes=notes,
            )
        )

    category_name = next(iter(doc_types), "document")
    summary = (
        f"Compared {len(documents)} {category_name}s across canonical terms including coverage, "
        "costs, waiting periods, and exclusions. Term deltas and null values are explicitly preserved."
    )
    recs = [
        "Review terms and conditions for specific clause differences before renewal.",
        "Check hospital/garage network lists for each policy provider.",
    ]

    resp: APIResponse[CompareResponse] = APIResponse(
        success=True,
        data=CompareResponse(
            summary=summary,
            comparisonMatrix=matrix,
            recommendations=recs,
        ),
    )
    await save_idempotent_response(db, request, current_user.id, resp)
    return resp


@router.delete("/{document_id}", response_model=APIResponse[dict])
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Deletes a document, its pages, chunks, citations, actions, and storage files.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise ResourceNotFoundError(f"Document {document_id} not found.")

    if document.user_id != current_user.id:
        raise PermissionDeniedError("Access denied.")

    # Delete storage object first; if it fails we must NOT claim full deletion.
    # ISSUE-005 (partial): surface storage failures instead of swallowing them.
    try:
        storage_service.delete_file(document.storage_path)
    except Exception as exc:
        logger.error(
            "Storage deletion failed during document delete",
            document_id=str(document_id),
            error=str(exc),
        )
        raise DocSenseException(
            message="Document could not be fully deleted. Please try again.",
            classification=ErrorClassification.RETRYABLE_FAILURE,
            status_code=500,
            code="STORAGE_DELETE_FAILED",
            is_retryable=True,
        ) from exc

    await db.delete(document)  # cascades to pages/chunks/extractions/actions
    await audit.record(
        db,
        user_id=current_user.id,
        event_type="document.deleted",
        document_id=document_id,
        ip_address=audit.client_ip(request),
    )
    await commit_now(db)

    return APIResponse(
        success=True,
        data={"deleted": True, "documentId": str(document_id)},
        message="Document and all associated data deleted successfully.",
    )
