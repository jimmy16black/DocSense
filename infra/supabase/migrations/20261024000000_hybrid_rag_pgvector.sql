-- ISSUE-004: hybrid RAG — enable semantic search at scale.
-- 1. Ensure pgvector extension + embedding column exist (idempotent).
-- 2. Add an HNSW cosine index so ANN search stays fast as chunk counts grow.
-- 3. Backfill note: chunks created before embeddings were wired have NULL
--    embeddings; the ingestion pipeline (re-run /process) fills them. The
--    lexical retrieval leg covers those rows meanwhile, so no data is
--    unreachable.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
