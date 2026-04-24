from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.core.logger import get_logger
from src.domain.schemas.api_payloads import (
    TargetCreate,
    TargetResponse,
    VendorMappingUpdate,
)
from src.storage.db.orm_models import TargetStatus
from src.storage.db.repositories.target_repo import TargetRepository
from src.tasks.workers.resolution_tasks import resolve_asset_symbols_task

logger = get_logger(__name__)
router = APIRouter(prefix="/targets", tags=["Target Configuration"])


@router.get("/", response_model=list[TargetResponse])
async def list_targets(db: AsyncSession = Depends(get_db)):
    """Retrieve all financial assets currently being tracked."""
    repo = TargetRepository(db)
    return await repo.get_all()


@router.post("/", response_model=TargetResponse, status_code=status.HTTP_202_ACCEPTED)
async def add_target(target: TargetCreate, db: AsyncSession = Depends(get_db)):
    """Add a new equity or mutual fund and queue it for symbol resolution."""
    repo = TargetRepository(db)
    db_obj = await repo.create(target)

    if not db_obj:
        # Structured Logging for the failure
        logger.warning(
            "Attempted to create duplicate target",
            extra={
                "extra_data": {
                    "identifier": target.identifier,
                    "asset_type": target.asset_type.value,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target with identifier '{target.identifier}' already exists.",
        )

    # Dispatch the background resolution task
    logger.info(
        "Target created. Dispatching resolution task.",
        extra={"extra_data": {"target_id": db_obj.id, "identifier": db_obj.identifier}},
    )
    resolve_asset_symbols_task.delay(db_obj.id)

    return db_obj


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_target(target_id: int, db: AsyncSession = Depends(get_db)):
    """Stop tracking a specific target and remove it from the database."""
    repo = TargetRepository(db)
    success = await repo.delete(target_id)

    if not success:
        logger.warning(
            "Attempted to delete non-existent target",
            extra={"extra_data": {"target_id": target_id}},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")


@router.patch(
    "/{target_id}/mapping",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
)
async def manual_update_vendor_mapping(
    target_id: int, payload: VendorMappingUpdate, db: AsyncSession = Depends(get_db)
):
    """
    Admin backdoor to manually map vendor symbols for a stuck/failed asset.
    Automatically shifts the target status to ACTIVE upon a successful update.
    """
    repo = TargetRepository(db)
    target = await repo.get_by_id(target_id)

    if not target:
        logger.warning(
            "Attempted to update mapping for non-existent target",
            extra={"extra_data": {"target_id": target_id}},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    # exclude_unset=True guarantees we ONLY update fields the user explicitly sent in the JSON
    update_data = payload.model_dump(exclude_unset=True)

    if update_data:
        # 1. Upsert the provided mappings
        await repo.upsert_vendor_mapping(target_id, update_data)

        # 2. Rescue the target by making it ACTIVE for tomorrow's ingestion
        await repo.update_status(target_id, TargetStatus.ACTIVE)

        logger.info(
            "Manually updated vendor mapping and activated target.",
            extra={"extra_data": {"target_id": target_id, "updates": update_data}},
        )

    # 3. Fetch the fresh object to return to the client
    updated_target = await repo.get_by_id(target_id)
    return updated_target
