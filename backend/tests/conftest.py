from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import CurrentUser, get_current_user
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app

settings = get_settings()

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_current_user() -> CurrentUser:
    return CurrentUser(
        id="user-test-1234",
        email="test@example.com",
        role="authenticated",
    )


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(
    db_session: AsyncSession, mock_current_user: CurrentUser
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return mock_current_user

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
