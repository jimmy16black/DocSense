import jwt
from fastapi import Header
from jwt import PyJWKClient
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.logging import get_logger, user_id_ctx

logger = get_logger("security")

_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient | None:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        if settings.SUPABASE_URL and settings.SUPABASE_URL.startswith("http"):
            jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
            _jwks_client = PyJWKClient(
                jwks_url,
                cache_keys=True,
                max_cached_keys=16,
                cache_jwk_set=True,
                lifespan=3600,
            )
    return _jwks_client


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    role: str = "authenticated"
    app_metadata: dict = {}
    user_metadata: dict = {}


async def get_current_user(
    authorization: str | None = Header(None, description="Bearer <JWT>"),
) -> CurrentUser:
    settings = get_settings()

    if not authorization:
        raise AuthenticationError("Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header format. Expected 'Bearer <token>'")

    token = parts[1]

    # Test mock token (ISSUE-006): previously enabled in *every* non-production
    # environment, so any deployed staging/QA instance accepted attacker-chosen
    # identities like "test-token-<victim-uuid>". Now it requires an explicit
    # opt-in (ALLOW_TEST_TOKENS=true), which stays false on real deployments
    # and is only set true by the automated test suite.
    if settings.ALLOW_TEST_TOKENS and token.startswith("test-token-"):
        mock_user_id = token.replace("test-token-", "")
        user = CurrentUser(id=mock_user_id, email=f"{mock_user_id}@example.com")
        user_id_ctx.set(user.id)
        return user

    try:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            logger.warning("Malformed JWT header", error=str(e))
            raise AuthenticationError("Invalid authentication token format") from e

        alg = unverified_header.get("alg")
        if not alg or str(alg).lower() == "none":
            raise AuthenticationError("Algorithm 'none' is disallowed")

        if alg not in ("HS256", "RS256", "ES256"):
            raise AuthenticationError(f"Unsupported algorithm '{alg}'")

        if alg == "HS256":
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        elif alg in ("RS256", "ES256"):
            jwks_client = get_jwks_client()
            if not jwks_client:
                raise AuthenticationError("Asymmetric JWKS validation unavailable")
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
        else:
            raise AuthenticationError(f"Unsupported algorithm '{alg}'")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("JWT token missing subject (sub) claim")

        # ISSUE-010: Enforce audience
        aud = payload.get("aud")
        if aud and aud != "authenticated":
            raise AuthenticationError(f"Invalid audience '{aud}', expected 'authenticated'")

        # ISSUE-010: Enforce role
        role = payload.get("role", "authenticated")
        if role not in ("authenticated", "service_role"):
            raise AuthenticationError(f"Unauthorized role '{role}'")

        user = CurrentUser(
            id=user_id,
            email=payload.get("email"),
            role=role,
            app_metadata=payload.get("app_metadata", {}),
            user_metadata=payload.get("user_metadata", {}),
        )
        user_id_ctx.set(user.id)
        return user
    except AuthenticationError:
        raise
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("JWT validation failed", error=str(e))
        raise AuthenticationError("Invalid authentication token")
