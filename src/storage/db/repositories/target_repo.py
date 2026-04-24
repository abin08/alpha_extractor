from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.schemas.api_payloads import TargetCreate
from src.storage.db.orm_models import AssetVendorMapping, TargetConfig, TargetStatus


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

    async def get_by_id(self, target_id: int) -> TargetConfig | None:
        """Fetch a target by ID, eager-loading its vendor mapping."""
        stmt = (
            select(TargetConfig)
            .where(TargetConfig.id == target_id)
            .options(selectinload(TargetConfig.vendor_mapping))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, target_id: int, status: TargetStatus) -> bool:
        """Update the lifecycle status of a target."""
        stmt = update(TargetConfig).where(TargetConfig.id == target_id).values(status=status)
        await self.session.execute(stmt)
        await self.session.commit()
        return True

    async def save_vendor_mapping(
        self, target_id: int, mapping_data: dict
    ) -> AssetVendorMapping | None:
        """Insert the resolved vendor routing symbols for a target safely."""
        mapping = AssetVendorMapping(target_id=target_id, **mapping_data)
        self.session.add(mapping)
        try:
            await self.session.commit()
            await self.session.refresh(mapping)
            return mapping
        except IntegrityError:
            # If the mapping already exists due to a partial previous run, roll back
            # and ignore the error so the orchestrator can proceed to update the status.
            await self.session.rollback()
            return None

    async def upsert_vendor_mapping(self, target_id: int, mapping_data: dict) -> AssetVendorMapping:
        """
        Admin override: Insert or update the vendor routing symbols for a target.
        """
        # 1. Check if a mapping already exists
        stmt = select(AssetVendorMapping).where(AssetVendorMapping.target_id == target_id)
        result = await self.session.execute(stmt)
        mapping = result.scalar_one_or_none()

        if mapping:
            # 2a. Update existing row safely
            for key, value in mapping_data.items():
                setattr(mapping, key, value)
        else:
            # 2b. Create new row if the automated resolver completely failed initially
            mapping = AssetVendorMapping(target_id=target_id, **mapping_data)
            self.session.add(mapping)

        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping
