# Vector & RAG Lifecycle

## Pipeline

```text
Document
 ↓
Text
 ↓
Chunks
 ↓
Embedding
 ↓
pgvector
```

## Metadata
Each vector record should contain:
- user ID
- document ID
- chunk ID
- page
- document type
- embedding model/version

## Rules
- Never retrieve across users.
- Delete vectors with the source lifecycle.
- Do not silently mix incompatible embedding dimensions/models.
- Re-embedding is a controlled migration.
- Stale vectors must be identifiable.

## Migration
Embedding model changes require:
1. new index/version
2. backfill
3. evaluation
4. controlled cutover
5. old-vector cleanup
