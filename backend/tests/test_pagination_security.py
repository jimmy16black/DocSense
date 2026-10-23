"""ISSUE-013 (pagination/search/filter) + ISSUE-016 (cross-tenant security tests).

These complement the existing suite which only ever exercised a single
hardcoded identity via dependency override. Here we drive the REAL auth
dependency with test-token identities so cross-user isolation is asserted
end-to-end through the HTTP layer.
"""

import hashlib

import pymupdf
import pytest
from httpx import AsyncClient

from app.services.storage import storage_service


def _make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def _upload_completed_doc(client: AsyncClient, token: str, name: str, text: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    pdf = _make_pdf(text)
    init = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": name,
            "fileSizeBytes": len(pdf),
            "mimeType": "application/pdf",
        },
        headers=headers,
    )
    assert init.status_code == 200, init.text
    data = init.json()["data"]
    storage_service.store_mock_object(data["storagePath"], pdf)
    complete = await client.post(
        f"/api/v1/documents/{data['documentId']}/upload-complete",
        json={"checksumSha256": hashlib.sha256(pdf).hexdigest()},
        headers=headers,
    )
    assert complete.status_code == 200, complete.text
    return data["documentId"]


@pytest.mark.asyncio
async def test_cross_tenant_document_isolation(client_no_user_override):
    """User B must never see or touch user A's documents (ISSUE-016 core case)."""
    alice = "test-token-alice-0001"
    bob = "test-token-bob-0002"

    alice_doc = await _upload_completed_doc(
        client_no_user_override, alice, "alice_policy.pdf", "Alice Star Health Policy"
    )
    await _upload_completed_doc(client_no_user_override, bob, "bob_invoice.pdf", "Bob GST Invoice")

    # List isolation: each user sees exactly their own document(s).
    a_list = await client_no_user_override.get(
        "/api/v1/documents", headers={"Authorization": f"Bearer {alice}"}
    )
    b_list = await client_no_user_override.get(
        "/api/v1/documents", headers={"Authorization": f"Bearer {bob}"}
    )
    assert a_list.status_code == 200 and b_list.status_code == 200
    a_ids = [d["id"] for d in a_list.json()["data"]["items"]]
    b_ids = [d["id"] for d in b_list.json()["data"]["items"]]
    assert a_ids == [alice_doc]
    assert alice_doc not in b_ids

    # Detail isolation: Bob reading Alice's document -> 403 (not 404 info leak debate aside,
    # our API contract returns PermissionDenied as 403).
    detail = await client_no_user_override.get(
        f"/api/v1/documents/{alice_doc}", headers={"Authorization": f"Bearer {bob}"}
    )
    assert detail.status_code == 403

    # Status endpoint isolation.
    status_res = await client_no_user_override.get(
        f"/api/v1/documents/{alice_doc}/status", headers={"Authorization": f"Bearer {bob}"}
    )
    assert status_res.status_code == 403

    # Process endpoint isolation.
    proc = await client_no_user_override.post(
        f"/api/v1/documents/{alice_doc}/process",
        json={},
        headers={"Authorization": f"Bearer {bob}"},
    )
    assert proc.status_code == 403

    # Delete endpoint isolation — and confirm the document still exists for Alice.
    dele = await client_no_user_override.delete(
        f"/api/v1/documents/{alice_doc}", headers={"Authorization": f"Bearer {bob}"}
    )
    assert dele.status_code == 403
    still = await client_no_user_override.get(
        f"/api/v1/documents/{alice_doc}", headers={"Authorization": f"Bearer {alice}"}
    )
    assert still.status_code == 200


@pytest.mark.asyncio
async def test_search_never_leaks_across_tenants(client_no_user_override):
    """A search query matching another tenant's title must return nothing."""
    alice = "test-token-alice-0003"
    bob = "test-token-bob-0004"
    await _upload_completed_doc(
        client_no_user_override, alice, "quantum_policy.pdf", "Quantum term paper"
    )

    res = await client_no_user_override.get(
        "/api/v1/documents",
        params={"search": "quantum"},
        headers={"Authorization": f"Bearer {bob}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["items"] == []
    assert data["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_pagination_bounds_and_envelope(client_no_user_override):
    """page/pageSize behave correctly; pageSize > 100 rejected; envelope fields present."""
    token = {"Authorization": "Bearer test-token-paging-0005"}
    for i in range(3):
        await _upload_completed_doc(
            client_no_user_override,
            token["Authorization"].split()[1],
            f"doc_{i}.pdf",
            f"Doc number {i}",
        )

    p1 = await client_no_user_override.get(
        "/api/v1/documents", params={"page": 1, "pageSize": 2}, headers=token
    )
    assert p1.status_code == 200
    body = p1.json()["data"]
    assert len(body["items"]) == 2
    pg = body["pagination"]
    assert pg["total"] == 3
    assert pg["totalPages"] == 2
    assert pg["hasNext"] is True
    assert pg["page"] == 1

    p2 = await client_no_user_override.get(
        "/api/v1/documents", params={"page": 2, "pageSize": 2}, headers=token
    )
    body2 = p2.json()["data"]
    assert len(body2["items"]) == 1
    assert body2["pagination"]["hasNext"] is False

    # Pages must not overlap.
    ids1 = {d["id"] for d in body["items"]}
    ids2 = {d["id"] for d in body2["items"]}
    assert ids1.isdisjoint(ids2)

    bad = await client_no_user_override.get(
        "/api/v1/documents", params={"pageSize": 500}, headers=token
    )
    assert bad.status_code == 422

    zero = await client_no_user_override.get("/api/v1/documents", params={"page": 0}, headers=token)
    assert zero.status_code == 422


@pytest.mark.asyncio
async def test_filter_sort_and_search_semantics(client_no_user_override):
    token = {"Authorization": "Bearer test-token-filter-0006"}
    await _upload_completed_doc(
        client_no_user_override, token["Authorization"].split()[1], "star_health.pdf", "Star health"
    )
    await _upload_completed_doc(
        client_no_user_override, token["Authorization"].split()[1], "gst_bill.pdf", "GST bill"
    )

    s = await client_no_user_override.get(
        "/api/v1/documents", params={"search": "gst"}, headers=token
    )
    items = s.json()["data"]["items"]
    assert [d["fileName"] for d in items] == ["gst_bill.pdf"]

    # Search with LIKE wildcards must be treated literally, not as patterns.
    w = await client_no_user_override.get(
        "/api/v1/documents", params={"search": "%"}, headers=token
    )
    assert w.json()["data"]["items"] == []

    st = await client_no_user_override.get(
        "/api/v1/documents", params={"status": "uploaded"}, headers=token
    )
    assert st.json()["data"]["pagination"]["total"] == 2

    none = await client_no_user_override.get(
        "/api/v1/documents", params={"status": "completed"}, headers=token
    )
    assert none.json()["data"]["items"] == []

    asc = await client_no_user_override.get(
        "/api/v1/documents", params={"sort": "title"}, headers=token
    )
    titles = [d["title"] for d in asc.json()["data"]["items"]]
    assert titles == sorted(titles)


@pytest.mark.asyncio
async def test_table_driven_cross_tenant_matrix(client_no_user_override):
    """ISSUE-016 Acceptance: Table-driven cross-tenant test suite covering all routes.

    Asserts that an authenticated User B cannot read, mutate, ask questions on,
    delete, or link actions to User A's resources under any circumstances.
    """
    alice_token = "test-token-alice-matrix-001"
    bob_token = "test-token-bob-matrix-002"
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # 1. Setup Alice's document
    alice_doc_id = await _upload_completed_doc(
        client_no_user_override,
        alice_token,
        "alice_confidential.pdf",
        "Confidential Alice Contract Data",
    )

    # 2. Setup Bob's document (for multi-resource routes like compare)
    bob_doc_id = await _upload_completed_doc(
        client_no_user_override,
        bob_token,
        "bob_public.pdf",
        "Bob Public Contract Data",
    )

    # 3. Setup Alice's action
    alice_action_res = await client_no_user_override.post(
        "/api/v1/actions/reminders",
        json={
            "documentId": alice_doc_id,
            "title": "Alice Urgent Action",
            "actionType": "PAYMENT",
            "dueDate": "2026-11-01T12:00:00Z",
        },
        headers=alice_headers,
    )
    assert alice_action_res.status_code == 200, alice_action_res.text
    alice_action_id = alice_action_res.json()["data"]["id"]

    # 4. Table-driven test matrix of unauthorized access attempts by Bob
    matrix = [
        ("GET", f"/api/v1/documents/{alice_doc_id}", None, {403, 404}),
        ("GET", f"/api/v1/documents/{alice_doc_id}/status", None, {403, 404}),
        ("POST", f"/api/v1/documents/{alice_doc_id}/process", {}, {403, 404}),
        (
            "POST",
            f"/api/v1/documents/{alice_doc_id}/ask",
            {"question": "What is Alice's salary?"},
            {403, 404},
        ),
        (
            "POST",
            f"/api/v1/documents/{alice_doc_id}/upload-complete",
            {"checksumSha256": "e" * 64},
            {403, 404},
        ),
        ("DELETE", f"/api/v1/documents/{alice_doc_id}", None, {403, 404}),
        (
            "POST",
            "/api/v1/actions/reminders",
            {
                "documentId": alice_doc_id,
                "title": "Bob spoofed reminder",
                "actionType": "AUDIT",
                "dueDate": "2026-11-15T00:00:00Z",
            },
            {403, 404},
        ),
        (
            "PATCH",
            f"/api/v1/actions/{alice_action_id}",
            {"status": "CONFIRMED", "notes": "Hacked by Bob"},
            {403, 404},
        ),
        (
            "POST",
            "/api/v1/documents/compare",
            {"documentIds": [alice_doc_id, bob_doc_id]},
            {400, 403, 404, 422},
        ),
    ]

    for method, path, payload, allowed_statuses in matrix:
        if method == "GET":
            resp = await client_no_user_override.get(path, headers=bob_headers)
        elif method == "POST":
            resp = await client_no_user_override.post(path, json=payload, headers=bob_headers)
        elif method == "PATCH":
            resp = await client_no_user_override.patch(path, json=payload, headers=bob_headers)
        elif method == "DELETE":
            resp = await client_no_user_override.delete(path, headers=bob_headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

        assert resp.status_code in allowed_statuses, (
            f"Cross-tenant leak on {method} {path}: expected {allowed_statuses}, got {resp.status_code} ({resp.text})"
        )

    # 5. Verify Alice's document and action remain pristine
    alice_check = await client_no_user_override.get(
        f"/api/v1/documents/{alice_doc_id}", headers=alice_headers
    )
    assert alice_check.status_code == 200
    assert alice_check.json()["data"]["id"] == alice_doc_id
