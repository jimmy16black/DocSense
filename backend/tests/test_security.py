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
