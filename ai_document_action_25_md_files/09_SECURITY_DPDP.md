# Security & DPDP Controls

## Core Controls
- Explicit consent where required.
- Consent timestamp.
- User-scoped data.
- Database RLS.
- Server-side authorization.
- User deletion workflow.
- Data minimization.
- PII-safe logging.

## File Security
Validate MIME type, extension, size, page count and file structure. Malware scanning should occur before sensitive processing where supported.

## AI Security
Defend against:
- prompt injection
- cross-user retrieval
- malicious document content
- data exfiltration
- unsafe action generation

## Mobile
Flutter receives only short-lived user credentials/tokens. Provider API keys and service-role keys never ship to the client.

## Audit
Security-sensitive actions must produce an audit event.
