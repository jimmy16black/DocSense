---
title: "[P2][API] List endpoints return unbounded arrays; no pagination/search/filters vs API contract"
labels: enhancement, medium, backend, api
---

## Problem
`GET /documents` and `GET /actions` select the entire per-user table into memory and JSON. 03_API_CONTRACT specifies cursor pagination; Document_8 Home flow starts with **Search**. At 500+ documents the payload degrades mobile scroll performance and eventually times out.

## Acceptance criteria
- [ ] Cursor-based pagination (`limit` ≤ 100 default 20, opaque `nextCursor`) on both endpoints; stable ordering `(created_at desc, id)`.
- [ ] Query params: `q` (title/typed-content ILIKE or FTS), `documentType`, `status`, `sortBy`.
- [ ] Update mobile providers for infinite scroll (Riverpod `invalidate` + fetch-next pattern).
- [ ] DB index check: existing `idx_doc_user_created` supports the keyset query; add migration if not.
