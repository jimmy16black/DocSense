# Document 9: Infrastructure as Code (IaC) & CI/CD Automation

> Parent Blueprint: AI Document → Action: Complete Product & Technical Blueprint  
> Audience: AI Coding Agents, DevOps Engineers, Platform Team

## 9.1 Monorepo

```text
doc-action/
├── backend/
├── mobile/
├── infra/
│   ├── supabase/migrations/
│   ├── cloudflare/
│   └── railway/
├── .github/workflows/
├── docker-compose.yml
├── Makefile
└── README.md
```

## 9.2 Environment Separation

Required:

```text
development
staging
production
```

Each must have separate database/project, storage bucket, queues, secrets and feature configuration.

Never use production data as uncontrolled development fixtures.

## 9.3 Environment Variables

```bash
APP_ENV=
APP_PORT=
SECRET_KEY=

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_DB_URL=

CLOUDFLARE_ACCOUNT_ID=
R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_BUCKET_NAME=

PORTKEY_API_KEY=
PORTKEY_VIRTUAL_KEY=
GEMINI_API_KEY=
OPENAI_API_KEY=

UPSTASH_REDIS_URL=
UPSTASH_REDIS_TOKEN=
UPSTASH_KAFKA_URL=
UPSTASH_KAFKA_TOKEN=

FIREBASE_SERVICE_ACCOUNT_JSON=

REVENUECAT_APP_ID=
REVENUECAT_API_KEY=
```

Secrets must never be committed.

## 9.4 Backend CI

```text
Checkout
→ dependency install
→ formatting/lint
→ mypy
→ unit tests
→ integration tests
→ coverage
→ security scan
→ build
```

## 9.5 Mobile CI

```text
Checkout
→ Flutter setup
→ pub get
→ format check
→ analyze
→ unit/widget tests
→ build validation
```

## 9.6 Deployment

```text
PR
 ↓
CI
 ↓
Human merge
 ↓
Immutable build
 ↓
Staging deploy
 ↓
Migration validation
 ↓
Smoke tests
 ↓
AI evaluation
 ↓
Production approval
 ↓
Production deploy
 ↓
Health checks
 ↓
Monitoring
```

Production deployment must not bypass required checks.

## 9.7 Docker

Use multi-stage builds with:
- minimal runtime image
- pinned lockfile
- no development secrets
- no unnecessary build tools
- health check
- non-root execution where compatible

## 9.8 Database Migration

Example order:

```text
users
 ↓
documents
 ↓
chunks
 ↓
actions
 ↓
chat
 ↓
RLS
 ↓
indexes
```

Rules:
- version-control every migration
- test forward migration
- define rollback/forward-fix strategy
- never implicitly destroy production data
- validate RLS after relevant migrations

## 9.9 Secrets

| Secret | Storage | Flutter exposed? |
|---|---|---|
| Supabase service role | CI/prod secret store | No |
| R2 credentials | CI/prod secret store | No |
| Portkey key | CI/prod secret store | No |
| Gemini/OpenAI keys | CI/prod secret store | No |
| Firebase service account | CI/prod secret store | No |
| RevenueCat server key | CI/prod secret store | No |
| Supabase anon key | Mobile config | Public by design |

Each secret needs a rotation/replacement procedure. A provider-specific "never rotate" setting must not mean "cannot replace after compromise."

## 9.10 Observability

Recommended stack:
- Sentry
- PostHog
- UptimeRobot
- Railway/Supabase metrics
- Portkey usage/cost
- structlog

Health status should distinguish `healthy`, `degraded` and `unhealthy`.

## 9.11 Initial Alerts

| Metric | Initial threshold |
|---|---|
| API 5xx | >5% / 5 min |
| Q&A P95 | >8 sec |
| Capacity | >80% |
| AI daily spend | Configurable budget |
| Uptime | 3 consecutive failures |

Tune thresholds after collecting production baselines.

## 9.12 Infrastructure Governance

Every infrastructure change must consider:
- cost
- security
- data residency
- backup
- rollback
- observability
- least privilege

Agents must not change production infrastructure merely to make a local test pass.
