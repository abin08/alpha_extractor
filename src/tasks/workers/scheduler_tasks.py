# src/tasks/workers/scheduler_tasks.py
import asyncio

from celery import chain, chord
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.logger import get_logger
from src.storage.db.orm_models import TargetConfig, TargetStatus
from src.storage.db.session import AsyncSessionLocal
from src.tasks.celery_app import celery_app
from src.tasks.workers.ai_tasks import generate_ai_brief_task
from src.tasks.workers.delivery_tasks import deliver_daily_digest_task
from src.tasks.workers.error_tasks import alert_failed_task
from src.tasks.workers.ingest_tasks import ingest_asset_task

logger = get_logger(__name__)


async def _dispatch_active_targets() -> int:
    """
    Async engine that queries the Postgres database for all active TargetConfigs
    and queues up a parallel Celery chord for the daily fan-out.
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

    logger.info(
        f"Dispatcher found {len(active_targets)} active targets. Initiating fan-out chord..."
    )

    job_chains = []

    # 2. Iterate and build the parallel processing chains
    for target in active_targets:
        try:
            # Defensive Guardrail
            if not target.vendor_mapping:
                logger.error(
                    f"Data anomaly: Target {target.identifier} is ACTIVE "
                    "but missing vendor mapping! Skipping.",
                    extra={"extra_data": {"target_id": target.id}},
                )
                continue

            asset_payload = {
                "internal_symbol": target.identifier,
                "company_name": target.name or target.identifier,
                "yfinance_symbol": target.vendor_mapping.yfinance_symbol,
                "screener_symbol": target.vendor_mapping.screener_symbol,
                "nse_symbol": target.vendor_mapping.nse_symbol,
                "amfi_code": target.vendor_mapping.amfi_code,
            }

            errback = alert_failed_task.s()

            # The individual asset chain (Ingest -> AI).
            # Note: The single delivery task has been removed.
            asset_chain = chain(
                ingest_asset_task.s(asset_payload).set(link_error=errback),
                generate_ai_brief_task.s().set(link_error=errback),
            )
            job_chains.append(asset_chain)

        except Exception as e:
            logger.error(
                f"Failed to build pipeline for target {target.identifier}: {e}",
                exc_info=True,
            )
            continue

    if not job_chains:
        logger.warning("No valid targets could be queued. Aborting dispatcher.")
        return 0

    # 3. Fire the Chord
    # This executes all job_chains in parallel, waits for ALL to finish (or degrade gracefully),
    # and then passes their return dictionaries as an array to deliver_daily_digest_task
    master_chord = chord(job_chains)(deliver_daily_digest_task.s())

    logger.info(f"Successfully dispatched master chord with ID: {master_chord.id}")

    return len(job_chains)


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
