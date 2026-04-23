import asyncio

from celery import shared_task

from src.core.exceptions import ResolutionError
from src.core.logger import get_logger
from src.storage.db.orm_models import AssetType, TargetStatus
from src.storage.db.repositories.target_repo import TargetRepository
from src.storage.db.session import AsyncSessionLocal
from src.tasks.workers.resolution_strategies import (
    resolve_equity_symbols,
    resolve_mutual_fund_symbols,
)

logger = get_logger(__name__)


async def _run_resolution_pipeline(target_id: int):
    """Async core of the orchestrator."""
    async with AsyncSessionLocal() as session:
        repo = TargetRepository(session)
        target = await repo.get_by_id(target_id)

        if not target:
            logger.error(
                "Resolution failed: Target not found",
                extra={"extra_data": {"target_id": target_id}},
            )
            return

        # Skip if already resolved
        if target.status == TargetStatus.ACTIVE:
            logger.info(
                "Target already active, skipping resolution",
                extra={"extra_data": {"target_id": target_id}},
            )
            return

        try:
            # 1. Route to Strategy
            mapping_data = {}
            if target.asset_type == AssetType.EQUITY:
                mapping_data = await resolve_equity_symbols(target.identifier)
            elif target.asset_type == AssetType.MUTUAL_FUND:
                mapping_data = await resolve_mutual_fund_symbols(target.identifier)

            # 2. Save Mapping & Update State Machine
            await repo.save_vendor_mapping(target_id, mapping_data)
            await repo.update_status(target_id, TargetStatus.ACTIVE)

            logger.info(
                "Successfully resolved asset symbols",
                extra={
                    "extra_data": {
                        "target_id": target_id,
                        "identifier": target.identifier,
                    }
                },
            )

        except ResolutionError as e:
            # 3. Handle Expected Domain Failures (Bad symbols, missing tickers)
            logger.warning(
                "Symbol resolution failed. Flagging for manual intervention.",
                extra={"extra_data": {"target_id": target_id, "reason": str(e)}},
            )
            await repo.update_status(target_id, TargetStatus.MANUAL_INTERVENTION)
            raise  # Re-raise so Celery marks the task as failed if we want visibility


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def resolve_asset_symbols_task(self, target_id: int):
    """
    The Traffic Cop. Manages the DB transaction and state machine for asset resolution.
    """
    logger.info(
        "Starting resolution orchestrator",
        extra={"extra_data": {"target_id": target_id}},
    )
    try:
        asyncio.run(_run_resolution_pipeline(target_id))
    except ResolutionError:
        # We don't retry ResolutionErrors because they represent
        # bad user input/unresolvable edge cases
        pass
    except Exception as e:
        # Systemic errors (DB timeout, network drop) should be retried
        logger.error(f"Systemic error in orchestrator: {str(e)}", exc_info=True)
        raise self.retry(exc=e)
