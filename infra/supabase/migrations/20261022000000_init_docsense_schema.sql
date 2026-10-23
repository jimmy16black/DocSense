-- =====================================================================
-- DocSense Database Initialization Migration
-- Stack: Supabase PostgreSQL 16 + pgvector + Row Level Security (RLS)
-- =====================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. Documents Table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(128) NOT NULL,
    title VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'UPLOADED',
    document_type VARCHAR(50),
    confidence_score FLOAT,
    page_count INTEGER DEFAULT 0,
    error_message TEXT,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 3. Document Pages Table
CREATE TABLE IF NOT EXISTS document_pages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL,
    page_number INTEGER NOT NULL,
    raw_text TEXT NOT NULL DEFAULT '',
    image_path VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_page_doc_num UNIQUE (document_id, page_number)
);

-- 4. Document Chunks Table (Vector Store)
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL,
    page_number INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 5. Extractions Table
CREATE TABLE IF NOT EXISTS extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    confidence_score FLOAT NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary_bullets JSONB DEFAULT '[]'::jsonb,
    important_alerts JSONB DEFAULT '[]'::jsonb,
    suggested_questions JSONB DEFAULT '[]'::jsonb,
    recommended_actions JSONB DEFAULT '[]'::jsonb,
    payload JSONB DEFAULT '{}'::jsonb,
    raw_llm_response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 6. Citations Table
CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extraction_id UUID REFERENCES extractions(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL,
    page_number INTEGER NOT NULL,
    section_heading VARCHAR(255),
    exact_quote TEXT NOT NULL,
    bounding_box JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 7. Document Actions Table
CREATE TABLE IF NOT EXISTS document_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 8. Chat Sessions & Messages Tables
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL,
    title VARCHAR(255) DEFAULT 'Document Q&A',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    user_id VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]'::jsonb,
    confidence VARCHAR(30) DEFAULT 'HIGH',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 9. Audit Events Table
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    action_id UUID REFERENCES document_actions(id) ON DELETE SET NULL,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- =====================================================================
-- Performance Indexes
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_document_pages_doc_user ON document_pages(document_id, user_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_user ON document_chunks(document_id, user_id);

-- HNSW Vector Index on embeddings (Cosine similarity)
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- PostgreSQL Full-Text Search Index on chunk content
CREATE INDEX IF NOT EXISTS idx_document_chunks_fts 
ON document_chunks USING gin (to_tsvector('english', content));

CREATE INDEX IF NOT EXISTS idx_extractions_doc_user ON extractions(document_id, user_id);
CREATE INDEX IF NOT EXISTS idx_citations_doc_user ON citations(document_id, user_id);
CREATE INDEX IF NOT EXISTS idx_actions_user_status ON document_actions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

-- =====================================================================
-- Row-Level Security (RLS) Policies (ADR-002)
-- =====================================================================
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

-- Documents RLS
CREATE POLICY "isolate_user_documents_select" ON documents FOR SELECT
USING (auth.uid()::text = user_id);
CREATE POLICY "isolate_user_documents_insert" ON documents FOR INSERT
WITH CHECK (auth.uid()::text = user_id);
CREATE POLICY "isolate_user_documents_update" ON documents FOR UPDATE
USING (auth.uid()::text = user_id);
CREATE POLICY "isolate_user_documents_delete" ON documents FOR DELETE
USING (auth.uid()::text = user_id);

-- Document Pages RLS
CREATE POLICY "isolate_user_pages_all" ON document_pages FOR ALL
USING (auth.uid()::text = user_id)
WITH CHECK (auth.uid()::text = user_id);

-- Document Chunks RLS
CREATE POLICY "isolate_user_chunks_all" ON document_chunks FOR ALL
USING (auth.uid()::text = user_id)
WITH CHECK (auth.uid()::text = user_id);

-- Extractions RLS
CREATE POLICY "isolate_user_extractions_all" ON extractions FOR ALL
USING (auth.uid()::text = user_id)
WITH CHECK (auth.uid()::text = user_id);

-- Citations RLS
CREATE POLICY "isolate_user_citations_all" ON citations FOR ALL
USING (auth.uid()::text = user_id)
WITH CHECK (auth.uid()::text = user_id);

-- Document Actions RLS
CREATE POLICY "isolate_user_actions_all" ON document_actions FOR ALL
USING (auth.uid()::text = user_id)
WITH CHECK (auth.uid()::text = user_id);

-- Chat RLS
CREATE POLICY "isolate_user_chat_sessions_all" ON chat_sessions FOR ALL
USING (auth.uid()::text = user_id)
WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "isolate_user_chat_messages_all" ON chat_messages FOR ALL
USING (auth.uid()::text = user_id)
WITH CHECK (auth.uid()::text = user_id);

-- Audit Events RLS (Users can view their own audit logs)
CREATE POLICY "isolate_user_audit_select" ON audit_events FOR SELECT
USING (auth.uid()::text = user_id);
