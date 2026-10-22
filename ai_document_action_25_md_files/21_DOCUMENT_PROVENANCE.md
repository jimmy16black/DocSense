# Document Provenance

## Evidence Chain

```text
Original file
 ↓
SHA-256
 ↓
Page
 ↓
OCR/text
 ↓
Extraction
 ↓
Chunk
 ↓
Embedding
 ↓
Citation
 ↓
Answer
```

## Requirements
Every derived artifact must retain:
- document ID
- user ID
- source/version reference
- creation timestamp

## Citation
A citation must identify the source page and preferably section and exact quote.

## Benefits
Provenance enables:
- auditability
- debugging
- deletion
- reprocessing
- model comparison
- evidence verification
