# Project Status

## Current Critical Path

`Repository Review → Foundation → Data → Ingestion → AI → Mobile → QA → Production`

## Phase Status

| Phase | Status | Owner |
|---|---|---|
| Repository Review | COMPLETED | Repository Analyst |
| Backend Foundation | COMPLETED | Backend Agent |
| Database | COMPLETED | Backend Agent |
| Ingestion | IN_PROGRESS | Backend Agent |
| AI/RAG | IN_PROGRESS | AI Agent |
| Mobile | COMPLETED | Mobile Agent |
| Infrastructure | COMPLETED | Infra Agent |
| Security | IN_PROGRESS | Security Agent |
| QA | IN_PROGRESS | QA Agent |
| AI Evaluation | TODO | QA/AI Agent |
| Production | TODO | Human + Agents |

## Environments

| Environment | Status | Version | Notes |
|---|---|---|---|
| Development | ACTIVE | 0.1.0-alpha | Monorepo scaffolding, FastAPI backend, local Docker, Supabase RLS migrations |
| Staging | TODO | | Target Cloudflare R2 + Supabase + Railway |
| Production | TODO | | |

## Completed Implementation Tasks
- **REPO-001 to REPO-004**: Complete repository inspection, architecture mapping, and gap analysis.
- **FOUND-001 to FOUND-006**:
  - Strongly typed configuration with `pydantic-settings`.
  - Structured JSON logging with `structlog` & correlation IDs (`X-Correlation-ID`).
  - Error state machine (`DocSenseException`, `ErrorClassification`) preventing stack trace leaks.
  - Supabase JWT authentication middleware with user context.
  - Database connectivity with async SQLAlchemy + asyncpg and connection pooling.
  - Liveness and readiness endpoints (`/healthz`, `/readyz`).
  - GitHub Actions CI workflow for backend lint, type check, and tests.
- **DB-001 to DB-007**:
  - Full relational schema in SQLAlchemy and Supabase PostgreSQL migration script (`20261022000000_init_docsense_schema.sql`).
  - Strict Row-Level Security (RLS) policies on all tables (`documents`, `document_pages`, `document_chunks`, `extractions`, `citations`, `document_actions`, `chat_sessions`, `chat_messages`).
  - HNSW cosine similarity index and PostgreSQL FTS full-text search indexes on vector chunks.
- **ING-001 to ING-008 & AI-001 to AI-004 (Core)**:
  - Presigned upload/download URLs for Cloudflare R2 vault.
  - File validation (MIME type and size limits).
  - PyMuPDF text extraction, chunking, and verbatim citation verification.
  - Portkey AI Gateway service with primary/fallback routing and Presidio PII redaction.
  - Hybrid RAG retrieval service using Reciprocal Rank Fusion (RRF).
  - Grounded Q&A endpoint, document comparison endpoint, action reminder scheduling, and DPDP account erasure (`DELETE /api/v1/users/me`).
- **MOB-001 to MOB-008 (Mobile Scaffolding & Screens)**:
  - Complete Flutter application in `mobile/` configured with `pubspec.yaml`.
  - Design tokens in `app_theme.dart` adhering to WCAG 2.1 AA (min 44x44 touch targets, high-contrast, accessible risk signaling).
  - Dio API client with `X-Correlation-ID` header and JWT Bearer interceptor.
  - Riverpod state providers for document listing and details.
  - Screens implemented: `HomeScreen`, `UploadScreen`, `DocumentDetailScreen`, `QAScreen`, `CompareScreen`, and `ActionsScreen`.
  - Interactive widgets: `ConfidenceBadge` and `CitationCard` with exact quote display and page jump navigation.
  - Mobile CI pipeline in `.github/workflows/mobile-ci.yml`.

## Blockers
None.

## Architecture Decisions
- ADR-001 (FastAPI + Python 3.12)
- ADR-002 (Supabase PostgreSQL + pgvector + RLS)
- ADR-003 (Cloudflare R2 Object Storage)
- ADR-004 (Portkey AI Gateway)
- ADR-005 (Hybrid Vector + FTS Retrieval with RRF)
- ADR-006 (PyMuPDF Layout Extraction)
- ADR-007 (Upstash Queue/Cache)

## Change Log
- 2026-10-22: Completed Repository Review and created `15_AGENT_REPO_REVIEW.md`.
- 2026-10-22: Created monorepo structure, `docker-compose.yml`, `Makefile`, `README.md`, `.gitignore`, and `.env.example`.
- 2026-10-22: Built complete FastAPI backend with models, routes, services, schemas, and error handling.
- 2026-10-22: Created Supabase PostgreSQL schema with RLS and pgvector migration script.
- 2026-10-22: Implemented GitHub Actions CI workflow in `.github/workflows/backend-ci.yml`.
- 2026-10-22: Established automated test suite (17 passed unit and integration tests, 0 warnings, mypy & ruff verified).
