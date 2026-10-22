# Agent Memory

## Memory Types
1. User preferences
2. Document-scoped context
3. Conversation memory
4. Agent execution state

## Retention
Every memory class must have an explicit retention policy. Conversation memory should have a bounded TTL; the exact production value is a configurable policy rather than an implementation assumption.

## Vector Memory
Document embeddings are derived data, not independent user-owned content. They must carry user/document lineage and be deleted or re-generated with the source lifecycle.

## Right to Be Forgotten
Account/document deletion must cover:
- original files
- OCR
- extracted data
- chunks
- embeddings
- chat context
- persistent agent memory
- caches where applicable

## Rule
Agents cannot create persistent memory merely because information appeared in a prompt.
