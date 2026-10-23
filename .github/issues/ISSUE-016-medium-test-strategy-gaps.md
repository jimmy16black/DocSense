---
title: "[P2][QA] Test suite covers happy paths only — no cross-tenant security tests, no AI eval harness, deprecated datetime APIs"
labels: enhancement, medium, testing, qa
---

## Problem
17 passing tests cover health/documents/actions/errors happy paths. Missing per 10_TEST_STRATEGY:
- **Security tests:** user B reading/deleting user A's documents via ID guessing (currently guarded ad-hoc per route — regression-prone), JWT forgery matrix (see ISSUE-010), RLS enforcement (ISSUE-007), upload spoofing (ISSUE-002).
- **AI evaluation:** 07_AI_EVALUATION golden-set harness (extraction precision/recall, groundedness, refusal correctness) is phase-TODO; no fixtures.
- **Contract tests:** OpenAPI schema snapshot diffing to catch breaking changes pre-release.
- **Property tests** for RRF fusion & citation verbatim matcher (hypothesis).
- Housekeeping: models/storage use deprecated naive `datetime.utcnow()` → migrate to `datetime.now(timezone.utc)`; add Alembic so `models/` ↔ `infra/migrations/` drift is CI-checked (`alembic check`).
- CORS default `["*"]` + `allow_credentials=True` is invalid/unsafe — pin explicit origins per env and test preflight.

## Acceptance criteria
- [ ] Cross-tenant access test-suite green (fails today if any route forgets ownership check — make it table-driven over all routes).
- [ ] Eval harness runs nightly workflow; PR-blocking thresholds documented.
- [ ] `alembic init` + autogenerate baseline reconciled with hand-written SQL; drift check in CI.
- [ ] Zero deprecation warnings under `-W error::DeprecationWarning` for datetime usage.
