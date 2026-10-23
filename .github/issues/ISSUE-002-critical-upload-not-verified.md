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
- [ ] Presign with enforced conditions: exact `ContentType`, `ContentLengthRange` (0..MAX_UPLOAD_SIZE_BYTES).
- [ ] New endpoint `POST /documents/{document_id}/upload-complete`: performs S3 HEAD, compares actual size/content-type to declared values, computes/verifies SHA-256 checksum, transitions `UPLOADED → VALIDATING` only on match; otherwise `FAILED` with `USER_ACTION_REQUIRED` classification.
- [ ] Add `checksum_sha256 CHAR(64)` column + migration; client sends expected checksum at init (or computed server-side at completion).
- [ ] Reject path traversal in `file_name` (sanitize; currently interpolated raw into `storage_path`).
- [ ] Tests: oversized upload rejected, MIME spoof rejected, missing object at completion → deterministic error, double-completion idempotent.
