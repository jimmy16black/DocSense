---
title: "[P1][SECURITY/COST] No rate limiting or per-user quotas — AI gateway and upload endpoints are open abuse surface"
labels: security, high, backend, cost
---

## Problem
`RateLimitExceededError` exists in the error state machine but is never raised. There is no limiter middleware (slowapi/Redis), no per-user quota on documents/storage/AI calls. 12_OBSERVABILITY_COST requires cost guardrails; Document_8 §8.6 defines a `QUOTA_EXCEEDED` UI state that cannot ever occur server-side today.

Impact: unbounded LLM spend via `/ask` & `/process`, vault flooding via `/upload-init`, credential-stuffing against auth-adjacent endpoints.

## Acceptance criteria
- [ ] Redis-backed sliding-window limiter middleware with per-route policies (e.g., upload-init 20/min, ask 30/min, process 10/hr free tier).
- [ ] Return canonical `RATE_LIMIT_EXCEEDED` envelope + `Retry-After` header (429) matching 08_ERROR_STATE_MACHINE.
- [ ] Entitlement/quota service (plan-aware): document count, storage bytes, monthly AI tokens; raise `QUOTA_EXCEEDED` classification consumed by mobile upgrade flow.
- [ ] Log limiter decisions with correlation ID; expose `rate_limit_remaining` headers.
- [ ] Load test proving 429s under burst and no bypass via missing headers.
