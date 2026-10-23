---
title: "[P0][SECURITY] upload-init trusts client-declared size/MIME; no upload-completion verification or checksum"
labels: bug, security, critical, backend
---

## Problem
`POST /api/v1/documents/upload-init` validates `file_size_bytes` and `mime_type` **from the request body only**. The presigned PUT URL has no constraints bound into it, and there is no completion endpoint that verifies what actually landed in R2.

Attack/enumeration:
- Declare `application/pdf, 1KB` → upload arbitrary bytes (HTML, JS-bearing SVG, binaries) to the vault.
- Bypass quota accounting (declared vs actual size diverge).
- Downstream ingestion parses unvalidated content → parser-fuzz / crafted-PDF exploitation surface.

## Expected behavior (09_SECURITY_DPDP, 22_DOCUMENT_LIFECYCLE)
Integrity of stored objects must be server-verified before any processing state advances past `UPLOADED`.

## Acceptance criteria
- [x] Presign with enforced conditions: exact `ContentType`, `ContentLengthRange` (0..MAX_UPLOAD_SIZE_BYTES).
- [x] New endpoint `POST /documents/{document_id}/upload-complete`: performs S3 HEAD, compares actual size/content-type to declared values, computes/verifies SHA-256 checksum, transitions `UPLOADED → VALIDATING` only on match; otherwise `FAILED` with `USER_ACTION_REQUIRED` classification.
- [x] Add `checksum_sha256 CHAR(64)` column + migration; client sends expected checksum at init (or computed server-side at completion).
- [x] Reject path traversal in `file_name` (sanitize; currently interpolated raw into `storage_path`).
- [x] Tests: oversized upload rejected, MIME spoof rejected, missing object at completion → deterministic error, double-completion idempotent.


## Resolution (2026-10-23) — implemented in commit pending push
- Presign now binds declared `ContentType` (+ ContentLengthRange hint where supported).
- New endpoint `POST /documents/{id}/upload-complete`: HEAD-existence, declared-vs-real size, max-size cap, magic-byte MIME sniffing (PDF/JPEG/PNG/WEBP), real PDF parse + page-count check, optional SHA-256 checksum verification. Failures durably transition to `FAILED` with USER_ACTION_REQUIRED; success records `checksum_sha256`/`verified_size_bytes`/`etag` in `metadata_json`.
- Lifecycle gate: documents start as `PENDING_UPLOAD`; `/process` refuses unverified uploads. DB CHECK constraint added via migration `20261023000000_upload_verification.sql`.
- Path traversal in `file_name` sanitized (`_safe_file_name`).
- Double completion is idempotent ("Upload already verified.").
- Mock storage mode upgraded from fake URL-trust to a bounded in-memory vault so verification runs end-to-end in CI without R2 creds.
- Mobile: upload screen now performs the real presigned PUT + upload-complete with client SHA-256 before `/process` (replaces fabricated progress delay); error snackbars surface server messages instead of raw exception strings.
- Tests: 6 new regression tests (missing object, size mismatch, MIME spoof, checksum mismatch, traversal sanitization, full lifecycle with verification + idempotent replay). Suite: 24 passed.
