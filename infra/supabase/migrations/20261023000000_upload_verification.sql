-- =====================================================================
-- DocSense: Upload integrity verification (ISSUE-002)
-- Adds server-verified upload metadata to documents. Checksums live in
-- documents.metadata_json ('checksum_sha256', 'verified_size_bytes') and
-- are enforced by POST /documents/{id}/upload-complete; this migration
-- backfills legacy rows that predate the PENDING_UPLOAD -> UPLOADED gate.
-- =====================================================================

ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_status;
ALTER TABLE documents ADD CONSTRAINT ck_documents_status CHECK (
    status IN (
        'PENDING_UPLOAD','UPLOADED','VALIDATING','OCR_RUNNING','EXTRACTING',
        'VALIDATING_EXTRACTION','CHUNKING','EMBEDDING','COMPLETED','RETRYING','FAILED'
    )
);

COMMENT ON COLUMN documents.status IS
    'Lifecycle state. PENDING_UPLOAD is set at upload-init; only server-side
     verification via /upload-complete may promote to UPLOADED (ISSUE-002).';
