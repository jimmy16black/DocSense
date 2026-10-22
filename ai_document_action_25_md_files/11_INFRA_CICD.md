# Infrastructure & CI/CD

## Target
- GitHub Actions
- Docker
- Railway
- Supabase
- Cloudflare R2
- Upstash
- Portkey

## CI
Backend: install → lint → type-check → tests → coverage → build.

Mobile: dependency install → analyze → tests → build validation.

## Database
All migrations are version controlled and tested before deployment.

## Secrets
Never commit provider keys, database passwords, service-role keys, JWT secrets or storage credentials.

## Environments
Development, staging and production must be independently configured.

## Deployment
Build → migrate safely → deploy → health check → smoke test → monitor → rollback/forward-fix if required.
