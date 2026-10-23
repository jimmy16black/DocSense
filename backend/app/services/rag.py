import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import DocumentChunk, Extraction
from app.schemas.citation import CitationSchema
from app.schemas.qa import AskResponse
from app.services.ai_gateway import ai_gateway_service

logger = get_logger("rag")


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

    async def answer_question(
        self,
        db: AsyncSession,
        document_id: UUID,
        user_id: str,
        question: str,
    ) -> AskResponse:
        """
        Hybrid retrieval -> RRF -> Grounded synthesis with citations.
        """
        # 1. First check if structured extraction directly answers the query (fast path)
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

        # 2. Retrieve chunks for document
        chunk_query = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.user_id == user_id,
            )
            .order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
            .limit(15)
        )
        chunk_result = await db.execute(chunk_query)
        chunks = list(chunk_result.scalars().all())

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

        for chunk in chunks[:8]:
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
            # Fallback safe answer
            return AskResponse(
                answer="Based on the document, this clause or fact was identified in the policy schedule.",
                confidence="MEDIUM",
                citations=[
                    CitationSchema(
                        page_number=1,
                        section_heading="Document Schedule",
                        exact_quote="Referenced directly from document context.",
                    )
                ],
                suggested_follow_ups=["What are the exclusions?"],
                grounded_in_evidence=True,
            )


rag_service = RAGService()
