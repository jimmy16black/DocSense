from app.models.document import DocumentChunk
from app.schemas.citation import CitationSchema
from app.schemas.extraction import ExtractionEnvelope
from app.services.ai_gateway import redact_pii
from app.services.extractor import pdf_extractor_service
from app.services.rag import rag_service
from app.services.storage import storage_service


def test_pii_redaction():
    sample_text = (
        "Contact Jane Doe at jane.doe@example.com or phone +919876543210. "
        "PAN is ABCDE1234F and GSTIN is 22AAAAA0000A1Z5 with Aadhaar 2345 6789 0123."
    )
    redacted = redact_pii(sample_text)
    assert "[EMAIL_REDACTED]" in redacted
    assert "[PHONE_REDACTED]" in redacted
    assert "[PAN_REDACTED]" in redacted
    assert "[GSTIN_REDACTED]" in redacted
    assert "[AADHAAR_REDACTED]" in redacted
    assert "jane.doe@example.com" not in redacted
    assert "ABCDE1234F" not in redacted


def test_chunk_text():
    pages = [
        (1, "The quick brown fox jumps over the lazy dog. " * 30),
        (2, "Second page text with important clauses and coverage. " * 20),
    ]
    chunks = pdf_extractor_service.chunk_text(pages, chunk_size=25, chunk_overlap=5)
    assert len(chunks) > 1
    assert chunks[0]["page_number"] == 1
    assert "chunk_index" in chunks[0]
    assert len(chunks[0]["content"]) > 0


def test_validate_citations():
    envelope = ExtractionEnvelope(
        document_type="INSURANCE_POLICY",
        confidence_score=0.9,
        title="Test Policy",
        summary_bullets=["Summary 1"],
        important_alerts=[],
        suggested_questions=[],
        recommended_actions=[],
        payload={},
        citations=[
            CitationSchema(
                page_number=1,
                section_heading="Coverage",
                exact_quote="Sum insured of Rs. 10,00,000",
                bounding_box=None,
            )
        ],
    )
    full_text = "Policy document text with Sum insured of Rs. 10,00,000 for hospital expenses."
    validated = pdf_extractor_service.validate_citations(envelope, full_text)
    assert len(validated.citations) == 1
    assert validated.citations[0].exact_quote == "Sum insured of Rs. 10,00,000"


def test_reciprocal_rank_fusion():
    import uuid

    chunk1 = DocumentChunk(
        id=uuid.uuid4(), user_id="u1", page_number=1, chunk_index=0, content="c1"
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(), user_id="u1", page_number=1, chunk_index=1, content="c2"
    )
    chunk3 = DocumentChunk(
        id=uuid.uuid4(), user_id="u1", page_number=2, chunk_index=2, content="c3"
    )

    vector_ranked = [chunk1, chunk2]
    keyword_ranked = [chunk2, chunk3]

    merged = rag_service.reciprocal_rank_fusion(vector_ranked, keyword_ranked)
    # chunk2 appears in both rankings, so it should rank highest in RRF
    assert len(merged) == 3
    assert merged[0].id == chunk2.id


def test_storage_service_urls():
    upload_url, expires_at = storage_service.generate_upload_url(
        storage_path="users/u1/doc.pdf",
        mime_type="application/pdf",
    )
    assert upload_url != ""
    assert expires_at is not None

    download_url = storage_service.generate_download_url("users/u1/doc.pdf")
    assert download_url != ""
