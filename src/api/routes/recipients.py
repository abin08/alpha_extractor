from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.core.logger import get_logger
from src.domain.schemas.api_payloads import RecipientCreate, RecipientResponse
from src.storage.db.repositories.recipient_repo import RecipientRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/recipients", tags=["Notification Management"])


@router.get("/", response_model=list[RecipientResponse])
async def list_recipients(db: AsyncSession = Depends(get_db)):
    """Retrieve all email recipients."""
    repo = RecipientRepository(db)
    return await repo.get_all()


@router.post("/", response_model=RecipientResponse, status_code=status.HTTP_201_CREATED)
async def add_recipient(payload: RecipientCreate, db: AsyncSession = Depends(get_db)):
    """Add a new email recipient for AI brief delivery."""
    repo = RecipientRepository(db)

    # We pass payload.email directly since our schema only has one field
    db_obj = await repo.create(payload.email)

    if not db_obj:
        logger.warning(
            "Attempted to add duplicate email recipient",
            extra={"extra_data": {"email": payload.email}},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{payload.email}' is already registered.",
        )

    logger.info(
        "Added new notification recipient",
        extra={"extra_data": {"recipient_id": db_obj.id, "email": db_obj.email}},
    )
    return db_obj


@router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_recipient(recipient_id: int, db: AsyncSession = Depends(get_db)):
    """Remove an email recipient from the distribution list."""
    repo = RecipientRepository(db)
    success = await repo.delete(recipient_id)

    if not success:
        logger.warning(
            "Attempted to delete non-existent recipient",
            extra={"extra_data": {"recipient_id": recipient_id}},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found.")
