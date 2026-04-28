import asyncio
from datetime import datetime

import markdown
from sqlalchemy import select

from src.core.logger import get_logger
from src.delivery.ung_client import UNGClient
from src.storage.db.orm_models import NotificationRecipient
from src.storage.db.session import AsyncSessionLocal
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _dispatch_error_alert(
    task_id: str, task_name: str, exception: str, argsrepr: str
) -> None:
    """Async engine to build the DLQ Markdown and push it to the UNG."""
    client = UNGClient()

    date_str = datetime.now().strftime("%B %d, %Y - %H:%M %Z").strip()

    markdown_payload = (
        f"# 🚨 DEAD LETTER QUEUE (DLQ) ALERT\n"
        f"**Severity:** CRITICAL 🔴\n"
        f"**Timestamp:** `{date_str}`\n"
        f"**Task ID:** `{task_id}`\n"
        f"**Task Name:** `{task_name}`\n"
        f"**Exception:** `{exception}`\n"
        f"**Arguments:** `{argsrepr}`\n\n"
        f"> *Action Required: Please check the worker container logs for the full stack trace.*"
    )

    # Convert alert to HTML before dispatching
    html_content = markdown.markdown(markdown_payload, extensions=["fenced_code"])

    async with AsyncSessionLocal() as session:
        stmt = select(NotificationRecipient.email).where(NotificationRecipient.is_active)
        result = await session.scalars(stmt)
        active_emails = result.all()

    if not active_emails:
        logger.error(
            f"DLQ Alert for {task_id} generated, but NO ACTIVE EMAILS configured to receive it!"
        )
        return

    await client.dispatch_brief(
        ticker="DLQ_ALERT",
        html_payload=html_content,
        recipients=list(active_emails),
    )


@celery_app.task(name="tasks.alert_failed_task", ignore_result=True)
def alert_failed_task(request: dict, exc: Exception, traceback: str) -> None:
    """
    The designated Celery Errback (DLQ) task.
    Triggered automatically when a task with `link_error` exhausts all retries.
    """
    # Celery passes the failed task's request payload as a dictionary
    task_id = request.get("id", "unknown_id")
    task_name = request.get("task", "unknown_task")
    argsrepr = request.get("argsrepr", "no_args")

    logger.error(f"DLQ Tripwire activated for {task_name} [{task_id}]. Formulating alert payload.")

    try:
        # Fire the async alert payload
        asyncio.run(_dispatch_error_alert(task_id, task_name, str(exc), argsrepr))
        logger.info(f"DLQ Alert successfully dispatched to UNG for task {task_id}.")
    except Exception as e:
        # The final safety net: If the DLQ fails to send the DLQ alert, we log it critically.
        logger.critical(f"FATAL: Failed to send DLQ alert via UNG! Error: {e}", exc_info=True)
