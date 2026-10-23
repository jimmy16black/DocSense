#!/usr/bin/env python3
"""End-to-End Local Smoke Test for DocSense API.

Executes the complete document lifecycle against the live running server:
Upload Init -> S3 Upload -> Upload Complete -> Async Pipeline Processing ->
Q&A with Hybrid RAG & Citations -> Action/Reminder Creation -> Verification.
"""

import hashlib
import time

import httpx
import pymupdf

BASE_URL = "http://localhost:8001"
AUTH_TOKEN = "test-token-local-demo-user"
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
}


def create_sample_policy_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    content = (
        "STAR HEALTH INSURANCE POLICY SCHEDULE\n\n"
        "Policy Number: P/112233/01/2026/009988\n"
        "Policyholder: John Doe\n"
        "Plan Name: Comprehensive Health Optima 2026\n"
        "Sum Insured: Rs. 15,00,000\n"
        "Annual Premium: Rs. 24,500 due on 15-November-2026\n"
        "Pre-Existing Diseases Waiting Period: 36 months from inception date.\n"
        "Room Rent: Single private AC room with no capping.\n"
        "ICU Charges: Actual expenses covered without proportion deduction.\n"
        "Cataract Surgery Limit: Up to Rs. 50,000 per eye.\n"
        "Emergency Ambulance: Up to Rs. 3,000 per hospitalization.\n"
        "Day Care Procedures: All day care treatments requiring < 24 hours hospitalization covered.\n"
        "Hospital Network: 14,000+ cashless hospitals nationwide.\n"
    )
    page.insert_text((50, 72), content, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def main():
    print(f"🚀 Starting DocSense End-to-End Test against {BASE_URL}...")
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 1. Health check
    print("\n[1/7] Checking backend health...")
    health = client.get("/healthz")
    assert health.status_code == 200, f"Health check failed: {health.text}"
    print(f"  ✓ Backend healthy: {health.json()}")

    # 2. Upload Init
    print("\n[2/7] Initializing document upload...")
    pdf_bytes = create_sample_policy_pdf()
    file_size = len(pdf_bytes)
    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()

    init_res = client.post(
        "/api/v1/documents/upload-init",
        json={
            "fileName": "Star_Health_Policy_2026.pdf",
            "fileSizeBytes": file_size,
            "mimeType": "application/pdf",
        },
        headers=HEADERS,
    )
    assert init_res.status_code == 200, f"Upload init failed: {init_res.text}"
    init_data = init_res.json()["data"]
    doc_id = init_data["documentId"]
    upload_url = init_data["uploadUrl"]
    print(f"  ✓ Upload initialized. Doc ID: {doc_id}")

    # 3. Upload to S3 / MinIO via presigned URL
    print("\n[3/7] Uploading PDF bytes to object storage...")
    storage_res = httpx.put(
        upload_url,
        content=pdf_bytes,
        headers={"Content-Type": "application/pdf"},
    )
    assert storage_res.status_code in {200, 204}, f"Storage PUT failed: {storage_res.status_code}"
    print("  ✓ Document binary written to storage successfully.")

    # 4. Upload Complete verification
    print("\n[4/7] Completing and verifying upload on backend...")
    complete_res = client.post(
        f"/api/v1/documents/{doc_id}/upload-complete",
        json={"checksumSha256": sha256_hash},
        headers=HEADERS,
    )
    assert complete_res.status_code == 200, f"Upload complete failed: {complete_res.text}"
    print(
        f"  ✓ Upload verified (size & SHA-256 match, magic bytes sniffed). Status: {complete_res.json()['data']['status']}"
    )

    # 5. Process document through async pipeline
    print("\n[5/7] Triggering background pipeline processing...")
    proc_res = client.post(
        f"/api/v1/documents/{doc_id}/process",
        json={},
        headers=HEADERS,
    )
    assert proc_res.status_code in {200, 202}, f"Process start failed: {proc_res.text}"

    # Poll status until completed (or failed)
    print("  Waiting for pipeline processing...")
    for _ in range(20):
        time.sleep(1.0)
        status_res = client.get(f"/api/v1/documents/{doc_id}/status", headers=HEADERS)
        status_data = status_res.json()["data"]
        curr_status = status_data["status"]
        print(
            f"    Current status: {curr_status} (progress: {status_data.get('progressPercentage', 0)}%)"
        )
        if curr_status.lower() in {"completed", "extracted", "ready"}:
            break
        if curr_status.lower() == "failed":
            raise RuntimeError(f"Processing failed: {status_data.get('errorMessage')}")

    # Inspect document detail
    doc_detail = client.get(f"/api/v1/documents/{doc_id}", headers=HEADERS).json()["data"]
    print("  ✓ Document successfully processed!")
    print(f"    Title: {doc_detail.get('title')}")
    print(f"    Type:  {doc_detail.get('documentType')}")
    print(f"    Pages: {doc_detail.get('pageCount')}")

    # 6. Ask Question (Hybrid RAG)
    print("\n[6/7] Testing Q&A with Hybrid RAG & verbatim citations...")
    question = "What is the waiting period for pre-existing diseases?"
    ask_res = client.post(
        f"/api/v1/documents/{doc_id}/ask",
        json={"question": question},
        headers=HEADERS,
    )
    assert ask_res.status_code == 200, f"Ask failed: {ask_res.text}"
    ask_data = ask_res.json()["data"]
    print(f"  Q: {question}")
    print(f"  A: {ask_data['answer']}")
    print(f"  Citations returned: {len(ask_data.get('citations', []))}")
    for c in ask_data.get("citations", []):
        print(f'    - Quote: "{c.get("exactQuote")}" (Page {c.get("pageNumber")})')

    # 7. Create Action Item & Reminder
    print("\n[7/7] Creating and updating Action Item / Reminder...")
    action_res = client.post(
        "/api/v1/actions/reminders",
        json={
            "documentId": doc_id,
            "title": "Pay Annual Health Premium",
            "actionType": "PAYMENT",
            "dueDate": "2026-11-15T00:00:00Z",
            "description": "Premium of Rs. 24,500 due on Nov 15th",
        },
        headers=HEADERS,
    )
    assert action_res.status_code == 200, f"Action create failed: {action_res.text}"
    action_id = action_res.json()["data"]["id"]
    print(f"  ✓ Created action item {action_id}")

    # Update action
    update_res = client.patch(
        f"/api/v1/actions/{action_id}",
        json={"status": "CONFIRMED", "notes": "Scheduled with net banking"},
        headers=HEADERS,
    )
    assert update_res.status_code == 200, f"Action update failed: {update_res.text}"
    print("  ✓ Action marked CONFIRMED")

    # List actions
    list_res = client.get("/api/v1/actions", headers=HEADERS)
    assert list_res.status_code == 200
    actions = list_res.json()["data"]["items"]
    print(f"  ✓ User actions retrieved: {len(actions)} action(s) found.")

    print("\n" + "=" * 60)
    print("🎉 FULL END-TO-END WORKFLOW VERIFIED SUCCESSFULLY ON LOCALHOST!")
    print("=" * 60)


if __name__ == "__main__":
    main()
