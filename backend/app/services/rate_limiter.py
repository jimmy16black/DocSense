"""Rate limiting and quota enforcement service (ISSUE-008).

Provides:
  * Sliding-window rate limiter per (client_id, route).
  * Fast in-memory deque state per window.
  * Canonical RATE_LIMIT_EXCEEDED (HTTP 429) + Retry-After header.
  * Monthly document quota check with QUOTA_EXCEEDED error.
"""

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import QuotaExceededError, RateLimitExceededError
from app.core.logging import get_logger
from app.models.document import Document

logger = get_logger("rate_limiter")


class SlidingWindowLimiter:
    """Sliding-window counter for rate limiting."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, max_requests: int, window_seconds: int) -> int:
        now = time.monotonic()
        q = self._windows[key]

        # Evict timestamps older than the window
        cutoff = now - window_seconds
        while q and q[0] <= cutoff:
            q.popleft()

        if len(q) >= max_requests:
            oldest = q[0]
            retry_after = max(1, math.ceil(oldest + window_seconds - now))
            logger.warning(
                "Rate limit exceeded",
                key=key,
                limit=max_requests,
                window=window_seconds,
                retry_after=retry_after,
            )
            raise RateLimitExceededError(
                message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                retry_after=retry_after,
            )

        q.append(now)
        return max_requests - len(q)

    def reset(self) -> None:
        """Clear all in-memory windows (used by tests)."""
        self._windows.clear()


limiter = SlidingWindowLimiter()


def rate_limit(
    max_requests: int, window_seconds: int = 60, key_prefix: str = ""
) -> Callable[..., Any]:
    """FastAPI route dependency enforcing sliding-window rate limits."""

    async def dependency(request: Request) -> None:
        # Key by user authorization token if present, else by client IP
        auth_header = request.headers.get("Authorization", "")
        client_id = (
            auth_header if auth_header else (request.client.host if request.client else "unknown")
        )
        rate_key = f"{key_prefix}:{request.url.path}:{client_id}"
        remaining = limiter.check(
            rate_key, max_requests=max_requests, window_seconds=window_seconds
        )
        request.state.rate_limit_remaining = remaining

    return dependency


async def check_user_quota(user_id: str, db: AsyncSession, max_documents: int = 50) -> None:
    """Checks if user has exceeded their document storage/processing quota (ISSUE-008)."""
    count_q = select(func.count(Document.id)).where(Document.user_id == user_id)
    doc_count = (await db.execute(count_q)).scalar() or 0
    if doc_count >= max_documents:
        logger.warning(
            "User exceeded document quota",
            user_id=user_id,
            count=doc_count,
            limit=max_documents,
        )
        raise QuotaExceededError(
            f"You have reached your limit of {max_documents} documents. Please delete existing documents or upgrade your plan."
        )
