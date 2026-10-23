---
title: "[P1][AI] /documents/compare returns static boilerplate — no term-level comparison despite CompareScreen UI"
labels: enhancement, high, ai, backend
---

## Problem
`compare_documents` emits two hardcoded rows ("Document Type", "Coverage / Title") plus one canned recommendation. Mobile ships a full `CompareScreen`, so users see confident-but-meaningless output — an anti-pattern vs the product principle *"Accuracy over fluency"* and 02_DATA_MODEL_CONTRACTS comparison schema (per-attribute deltas, winner detection, citation per compared value).

## Acceptance criteria
- [ ] Validate inputs server-side: 2–5 docs, all COMPLETED, comparable `document_type` (else `VALIDATION_ERROR` — Document_8 §8.6 "Invalid comparison").
- [ ] Build comparison matrix from stored extraction payloads: align canonical fields (sum insured, premium, deductible, exclusions count, renewal date…), compute per-row values + delta + `winnerDocumentId` using rule-based scoring first, LLM synthesis for narrative summary second (with citations per row).
- [ ] Every matrix cell carries citation refs; unsupported attributes render `[Not specified in document]` (null-preservation rule).
- [ ] Contract tests against fixture extractions; golden-file eval for narrative groundedness.
