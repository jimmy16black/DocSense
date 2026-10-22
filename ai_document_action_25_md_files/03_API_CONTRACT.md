# API Contract

## Authentication
Protected APIs require a short-lived user JWT.

## Core APIs

### Upload
`POST /api/v1/documents/upload-init`

### Process
`POST /api/v1/documents/{id}/process`

### Events
`GET /api/v1/documents/{id}/events`

### Document
`GET /api/v1/documents/{id}`

### Q&A
`POST /api/v1/documents/{id}/ask`

### Compare
`POST /api/v1/documents/compare`

### Reminder
`POST /api/v1/actions/reminders`

### Delete Account
`DELETE /api/v1/users/me`

## API Rules
- Validate all inputs.
- Enforce ownership.
- Use stable error codes.
- Never expose stack traces.
- Processing requests must be idempotent.
- Apply authentication and rate limits.
- Keep provider credentials server-side.
- Maintain backward compatibility for versioned contracts.
