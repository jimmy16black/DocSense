import json
import math
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.document import DocumentChunk, Extraction
from app.schemas.citation import CitationSchema
from app.schemas.qa import AskResponse
from app.services.ai_gateway import ai_gateway_service

logger = get_logger("rag")
settings = get_settings()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# Words that carry no retrieval signal; also strips short tokens.
_STOPWORDS = frozenset(
    """a an the and or but if then than that this these those is are was were be been being
    of in on at to for with from by as it its into about over after before what when where
    which who whom how why do does did done can could should would will shall may might must
    not no nor so too very just also""".split()
)


def extract_keywords(query: str, max_terms: int = 6) -> list[str]:
    """Deterministic, zero-dependency keyword extraction for the lexical leg.

    In production the vector leg carries semantic meaning; this lexical leg
    guarantees exact-term recall (policy numbers, clause names, amounts) even
    when embeddings are unavailable or offline pseudo-vectors are used.
    """
    tokens = re.findall(r"[A-Za-z0-9_]+(?:\.[0-9]+)?", query.lower())
    seen: dict[str, None] = {}
    for tok in tokens:
        if len(tok) < 3 or tok in _STOPWORDS:
            continue
        seen.setdefault(tok, None)
    return list(seen.keys())[:max_terms]


class RAGService:
    @staticmethod
    def reciprocal_rank_fusion(
        vector_results: list[DocumentChunk],
        keyword_results: list[DocumentChunk],
        k: int = 60,
    ) -> list[DocumentChunk]:
        """
        Merges two ranked lists using Reciprocal Rank Fusion (RRF).
        """
        scores: dict[str, float] = {}
        chunk_map: dict[str, DocumentChunk] = {}

        for rank, chunk in enumerate(vector_results):
            cid = str(chunk.id)
            chunk_map[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank + 1))

        for rank, chunk in enumerate(keyword_results):
            cid = str(chunk.id)
            chunk_map[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank + 1))

        sorted_cids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [chunk_map[cid] for cid in sorted_cids]

    async def vector_search(
        self, db: AsyncSession, document_id: UUID, user_id: str, question: str, limit: int = 8
    ) -> list[DocumentChunk]:
        """Semantic leg: embed the question, score chunks by cosine similarity.

        Uses a native pgvector ``<=>`` operator when available; falls back to
        in-process cosine scoring (Postgres-independent, e.g. SQLite tests).
        Chunks without embeddings are skipped here — the lexical leg covers them.
        """
        query_vec = await ai_gateway_service.generate_embeddings([question])
        qvec = query_vec[0] if query_vec else None
        if not qvec:
            return []

        res = await db.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.user_id == user_id,
            )
        )
        chunks = list(res.scalars().all())

        # Production path: native pgvector ANN query (<=> cosine distance) —
        # O(log n) with the HNSW index instead of scanning every chunk.
        if self._pgvector_available(db) and any(c.embedding for c in chunks):
            try:
                from sqlalchemy import text as sql_text

                pv_res = await db.execute(
                    sql_text(
                        """
                        SELECT id FROM document_chunks
                        WHERE document_id = :doc_id AND user_id = :user_id
                          AND embedding IS NOT NULL
                        ORDER BY embedding <=> CAST(:query_vec AS vector)
                        LIMIT :lim
                        """
                    ),
                    {
                        "doc_id": str(document_id),
                        "user_id": user_id,
                        "query_vec": str(qvec),
                        "lim": limit,
                    },
                )
                ordered_ids = [str(row[0]) for row in pv_res.fetchall()]
                if ordered_ids:
                    by_id = {str(c.id): c for c in chunks}
                    hits = [by_id[i] for i in ordered_ids if i in by_id]
                    if hits:
                        return hits
            except Exception as e:
                logger.warning(
                    "pgvector search failed, falling back to in-process cosine",
                    error=str(e),
                )
                # Keep the session usable after a failed statement.
                try:
                    await db.rollback()
                    res = await db.execute(
                        select(DocumentChunk).where(
                            DocumentChunk.document_id == document_id,
                            DocumentChunk.user_id == user_id,
                        )
                    )
                    chunks = list(res.scalars().all())
                except Exception:
                    return []

        # Portable path (SQLite tests / pre-migration DBs): in-process cosine.
        scored = [(_cosine_similarity(qvec, c.embedding), c) for c in chunks if c.embedding]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [c for _, c in scored[:limit]]

    @staticmethod
    def _pgvector_available(db: AsyncSession) -> bool:
        """pgvector's ``<=>`` operator only exists on PostgreSQL."""
        try:
            return db.bind.dialect.name == "postgresql"
        except Exception:
            return False

    async def keyword_search(
        self, db: AsyncSession, document_id: UUID, user_id: str, question: str, limit: int = 8
    ) -> list[DocumentChunk]:
        """Lexical leg: rank chunks by number of distinct query terms present.

        Portable across Postgres/SQLite (no tsvector dependency). Exact-term
        hits (clause names, policy numbers, amounts) always get recalled here.
        """
        keywords = extract_keywords(question)
        if not keywords:
            return []

        res = await db.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.user_id == user_id,
            )
        )
        chunks = list(res.scalars().all())
        scored: list[tuple[float, int, DocumentChunk]] = []
        for c in chunks:
            content_lower = c.content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches:
                # Primary: coverage; tie-break: earlier page/chunk for stability.
                scored.append((matches / len(keywords), -(c.page_number * 1000 + c.chunk_index), c))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [c for _, _, c in scored[:limit]]

    async def retrieve(
        self, db: AsyncSession, document_id: UUID, user_id: str, question: str, top_k: int = 6
    ) -> list[DocumentChunk]:
        """Hybrid retrieval: vector leg + lexical leg fused via RRF."""
        vector_hits = await self.vector_search(db, document_id, user_id, question)
        keyword_hits = await self.keyword_search(db, document_id, user_id, question)
        fused = self.reciprocal_rank_fusion(vector_hits, keyword_hits)
        return fused[:top_k]

    async def answer_question(
        self,
        db: AsyncSession,
        document_id: UUID,
        user_id: str,
        question: str,
    ) -> AskResponse:
        """
        Hybrid retrieval -> RRF -> Grounded synthesis with citations.

        FIX (ISSUE-004): replaced the previous "first 15 chunks" stub with
        real two-leg hybrid retrieval fused by Reciprocal Rank Fusion, so the
        LLM context is actually relevant to the question asked.
        """
        # Fast path: structured extraction metadata (title/type/summary) is
        # always included alongside retrieved evidence.
        ext_query = (
            select(Extraction)
            .where(
                Extraction.document_id == document_id,
                Extraction.user_id == user_id,
            )
            .order_by(Extraction.created_at.desc())
            .limit(1)
        )
        ext_result = await db.execute(ext_query)
        extraction = ext_result.scalar_one_or_none()

        # 2. Hybrid retrieval (vector + lexical, RRF-fused)
        try:
            chunks = await self.retrieve(db, document_id, user_id, question)
        except Exception as e:
            logger.error("Hybrid retrieval failed", error=str(e))
            chunks = []

        if not chunks and not extraction:
            return AskResponse(
                answer="No processed content found for this document yet.",
                confidence="UNSUPPORTED",
                citations=[],
                suggestedFollowUps=[],
                groundedInEvidence=False,
            )

        # Context assembly
        context_parts = []
        if extraction:
            context_parts.append(
                f"DOCUMENT METADATA & STRUCTURED SUMMARY:\n"
                f"Title: {extraction.title}\n"
                f"Type: {extraction.document_type}\n"
                f"Summary: {json.dumps(extraction.summary_bullets)}\n"
                f"Payload: {json.dumps(extraction.payload)}\n"
            )

        for chunk in chunks:
            context_parts.append(
                f"[PAGE {chunk.page_number} (Chunk {chunk.chunk_index})]:\n{chunk.content}"
            )

        context_str = "\n\n".join(context_parts)

        system_prompt = (
            "You are a strictly grounded AI document assistant. Answer the user question ONLY based on the provided context.\n"
            "Rules:\n"
            "1. If the answer is directly and clearly supported by the context, answer concisely and cite the exact quote and page number.\n"
            "2. If the context does NOT contain enough information to answer, state clearly: 'The document does not specify this information.' and set confidence to 'UNSUPPORTED'.\n"
            "3. Format your JSON response as:\n"
            "   {\n"
            '     "answer": "...",\n'
            '     "confidence": "HIGH" | "MEDIUM" | "LOW" | "UNSUPPORTED",\n'
            '     "suggestedFollowUps": ["..."],\n'
            '     "citations": [{"pageNumber": 1, "sectionHeading": "...", "exactQuote": "..."}]\n'
            "   }"
        )

        user_prompt = f"Question: {question}\n\nContext:\n{context_str}"

        try:
            raw_response = await ai_gateway_service.generate_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            clean_json = raw_response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            data = json.loads(clean_json.strip())

            citations = [CitationSchema.model_validate(c) for c in data.get("citations", [])]
            confidence = data.get("confidence", "HIGH")
            if confidence not in ["HIGH", "MEDIUM", "LOW", "UNSUPPORTED"]:
                confidence = "MEDIUM"

            return AskResponse(
                answer=data.get("answer", "Here is what the document states."),
                confidence=confidence,
                citations=citations,
                suggestedFollowUps=data.get("suggestedFollowUps", []),
                groundedInEvidence=(confidence != "UNSUPPORTED"),
            )
        except Exception as e:
            logger.error("Error generating grounded RAG answer", error=str(e))
            # FIX (ISSUE-004): never fabricate a confident-sounding answer with
            # invented quotes when generation fails. Degrade honestly: tell the
            # user we couldn't answer and let them retry. A fabricated citation
            # destroys exactly the trust the product promises (§8.5 grounding).
            return AskResponse(
                answer=(
                    "I couldn't generate an answer right now. The document content "
                    "was retrieved successfully — please try again in a moment."
                ),
                confidence="UNSUPPORTED",
                citations=[],
                suggestedFollowUps=["What are the exclusions?", "Summarize this document"],
                grounded_in_evidence=False,
            )


rag_service = RAGService()
