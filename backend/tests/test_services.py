import pytest

from app.models.document import DocumentChunk
from app.schemas.citation import CitationSchema
from app.schemas.extraction import ExtractionEnvelope
from app.services.ai_gateway import redact_pii, redact_pii_with_details
from app.services.extractor import pdf_extractor_service
from app.services.rag import RAGService, rag_service
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


def test_pii_redaction_indian_tokens():
    """ISSUE-009: Test comprehensive Indian identity & financial tokens redaction."""
    sample_text = (
        "Passport: A1234567, Driving License: DL-1420110012345, IFSC: SBIN0001234, "
        "UPI: user@okaxis, DOB: 12/04/1988, Vehicle: DL01AB1234, Account: 12345678901234."
    )
    redacted, counts = redact_pii_with_details(sample_text)
    assert "[PASSPORT_REDACTED]" in redacted
    assert "[DRIVING_LICENSE_REDACTED]" in redacted
    assert "[IFSC_REDACTED]" in redacted
    assert "[UPI_REDACTED]" in redacted
    assert "[DOB_REDACTED]" in redacted
    assert "[VEHICLE_NO_REDACTED]" in redacted
    assert "[ACCOUNT_NUMBER_REDACTED]" in redacted
    assert counts["PASSPORT"] == 1
    assert counts["IFSC"] == 1
    assert counts["UPI_VPA"] == 1


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


# ---------- ISSUE-004: hybrid RAG regression tests ----------


def test_extract_keywords_stops_short_words_and_stopwords():
    from app.services.rag import extract_keywords

    kws = extract_keywords("what is the waiting period for pre-existing diseases?")
    assert "waiting" in kws
    assert "period" in kws
    assert "pre-existing" not in kws  # punctuation splits token; "existing" kept
    assert "existing" in kws
    assert "the" not in kws and "is" not in kws and "for" not in kws


def test_rrf_favors_consensus_across_legs():
    class FakeChunk:
        def __init__(self, i):
            self.id = f"cid-{i}"

    v = [FakeChunk(1), FakeChunk(2), FakeChunk(3)]
    k = [FakeChunk(2), FakeChunk(1), FakeChunk(4)]
    fused = RAGService.reciprocal_rank_fusion(v, k)
    # chunk appearing top-2 in BOTH legs must outrank one that tops only one leg
    assert str(fused[0].id) in ("cid-1", "cid-2")
    ids = [str(c.id) for c in fused]
    assert set(ids) == {"cid-1", "cid-2", "cid-3", "cid-4"}
    # cid-4 (only in keyword leg, rank 3) should be last
    assert ids[-1] == "cid-4"


def test_cosine_similarity_math():
    from app.services.rag import _cosine_similarity

    assert _cosine_similarity([1, 0], [1, 0]) == 1.0
    assert abs(_cosine_similarity([1, 0], [0, 1])) < 1e-9
    assert _cosine_similarity([], [1]) == 0.0
    assert _cosine_similarity([0, 0], [1, 1]) == 0.0


@pytest.mark.asyncio
async def test_keyword_search_ranks_by_term_coverage(db_session, mock_current_user):
    """Lexical leg must recall exact terms regardless of embeddings."""
    import uuid as uuid_mod

    from app.models.document import DocumentChunk

    doc_id = uuid_mod.uuid4()
    uid = mock_current_user.id
    rows = [
        DocumentChunk(
            id=uuid_mod.uuid4(),
            document_id=doc_id,
            user_id=uid,
            page_number=1,
            chunk_index=0,
            content="The premium renewal date is 15 April each policy year.",
        ),
        DocumentChunk(
            id=uuid_mod.uuid4(),
            document_id=doc_id,
            user_id=uid,
            page_number=2,
            chunk_index=1,
            content="Claim settlement requires original hospital discharge summaries.",
        ),
        DocumentChunk(
            id=uuid_mod.uuid4(),
            document_id=doc_id,
            user_id=uid,
            page_number=3,
            chunk_index=2,
            content="Premium payment can be made via UPI, card or auto-debit mandate.",
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    hits = await rag_service.keyword_search(
        db_session, doc_id, uid, "when is the premium renewal date due?", limit=3
    )
    assert hits, "lexical leg found nothing"
    assert "renewal date" in hits[0].content.lower()


@pytest.mark.asyncio
async def test_retrieve_hybrid_returns_relevant_topk(db_session, mock_current_user):
    import uuid as uuid_mod

    from app.models.document import DocumentChunk

    doc_id = uuid_mod.uuid4()
    uid = mock_current_user.id
    rows = []
    for i in range(20):
        topic = "deductible" if i % 5 == 0 else "boilerplate lorem text about general matters"
        rows.append(
            DocumentChunk(
                id=uuid_mod.uuid4(),
                document_id=doc_id,
                user_id=uid,
                page_number=i + 1,
                chunk_index=i,
                content=f"The {topic} clause number {i} applies here.",
            )
        )
    db_session.add_all(rows)
    await db_session.commit()

    results = await rag_service.retrieve(db_session, doc_id, uid, "what is the deductible amount?")
    assert 0 < len(results) <= 6
    # Retrieved context must contain the term-bearing chunks (not just first-N)
    joined = " ".join(c.content for c in results).lower()
    assert "deductible" in joined


@pytest.mark.asyncio
async def test_ai_gateway_completion_with_openai_compatible_endpoint(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.services.ai_gateway import AIGatewayService

    svc = AIGatewayService()
    svc.openai_api_key = "test-local-key"
    svc.portkey_client = None

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"status": "ok"}'))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kwargs: mock_client)

    result = await svc.generate_completion(
        system_prompt="system",
        user_prompt="user question",
        model="llama3.2",
    )
    assert result == '{"status": "ok"}'
    mock_client.chat.completions.create.assert_awaited_once()
