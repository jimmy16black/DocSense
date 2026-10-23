---
title: "[P0][CORE] Document processing uses hardcoded mock pages — real ingestion pipeline (workers) missing"
labels: bug, critical, backend, ai
---

## Problem
`POST /documents/{id}/process` never reads the uploaded file. It extracts from a **hardcoded mock**:

```python
mock_pages = [
    (1, f"Document: {document.title}\nPolicy Schedule\nSum Insured: Rs. 10,00,000/- for Jane Doe."),
    (2, "Terms & Conditions\nSection 4.1: Pre-existing diseases covered after 24 consecutive months."),
]
```

Every document in production would receive identical fake facts. Additionally:
- Processing runs **synchronously inside the request** — LLM latency will exceed gateway timeouts (Railway/Cloudflare ~60–100s).
- `app/workers/` does not exist despite README's repository layout; Kafka/Redis config (`UPSTASH_KAFKA_URL`) is unused.
- Mobile fabricates progress with `Future.delayed(600ms)` steps — Document_8 §8.4: *"Progress should come from backend events rather than fabricated client-side progress."*

## Expected behavior (01_SYSTEM_ARCHITECTURE, 05_AGENT_TASK_BREAKDOWN, 08_ERROR_STATE_MACHINE)
Real PyMuPDF extraction of the verified R2 object → chunking → embedding → LLM structured extraction with citation verification, executed by an async worker with retry/backoff and observable stage events.

## Acceptance criteria
- [ ] Implement `app/workers/ingestion_worker.py`: consume queue jobs, download object from R2, run `pdf_extractor_service` on **actual bytes** (PyMuPDF per ADR-006; image path via OCR), persist `document_pages`, chunks, extractions, citations.
- [ ] `/process` becomes job-enqueueing only: returns `job_id`, sets `VALIDATING`, 202-style response; add `GET /documents/{id}/status` (or SSE) emitting spec stages: `Reading pages → Identifying document → Extracting facts → Preparing Q&A → Completed`.
- [ ] Idempotent job initiation keyed by `Idempotency-Key` header (08 state machine); bounded retries with exponential backoff into `RETRYING` then `FAILED` with sanitized `error_message`.
- [ ] Password-protected PDF detection → `USER_ACTION_REQUIRED` ("Request password locally", do not store locked binary) per Document_8 §8.6.
- [ ] Mobile consumes backend stage events; remove fabricated delays.
- [ ] E2E test with a real fixture PDF asserting page-specific quotes appear in citations.
