from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency Injection provider for async database sessions.
    Ensures sessions are properly yielded to the route and closed afterward.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
