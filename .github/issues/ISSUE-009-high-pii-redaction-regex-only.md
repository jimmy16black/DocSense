---
title: "[P1][COMPLIANCE] PII redaction before LLM is regex-only; spec mandates Presidio; redaction can corrupt citation quotes"
labels: security, high, compliance, ai
---

## Problem
`ai_gateway.redact_pii()` covers 5 Indian-format patterns (email, phone, Aadhaar, PAN, GSTIN). Names, addresses, bank/account numbers, DOB, vehicle registration all transit to Gemini/OpenAI **unredacted**, violating 09_SECURITY_DPDP ("PII masking with Presidio") and the repo's own Privacy-by-default principle.

Secondary defect: redaction happens on the prompt text that includes evidence spans; replaced tokens (`[PHONE_REDACTED]`) break verbatim citation verification downstream — order-of-operations needs an explicit design (redact at rest? at send? map back for display?).

## Acceptance criteria
- [ ] Integrate Microsoft Presidio analyzer+masker (or equivalent NER) as the primary path; keep regex as fast pre-filter only.
- [ ] Define & document redaction pipeline position in 06_AI_PROMPTS_GUARDRAILS terms: citations verified against **pre-redaction** source text stored in DB; provider sees masked context with reversible token map held server-side.
- [ ] Unit tests: known-name/address fixtures fully masked; verbatim quote check still passes post-mask roundtrip.
- [ ] Add telemetry counter of PII entities masked per request (privacy audit evidence).
