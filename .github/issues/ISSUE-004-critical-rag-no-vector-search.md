---
title: "[P0][AI] Hybrid retrieval is decorative — embeddings never generated, no pgvector or FTS query leg"
labels: bug, critical, ai, backend
---

## Problem
ADR-005 / 24_RAG_RETRIEVAL_STRATEGY require hybrid dense+sparse retrieval fused via RRF. Current `services/rag.py::answer_question` instead runs:

```sql
SELECT ... FROM document_chunks WHERE document_id=? AND user_id=?
ORDER BY page_number, chunk_index LIMIT 15
```

- No embedding is ever computed at ingest (`DocumentChunk.embedding` is always NULL; `DEFAULT_EMBEDDING_MODEL` config unused).
- No `ts_vector/ts_rank_cd` full-text leg.
- `reciprocal_rank_fusion()` exists and is unit-testable but receives at most one real ranked list — fusion math is dead code.
- Retrieval quality therefore equals "first 15 chunks", which fails on long documents (>15 chunks silently truncated).

## Impact
Grounded answers degrade to keyword-luck; every market competitor (DocuAI-class apps) does semantic retrieval. This breaks the product's #1 principle: *Evidence over unsupported inference*.

## Acceptance criteria
- [ ] Embedding generation service (Portkey/OpenAI `text-embedding-3-small`, dim 1536) invoked during ingestion; batched writes to `document_chunks.embedding`.
- [ ] Dense leg: pgvector cosine `<=>` query with HNSW index (`ef_search` tuned), top-K configurable.
- [ ] Sparse leg: `ts_rank_cd` over a `tsvector` generated-column or indexed column (migration already ships FTS index — wire it).
- [ ] Fuse both legs with existing RRF (k=60); tenant filter (`user_id`) enforced inside both queries.
- [ ] Answer synthesis cites only retrieved spans; citation verbatim-check against source text before returning (25_AI_CONFIDENCE_POLICY confidence tiers).
- [ ] Eval harness: golden set from 07_AI_EVALUATION with retrieval hit-rate@K and groundedness thresholds as CI gate (can be non-blocking initially).
