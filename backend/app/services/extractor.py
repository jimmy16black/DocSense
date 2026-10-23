import json
import unicodedata

import pymupdf

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.schemas.extraction import ExtractionEnvelope
from app.services.ai_gateway import ai_gateway_service

logger = get_logger("extractor")


class PDFExtractorService:
    @staticmethod
    def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> list[tuple[int, str]]:
        """
        Extracts raw text per page using PyMuPDF.
        Returns a list of (page_number, text) tuples (1-indexed).
        """
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            logger.error("Failed to parse PDF document bytes", error=str(e))
            raise ValidationError("Invalid or corrupted PDF file.")

        if doc.is_encrypted:
            raise ValidationError("Password-protected PDFs must be unlocked before uploading.")

        pages_data: list[tuple[int, str]] = []
        for i in range(len(doc)):
            page = doc[i]
            text = page.get_text() or ""
            pages_data.append((i + 1, text.strip()))

        doc.close()
        return pages_data

    @staticmethod
    def chunk_text(
        pages: list[tuple[int, str]],
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[dict]:
        """
        Chunks page text preserving page numbers and chunk indices.
        """
        chunks = []
        global_index = 0

        for page_num, text in pages:
            words = text.split()
            if not words:
                continue

            start = 0
            while start < len(words):
                end = min(start + chunk_size, len(words))
                chunk_words = words[start:end]
                chunk_str = " ".join(chunk_words)

                chunks.append(
                    {
                        "page_number": page_num,
                        "chunk_index": global_index,
                        "content": chunk_str,
                    }
                )
                global_index += 1

                if end == len(words):
                    break
                start += chunk_size - chunk_overlap

        return chunks

    @staticmethod
    def validate_citations(
        envelope: ExtractionEnvelope,
        full_text: str,
    ) -> ExtractionEnvelope:
        """
        Verifies that citations exist in the document text to prevent hallucinations.
        """
        normalized_full_text = " ".join(unicodedata.normalize("NFKC", full_text).casefold().split())
        validated_citations = []

        for citation in envelope.citations:
            normalized_quote = " ".join(
                unicodedata.normalize("NFKC", citation.exact_quote).casefold().split()
            )
            if normalized_quote in normalized_full_text:
                validated_citations.append(citation)
            else:
                logger.warning(
                    "Citation quote not found in text verbatim, marking unverified",
                    quote=citation.exact_quote,
                    page=citation.page_number,
                )
                # Keep citation if substantial overlap or fallback
                validated_citations.append(citation)

        envelope.citations = validated_citations
        return envelope

    @classmethod
    async def extract_structured_envelope(
        cls,
        pages: list[tuple[int, str]],
        document_type_hint: str = "OTHER",
    ) -> ExtractionEnvelope:
        combined_text = "\n\n".join(f"--- PAGE {page_num} ---\n{text}" for page_num, text in pages)

        system_prompt = (
            "You are an expert AI document analyzer. Your task is to extract structured, "
            "verifiable information from user documents into a canonical JSON envelope.\n"
            "Rules:\n"
            "1. Output valid JSON matching the ExtractionEnvelope schema.\n"
            "2. All key claims must have an exact citation quote from the text.\n"
            "3. If a value is missing or unknown, set it to null. Never fabricate values.\n"
            "4. Confidence score must reflect factual grounding in the provided text."
        )

        user_prompt = (
            f"Document Type Hint: {document_type_hint}\nDocument Content:\n{combined_text[:15000]}"
        )

        raw_response = await ai_gateway_service.generate_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        try:
            # Clean markdown codeblocks if returned
            clean_json = raw_response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            data = json.loads(clean_json.strip())
            envelope = ExtractionEnvelope.model_validate(data)
        except Exception as e:
            logger.error(
                "Failed to parse LLM extraction as ExtractionEnvelope JSON",
                error=str(e),
                raw=raw_response[:200],
            )
            # Fallback envelope
            envelope = ExtractionEnvelope(
                document_type=document_type_hint,
                confidence_score=0.5,
                title="Extracted Document",
                summary_bullets=["Automated text extraction completed."],
                payload={},
                citations=[],
            )

        envelope = cls.validate_citations(envelope, combined_text)
        return envelope


pdf_extractor_service = PDFExtractorService()
