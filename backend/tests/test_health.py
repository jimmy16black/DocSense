import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient):
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_readyz(client: AsyncClient):
    response = await client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["redis"] == "connected"
