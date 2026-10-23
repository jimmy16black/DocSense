-- =====================================================================
-- DocSense: Idempotency-Key storage (ISSUE-016)
-- Backs the `Idempotency-Key` header contract on unsafe POST endpoints
-- (/documents/{id}/process, /documents/{id}/ask, /actions/reminders).
-- Scope = sha256(user_id | method | path)[:64]; keys are scoped per user
-- so cross-tenant replays/collisions are impossible. Rows expire after
-- 24h and are purged opportunistically by the guard itself.
-- =====================================================================

CREATE TABLE IF NOT EXISTS idempotency_keys (
    id              VARCHAR(256) NOT NULL,
    scope           VARCHAR(64)  NOT NULL,
    response_status INTEGER,
    response_body   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (scope, id)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_expires
    ON idempotency_keys (expires_at);

COMMENT ON TABLE idempotency_keys IS
    'Recorded responses for Idempotency-Key replays (ISSUE-016). A row with '
    'NULL response_body is an in-flight reservation; replays of it get 409.';
