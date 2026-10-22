# Test Strategy

## Layers
- Unit
- Integration
- API
- E2E
- Security
- AI evaluation
- Performance

## Critical E2E

```text
Login
→ Upload
→ Process
→ Extract
→ Open citation
→ Ask question
→ Verify answer
→ Create reminder
```

## Security Tests
- cross-user access
- RLS bypass attempts
- expired JWT
- malformed uploads
- prompt injection
- secret exposure
- deletion completeness
- rate limits

## Release Gate
All required unit/integration/API/E2E/security/AI evaluation checks must pass before release.
