# DocSense — Regressive Repository Review (v0.1.0-alpha)

**Date:** 2026-10-23
**Scope:** Full monorepo audit against `ai_document_action_25_md_files/` specs (01 Architecture, 02 Data Contracts, 03 API Contract, 08 Error State Machine, 09 Security/DPDP, 10 Test Strategy, 11 CI/CD, Document_8 UI/UX Design System, 24 RAG Retrieval Strategy).
**Method:** Line-by-line inspection of `backend/app/**`, `mobile/lib/**`, `infra/supabase/migrations/**`, `.github/workflows/**`.

---

## Critical Bugs (P0) — Blockers for any production path

### BUG-1: All database writes are silently discarded (missing commit / broken flush pattern)
- **Evidence:** `app/db/session.py::get_db_session` commits only *after* the response generator finishes; every route handler calls `await db.flush()` and never `commit()`. Under SQLAlchemy's default `autoflush=False`, subsequent `SELECT`s in the same transaction do not see flushed rows, and any exception raised after a flush (e.g., `ResourceNotFoundError` in later handlers, validation errors) triggers rollback that discards earlier "successful" writes. The `/documents/{id}/process` endpoint returns `"Document processed and indexed successfully"` while nothing is durably persisted if the session lifecycle is interrupted (client disconnect, middleware error).
- **Impact:** Data loss on virtually every mutation endpoint. Tests pass because they run inside one live session; this is exactly the kind of bug unit tests miss.
- **Spec violated:** 02_DATA_MODEL_CONTRACTS (durability), 08_ERROR_STATE_MACHINE (state transitions must be atomic).

### BUG-2: `POST /documents/upload-init` trusts client-declared size/MIME; no upload verification exists
- **Evidence:** `routes/documents.py::init_upload` validates `req.file_size_bytes` and `req.mime_type` from the request body only. There is no completion callback, no HEAD-object check against R2, no checksum verification. A user can declare `application/pdf` + tiny size and store arbitrary content (HTML, SVG-with-JS, executables) under their vault path. `process_document` then reads whatever binary lands at `storage_path`.
- **Impact:** Stored-content spoofing, quota bypass, downstream parser injection (SSRF-adjacent via crafted PDFs), ransomware-style abuse of the vault.
- **Fix direction:** Add `POST /documents/{id}/upload-complete` that performs an S3 HEAD (`Content-Length`, `Content-Type`), computes SHA-256, compares to declared values, and only then transitions `UPLOADED → VALIDATING`. Enforce presigned URL conditions (`ContentLengthRange`, exact `ContentType`). Store `checksum_sha256` on `documents` (column missing in migration).

### BUG-3: Document processing runs synchronously in-request with fabricated pipeline stages
- **Evidence:** `process_document` performs extraction inline and uses hardcoded `mock_pages` ("Policy Schedule / Sum Insured: Rs. 10,00,000/- for Jane Doe") instead of reading the actual uploaded file. No `app/workers/` module exists despite README claiming it; Kafka/Redis queue configured but unused. The mobile `upload_screen.dart` adds fake `Future.delayed(600ms)` progress steps — spec Document_8 §8.4 explicitly requires "Progress should come from backend events rather than fabricated client-side progress."
- **Impact:** Every processed document gets the *same mock facts*; the product's core value proposition (real extraction) is absent. Long LLM calls will hit gateway timeouts; no retry/idempotency per 08_ERROR_STATE_MACHINE.

### BUG-4: Hybrid retrieval has no vector or FTS leg — RRF operates on a single ordered list
- **Evidence:** `services/rag.py` retrieves chunks with a plain `ORDER BY page_number, chunk_index LIMIT 15`. Embeddings are never generated or stored (`DocumentChunk.embedding` always NULL); `reciprocal_rank_fusion()` is called with one real list or is decorative. No query embedding call anywhere in the codebase.
- **Spec violated:** ADR-005, 24_RAG_RETRIEVAL_STRATEGY (pgvector cosine + `ts_rank_cd` + RRF k=60), 23_VECTOR_RAG_LIFECYCLE.

### BUG-5: DPDP erasure does not delete the Supabase Auth user; storage purge is fire-and-forget
- **Evidence:** `routes/users.py::delete_user_account` purges app tables and calls `storage_service.delete_file()` per document, which swallows all exceptions (`except ... logger.error`) — erasure can silently fail while returning `"permanently deleted"`. The auth identity (email, phone metadata in `auth.users`) is never removed via service-role admin API.
- **Spec violated:** 09_SECURITY_DPDP right-to-erasure contract. This is a legal-compliance failure, not just a bug.

### BUG-6: Hardcoded `test-token-*` auth backdoor ships in `get_current_user`
- **Evidence:** `core/security.py`: any non-production env accepts `Bearer test-token-<anything>` as a fully privileged user, keyed by an attacker-chosen string. If `APP_ENV` defaults misconfigure a staging deploy (`APP_ENV` default is `"development"`), anyone can impersonate any user ID.
- **Fix direction:** Gate behind an explicit `ALLOW_TEST_TOKENS` flag that is force-disabled when `SUPABASE_URL` points at a real project; never allow in staging; add a test-only dependency override instead of runtime branching.

---

## High-Severity Issues (P1)

### SEC-1: No rate limiting anywhere
`RateLimitExceededError` is defined but never raised; no slowapi/Redis limiter middleware. Upload-init, ask, and compare endpoints are open to brute-force cost attacks against the AI gateway (12_OBSERVABILITY_COST mandates per-user quotas; `QUOTA_EXCEEDED` state from Document_8 §8.6 is unimplemented server-side).

### SEC-2: PII redaction is regex-only; Presidio required by spec
`ai_gateway.redact_pii()` covers 5 patterns (email/phone/Aadhaar/PAN/GSTIN). Names, addresses, account numbers, dates-of-birth flow to the LLM unredacted. 09_SECURITY_DPDP specifies Microsoft Presidio before any provider call. Regex also destroys evidence quotes needed for citation verification — order of operations (redact-before-vs-after grounding) is unspecified in code.

### SEC-3: JWTs validated with legacy HS256 shared secret only
Supabase projects issued after ~2024 use asymmetric signing keys (JWT signing config / JWKS). Code hardcodes `algorithms=["HS256"]` and `verify_aud: False`; no RS256/JWKS path, no issuer/audience checks. Also no token revocation/jti blacklist.

### ARCH-1: Application never sets `request.user_uuid` for Postgres RLS
Migrations define 12 RLS policies keyed to `auth.uid()`/`current_setting('request.user_uuid')`, but `get_db_session` never executes `SET LOCAL`. With the direct `SUPABASE_DB_URL` (postgres role), **RLS is bypassed entirely** — defense-in-depth promised in README ("User-scoped Row-Level Security") is inert. Ownership checks exist only in application code (single point of failure).

### ARCH-2: Zero pagination on list endpoints
`GET /documents` and `GET /actions` return full tables per user. Compare against 03_API_CONTRACT (cursor pagination). Mobile will OOM/flicker on large libraries.

### MOB-1: `flutter_secure_storage` used without platform configuration
Android requires `encryptedSharedPreferences: true` + minSdk 18+ handling; iOS needs Keychain accessibility level. No `android/` or `ios/` runner directories exist in `mobile/` — the app cannot actually build for either platform today (`pubspec.yaml` alone is not a Flutter project scaffold). CI `mobile-ci.yml` presumably only analyzes.

### MOB-2: No connectivity/offline handling
Document_8 §8.6 mandates offline behavior (cached reading, disabled network actions, explicit banners). `connectivity_plus`, Hive cache, and SSE reconnect are all absent from pubspec and code. `ApiClient.baseUrl` is hardcoded `http://localhost:8000` with no environment switching (kDebugMode/profile/flavor).

### MOB-3: Silent auth fallback `'test-token-demo-user'`
`api_client.dart` line: `?? 'test-token-demo-user'` — the app never surfaces a logged-out state; there is no login screen at all despite Supabase Auth being the chosen identity provider.

### QA-1: Comparison endpoint returns static boilerplate
`compare_documents` builds a two-row matrix of title/type with hardcoded recommendation text — violates 02_DATA_MODEL_CONTRACTS comparison schema (term-level deltas with citations per row).

---

## Medium / Polish (P2) — UI/UX competitiveness gaps vs market players

| ID | Finding | Spec ref |
|---|---|---|
| UX-1 | No dark theme (`MaterialApp` sets only `lightTheme`) — table stakes for 2026 market apps | Document_8 §8.2 |
| UX-2 | No search on Home (spec flow starts with Search); no filtering by document type/status | Document_8 §8.4 |
| UX-3 | Processing stage names in upload screen don't match spec vocabulary ("Reading pages → Identifying document → Extracting facts → Preparing Q&A"); no shimmer/Lottie skeletons | Document_8 §8.4 |
| UX-4 | Citation cards lack "jump to source page + highlight quote" (no PDF viewer integrated; Syncfusion/`pdfx` absent from pubspec) | Document_8 §8.5 |
| UX-5 | Empty-list state lacks onboarding CTA design; error state copy exposes raw Dart exception strings (`'$e'`) to users | Document_8 §8.6 |
| UX-6 | Risk severity color-only in some widgets despite badge icons (audit all states); contrast tokens partially deviate from spec palette (`0xFFFFEDD5` orange bg not in token set) | Document_8 §8.2 |
| UX-7 | No camera scan (ML Kit), no cloud import, no push notifications, no calendar export — all listed as core components | Document_8 §8.3 |
| UX-8 | `ConfidenceBadge` default branch maps unknown values to UNSUPPORTED/red — a typo'd enum turns trusted answers into alarming red badges; needs explicit exhaustive switch + neutral fallback | 25_AI_CONFIDENCE_POLICY |
| BE-1 | `datetime.utcnow()` deprecated naive datetimes across models/storage; use `datetime.now(timezone.utc)` | 02 contracts (timestamptz) |
| BE-2 | No Alembic; hand-written SQL migration is the single source of truth — schema drift risk between `models/` and `infra/` | 11_INFRA_CICD |
| BE-3 | CORS `allow_origins=["*"]` default combined with `allow_credentials=True` is rejected by browsers and unsafe if widened | OWASP |
| BE-4 | `ValidationError` mapped to 422 `HTTP_422_UNPROCESSABLE_CONTENT` constant name suggests version fragility; verify FastAPI starlette constant exists in pinned version (it passed lint, but pin explicitly) | — |
| BE-5 | Audit trail: `AuditEvent` model exists but nothing ever writes audit rows (erasure, access, action confirmations must be auditable per 09) | 09_SECURITY_DPDP |
| INF-1 | No CD workflow (staging/production deploys), no IaC validation (terraform plan/tflint), no secret scanning (gitleaks/trufflehog) or dependency audit (`pip-audit`, `npm audit`, dependabot) in CI | Document_9, 11_INFRA_CICD |
| INF-2 | `docker-compose.yml` provides Postgres+Redis but no MinIO/R2-mock, so local dev silently exercises the mock storage path — integration reality gap | — |
| TEST-1 | Only 4 test modules; no security tests (cross-user access, RLS enforcement, JWT alg confusion), no AI-eval golden-set harness (07_AI_EVALUATION, phase status "TODO"), no load/contract tests | 10_TEST_STRATEGY |
| TEST-2 | Idempotency-Key header support claimed by 08 state machine for upload initiation; unimplemented/untested | 08_ERROR_STATE_MACHINE |

---

## What's genuinely good (keep)
- Clean layering (`core/db/models/routes/schemas/services`), consistent envelope `APIResponse[T]`.
- Structured logging with correlation IDs end-to-end (FastAPI middleware ↔ Dio interceptor).
- Error classification state machine with no stack-trace leakage; centralized handlers.
- WCAG-minded components (icon+color dual encoding in `ConfidenceBadge`, ≥44px targets).
- CI quality gates (ruff format+lint, mypy, pytest w/ coverage, pgvector service container).
- Migration includes HNSW + FTS indexes and 12 RLS policies (correct intent, even if unwired — see ARCH-1).

## Recommended sequencing to production-ready
1. **P0 bugs first:** BUG-1 (session commit strategy), BUG-2 (upload verification), BUG-6 (auth backdoor gating).
2. **Core value:** BUG-3 (real ingestion + worker pipeline), BUG-4 (embeddings + hybrid retrieval).
3. **Compliance:** BUG-5 (full DPDP erasure), SEC-2 (Presidio), ARCH-1 (RLS wiring), BE-5 (audit events).
4. **Scale guards:** SEC-1 (rate limits/quotas), ARCH-2 (pagination).
5. **Mobile real-build:** MOB-1 (platform runners), MOB-3 (auth flow/login), MOB-2 (offline).
6. **UX polish for market parity:** UX-1…UX-8, QA-1.
7. **Hardening:** INF-1/2, TEST-1/2.

GitHub issue files: see `.github/issues/ISSUE-001 … ISSUE-016.md` (title = frontmatter `title:`, ready for `gh issue create --body-file`).

---

## Changelog — fixes applied

### 2026-10-23 — commit `e98d3e7` (P0 batch 1: #001, #005, #006 + latent bug)
- **#001 DB durability**: `commit_now()` helper added to `app/db/session.py`; every observable write in `documents.py` (upload-init, process pipeline incl. durable EXTRACTING/FAILED state transitions), `actions.py` (create/patch), and `users.py` (erasure) now commits before returning success. Request-scoped session commits deterministically.
- **#005 DPDP erasure**: storage-delete failures are no longer swallowed — erasure aborts with retryable `ERASURE_STORAGE_FAILED`; Supabase Auth identity is deleted via service-role admin API; response honestly reports `authIdentityDeleted`. `storage_service.delete_file()` now raises on failure.
- **#006 auth backdoor gated**: `test-token-*` accepted only when `ALLOW_TEST_TOKENS=true` (default false; validator refuses it in production). CI opts in via `tests/conftest.py`. Regression tests added both ways. Documented in `.env.example`.
- **New latent bug found & fixed during verification**: `ValidationError` referenced nonexistent `HTTP_422_UNPROCESSABLE_CONTENT` → every validation error crashed as an unhandled 500 under the pinned starlette version. Fixed to `HTTP_422_UNPROCESSABLE_ENTITY`. (Two previously "passing" tests were actually never exercising the 422 path correctly.)
- **Test suite**: 19 passed (was 17, +2 security regression tests).

**Remaining P0**: #002 (upload completion verification), #003 (real ingestion pipeline replacing mock pages), #004 (hybrid RAG with real embeddings) — these require infra (worker queue, pgvector migration, AI gateway wiring) and are next in sequence.


---

## Changelog — 2026-10-23 (Batch 2): ISSUE-002 closed
Server-side upload integrity verification shipped:
- `PENDING_UPLOAD` state + `/upload-complete` verification endpoint (existence, size match, max cap, magic-byte MIME sniff, PDF parseability + page limit, SHA-256 checksum) with durable FAILED transitions and idempotent replays.
- `/process` hard-gated on verified uploads; status CHECK-constraint migration added.
- `file_name` path-traversal sanitization; presign binds ContentType (+size range).
- Dev/CI mock storage replaced by a real in-memory vault so verification is exercised without cloud creds.
- Flutter upload flow now does PUT → upload-complete (client checksum) → process; friendly error surfacing.
- Backend suite green: 24 passed (6 new ISSUE-002 regression tests).
