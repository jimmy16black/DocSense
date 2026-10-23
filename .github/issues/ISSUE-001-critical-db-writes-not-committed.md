---
title: "[P0][BUG] Database writes are never durably committed — flush-only session pattern loses data"
labels: bug, critical, backend
---

## Problem
`app/db/session.py::get_db_session` only calls `commit()` *after* the route handler's response has been generated. Every mutation route (`upload-init`, `process`, `create_reminder`, `update_action`, `delete_document`, `delete_user_account`) relies on `await db.flush()` and never commits explicitly.

Consequences:
1. With SQLAlchemy `autoflush=False`, in-transaction `SELECT`s after a flush may not observe pending state consistently.
2. Any exception raised mid-handler rolls back **all** prior "successful" writes while the API already logged progress — violating atomic state transitions in `08_ERROR_STATE_MACHINE.md`.
3. Client disconnects / middleware errors after response construction can discard writes that the API reported as successful (e.g., `"Document processed and indexed successfully"`).
4. Integration tests pass because everything shares one live session — masking the bug.

## Expected behavior
Per 02_DATA_MODEL_CONTRACTS + 08_ERROR_STATE_MACHINE: each state transition is atomically committed; success responses imply durability.

## Acceptance criteria
- [ ] Introduce an explicit unit-of-work pattern: service layer commits at defined transaction boundaries (or session dependency commits before response serialization completes).
- [ ] `process_document` persists status transitions (`VALIDATING → EXTRACTING → COMPLETED/FAILED`) with a commit per transition so failure states survive crashes.
- [ ] Add integration test that kills the request cycle post-response and re-reads rows from a **fresh session/connection** to prove durability.
- [ ] Add regression test: exception after partial writes leaves DB consistent (no orphaned extraction without document status update).

## Evidence
- `backend/app/db/session.py` lines 33–42
- All handlers in `backend/app/routes/documents.py`, `actions.py`, `users.py` (grep `db.flush()` — zero `commit()` outside session teardown)

---

## ✅ Fix status (2026-10-23)

Resolved in commit `e98d3e7` — fix implemented with regression tests; full suite green (19 passed). See REVIEW_FINDINGS.md changelog.
