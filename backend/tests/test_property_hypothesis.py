"""ISSUE-016: Property-based testing with Hypothesis for RRF fusion & citation verification."""

import string
import unicodedata
import uuid

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.document import DocumentChunk
from app.schemas.citation import CitationSchema
from app.schemas.extraction import ExtractionEnvelope
from app.services.extractor import PDFExtractorService
from app.services.rag import RAGService


def _make_dummy_chunk(cid: uuid.UUID | None = None) -> DocumentChunk:
    chunk_id = cid or uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        document_id=uuid.uuid4(),
        user_id="user-hypo",
        page_number=1,
        chunk_index=0,
        content=f"Sample content for {chunk_id}",
    )
    return chunk


@settings(max_examples=50)
@given(
    st.lists(st.uuids(), min_size=1, max_size=20, unique=True),
    st.lists(st.uuids(), min_size=1, max_size=20, unique=True),
    st.integers(min_value=1, max_value=100),
)
def test_rrf_preserves_union_and_no_duplicates(uids1, uids2, k):
    """Property: RRF result must contain exactly the union of all input chunks, with 0 duplicates."""
    vec_chunks = [_make_dummy_chunk(uid) for uid in uids1]
    kw_chunks = [_make_dummy_chunk(uid) for uid in uids2]

    fused = RAGService.reciprocal_rank_fusion(vec_chunks, kw_chunks, k=k)

    expected_ids = set(uids1) | set(uids2)
    result_ids = [c.id for c in fused]

    # No duplicates
    assert len(result_ids) == len(set(result_ids))
    # Exactly all elements preserved
    assert set(result_ids) == expected_ids


@settings(max_examples=50)
@given(st.uuids(), st.integers(min_value=1, max_value=100))
def test_rrf_consensus_champion(champion_id, k):
    """Property: An item ranked #1 in BOTH legs must always emerge as rank #1 in fused output."""
    champ = _make_dummy_chunk(champion_id)
    other_a = [_make_dummy_chunk() for _ in range(5)]
    other_b = [_make_dummy_chunk() for _ in range(5)]

    vec_chunks = [champ] + other_a
    kw_chunks = [champ] + other_b

    fused = RAGService.reciprocal_rank_fusion(vec_chunks, kw_chunks, k=k)
    assert fused[0].id == champion_id


@settings(max_examples=50)
@given(
    st.text(
        min_size=10,
        max_size=100,
        alphabet=st.sampled_from(string.ascii_letters + string.digits + " \n\t.,;:"),
    ),
    st.integers(min_value=0, max_value=5),
    st.integers(min_value=5, max_value=25),
)
def test_citation_verbatim_matcher_property(full_text, start_offset, length):
    """Property: Any valid non-empty slice of full_text, regardless of case or spacing, is recognized."""
    words = full_text.split()
    if not words:
        return

    # Pick a contiguous sequence of words
    start = min(start_offset, len(words) - 1)
    end = min(start + length, len(words))
    if start >= end:
        return

    quote_words = words[start:end]
    quote = "  ".join(quote_words).upper()  # Test irregular spacing and upper case

    envelope = ExtractionEnvelope(
        title="Hypothesis Test Doc",
        documentType="POLICY",
        confidenceScore=0.95,
        citations=[
            CitationSchema(
                pageNumber=1,
                exactQuote=quote,
                confidenceScore=0.95,
            )
        ],
    )

    result = PDFExtractorService.validate_citations(envelope, full_text)
    assert len(result.citations) == 1
    # Check normalized matching logic
    norm_quote = " ".join(unicodedata.normalize("NFKC", quote).casefold().split())
    norm_text = " ".join(unicodedata.normalize("NFKC", full_text).casefold().split())
    assert norm_quote in norm_text
