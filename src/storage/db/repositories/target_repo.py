from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.schemas.api_payloads import TargetCreate
from src.storage.db.orm_models import TargetConfig


class TargetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> Sequence[TargetConfig]:
        """Fetch all configured targets."""
        stmt = select(TargetConfig).order_by(TargetConfig.id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, target_in: TargetCreate) -> TargetConfig | None:
        """Create a new target. Returns None if identifier already exists."""
        db_obj = TargetConfig(**target_in.model_dump())
        self.session.add(db_obj)
        try:
            await self.session.commit()
            await self.session.refresh(db_obj)
            return db_obj
        except IntegrityError:
            await self.session.rollback()
            return None

    async def delete(self, target_id: int) -> bool:
        """Delete a target by ID. Returns True if deleted, False if not found."""
        stmt = select(TargetConfig).where(TargetConfig.id == target_id)
        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj:
            await self.session.delete(db_obj)
            await self.session.commit()
            return True
        return False
