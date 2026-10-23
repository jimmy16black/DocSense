"""Idempotency-Key support for unsafe POST endpoints (ISSUE-016).

Contract:
  * Client sends ``Idempotency-Key: <opaque token>`` on a POST.
  * First request with a given key (per user + endpoint) executes normally;
    the route records its final response against the key.
  * Replays of the same key return the *recorded* response verbatim without
    re-executing the endpoint body.
  * A second attempt while the first is still in flight receives 409 and
    must retry later to receive the original response.
  * Scoping is (user_id, method, path, key) so one user can never collide
    with or replay another user's operations.

Storage is the database (table ``idempotency_keys``): an in-memory cache
would silently lose replay protection exactly when retries matter most
(process crashes), and durability matches ISSUE-001's commit discipline.

Usage in a route::

    @router.post("/x", dependencies=[Depends(idempotency_guard)])
    async def x(request: Request, db=Depends(get_db_session), user=...):
        ...
        await save_idempotent_response(db, request, user.id, api_response_obj)
        return api_response_obj
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.errors import DocSenseException, ErrorClassification
from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import get_db_session

logger = get_logger("services.idempotency")

HEADER_NAME = "Idempotency-Key"
RECORD_TTL = timedelta(hours=24)


class IdempotencyConflictError(DocSenseException):
    def __init__(self) -> None:
        super().__init__(
            message=(
                "A request with this Idempotency-Key is still being processed. "
                "Retry shortly to receive the original response."
            ),
            classification=ErrorClassification.RETRYABLE_FAILURE,
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            is_retryable=True,
        )


class IdempotencyKeyRecord(Base):
    __tablename__ = "idempotency_keys"

    # client-supplied opaque token (uuid recommended); PK together with scope
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _scope(request: Request, user_id: str) -> str:
    """Stable identity for one logical operation: user + method + path."""
    raw = f"{user_id}|{request.method}|{request.url.path}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


async def _resolve_user_id(request: Request) -> str:
    """User identity for scoping.

    FastAPI caches dependency results per request, so re-invoking the
    (possibly test-overridden) ``get_current_user`` callable is cheap and
    consistent with what the route itself resolves. The real implementation
    reads the bearer token from the Starlette connection state; overrides
    usually ignore their argument entirely.
    """
    from app.core.security import get_current_user

    dep = request.scope["app"].dependency_overrides.get(get_current_user, get_current_user)
    result = dep(request)
    if hasattr(result, "__await__"):
        result = await result
    return str(result.id)


async def idempotency_guard(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Route dependency enforcing the Idempotency-Key contract.

    No-op when the header is absent. On replay raises Starlette's
    ``HTTPException`` carrying the recorded status/body — FastAPI returns it
    verbatim, so the client sees the original response again without the
    endpoint re-executing. Otherwise it reserves the key (INSERT) so a
    concurrent duplicate collides instead of double-processing.
    """
    key = request.headers.get(HEADER_NAME)
    if not key:
        return

    key = key.strip()[:256]
    if not key:
        return

    user_id = await _resolve_user_id(request)
    scope = _scope(request, user_id)

    # Opportunistic TTL purge keeps the table bounded without a cron job.
    await db.execute(delete(IdempotencyKeyRecord).where(IdempotencyKeyRecord.expires_at < datetime.now(UTC)))

    existing = (
        await db.execute(
            select(IdempotencyKeyRecord).where(
                IdempotencyKeyRecord.scope == scope,
                IdempotencyKeyRecord.id == key,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.response_body is not None:
            logger.info("idempotency_replay", extra={"scope": scope})
            raise HTTPException(
                status_code=existing.response_status or 200,
                content=json.loads(existing.response_body),
                headers={"Idempotent-Replay": "true"},
            )
        raise IdempotencyConflictError()

    db.add(
        IdempotencyKeyRecord(
            id=key,
            scope=scope,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + RECORD_TTL,
        )
    )
    # Durable reservation BEFORE the endpoint runs (ISSUE-001 discipline):
    # if we crashed after responding but before recording, the reserved-but
    # empty row makes the next attempt a 409 rather than a silent double-run.
    from app.db.session import commit_now

    await commit_now(db)


async def save_idempotent_response(
    db: AsyncSession,
    request: Request,
    user_id: str,
    payload: BaseModel,
    status_code: int = 200,
) -> None:
    """Record the endpoint's response against the request's Idempotency-Key.

    Called at the END of a guarded route, before returning. The row was
    already reserved by ``idempotency_guard``; here we only fill it in. If no
    key was sent this is a no-op.
    """
    key = (request.headers.get(HEADER_NAME) or "").strip()[:256]
    if not key:
        return

    scope = _scope(request, user_id)
    record = (
        await db.execute(
            select(IdempotencyKeyRecord).where(
                IdempotencyKeyRecord.scope == scope,
                IdempotencyKeyRecord.id == key,
            )
        )
    ).scalar_one_or_none()
    if record is None:  # guard skipped (e.g. tests overriding deps) — create now
        record = IdempotencyKeyRecord(
            id=key,
            scope=scope,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + RECORD_TTL,
        )
        db.add(record)

    body = payload.model_dump_json(by_alias=True)
    record.response_status = status_code
    record.response_body = body
