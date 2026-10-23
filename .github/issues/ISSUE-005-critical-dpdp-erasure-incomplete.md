---
title: "[P0][COMPLIANCE] DPDP right-to-erasure is incomplete — auth identity survives, storage deletes fail silently"
labels: bug, security, critical, compliance
---

## Problem
`DELETE /api/v1/users/me` (09_SECURITY_DPDP contract) claims *"All user documents, records, and data have been permanently deleted"* but:

1. **Supabase Auth user is never deleted.** Email/phone identities persist in `auth.users`/`auth.identities`. Erasure is legally incomplete.
2. **Storage purge is fire-and-forget.** `storage_service.delete_file()` catches all exceptions and only logs; the endpoint returns success even when R2 objects remain.
3. No audit event written for the erasure itself (`AuditEvent` model exists but unused).
4. Deletion order relies on manual table list — any new table with user data will be forgotten (silent non-compliance by construction).

## Acceptance criteria
- [ ] Call Supabase GoTrue admin API (`DELETE /admin/users/{id}`) using `SUPABASE_SERVICE_ROLE_KEY`; propagate failure as `SYSTEM_FAILURE` + partial-state flag, or enqueue a compensating deletion job.
- [ ] Make storage deletion verifiable: collect per-key delete results; if any fail, record document rows in a `deletion_jobs` retry queue rather than claiming success.
- [ ] Write an `AuditEvent(actor, action='USER_ERASURE', payload)` row before purging (retained anonymized metadata only, per spec).
- [ ] Prefer DB-level `ON DELETE CASCADE` from `documents` (migration already defines FK cascades — rely on it instead of hand-listed deletes) plus a schema test that fails CI if a new `user_id` table lacks cascade coverage.
- [ ] Integration test: full lifecycle signup→upload→process→erase asserts zero residual rows across **all** tables, auth user gone, R2 objects HEAD → 404.

---

## ✅ Fix status (2026-10-23)

Resolved in commit `e98d3e7` — fix implemented with regression tests; full suite green (19 passed). See REVIEW_FINDINGS.md changelog.
