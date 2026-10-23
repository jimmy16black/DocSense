---
title: "[P1][SECURITY] Postgres RLS policies are inert — app connects as superuser and never sets request.user_uuid"
labels: security, high, backend, database
---

## Problem
The migration ships 12 RLS policies keyed on `auth.uid()` / `current_setting('request.user_uuid')`, and README promises *"User-scoped Row-Level Security"* as defense-in-depth. However:

- The app connects via `SUPABASE_DB_URL` as `postgres` (owner/bypassrls role).
- `get_db_session` never executes `SET LOCAL request.user_uuid = '<jwt-sub>'`.
- Therefore **every query bypasses RLS**; isolation depends solely on application-level `user_id != current_user.id` checks — one forgotten check = cross-tenant leak.

## Acceptance criteria
- [ ] Create a least-privilege DB role (e.g. `docsense_app`, `NOBYPASSRLS`) used at runtime; owner role only for migrations.
- [ ] In the session dependency, after JWT verification run `SET LOCAL request.user_uuid = :uid` (bind parameter, not string interpolation) inside the transaction.
- [ ] Add integration test: raw query without ownership filter returns **zero** foreign-user rows when connected as `docsense_app`.
- [ ] Verify policies reference `current_setting('request.user_uuid', true)::uuid` consistently with `documents.user_id` type (currently `VARCHAR(128)` vs UUID mismatch — reconcile types).
