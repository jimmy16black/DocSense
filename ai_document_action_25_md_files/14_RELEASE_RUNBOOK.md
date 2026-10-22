# Release Runbook

## Pre-Release
- Git status
- changed-file review
- unit tests
- integration tests
- security checks
- AI evaluation
- migration validation
- container build
- mobile validation

## AI Release Validation
Verify:
- prompt version
- model version
- schema version
- embedding version
- retrieval configuration
- feature flags
- evaluation dataset version

## Staging Smoke Test
Upload → Process → Summary → Citation → Q&A → Reminder.

## Human Approval
Required for destructive data migrations, security-policy changes, retention changes and material AI provider/model changes.

## Post-Release
Monitor errors, latency, queue health, AI spend, storage and processing success.

## Rollback
Application rollback and database recovery must be treated separately. Never blindly roll back a production database migration.
