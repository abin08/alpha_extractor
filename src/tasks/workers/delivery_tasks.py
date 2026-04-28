import asyncio

import httpx
from sqlalchemy import select

from src.core.logger import get_logger
from src.delivery.formatter import MarkdownFormatter
from src.delivery.ung_client import UNGClient
from src.storage.db.orm_models import JobRunMetadata, NotificationRecipient
from src.storage.db.session import AsyncSessionLocal
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _process_daily_digest(chord_results: list[dict]) -> str:
    """
    Async engine that filters chord results, fetches successful markdowns,
    stitches them together, and delivers the mega-payload via UNG.
    """
    # 1. Filter out errors and grab the successful Job IDs
    successful_jobs = {
        res["ticker"]: res["job_id"]
        for res in chord_results
        if res.get("status") == "success" and res.get("job_id")
    }

    brief_map = {}
    async with AsyncSessionLocal() as session:
        # 2. Fetch the Markdown content from Postgres for each successful job
        for ticker, job_id in successful_jobs.items():
            stmt = select(JobRunMetadata.brief_markdown).where(JobRunMetadata.id == job_id)
            markdown = await session.scalar(stmt)
            if markdown:
                brief_map[ticker] = markdown

        # 3. Fetch Dynamic Delivery Route
        stmt_recipients = select(NotificationRecipient.email).where(NotificationRecipient.is_active)
        result = await session.scalars(stmt_recipients)
        active_emails = result.all()

    if not active_emails:
        logger.warning("No active email recipients configured. Skipping Daily Digest delivery.")
        return "Skipped Daily Digest (no recipients)"

    # 4. Format the final mega-payload
    mega_markdown = MarkdownFormatter.format_daily_digest(brief_map)

    # 5. Dispatch via UNG Client
    client = UNGClient()
    await client.dispatch_brief(
        ticker="DAILY_DIGEST",
        markdown_payload=mega_markdown,
        recipients=list(active_emails),
    )

    return f"Delivered Daily Digest ({len(brief_map)} assets) to {len(active_emails)} recipients"


@celery_app.task(
    name="tasks.deliver_daily_digest",
    bind=True,
    max_retries=5,
    autoretry_for=(httpx.RequestError,),
    retry_backoff=30,
)
def deliver_daily_digest_task(self, chord_results: list[dict]) -> str:
    """
    The Fan-In Celery Callback.
    Triggered only after all parallel Ingestion/AI chains complete.
    """
    logger.info(
        f"Fan-In Delivery Worker active. Received {len(chord_results)} results from the Chord."
    )

    try:
        result = asyncio.run(_process_daily_digest(chord_results))
        logger.info(f"Daily Digest delivery completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Daily Digest delivery failed: {exc}")
        raise
