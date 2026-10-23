---
title: "[P0][SECURITY] Hardcoded `test-token-*` authentication backdoor active in every non-production environment"
labels: security, critical, backend
---

## Problem
`core/security.py::get_current_user`:

```python
if not settings.is_production and token.startswith("test-token-"):
    mock_user_id = token.replace("test-token-", "")
    ...
```

Any bearer token of form `test-token-<attacker-chosen-id>` authenticates as that user wherever `APP_ENV != "production"` — including staging or a production deploy with a mis-set env var (default is `"development"`!). Combined with mobile's silent fallback `'test-token-demo-user'`, this is a standing impersonation vector.

## Acceptance criteria
- [ ] Remove runtime branching from `get_current_user`; tests use FastAPI `app.dependency_overrides[get_current_user]` in `conftest.py`.
- [ ] If a dev-mode escape hatch is retained, gate it behind explicit `ALLOW_TEST_TOKENS: bool = False` that (a) cannot be enabled when `APP_ENV in {staging, production}`, (b) refuses to start if `SUPABASE_URL` is a real project URL, (c) logs a loud startup warning.
- [ ] Startup guard: fail-fast in `lifespan` if `APP_ENV=production` and any secret still equals its insecure default.
- [ ] Add security regression test asserting `Bearer test-token-x` yields 401 under default config.
