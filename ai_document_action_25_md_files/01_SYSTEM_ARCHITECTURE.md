# System Architecture

## Target Stack
- Flutter mobile
- Python FastAPI
- Supabase Auth
- Supabase PostgreSQL
- pgvector
- Cloudflare R2
- Railway
- Upstash Redis/Kafka
- Portkey AI Gateway
- Gemini primary
- OpenAI fallback

## Logical Architecture

```text
Flutter
  ↓ HTTPS/JWT
FastAPI
  ├── Supabase Auth
  ├── PostgreSQL + pgvector
  ├── Cloudflare R2
  ├── Upstash
  └── Portkey
        ├── Primary model
        └── Fallback model
```

## Processing
Upload → Validation → OCR/Text extraction → Classification → Extraction → Schema validation → Citation validation → Chunking → Embeddings → Indexing → Completed

## Q&A
Use structured data for deterministic fact lookup. Use hybrid RAG for clause/content questions.

## Architectural Rule
The actual repository must be inspected before implementation. Existing working functionality should be reused where compatible with the target architecture.
