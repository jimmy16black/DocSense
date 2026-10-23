import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_missing_auth_header():
    # Calling endpoint without test dependency override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/documents")
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_invalid_bearer_format():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/documents",
            headers={"Authorization": "Basic invalid-credentials"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_test_token_rejected_when_not_opted_in(monkeypatch):
    """ISSUE-006 regression guard: the mock-token backdoor must stay closed
    unless ALLOW_TEST_TOKENS is explicitly enabled (CI sets it in conftest)."""
    from app.core import security
    from app.core.config import get_settings
    from app.core.errors import AuthenticationError

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_TEST_TOKENS", False, raising=False)

    with pytest.raises(AuthenticationError):
        await security.get_current_user(authorization="Bearer test-token-victim-uuid")


@pytest.mark.asyncio
async def test_test_token_accepted_when_opted_in(monkeypatch):
    from app.core import security
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_TEST_TOKENS", True, raising=False)

    user = await security.get_current_user(authorization="Bearer test-token-user-abc")
    assert user.id == "user-abc"


@pytest.mark.asyncio
async def test_jwt_none_algorithm_rejected(monkeypatch):
    """ISSUE-010: Reject forged 'none' algorithm tokens."""
    import jwt

    from app.core import security
    from app.core.config import get_settings
    from app.core.errors import AuthenticationError

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_TEST_TOKENS", False, raising=False)

    token = jwt.encode({"sub": "victim-user", "aud": "authenticated"}, key="", algorithm="none")
    with pytest.raises(AuthenticationError, match="Algorithm 'none' is disallowed"):
        await security.get_current_user(authorization=f"Bearer {token}")


@pytest.mark.asyncio
async def test_jwt_invalid_audience_rejected(monkeypatch):
    """ISSUE-010: Reject tokens with invalid audience claim."""
    import jwt

    from app.core import security
    from app.core.config import get_settings
    from app.core.errors import AuthenticationError

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_TEST_TOKENS", False, raising=False)

    token = jwt.encode(
        {"sub": "user-123", "aud": "untrusted-app"},
        key=settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError, match="Invalid audience"):
        await security.get_current_user(authorization=f"Bearer {token}")


@pytest.mark.asyncio
async def test_jwt_unauthorized_role_rejected(monkeypatch):
    """ISSUE-010: Reject tokens with unauthorized role claim."""
    import jwt

    from app.core import security
    from app.core.config import get_settings
    from app.core.errors import AuthenticationError

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_TEST_TOKENS", False, raising=False)

    token = jwt.encode(
        {"sub": "user-123", "aud": "authenticated", "role": "anonymous"},
        key=settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError, match="Unauthorized role"):
        await security.get_current_user(authorization=f"Bearer {token}")


@pytest.mark.asyncio
async def test_jwt_valid_hs256_accepted(monkeypatch):
    """ISSUE-010: Accept valid HS256 signed token."""
    import jwt

    from app.core import security
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_TEST_TOKENS", False, raising=False)

    token = jwt.encode(
        {
            "sub": "valid-user-999",
            "email": "valid@example.com",
            "aud": "authenticated",
            "role": "authenticated",
        },
        key=settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    user = await security.get_current_user(authorization=f"Bearer {token}")
    assert user.id == "valid-user-999"
    assert user.email == "valid@example.com"
    assert user.role == "authenticated"


@pytest.mark.asyncio
async def test_jwt_expired_token_rejected(monkeypatch):
    """ISSUE-010: Reject expired tokens with standard message."""
    import time

    import jwt

    from app.core import security
    from app.core.config import get_settings
    from app.core.errors import AuthenticationError

    settings = get_settings()
    monkeypatch.setattr(settings, "ALLOW_TEST_TOKENS", False, raising=False)

    token = jwt.encode(
        {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) - 3600},
        key=settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError, match="Authentication token has expired"):
        await security.get_current_user(authorization=f"Bearer {token}")
