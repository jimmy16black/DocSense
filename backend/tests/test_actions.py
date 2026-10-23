from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_action_and_reminder_lifecycle(client: AsyncClient):
    # 1. Create a document first
    upload_res = await client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "gst_invoice_inv101.pdf",
            "fileSizeBytes": 50000,
            "mimeType": "application/pdf",
            "documentType": "GST_INVOICE",
        },
    )
    doc_id = upload_res.json()["data"]["documentId"]

    # 2. Create a reminder action
    due = (datetime.now(UTC) + timedelta(days=15)).isoformat()
    rem_res = await client.post(
        "/api/v1/actions/reminders",
        json={
            "documentId": doc_id,
            "title": "Pay GST Invoice 101",
            "description": "Tax payment due for vendor",
            "dueDate": due,
            "actionType": "PAYMENT_REMINDER",
            "payload": {"invoiceAmount": 12500},
        },
    )
    assert rem_res.status_code == 200
    action_data = rem_res.json()["data"]
    action_id = action_data["id"]
    assert action_data["title"] == "Pay GST Invoice 101"
    assert action_data["status"] == "PENDING"

    # 3. List actions
    list_res = await client.get("/api/v1/actions")
    assert list_res.status_code == 200
    res_data = list_res.json()["data"]
    actions = res_data["items"] if isinstance(res_data, dict) and "items" in res_data else res_data
    assert len(actions) >= 1
    assert any(a["id"] == action_id for a in actions)

    # 4. Update action status to CONFIRMED
    update_res = await client.patch(
        f"/api/v1/actions/{action_id}",
        json={"status": "CONFIRMED", "notes": "Approved by user"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["status"] == "CONFIRMED"

    # 5. Test pagination, filtering, and search
    paged_res = await client.get("/api/v1/actions?page=1&pageSize=1&status=CONFIRMED")
    assert paged_res.status_code == 200
    pdata = paged_res.json()["data"]
    assert "items" in pdata
    assert "pagination" in pdata
    assert pdata["pagination"]["page"] == 1
    assert pdata["pagination"]["pageSize"] == 1
    assert len(pdata["items"]) == 1
    assert pdata["items"][0]["status"] == "CONFIRMED"

    # Search filter
    search_res = await client.get("/api/v1/actions?search=GST+Invoice")
    assert search_res.status_code == 200
    assert len(search_res.json()["data"]["items"]) >= 1


@pytest.mark.asyncio
async def test_dpdp_user_deletion(client: AsyncClient):
    # Call DELETE /api/v1/users/me
    del_res = await client.delete("/api/v1/users/me")
    assert del_res.status_code == 200
    body = del_res.json()
    assert body["success"] is True
    assert body["data"]["deleted"] is True
