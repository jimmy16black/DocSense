# Data Model & Contracts

## Core Entities
User, Document, DocumentPage, DocumentChunk, Extraction, Citation, ChatSession, ChatMessage, Action, Reminder, ProcessingJob, AIRequest, AIUsage, AuditEvent.

## Document Status
`UPLOADED → VALIDATING → OCR_RUNNING → EXTRACTING → VALIDATING_EXTRACTION → CHUNKING → EMBEDDING → COMPLETED`

Retryable failures enter `RETRYING`; permanent failures enter `FAILED`.

## Canonical Extraction Envelope

```json
{
  "documentType": "INSURANCE_POLICY",
  "confidenceScore": 0.94,
  "title": "...",
  "summaryBullets": [],
  "importantAlerts": [],
  "suggestedQuestions": [],
  "recommendedActions": [],
  "payload": {},
  "citations": []
}
```

## Citation

```json
{
  "pageNumber": 7,
  "sectionHeading": "Section 4.2",
  "exactQuote": "..."
}
```

## Rules
- Missing values are `null`.
- Critical facts require citations.
- User ownership is mandatory.
- Database RLS is required.
- Derived artifacts must retain document/user lineage.
