import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_error_handling_not_found(client: AsyncClient):
    import uuid

    random_id = uuid.uuid4()
    response = await client.get(f"/api/v1/documents/{random_id}")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert "error" in body
    error = body["error"]
    assert error["code"] == "RESOURCE_NOT_FOUND"
    assert error["classification"] == "PERMANENT_FAILURE"
    assert error["isRetryable"] is False
    assert "correlationId" in error


@pytest.mark.asyncio
async def test_validation_error_format(client: AsyncClient):
    # Missing required fields
    response = await client.post("/api/v1/documents/upload-init", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["classification"] == "USER_ACTION_REQUIRED"
    assert "correlationId" in body["error"]
