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
