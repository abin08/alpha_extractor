# src/tasks/workers/scheduler_tasks.py
import asyncio

from celery import chain
from sqlalchemy import select

from src.core.logger import get_logger
from src.storage.db.orm_models import TargetConfig
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
        # 1. Fetch only active targets from the database
        stmt = select(TargetConfig).where(TargetConfig.is_active)
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
            # Reconstruct the payload dictionary expected by ingest_asset_task
            # CRITICAL FIX: Translate DB fields to match Pydantic's AssetContext schema
            asset_payload = {
                "id": target.id,
                "asset_type": (
                    target.asset_type.value
                    if hasattr(target.asset_type, "value")
                    else target.asset_type
                ),
                "internal_symbol": target.identifier,  # MAP 'identifier' -> 'internal_symbol'
                "company_name": target.name,  # MAP 'name' -> 'company_name'
                "is_active": target.is_active,
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
            logger.info(f"Successfully queued pipeline chain for: {target.identifier}")
            dispatched_count += 1

        except Exception as e:
            # If one target fails to queue (e.g., bad data), we log it and CONTINUE.
            # We must not let one broken asset stop the rest from running.
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
