import jwt
from fastapi import Header
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.logging import get_logger, user_id_ctx

logger = get_logger("security")


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

    # In non-production environments, allow a test mock token for automated testing
    if not settings.is_production and token.startswith("test-token-"):
        mock_user_id = token.replace("test-token-", "")
        user = CurrentUser(id=mock_user_id, email=f"{mock_user_id}@example.com")
        user_id_ctx.set(user.id)
        return user

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("JWT token missing subject (sub) claim")

        user = CurrentUser(
            id=user_id,
            email=payload.get("email"),
            role=payload.get("role", "authenticated"),
            app_metadata=payload.get("app_metadata", {}),
            user_metadata=payload.get("user_metadata", {}),
        )
        user_id_ctx.set(user.id)
        return user
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Authentication token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("JWT validation failed", error=str(e))
        raise AuthenticationError("Invalid authentication token")
