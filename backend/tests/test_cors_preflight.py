"""ISSUE-016: CORS Preflight and Header Security Tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_preflight_request(client: AsyncClient):
    """CORS preflight request must return safe headers and origin matching."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    resp = await client.options("/healthz", headers=headers)
    assert resp.status_code == 200

    # Verify CORS headers
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin in {"*", "http://localhost:3000"}

    # If wildcard is used, credentials MUST NOT be true per browser Fetch spec
    if allow_origin == "*":
        assert (
            resp.headers.get("access-control-allow-credentials") is None
            or resp.headers.get("access-control-allow-credentials").lower() != "true"
        )
    else:
        assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_datetime_timezone_utc_compliance():
    """Verify all models and timestamps default to timezone-aware UTC datetime."""
    from datetime import UTC

    from app.models.document import Document, _utcnow
    from app.services.idempotency import IdempotencyKeyRecord

    now = _utcnow()
    assert now.tzinfo is not None
    assert now.tzinfo == UTC

    # Model default callable verification on SQLAlchemy schema columns
    doc_default = Document.__table__.columns["created_at"].default.arg(None)
    assert doc_default is not None
    assert doc_default.tzinfo == UTC

    rec_default = IdempotencyKeyRecord.__table__.columns["created_at"].default.arg(None)
    assert rec_default is not None
    assert rec_default.tzinfo == UTC
