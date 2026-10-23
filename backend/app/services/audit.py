"""Audit trail service (BE-5, 09_SECURITY_DPDP).

Every privacy/security-relevant mutation must be auditable: document
lifecycle events, action confirmations/cancellations, data access
exports and account erasure. Rows are written in the *same* transaction
as the operation they describe (durable via commit_now pattern), so an
audit record can never claim success for a rolled-back change.

Design notes:
- ``record()`` only adds the row to the session; callers keep control of
  when the transaction commits. This keeps auditing crash-safe without
  introducing a second write path.
- ``details`` is deliberately schema-free JSONB but must never contain
  raw PII or document content — only ids, counts and status strings.
  A conservative redaction pass is applied to string values as defense
  in depth.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import AuditEvent

# Defense-in-depth scrubbers for `details` values (never trust callers).
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\s-]?){7,}\d")


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        value = _EMAIL_RE.sub("[redacted-email]", value)
        value = _PHONE_RE.sub("[redacted-phone]", value)
        return value[:200]
    if isinstance(value, dict):
        return {str(k)[:64]: _scrub(v) for k, v in list(value.items())[:32]}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in list(value)[:32]]
    if isinstance(value, (int, float, bool, uuid.UUID)) or value is None:
        return value
    return str(value)[:200]


def client_ip(request: Request | None) -> str | None:
    """Best-effort client IP honoring proxy headers."""
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:45]
    if request.client:
        return str(request.client.host)[:45]
    return None


async def record(
    db: AsyncSession,
    *,
    user_id: str,
    event_type: str,
    document_id: uuid.UUID | None = None,
    action_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """Append an audit row to the current transaction (caller commits)."""
    event = AuditEvent(
        user_id=user_id,
        event_type=event_type,
        document_id=document_id,
        action_id=action_id,
        details=_scrub(details or {}),
        ip_address=ip_address,
    )
    db.add(event)
    return event
