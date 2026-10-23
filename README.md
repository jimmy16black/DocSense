# DocSense — AI Document → Action

DocSense turns user documents (insurance policies, GST invoices, bills, contracts) into structured understanding, grounded answers with exact page/clause citations, and actionable automated workflows.

## System Architecture

```text
Flutter Mobile App (iOS / Android)
        │ HTTPS / JWT
        ▼
FastAPI Application (Python 3.12)
 ├── Authentication: Supabase Auth (JWT + RLS)
 ├── Storage: Cloudflare R2 (S3-compatible presigned URLs)
 ├── Database: Supabase PostgreSQL 16 + pgvector (Hybrid FTS + Dense Retrieval)
 ├── Cache & Queue: Upstash Redis & Kafka
 └── AI Gateway: Portkey (Gemini 1.5 primary, OpenAI fallback)
```

## Core Principles

1. **Accuracy over fluency:** Deterministic schema validation and source grounding.
2. **Evidence over unsupported inference:** Every critical extraction and answer requires page/quote citations.
3. **Privacy by default (DPDP):** User-scoped Row-Level Security (RLS), PII masking with Presidio, short-lived tokens, right to erasure (`DELETE /api/v1/users/me`).
4. **Constrained agent execution:** Autonomous agents operate under least-privilege tool contracts; consequential actions require explicit user confirmation.

## Repository Layout

```text
DocSense/
├── backend/                   # Python FastAPI Backend
│   ├── app/
│   │   ├── core/              # Config, security, logging, error state machine
│   │   ├── db/                # SQLAlchemy async session & base
│   │   ├── models/            # Database entities & RLS models
│   │   ├── routes/            # REST API routers (/api/v1/...)
│   │   ├── schemas/           # Pydantic v2 data models & contracts
│   │   ├── services/          # Ingestion, OCR, RAG, AI Gateway, Actions
│   │   └── workers/           # Asynchronous task workers
│   ├── tests/                 # Unit, integration, security & AI evaluation tests
│   ├── pyproject.toml         # UV / PEP 621 dependency manifest
│   ├── Dockerfile
│   └── .env.example
├── infra/                     # Infrastructure definitions
│   ├── supabase/migrations/   # SQL migrations with pgvector & RLS
│   ├── cloudflare/            # R2 bucket configuration
│   └── railway/               # Deployment configurations
├── .github/workflows/         # CI/CD pipelines
├── ai_document_action_25_md_files/ # Architecture specifications & ADRs
├── docker-compose.yml         # Local dev environment (Postgres + Redis)
└── Makefile                   # Common development tasks
```

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.12+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker & Docker Compose

### 2. Start Local Databases
```bash
make up
```

### 3. Install Backend Dependencies
```bash
make install
```

### 4. Run Development Server
```bash
make dev
```
The server will start at `http://localhost:8000`.
- API Documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/healthz`
- Readiness check: `http://localhost:8000/readyz`

### 5. Run Tests
```bash
make test
```
