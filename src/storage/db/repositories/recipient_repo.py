from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.db.orm_models import NotificationRecipient


class RecipientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> Sequence[NotificationRecipient]:
        """Fetch all configured email recipients."""
        stmt = select(NotificationRecipient).order_by(NotificationRecipient.id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_active(self) -> Sequence[NotificationRecipient]:
        """Fetch only active email recipients for the delivery worker."""
        stmt = (
            select(NotificationRecipient)
            .where(NotificationRecipient.is_active)
            .order_by(NotificationRecipient.id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, email: str) -> NotificationRecipient | None:
        """Create a new recipient. Returns None if the email already exists."""
        db_obj = NotificationRecipient(email=email)
        self.session.add(db_obj)
        try:
            await self.session.commit()
            await self.session.refresh(db_obj)
            return db_obj
        except IntegrityError:
            await self.session.rollback()
            return None

    async def delete(self, recipient_id: int) -> bool:
        """Delete a recipient by ID. Returns True if deleted, False if not found."""
        stmt = select(NotificationRecipient).where(NotificationRecipient.id == recipient_id)
        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj:
            await self.session.delete(db_obj)
            await self.session.commit()
            return True
        return False
