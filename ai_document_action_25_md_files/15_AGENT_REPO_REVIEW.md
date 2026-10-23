# Agent Repository Review

## Objective
Understand the actual Git repository before implementation.

## Inventory

| Area | Current | Target | Gap |
|---|---|---|---|
| Repository Tree | Greenfield specs in `ai_document_action_25_md_files/` | Monorepo (`backend/`, `infra/`, `mobile/`, `.github/`) | Complete codebase scaffolding required |
| Backend | None | FastAPI (Python 3.12) | Scaffolding, core app, services, workers, tests required |
| Mobile | None | Flutter (iOS/Android) | Scaffolding, Riverpod, Dio, UI flows required |
| Database | None | Supabase PostgreSQL 16 + RLS | Migration scripts, models, RLS policies required |
| Vector | None | pgvector (HNSW / IVFFlat) + Hybrid FTS | Vector schemas, chunking, embeddings pipeline required |
| Storage | None | Cloudflare R2 (S3-compatible API) | Presigned upload/download client required |
| Queue | None | Upstash Redis / Kafka | Async worker job queue & rate limiting required |
| AI Gateway | None | Portkey (Gemini primary, OpenAI fallback) | Gateway client & prompt orchestration required |
| Models | None | Gemini 1.5 Pro / Flash & GPT-4o fallback | Structured output extraction & grounding required |
| Prompts | Markdown specs | Versioned JSON/YAML prompt templates | Versioned prompt repository required |
| Schemas | Markdown specs (`02_DATA_MODEL_CONTRACTS.md`) | Pydantic v2 & JSON Schema contracts | Canonical extraction models required |
| CI/CD | None | GitHub Actions (Backend & Mobile) | Lint, test, audit, and build workflows required |

## Detailed Inspection Findings

1. **Source Tree**:
   - The workspace initially contains only the specification directory `ai_document_action_25_md_files/`.
   - No code or runtime configuration exists yet.
   - Clean slate allows greenfield implementation strictly adhering to ADR-001 through ADR-007.

2. **Local Environment & Tooling**:
   - OS: macOS (aarch64)
   - Python: 3.12 available (`/Users/gautamkale/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12` and `/opt/homebrew/bin/python3.12`)
   - Package manager: `uv` available at `/Users/gautamkale/.local/bin/uv`
   - Node.js: v22.22.3 available
   - Docker: available at `/usr/local/bin/docker`
   - Git: version 2.54.0

3. **Dependencies & APIs**:
   - Backend needs Python 3.12 with FastAPI, Pydantic v2, SQLAlchemy async, asyncpg, pgvector, Alembic, PyMuPDF, Unstructured, Portkey, Presidio, APScheduler, structlog, pytest, mypy, ruff.
   - Target API contracts in `03_API_CONTRACT.md` (`/api/v1/documents/*`, `/api/v1/actions/*`, `/api/v1/users/me`).

4. **Database & Migrations**:
   - Supabase PostgreSQL with RLS enabled on all user-scoped tables (`documents`, `document_pages`, `document_chunks`, `document_actions`, `chat_messages`, etc.).
   - Need Alembic / raw SQL migrations under `infra/supabase/migrations/` and `backend/alembic/`.

5. **AI Integration, Prompts & Vector Strategy**:
   - Extraction pipeline with deterministic validation, citation mapping, and confidence scoring (`25_AI_CONFIDENCE_POLICY.md`).
   - Hybrid retrieval (pgvector + PostgreSQL full-text search + Reciprocal Rank Fusion) with tenant isolation.

6. **Security & DPDP Controls**:
   - Data minimization, PII masking via Presidio before LLM, user-scoped RLS, encrypted storage, right to erasure (`DELETE /api/v1/users/me`).

## Reusable Components & Foundation Strategy
- All 25 architecture documents provide unambiguous schemas, contracts, state machines, and rules.
- We will construct the target monorepo starting with `backend/` foundation, followed by `infra/` and database migrations.

## Recommended Task Execution Order
1. **Foundation (FOUND-001 to FOUND-006)**:
   - Create monorepo skeleton (`backend/`, `infra/`, `docker-compose.yml`, `Makefile`, `README.md`, `.env.example`).
   - Backend setup with Python 3.12 + `uv` (`pyproject.toml`).
   - Core FastAPI application, configuration (`pydantic-settings`), structured logging, correlation IDs, error handlers, and health endpoints (`/healthz`, `/readyz`).
   - Test harness (`pytest`, `pytest-asyncio`, `httpx`).
2. **Data & Storage (DB-001 to DB-007, ING-001)**:
   - Supabase/PostgreSQL schema with pgvector & RLS policies in `infra/supabase/migrations/` and SQLAlchemy models in `backend/app/models/`.
   - Canonical Pydantic schemas in `backend/app/schemas/` matching `02_DATA_MODEL_CONTRACTS.md`.
   - Cloudflare R2 / S3 client for presigned URLs.
3. **Ingestion & AI Pipeline (ING-002 to ING-010, AI-001 to AI-007)**:
   - Validation, PDF text extraction with PyMuPDF, chunking, embedding generation.
   - AI Gateway (Portkey / Gemini / OpenAI fallback) with prompt guardrails and PII redaction.
   - Structured extraction envelope and citation validation.
   - Hybrid vector + FTS search with RRF.
4. **Action & Chat APIs (API-001 to API-007)**:
   - Q&A endpoint, document comparison, reminder scheduling, account deletion.

## Decision
`READY` - Proceed directly with Foundation & Monorepo scaffolding.
