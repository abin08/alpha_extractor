# src/tasks/workers/scheduler_tasks.py
import asyncio

from celery import chain
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.logger import get_logger
from src.storage.db.orm_models import TargetConfig, TargetStatus
from src.storage.db.session import AsyncSessionLocal
from src.tasks.celery_app import celery_app
from src.tasks.workers.ai_tasks import generate_ai_brief_task
from src.tasks.workers.delivery_tasks import deliver_ai_brief_task
from src.tasks.workers.error_tasks import alert_failed_task
from src.tasks.workers.ingest_tasks import ingest_asset_task

logger = get_logger(__name__)


async def _dispatch_active_targets() -> int:
    """
    Async engine that queries the Postgres database for all active TargetConfigs
    and queues up an independent Celery chain for each one.
    """
    async with AsyncSessionLocal() as session:
        # 1. Fetch only fully ACTIVE targets and eager-load their vendor mappings
        stmt = (
            select(TargetConfig)
            .where(TargetConfig.is_active)
            .where(TargetConfig.status == TargetStatus.ACTIVE)
            .options(selectinload(TargetConfig.vendor_mapping))
        )
        result = await session.scalars(stmt)
        active_targets = result.all()

    if not active_targets:
        logger.warning("No active targets found in the database. Dispatcher idling.")
        return 0

    logger.info(f"Dispatcher found {len(active_targets)} active targets. Initiating fan-out...")

    dispatched_count = 0
    # 2. Iterate and trigger the pipeline for each target
    for target in active_targets:
        try:
            # 3. Defensive Guardrail: Ensure mapping exists
            if not target.vendor_mapping:
                logger.error(
                    f"Data anomaly: Target {target.identifier} is ACTIVE but \
                      missing vendor mapping! Skipping.",
                    extra={"extra_data": {"target_id": target.id}},
                )
                continue

            # 4. Exact Payload Rehydration matching AssetContext Pydantic Model
            asset_payload = {
                "internal_symbol": target.identifier,
                "company_name": target.name or target.identifier,  # Fallback to ID if name is None
                "yfinance_symbol": target.vendor_mapping.yfinance_symbol,
                "screener_symbol": target.vendor_mapping.screener_symbol,
                "nse_symbol": target.vendor_mapping.nse_symbol,
                "amfi_code": target.vendor_mapping.amfi_code,
            }

            # Define the DLQ errback signature
            errback = alert_failed_task.s()

            # Construct the complete extraction/AI/delivery chain
            pipeline = chain(
                ingest_asset_task.s(asset_payload).set(link_error=errback),
                generate_ai_brief_task.s().set(link_error=errback),
                deliver_ai_brief_task.s().set(link_error=errback),
            )

            # Fire and forget into the Redis queue
            pipeline.apply_async()
            logger.info(
                f"Successfully queued pipeline chain for: {target.identifier}",
                extra={"extra_data": {"internal_symbol": target.identifier}},
            )
            dispatched_count += 1

        except Exception as e:
            # If one target fails to queue (e.g., bad data), we log it and CONTINUE.
            logger.error(
                f"Failed to queue pipeline for target {target.identifier}: {e}",
                exc_info=True,
            )
            continue

    return dispatched_count


@celery_app.task(name="tasks.dispatch_daily_pipeline")
def dispatch_daily_pipeline_task() -> str:
    """
    Master Dispatcher task triggered exclusively by Celery Beat.
    It orchestrates the morning fan-out to all active assets.
    """
    logger.info("Morning Dispatcher waking up. Gathering active targets for 8:00 AM run.")
    try:
        # Run the async database query and dispatch loop
        count = asyncio.run(_dispatch_active_targets())
        logger.info(
            f"Dispatcher completed. Successfully fanned out {count} pipelines to the queue."
        )
        return f"Dispatched {count} pipelines"
    except Exception as e:
        logger.critical(
            f"FATAL: Dispatcher encountered an unhandled infrastructure error: {e}",
            exc_info=True,
        )
        raise
