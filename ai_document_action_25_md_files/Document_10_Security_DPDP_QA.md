# Document 10: Security, DPDP & QA Strategy

> Parent Blueprint: AI Document → Action: Complete Product & Technical Blueprint  
> Audience: AI Coding Agents, Security Engineers, Compliance Team, QA Engineers

## 10.1 Data Protection Architecture

Map applicable privacy obligations to concrete controls.

| Concern | Engineering control |
|---|---|
| Consent | Versioned consent record |
| Purpose | Processing limited to declared product purposes |
| Deletion | End-to-end deletion workflow |
| Minimization | Minimum necessary AI context |
| Access | JWT + ownership + RLS |
| Auditability | Security/action audit events |
| Privacy contact | Product privacy/support channel |
| Residency | Verify provider processing locations before launch |

Legal claims must be validated against current law, rules and legal advice before production.

## 10.2 Right to Erasure

Deletion must cover:

```text
User
 ↓
Documents
 ↓
Pages/OCR
 ↓
Extraction
 ↓
Chunks
 ↓
Embeddings
 ↓
Chat
 ↓
Actions
 ↓
Caches / queued jobs / derived artifacts
```

Recommended state machine:

```text
REQUESTED
 ↓
DELETION_PENDING
 ↓
SOURCE_DELETED
 ↓
DERIVED_DATA_DELETED
 ↓
AUTH_REVOKED
 ↓
VERIFIED
```

If a subsystem fails, do not report complete deletion until the deletion contract is actually satisfied.

## 10.3 Consent

Consent should be:
- explicit where required
- timestamped
- versioned
- purpose-specific
- auditable

Changing consent text/version must preserve historical records.

## 10.4 PII

Potential Indian PII includes PAN, Aadhaar, bank account numbers, IFSC, phone, UPI ID, GSTIN, names, email, addresses and sensitive financial/health information.

Use deterministic patterns plus NLP/NER tooling where appropriate.

### Important

Regex masking is not sufficient evidence of complete PII protection.

Test:
- OCR errors
- punctuation/spaces
- multilingual content
- image-only documents
- tables
- partial identifiers
- false positives

## 10.5 AI Data Minimization

```text
Source
 ↓
Purpose check
 ↓
PII policy
 ↓
Minimum required context
 ↓
AI gateway
```

The system must explicitly define when original unmasked content is necessary. Do not assume full masking is always compatible with extraction accuracy.

## 10.6 Encryption

Use encryption at rest and TLS in transit provided by the selected infrastructure providers.

Required:
- TLS client/API
- TLS database
- TLS storage
- TLS AI gateway
- encrypted backups
- restricted credentials

## 10.7 API Security

Every protected endpoint enforces:

1. authentication
2. authorization
3. input validation
4. rate limiting
5. safe errors
6. audit logging where sensitive

Never rely on Flutter-side authorization.

## 10.8 Rate Limiting & Abuse

Initial product defaults:

| Tier | API | Uploads | Q&A |
|---|---:|---:|---:|
| Free | 30/min | 5/month | 10/month |
| Pro | 60/min | 50/month | Configurable |
| Power | 120/min | 200/month | Configurable |

Protect against:
- automated uploads
- oversized files
- expensive repeated questions
- account enumeration
- credential abuse
- AI cost attacks
- queue flooding

## 10.9 AI Threat Model

Test for:
- prompt injection in documents
- malicious PDF instructions
- cross-user retrieval
- cross-document leakage
- fabricated citations
- tool misuse
- secret leakage
- context denial-of-service
- unsafe action recommendations

Document content is untrusted data, never executable instructions.

## 10.10 QA Matrix

| Test | Tool | Starting target |
|---|---|---:|
| Schema validation | pytest/Pydantic | 95% |
| Critical PII masking | pytest | 100% |
| Query routing | pytest | 90% |
| RAG integration | pytest/asyncpg | 85% |
| Ingestion | fixtures | 80% |
| Mobile E2E | Maestro | Core flows |
| Load | k6 | Defined SLA |
| Container security | Trivy | No unresolved critical issues |
| Dependencies | Dependabot/scanner | No known critical issues |

Critical security and authorization paths should exceed ordinary coverage requirements.

## 10.11 AI QA

Test:
- extraction correctness
- null-field behavior
- citation accuracy
- retrieval relevance
- groundedness
- unsupported questions
- prompt-injection resistance
- PII leakage
- provider fallback
- prompt/model/schema regression

A fluent answer is not a passing answer.

## 10.12 Performance Targets

| Endpoint | P50 | P95 | P99 |
|---|---:|---:|---:|
| upload-init | <200ms | <500ms | <1s |
| document read | <300ms | <800ms | <1.5s |
| Q&A fast path | <700ms | <1.5s | <2s |
| Q&A RAG | <2s | <4s | <6s |
| comparison | <5s | <10s | <15s |
| SSE TTFB | <100ms | <200ms | <500ms |

Validate these under realistic workload; they are targets, not guarantees.

## 10.13 Incident Severity

| Severity | Example |
|---|---|
| SEV-1 | Data breach, public storage exposure, major outage |
| SEV-2 | Major feature failure affecting significant users |
| SEV-3 | Limited feature degradation |
| SEV-4 | Cosmetic/non-impacting issue |

SEV-1/SEV-2 incidents require timeline, impact, root cause, containment, remediation and regression coverage.

## 10.14 Disaster Recovery

RTO/RPO must be agreed and tested.

Validate recovery for:
- PostgreSQL
- R2 documents
- vectors
- authentication
- queues
- application deployment
- provider/region outage

A backup is not a recovery strategy until a restore has been successfully tested.

## 10.15 Security Release Gate

Block production when:
- critical authorization tests fail
- cross-user retrieval is possible
- secrets are exposed
- critical vulnerabilities remain without approved exception
- deletion verification fails
- mandatory AI safety thresholds fail
- required migrations are unvalidated

## 10.16 Security Evidence

Retain evidence for:
- CI results
- security scans
- RLS tests
- deletion tests
- AI evaluation
- load tests
- restore exercises
- migration tests
- release approvals
