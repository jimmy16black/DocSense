# Agent Orchestration

## Master Orchestrator
Coordinates repository analysis, task planning, implementation, validation, review and status updates.

## Agents

### Repository Analyst
Maps the existing repository and identifies gaps.

### Backend Agent
Implements FastAPI, database, ingestion, AI gateway and RAG.

### Mobile Agent
Implements Flutter UI, state and API integration.

### Infrastructure Agent
Owns Docker, CI/CD, migrations and cloud configuration.

### Security Agent
Reviews authentication, authorization, RLS, secrets, PII, uploads and AI security.

### QA Agent
Runs software and AI regression tests.

### Review Agent
Checks architecture, contracts, security, tests and unnecessary changes.

## Execution Loop
Repository Review → Task Graph → Implement → Test → Security Review → Code Review → AI Evaluation → Update Docs → Next Task

## Stop Conditions
Require human approval for destructive migrations, material architecture changes, security weakening, retention-policy changes, or major AI provider/model changes.
