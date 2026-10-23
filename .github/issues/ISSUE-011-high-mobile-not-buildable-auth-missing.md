---
title: "[P1][MOBILE] Flutter app cannot build for iOS/Android (no runner scaffold); no login flow — silent `test-token-demo-user` fallback"
labels: bug, high, mobile
---

## Problem
1. `mobile/` contains only `lib/` + `pubspec.yaml` — **no `android/` or `ios/` runner projects**. The app cannot be compiled, signed, or shipped; mobile CI can only analyze.
2. `api_client.dart`: `storage.read(key:'jwt_token') ?? 'test-token-demo-user'` — there is no Supabase Auth integration, no login/signup screen, no session refresh, no logout, and the user is never shown a logged-out state. When ISSUE-006 removes the backend backdoor, the app breaks silently instead of prompting login.
3. `flutter_secure_storage` used with default options: on Android without `encryptedSharedPreferences: true` values land in plain SharedPreferences; iOS accessibility class unspecified (background-read exposure).

## Acceptance criteria
- [ ] `flutter create . --platforms=android,ios` to generate runners; pin minSdk 23+, iOS 13+; add to mobile CI (`flutter build apk --debug` smoke).
- [ ] Integrate `supabase_flutter`: email OTP + Google sign-in; store session via secure storage with explicit options; refresh-ahead interceptor on Dio (retry once on 401 after refresh).
- [ ] Route guard: unauthenticated → LoginScreen; remove hardcoded demo token entirely; account deletion (DPDP) wired to `DELETE /users/me` with confirm-typing UX.
- [ ] Logout clears tokens + Riverpod caches.
