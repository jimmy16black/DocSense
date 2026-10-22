# Document 7: Architecture Decision Records (ADRs) & Modern Stack Pivot

> Parent Blueprint: AI Document → Action: Complete Product & Technical Blueprint  
> Audience: AI Coding Agents, Backend Engineers, DevOps, CTO

## 7.1 ADR-001: Backend — Python FastAPI

**Status:** ACCEPTED  
**Decision:** Python 3.12 + FastAPI + Uvicorn.

The target backend is optimized for document parsing, AI/RAG integration, typed JSON contracts, and rapid iteration.

### Structure

```text
backend/
├── app/
│   ├── core/
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── workers/
│   └── db/
├── tests/
├── pyproject.toml
├── Dockerfile
└── .env.example
```

### Core Dependencies

FastAPI, Pydantic v2, SQLAlchemy async, asyncpg, pgvector, Alembic, PyMuPDF, Unstructured, Portkey, Gemini/OpenAI clients, Redis, Presidio, APScheduler, structlog, pytest, mypy and ruff.

## 7.2 ADR-002: Database & Auth — Supabase

**Status:** ACCEPTED  
**Decision:** Supabase PostgreSQL + pgvector + Auth + RLS.

All user-scoped tables must enforce ownership at the database layer.

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "isolate_user_documents_select"
ON documents FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "isolate_user_documents_insert"
ON documents FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "isolate_user_documents_delete"
ON documents FOR DELETE
USING (auth.uid() = user_id);

CREATE POLICY "isolate_user_chunks_all"
ON document_chunks FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);
```

The same ownership model applies to actions, chat and future user-scoped tables.

## 7.3 ADR-003: Object Storage — Cloudflare R2

**Status:** ACCEPTED  
**Decision:** Cloudflare R2 using its S3-compatible API.

Use environment-specific buckets:

```text
doc-action-vault-dev
doc-action-vault-staging
doc-action-vault-prod
```

Use short-lived presigned URLs. Never expose permanent storage credentials to Flutter.

## 7.4 ADR-004: AI Gateway — Portkey

All production model traffic goes through the AI gateway.

```text
FastAPI
 ↓
Policy + PII handling
 ↓
Portkey
 ├── Primary model
 └── Fallback model
```

The gateway provides provider abstraction, observability, cost tracking and controlled fallback.

## 7.5 ADR-005: Vector Search — pgvector + Hybrid Retrieval

Use pgvector for semantic retrieval and PostgreSQL full-text search for exact terminology.

```text
Question
 ├── Vector search
 └── Full-text search
        ↓
Reciprocal Rank Fusion
        ↓
Optional reranking
        ↓
Grounded answer
```

Vector records must retain user/document/chunk lineage and embedding version.

## 7.6 ADR-006: PDF Processing

- PyMuPDF: primary PDF parsing/rendering.
- Unstructured: layout-aware parsing where needed.
- OCR: only where text extraction is insufficient.

Password-protected PDFs must be handled according to the mobile/security policy before server-side processing.

## 7.7 ADR-007: Queue & Cache — Upstash

Use Upstash Redis for cache/rate limiting and Upstash Kafka where durable asynchronous processing is required.

```text
Upload → Job → Queue → Worker → Processing Pipeline
```

Jobs must be idempotent, retryable and observable.

## 7.8 Cost and Provider Assumptions

The stack targets low operational overhead for the MVP. Provider pricing, quotas, regions and capabilities must be verified before production because they can change.

## 7.9 ADR Governance

Every material architecture change records:

- context
- decision
- alternatives
- consequences
- migration plan
- rollback plan
- owner
- date
- status

Agents may propose ADR changes. Human approval is required for accepted changes affecting security, data lifecycle, architecture, cost or major provider dependencies.
