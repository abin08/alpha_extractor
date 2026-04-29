import asyncio
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

from src.core.logger import get_logger
from src.delivery.email_renderer import AlphaExtractorEmail
from src.delivery.ung_client import UNGClient
from src.storage.db.orm_models import (
    JobRunMetadata,
    NotificationRecipient,
    TargetConfig,
)
from src.storage.db.session import AsyncSessionLocal
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _process_daily_digest(chord_results: list[dict]) -> str:
    """
    Async engine that fetches raw AI JSON, maps it to the component schema,
    renders the pure-Python HTML template, and delivers via UNG.
    """
    successful_jobs = {
        res["ticker"]: res["job_id"]
        for res in chord_results
        if res.get("status") == "success" and res.get("job_id")
    }

    async with AsyncSessionLocal() as session:
        # 1. Fetch Recipients
        stmt_recipients = select(NotificationRecipient.email).where(NotificationRecipient.is_active)
        result = await session.scalars(stmt_recipients)
        active_emails = result.all()

        if not active_emails:
            logger.warning("No active email recipients configured. Skipping Daily Digest delivery.")
            return "Skipped Daily Digest (no recipients)"

        # 2. Fetch Company Names
        target_names = {}
        if successful_jobs:
            stmt_targets = select(TargetConfig.identifier, TargetConfig.name).where(
                TargetConfig.identifier.in_(successful_jobs.keys())
            )
            target_rows = await session.execute(stmt_targets)
            target_names = {row.identifier: (row.name or row.identifier) for row in target_rows}

        # 3. Fetch Raw JSON Responses & Macro Sentiment
        job_map = {}
        if successful_jobs:
            stmt_jobs = select(JobRunMetadata).where(
                JobRunMetadata.id.in_(successful_jobs.values())
            )
            jobs = await session.scalars(stmt_jobs)
            job_map = {job.id: job for job in jobs}

    # 4. Data Mapping for AlphaExtractorEmail Component
    ist_tz = ZoneInfo("Asia/Kolkata")
    date_str = datetime.now(ist_tz).strftime("%A, %B %d, %Y at %I:%M %p")
    trace_id = f"alpha-extractor-email-{uuid.uuid4().hex[:8]}"

    # Default fallback state
    macro_sentiment = "neutral"
    macro_summary = "System Alert: The pipeline ran, but no actionable data could be extracted \
        or processed today. Please check the system logs."
    assets_data = []

    if job_map:
        # Extract global macro view from the first available successful job
        first_job = next(iter(job_map.values()))
        macro_sentiment = (
            first_job.macro_sentiment.lower() if first_job.macro_sentiment else "neutral"
        )
        macro_summary = first_job.sector_rotation or "Market overview unavailable."

        # Map individual asset insights
        for ticker, job_id in successful_jobs.items():
            job = job_map.get(job_id)
            if not job or not job.raw_response:
                continue

            insights = job.raw_response.get("insights", [])
            for idx, insight in enumerate(insights):
                assets_data.append(
                    {
                        "ticker": ticker if idx == 0 else f"{ticker} (Cont.)",
                        "name": target_names.get(ticker, ticker),
                        "sentiment": insight.get("sentiment", "neutral").lower(),
                        "catalyst": insight.get("catalyst", "N/A"),
                        "actionableEdge": insight.get("actionable_edge", "N/A"),
                    }
                )

    # Assemble final UI payload
    template_data = {
        "date": date_str,
        "macroSentiment": macro_sentiment,
        "macroSummary": macro_summary,
        "assets": assets_data,
        "traceId": trace_id,
    }

    # 5. Render the Component UI
    renderer = AlphaExtractorEmail()
    final_html = renderer.render(template_data)

    # 6. Dispatch via UNG Client
    client = UNGClient()
    await client.dispatch_brief(
        ticker="DAILY_DIGEST",
        html_payload=final_html,
        recipients=list(active_emails),
        trace_id=trace_id,
    )

    return f"Delivered Daily Digest ({len(assets_data)} insights) \
        to {len(active_emails)} recipients"


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
