import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_init_success(client: AsyncClient):
    payload = {
        "fileName": "health_insurance_policy.pdf",
        "fileSizeBytes": 1024 * 500,  # 500 KB
        "mimeType": "application/pdf",
        "documentType": "INSURANCE_POLICY",
    }
    response = await client.post("/api/v1/documents/upload-init", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "documentId" in data
    assert "uploadUrl" in data
    assert "storagePath" in data
    assert "expiresAt" in data


@pytest.mark.asyncio
async def test_upload_init_oversized_file(client: AsyncClient):
    payload = {
        "fileName": "huge_file.pdf",
        "fileSizeBytes": 50 * 1024 * 1024,  # 50 MB (exceeds 25 MB)
        "mimeType": "application/pdf",
    }
    response = await client.post("/api/v1/documents/upload-init", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_upload_init_invalid_mime_type(client: AsyncClient):
    payload = {
        "fileName": "virus.exe",
        "fileSizeBytes": 1024,
        "mimeType": "application/x-msdownload",
    }
    response = await client.post("/api/v1/documents/upload-init", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_document_full_lifecycle(client: AsyncClient):
    # 1. Initialize upload
    upload_res = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "star_health_policy.pdf",
            "fileSizeBytes": 1024 * 200,
            "mimeType": "application/pdf",
            "documentType": "INSURANCE_POLICY",
        },
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["data"]["documentId"]

    # 2. Process document
    process_res = await client.post(
        f"/api/v1/documents/{doc_id}/process",
        json={"forceReprocess": False},
    )
    assert process_res.status_code == 200
    proc_body = process_res.json()
    assert proc_body["data"]["status"] == "COMPLETED"

    # 3. Retrieve document details
    get_res = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    doc_data = get_res.json()["data"]
    assert doc_data["id"] == doc_id
    assert doc_data["status"] == "COMPLETED"
    assert doc_data["latestExtraction"] is not None
    assert len(doc_data["citations"]) > 0

    # 4. Ask grounded question
    ask_res = await client.post(
        f"/api/v1/documents/{doc_id}/ask",
        json={"question": "What is the waiting period for pre-existing diseases?"},
    )
    assert ask_res.status_code == 200
    ask_data = ask_res.json()["data"]
    assert ask_data["answer"] != ""
    assert ask_data["confidence"] in ["HIGH", "MEDIUM", "LOW", "UNSUPPORTED"]
    assert len(ask_data["citations"]) > 0

    # 5. Delete document
    del_res = await client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True
