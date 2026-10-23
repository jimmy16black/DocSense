import hashlib

import pymupdf
import pytest
from httpx import AsyncClient

from app.services.storage import storage_service


def _make_pdf(text: str) -> bytes:
    """Build a real one-page PDF with extractable text (test fixture bytes)."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


_VALID_PDF = _make_pdf(
    "Star Health Insurance Policy Schedule. Sum Insured: Rs. 10,00,000 for Jane Doe. "
    "Section 4.1: Pre-existing diseases covered after 24 consecutive months."
)


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
            "fileSizeBytes": len(_VALID_PDF),
            "mimeType": "application/pdf",
            "documentType": "INSURANCE_POLICY",
        },
    )
    assert upload_res.status_code == 200
    data = upload_res.json()["data"]
    doc_id = data["documentId"]
    storage_path = data["storagePath"]

    # 1b. ISSUE-002: processing must be refused before server-side verification
    early_process = await client.post(f"/api/v1/documents/{doc_id}/process", json={})
    assert early_process.status_code == 422
    assert "upload-complete" in early_process.json()["error"]["message"]

    # 1c. Simulate the presigned PUT landing real bytes, then verify upload
    storage_service.store_mock_object(storage_path, _VALID_PDF)
    complete_res = await client.post(
        f"/api/v1/documents/{doc_id}/upload-complete",
        json={"checksumSha256": hashlib.sha256(_VALID_PDF).hexdigest()},
    )
    assert complete_res.status_code == 200
    cdata = complete_res.json()["data"]
    assert cdata["status"] == "UPLOADED"
    assert cdata["verifiedSizeBytes"] == len(_VALID_PDF)

    # 1d. Replaying upload-complete is idempotent
    replay = await client.post(f"/api/v1/documents/{doc_id}/upload-complete", json={})
    assert replay.status_code == 200
    assert replay.json()["data"]["message"] == "Upload already verified."

    # 2. Process document -> async job accepted (ISSUE-003)
    process_res = await client.post(
        f"/api/v1/documents/{doc_id}/process",
        json={"forceReprocess": False},
    )
    assert process_res.status_code == 202
    proc_body = process_res.json()
    assert proc_body["data"]["status"] == "ACCEPTED"

    # 2b. Wait for the real background pipeline to finish, then poll status
    from app.services.pipeline import pipeline_worker

    await pipeline_worker.drain(timeout=15.0)

    status_res = await client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_res.status_code == 200
    sdata = status_res.json()["data"]
    assert sdata["status"] == "COMPLETED"
    assert sdata["progressPercentage"] == 100
    assert [e["stage"] for e in sdata["events"]] == [
        "QUEUED",
        "EXTRACTING",
        "CHUNKING",
        "EMBEDDING",
        "COMPLETED",
    ]

    # 2c. Re-processing a COMPLETED doc is idempotent (no new job)
    replay_process = await client.post(
        f"/api/v1/documents/{doc_id}/process", json={"forceReprocess": False}
    )
    assert replay_process.json()["data"]["message"] == "Document is already processed."

    # 3. Retrieve document details — extraction must reflect REAL page text
    get_res = await client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    doc_data = get_res.json()["data"]
    assert doc_data["id"] == doc_id
    assert doc_data["status"] == "COMPLETED"
    assert doc_data["pageCount"] == 1  # real PDF has exactly one page
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


@pytest.mark.asyncio
async def test_upload_complete_missing_object_fails(client: AsyncClient):
    """Object never uploaded -> deterministic FAILED transition (ISSUE-002)."""
    up = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "never_uploaded.pdf",
            "fileSizeBytes": 1234,
            "mimeType": "application/pdf",
        },
    )
    data = up.json()["data"]
    res = await client.post(f"/api/v1/documents/{data['documentId']}/upload-complete", json={})
    assert res.status_code == 422
    body = res.json()
    assert body["success"] is False
    assert "No object found" in body["error"]["message"]

    # Document must now be durably FAILED
    get_res = await client.get(f"/api/v1/documents/{data['documentId']}")
    assert get_res.json()["data"]["status"] == "FAILED"


@pytest.mark.asyncio
async def test_upload_complete_size_mismatch_rejected(client: AsyncClient):
    """Declared size != stored size -> quota bypass blocked (ISSUE-002)."""
    up = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "liar.pdf",
            "fileSizeBytes": 999,  # declare small...
            "mimeType": "application/pdf",
        },
    )
    data = up.json()["data"]
    storage_service.store_mock_object(data["storagePath"], _VALID_PDF)  # ...store big
    res = await client.post(f"/api/v1/documents/{data['documentId']}/upload-complete", json={})
    assert res.status_code == 422
    assert "size does not match" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_complete_mime_spoof_rejected(client: AsyncClient):
    """Declare application/pdf, store HTML/JS bytes -> magic sniff blocks it."""
    up = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "evil.pdf",
            "fileSizeBytes": 38,
            "mimeType": "application/pdf",
        },
    )
    data = up.json()["data"]
    payload = b"<html><script>alert(1)</script></html>"
    assert len(payload) == 38
    storage_service.store_mock_object(data["storagePath"], payload)
    res = await client.post(f"/api/v1/documents/{data['documentId']}/upload-complete", json={})
    assert res.status_code == 422
    assert "not a recognized" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upload_complete_checksum_mismatch_rejected(client: AsyncClient):
    up = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "policy.pdf",
            "fileSizeBytes": len(_VALID_PDF),
            "mimeType": "application/pdf",
        },
    )
    data = up.json()["data"]
    storage_service.store_mock_object(data["storagePath"], _VALID_PDF)
    res = await client.post(
        f"/api/v1/documents/{data['documentId']}/upload-complete",
        json={"checksumSha256": "0" * 64},
    )
    assert res.status_code == 422
    assert "checksum mismatch" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_upload_init_sanitizes_path_traversal(client: AsyncClient):
    """file_name can no longer escape the per-user storage prefix (ISSUE-002)."""
    up = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "../../../../etc/passwd.pdf",
            "fileSizeBytes": 10,
            "mimeType": "application/pdf",
        },
    )
    assert up.status_code == 200
    path = up.json()["data"]["storagePath"]
    assert ".." not in path
    assert path.startswith("users/user-test-1234/documents/")
    assert path.endswith("_etc_passwd.pdf") or path.endswith("passwd.pdf")
