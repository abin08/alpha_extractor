from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

# Create the async engine using asyncpg
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True if you want to see raw SQL generated in the console
    future=True,
    pool_size=10,
    max_overflow=20,
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
