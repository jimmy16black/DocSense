---
title: "[P1][SECURITY] JWT validation hardcodes HS256 shared secret; modern Supabase uses asymmetric keys — plus no iss/aud enforcement"
labels: security, high, backend
---

## Problem
`get_current_user` decodes with `algorithms=["HS256"]`, `verify_aud=False`, no issuer check. New Supabase projects default to asymmetric JWT signing (JWKS); tokens from such projects will be rejected (outage) while the HS256 path invites algorithm-confusion mistakes if any upstream ever issues `alg:none`/RS256 tokens against the same endpoint.

## Acceptance criteria
- [ ] Support both legacy HS256 (SUPABASE_JWT_SECRET) and current RS256/ES256 via `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` with cached key rotation.
- [ ] Enforce `iss == {SUPABASE_URL}/auth/v1`, `aud == authenticated`, `role` claim allowlist; reject tokens missing these.
- [ ] Optional jti/revoke check against Redis denylist on logout/erase.
- [ ] Tests: forged-none-alg rejected, wrong-aud rejected, expired rejected with canonical AUTHENTICATION_FAILED envelope, valid RS256 accepted after JWKS fetch.
