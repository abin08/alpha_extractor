"""
Ingestion Worker Tasks.

This module defines the Celery tasks responsible for orchestrating the Big Data
ingestion pipeline. It bridges the synchronous task queue environment of Celery
with the highly concurrent, asynchronous asyncio execution of our DataFetchers.
"""

import asyncio
import time
from typing import Any

from src.core.logger import get_logger
from src.domain.models import AssetContext
from src.ingestion.factory import DataSource, FetcherFactory
from src.ingestion.strategies import register_strategies
from src.storage.object_store.s3_client import AsyncS3Client
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _gather_and_upload(asset: AssetContext) -> str:
    """
    Asynchronously orchestrates the concurrent extraction of asset data and stores the payload.

    Architectural Note on Resilience:
    We do NOT apply custom @circuit_breaker or @with_retry_and_jitter here.
    Those patterns are handled atomically inside the individual strategy classes.
    If a fetcher completely fails, `asyncio.gather(..., return_exceptions=True)`
    catches the exception gracefully, allowing the rest of the payload to succeed
    rather than crashing the entire ingestion run.
    """
    # 0. Ensure all strategy decorators are executed to register them with the Factory
    register_strategies()

    # 1. Instantiate the data fetchers
    yf_fetcher = FetcherFactory.create(DataSource.YFINANCE)
    screener_fetcher = FetcherFactory.create(DataSource.SCREENER)
    rss_fetcher = FetcherFactory.create(DataSource.RSS_FEED)
    amfi_fetcher = FetcherFactory.create(DataSource.AMFI)
    nse_fetcher = FetcherFactory.create(DataSource.NSE_PDF)

    logger.info(f"Initiating concurrent data extraction for {asset.internal_symbol}...")

    # 2. Build the task list for the event loop
    tasks = [
        yf_fetcher.fetch_price_history(asset, period="1mo"),
        screener_fetcher.fetch_company_info(asset),
        rss_fetcher.fetch_news(asset),
        nse_fetcher.fetch_news(asset),
    ]

    if asset.amfi_code:
        logger.debug(f"AMFI code detected ({asset.amfi_code}). Appending mutual fund tasks.")
        tasks.append(amfi_fetcher.fetch_company_info(asset))
        tasks.append(amfi_fetcher.fetch_price_history(asset))

    # 3. Execute all network I/O concurrently
    logger.debug(f"Awaiting {len(tasks)} concurrent ingestion tasks...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    logger.info(f"Successfully gathered source data for {asset.internal_symbol}.")

    # 4. Construct the final JSON payload
    payload = {
        "asset": asset.model_dump(),
        "timestamp": time.time(),
        # Extract results, converting exceptions to strings for traceability if a source failed
        "price_action": (results[0] if not isinstance(results[0], Exception) else str(results[0])),
        "fundamentals": (results[1] if not isinstance(results[1], Exception) else str(results[1])),
        "news": (results[2] if not isinstance(results[2], Exception) else str(results[2])),
        "corporate_filings": (
            results[3] if not isinstance(results[3], Exception) else str(results[3])
        ),
    }

    if asset.amfi_code:
        payload["mutual_fund_info"] = (
            results[4] if not isinstance(results[4], Exception) else str(results[4])
        )
        payload["mutual_fund_nav"] = (
            results[5] if not isinstance(results[5], Exception) else str(results[5])
        )

    # 5. S3 Pointer Pattern: Upload the large payload to MinIO/S3
    logger.debug("Serializing massive payload and uploading to object store...")
    s3_client = AsyncS3Client()
    timestamp_str = str(int(time.time()))
    s3_key = f"raw-contexts/{asset.internal_symbol}_{timestamp_str}.json"

    s3_uri = await s3_client.upload_json(payload, s3_key)
    return s3_uri


@celery_app.task(name="tasks.ingest_asset", bind=True, max_retries=3)
def ingest_asset_task(self, asset_dict: dict[str, Any]) -> str:
    """
    Celery worker task that acts as the entry point for Big Data ingestion.
    """
    task_id = self.request.id
    logger.info(f"Received Celery ingestion task for: {asset_dict.get('internal_symbol')}")

    try:
        # 1. Rehydrate the strict Pydantic Domain Model from the untyped Celery dictionary
        asset = AssetContext(**asset_dict)
        logger.debug(f"Successfully rehydrated AssetContext for {asset.internal_symbol}.")

        # 2. Bridge the sync Celery world with our async asyncio pipeline
        s3_uri = asyncio.run(_gather_and_upload(asset))
        logger.info(f"Ingestion task completed successfully. Payload S3 URI: {s3_uri}")
        return s3_uri

    except ValueError as ve:
        # 3. Deterministic Error: Do NOT retry.
        # Pydantic validation failed. This will never succeed on a retry.
        logger.error(
            f"FATAL: Invalid payload structure for task {task_id}. "
            f"Failing instantly to trigger DLQ. Error: {ve}"
        )
        raise  # This bypasses retries and instantly trips the link_error DLQ!

    except Exception as exc:
        # 4. Transient/Infrastructural Errors: Eligible for retry.
        if self.request.retries >= self.max_retries:
            logger.critical(
                f"CRITICAL: Max retries exhausted for task {task_id}. Final Error: {exc}",
                exc_info=True,
            )
            raise exc

        # Execute surgical retry with exponential backoff (30s, 60s, 120s)
        backoff_delay = 30 * (2**self.request.retries)

        logger.warning(
            f"Transient failure in task {task_id}. "
            f"Retrying in {backoff_delay}s ({self.request.retries + 1}/{self.max_retries}). "
            f"Error: {exc}"
        )

        raise self.retry(exc=exc, countdown=backoff_delay)
