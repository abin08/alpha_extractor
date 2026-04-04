from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import settings

# Check if we are using SQLite (for CI/CD tests) or Postgres (for Production/Local)
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
else:
    # Create the async engine using asyncpg
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
    )

# Create a session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncSession:  # type: ignore
    """
    Dependency function to yield an async database session.
    Used heavily in FastAPI routes and internal repository classes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
