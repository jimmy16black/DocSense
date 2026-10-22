# Error, Retry & Idempotency

## Error Classes
- SUCCESS
- RETRYABLE_FAILURE
- PERMANENT_FAILURE
- USER_ACTION_REQUIRED
- SYSTEM_FAILURE

## Retry
Retry only transient failures using bounded exponential backoff.

LLM failure:
Primary retry → fallback model/provider → queued retry where appropriate → failed state.

## Idempotency
Required for:
- processing
- reminders
- deletion
- notifications

Duplicate requests must not create duplicate jobs or actions.

## User Errors
Return actionable messages without stack traces, credentials, SQL or infrastructure details.

## Dead-Letter Handling
Exhausted jobs must become inspectable failed jobs with correlation IDs and safe retry capability.
