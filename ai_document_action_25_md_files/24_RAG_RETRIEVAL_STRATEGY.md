# RAG Retrieval Strategy

## Retrieval Flow

```text
Question
 ↓
Intent classification
 ↓
Authorization filter
 ↓
Metadata filtering
 ↓
Vector retrieval + keyword retrieval
 ↓
Hybrid ranking
 ↓
Optional reranking
 ↓
Context assembly
 ↓
Grounded generation
 ↓
Citation validation
```

## Rules
- Retrieval must always be user/document scoped.
- Structured facts should bypass RAG when possible.
- Retrieved context must preserve page/chunk identity.
- Duplicate evidence should be collapsed.
- Retrieval configuration is versioned.

## Quality Controls
Measure recall, relevance, citation correctness and answer groundedness.

## Insufficient Evidence
If retrieval does not provide sufficient evidence, the answer must say that the document does not specify the information rather than guessing.
