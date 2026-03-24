from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.domain.schemas.api_payloads import TargetCreate, TargetResponse
from src.storage.db.repositories.target_repo import TargetRepository

router = APIRouter(prefix="/targets", tags=["Target Configuration"])


@router.get("/", response_model=list[TargetResponse])
async def list_targets(db: AsyncSession = Depends(get_db)):
    """Retrieve all financial assets currently being tracked."""
    repo = TargetRepository(db)
    return await repo.get_all()


@router.post("/", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def add_target(target: TargetCreate, db: AsyncSession = Depends(get_db)):
    """Add a new equity or mutual fund to the tracking list."""
    repo = TargetRepository(db)
    db_obj = await repo.create(target)

    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target with identifier '{target.identifier}' already exists.",
        )
    return db_obj


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_target(target_id: int, db: AsyncSession = Depends(get_db)):
    """Stop tracking a specific target and remove it from the database."""
    repo = TargetRepository(db)
    success = await repo.delete(target_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")
