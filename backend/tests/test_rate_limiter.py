import pytest
from httpx import AsyncClient

from app.core.errors import QuotaExceededError, RateLimitExceededError
from app.services.rate_limiter import SlidingWindowLimiter, check_user_quota


def test_sliding_window_rate_limiting():
    limiter = SlidingWindowLimiter()
    key = "user-1:test"

    # 3 requests allowed in 60s
    rem1 = limiter.check(key, max_requests=3, window_seconds=60)
    assert rem1 == 2
    rem2 = limiter.check(key, max_requests=3, window_seconds=60)
    assert rem2 == 1
    rem3 = limiter.check(key, max_requests=3, window_seconds=60)
    assert rem3 == 0

    # 4th request must raise RateLimitExceededError with retry_after
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.check(key, max_requests=3, window_seconds=60)

    err = exc_info.value
    assert err.code == "RATE_LIMIT_EXCEEDED"
    assert err.retry_after > 0


@pytest.mark.asyncio
async def test_quota_check_raises_when_limit_reached(db_session):
    import uuid

    from app.models.document import Document, DocumentStatus

    user_id = "user-quota-test-99"

    # Seed 3 documents
    for i in range(3):
        d = Document(
            id=uuid.uuid4(),
            user_id=user_id,
            title=f"Doc {i}",
            file_name=f"doc_{i}.pdf",
            file_size_bytes=100,
            mime_type="application/pdf",
            storage_path=f"path_{i}",
            status=DocumentStatus.COMPLETED,
        )
        db_session.add(d)
    await db_session.commit()

    # Quota with max 3 should raise QuotaExceededError
    with pytest.raises(QuotaExceededError) as exc_info:
        await check_user_quota(user_id=user_id, db=db_session, max_documents=3)

    assert exc_info.value.code == "QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_rate_limit_http_response_returns_429(client: AsyncClient):
    """ISSUE-008: Verify HTTP 429 response structure and Retry-After header."""
    from app.services.rate_limiter import limiter

    limiter.reset()

    # Send requests to exceed the 20/min limit on upload-init
    hit_429 = False
    for _ in range(25):
        res = await client.post(
            "/api/v1/documents/upload-init",
            json={
                "fileName": "test.pdf",
                "fileSizeBytes": 100,
                "mimeType": "application/pdf",
            },
        )
        if res.status_code == 429:
            hit_429 = True
            assert "Retry-After" in res.headers
            assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            break

    assert hit_429 is True
