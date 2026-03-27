from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.dependencies import get_db
from src.api.main import app
from src.storage.db.orm_models import Base

# Use an in-memory SQLite database for instant, isolated tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
async def setup_database():
    """Creates fresh database tables before each test, and drops them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    """Yields a database session to the test functions."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def async_client():
    """Overrides the FastAPI dependency to use the test database, and yields a test client."""

    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_redis_client():
    """
    Globally mocks the async Redis client for all unit tests.
    Prevents tests from crashing in CI environments where Redis is not running.
    """
    # Patch the main Redis connection classes
    with (
        patch("redis.asyncio.Redis") as mock_redis_class,
        patch("redis.asyncio.from_url") as mock_from_url,
    ):
        mock_client = AsyncMock()

        # Mock basic circuit breaker methods so it always evaluates as "Closed" (Healthy)
        mock_client.get.return_value = None
        mock_client.set.return_value = True
        mock_client.incr.return_value = 1
        mock_client.expire.return_value = True

        mock_redis_class.return_value = mock_client
        mock_from_url.return_value = mock_client

        yield mock_client
