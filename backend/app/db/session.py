from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("db")
settings = get_settings()

engine = create_async_engine(
    settings.SUPABASE_DB_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped session with guaranteed commit/rollback semantics.

    FIX (ISSUE-001): previously routes used ``flush()`` and relied on a commit
    that happened *after* the response object was constructed — any failure or
    client disconnect between those points silently discarded the write while
    the API had already reported success. Now we commit as soon as the route
    handler returns normally, before the response is serialized, so a
    "success" response always implies durable data.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def commit_now(session: AsyncSession) -> None:
    """Explicitly persist pending work mid-handler.

    Use this when subsequent logic (e.g. an AI call that may fail or a long
    pipeline step) must not roll back already-successful writes, or when the
    handler needs its own flushed+committed state visible to a later session.
    Routes should prefer this over bare ``flush()`` for every mutation that is
    observable from a successful response.
    """
    await session.commit()
