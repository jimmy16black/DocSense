# Document Lifecycle

## States

```text
CREATED
→ UPLOADING
→ UPLOADED
→ PROCESSING
→ COMPLETED
```

Failure paths:
`PROCESSING → RETRYING → PROCESSING`
or
`PROCESSING → FAILED`

Deletion:
`COMPLETED → DELETING → DELETED`

## Operations
Define behavior for:
- duplicate uploads
- reprocessing
- replacement
- versioning
- corrupted documents
- unsupported types
- failed OCR
- failed extraction
- deletion

## Versioning
The system should support identifying related versions of a document where reliable identity signals exist, without assuming two similarly named files are the same document.
