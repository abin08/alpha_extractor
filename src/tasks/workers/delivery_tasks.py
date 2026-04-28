import asyncio
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import markdown
from sqlalchemy import select

from src.core.logger import get_logger
from src.delivery.formatter import MarkdownFormatter
from src.delivery.renderer import EmailRenderer
from src.delivery.ung_client import UNGClient
from src.storage.db.orm_models import JobRunMetadata, NotificationRecipient
from src.storage.db.session import AsyncSessionLocal
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _process_daily_digest(chord_results: list[dict]) -> str:
    """
    Async engine that filters chord results, fetches successful markdowns,
    renders the futuristic HTML template, and delivers via UNG.
    """
    successful_jobs = {
        res["ticker"]: res["job_id"]
        for res in chord_results
        if res.get("status") == "success" and res.get("job_id")
    }

    brief_map = {}
    async with AsyncSessionLocal() as session:
        for ticker, job_id in successful_jobs.items():
            stmt = select(JobRunMetadata.brief_markdown).where(JobRunMetadata.id == job_id)
            markdown_content = await session.scalar(stmt)
            if markdown_content:
                brief_map[ticker] = markdown_content

        stmt_recipients = select(NotificationRecipient.email).where(NotificationRecipient.is_active)
        result = await session.scalars(stmt_recipients)
        active_emails = result.all()

    if not active_emails:
        logger.warning("No active email recipients configured. Skipping Daily Digest delivery.")
        return "Skipped Daily Digest (no recipients)"

    # 1. Format the raw mega-markdown
    mega_markdown = MarkdownFormatter.format_daily_digest(brief_map)

    # 2. Convert Markdown to HTML tags
    html_content = markdown.markdown(mega_markdown, extensions=["fenced_code", "tables"])

    # 3. Prepare Jinja2 Context
    ist_tz = ZoneInfo("Asia/Kolkata")
    date_str = datetime.now(ist_tz).strftime("%A, %B %d, %Y at %I:%M %p")
    trace_id = f"alpha-extractor-email-{uuid.uuid4().hex[:8]}"

    context = {
        "date": date_str,
        "target_count": len(brief_map),
        "trace_id": trace_id,
        "markdown_content": html_content,
    }

    # 4. Render the Final UI Template
    renderer = EmailRenderer()
    final_html = renderer.render_template("daily_digest.html", context)

    # 5. Dispatch via UNG Client
    client = UNGClient()
    await client.dispatch_brief(
        ticker="DAILY_DIGEST",
        html_payload=final_html,
        recipients=list(active_emails),
        trace_id=trace_id,
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
