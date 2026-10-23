# Supabase Production Setup & Hardening Guide

This document outlines the step-by-step procedure for provisioning, configuring, and securing Supabase production services for DocSense.

---

## 1. Project Provisioning & Architecture

- **Database Engine**: PostgreSQL 16 (AWS or GCP region closest to primary user base).
- **Required Extensions**:
  ```sql
  CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
  CREATE EXTENSION IF NOT EXISTS "vector";
  ```
  *(Both extensions are pre-configured in `infra/supabase/migrations/20261022000000_init_docsense_schema.sql`)*.

---

## 2. Connection Strings & Supavisor Connection Pooling

Supabase provides two database endpoints. DocSense distinguishes between them:

### A. Application Runtime (`SUPABASE_DB_URL`)
Use the **Supavisor Transaction Pooler** (port `6543`):
```text
postgresql+asyncpg://postgres.<project-ref>:<db-password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```
* **Why**: High-concurrency async connections from FastAPI / Railway instances without exhausting PostgreSQL connection limits.
* **Pooler settings in `app/db/session.py`**: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`.

### B. Migration Runner (`make db-migrate`)
Use the **Direct Session Connection** (port `5432`):
```text
postgresql+asyncpg://postgres.<project-ref>:<db-password>@db.<project-ref>.supabase.co:5432/postgres
```
* **Why**: Schema changes (DDL, `CREATE INDEX`, `ALTER TABLE`) require direct session mode.

---

## 3. Applying Migrations in Order

DocSense migrations are version-controlled in [`infra/supabase/migrations/`](file:///Users/gautamkale/Docsense/DocSense/infra/supabase/migrations/):

```bash
# 1. Set direct connection in environment
export SUPABASE_DB_URL="postgresql+asyncpg://postgres.<ref>:<pass>@db.<ref>.supabase.co:5432/postgres"

# 2. Run the migration runner
make db-migrate
```

### Migration Execution Sequence:
1. `20261022000000_init_docsense_schema.sql` — Core tables (`documents`, `document_pages`, `document_chunks`, `extractions`, `citations`, `document_actions`, `chat_sessions`, `chat_messages`, `audit_events`), initial RLS policies, HNSW & FTS indexes.
2. `20261023000000_upload_verification.sql` — Server-side verification constraints and status validation.
3. `20261024000000_hybrid_rag_pgvector.sql` — pgvector cosine ops HNSW index (`m=16, ef_construction=64`).
4. `20261025000000_idempotency_keys.sql` — Distributed idempotency keys table with RLS enabled.

---

## 4. Row-Level Security (RLS) Matrix

Every table has RLS enabled (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`).

| Table | Policy Name | Permitted Scope |
|---|---|---|
| `documents` | `isolate_user_documents_*` | `auth.uid()::text = user_id` (SELECT, INSERT, UPDATE, DELETE) |
| `document_pages` | `isolate_user_pages_all` | `auth.uid()::text = user_id` (ALL) |
| `document_chunks` | `isolate_user_chunks_all` | `auth.uid()::text = user_id` (ALL) |
| `extractions` | `isolate_user_extractions_all` | `auth.uid()::text = user_id` (ALL) |
| `citations` | `isolate_user_citations_all` | `auth.uid()::text = user_id` (ALL) |
| `document_actions`| `isolate_user_actions_all` | `auth.uid()::text = user_id` (ALL) |
| `chat_sessions` | `isolate_user_chat_sessions_all` | `auth.uid()::text = user_id` (ALL) |
| `chat_messages` | `isolate_user_chat_messages_all` | `auth.uid()::text = user_id` (ALL) |
| `audit_events` | `isolate_user_audit_select` | `auth.uid()::text = user_id` (SELECT only; mutations via service) |
| `idempotency_keys`| `RLS enabled` | Access isolated by application-level tenant scope |

---

## 5. Supabase Auth & JWT Configuration

1. **JWT Secret**:
   - Go to Supabase Dashboard $\rightarrow$ **Project Settings** $\rightarrow$ **API** $\rightarrow$ **JWT Settings**.
   - Copy the JWT Secret and configure as `SUPABASE_JWT_SECRET` in production secrets.
   - Must be at least 32 characters (enforced by Pydantic validator).

2. **Service Role Key**:
   - Copy `service_role` secret (bypasses RLS) and configure as `SUPABASE_SERVICE_ROLE_KEY`.
   - **Crucial for DPDP compliance**: Used in `backend/app/routes/users.py` to permanently delete the identity from `auth.users` when a user invokes `DELETE /api/v1/users/me`.

---

## 6. Verification Checklist Before Launch

- [ ] Supabase CLI / `make db-migrate` completed with zero errors.
- [ ] Supabase Linter (Security Advisor) reports 0 tables with RLS disabled.
- [ ] Pydantic startup validation passes (`APP_ENV=production` boots cleanly).
- [ ] HNSW index on `document_chunks.embedding` is populated and active.
- [ ] PITR (Point-In-Time Recovery) or daily automated backups enabled in Supabase dashboard.
