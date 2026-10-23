---
title: "[P2][INFRA] CI has quality gates but no CD, no security scanning, no dependency auditing; compose lacks storage emulator"
labels: enhancement, medium, infra, ci-cd
---

## Problem
`backend-ci.yml` (lint/mypy/pytest with pgvector service) and `mobile-ci.yml` exist, but:
1. **No CD pipeline** — nothing deploys staging/production (Document_9, 11_INFRA_CICD, 14_RELEASE_RUNBOOK require promote-gate flow with migrations-before-code ordering).
2. **No secret scanning** (gitleaks/trufflehog) or **dependency audit** (`pip-audit`, `npm audit`/dependabot, `flutter pub outdated` policy).
3. **No IaC validation** — `infra/` never plan-validated in CI.
4. **docker-compose has Postgres+Redis but no S3-compatible emulator (MinIO)** — local dev always hits the mock storage path, so presign/HEAD/delete logic is never exercised locally (integration reality gap).
5. No container image build/scanning step (Trivy) despite backend Dockerfile existing.

## Acceptance criteria
- [ ] `cd-staging.yml` / `cd-production.yml` with environment protection rules, manual approval for prod, migration job gating deploy (per 14_RELEASE_RUNBOOK).
- [ ] Add gitleaks + pip-audit + Trivy jobs; dependabot config for pip/github-actions.
- [ ] MinIO service in compose with bucket bootstrap script; `.env.example` documents `R2_ENDPOINT_URL=http://localhost:9000` local profile.
- [ ] Workflow-dispatch rollback path + version tagging convention `vMAJOR.MINOR.PATCH`.
