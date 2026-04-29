import asyncio
from datetime import datetime

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
    """Async engine to build the DLQ HTML alert and push it to the UNG."""
    client = UNGClient()

    date_str = datetime.now().strftime("%B %d, %Y - %H:%M %Z").strip()

    # Native HTML payload - No markdown parsing required!
    html_content = f"""
    <div style="font-family: sans-serif; color: #333; max-width: 600px; margin: 0 auto; 
    border: 1px solid #ffcccc; border-radius: 8px; padding: 20px; background-color: #fffafa;">
        <h2 style="color: #d9534f; margin-top: 0;">🚨 DEAD LETTER QUEUE (DLQ) ALERT</h2>
        <p><b>Severity:</b> <span style="color: #d9534f; font-weight: bold;">CRITICAL 🔴</span></p>
        <p><b>Timestamp:</b> <code>{date_str}</code></p>
        <p><b>Task ID:</b> <code>{task_id}</code></p>
        <p><b>Task Name:</b> <code>{task_name}</code></p>
        <p><b>Exception:</b></p>
        <pre style="background-color: #f8f9fa; padding: 10px; border-left: 4px solid #d9534f; 
        overflow-x: auto;">{exception}</pre>
        <p><b>Arguments:</b></p>
        <pre style="background-color: #f8f9fa; padding: 10px; border-left: 4px solid #f0ad4e; 
        overflow-x: auto;">{argsrepr}</pre>
        <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
        <blockquote style="margin: 0; font-style: italic; color: #777;">
            Action Required: Please check the worker container logs for the full stack trace.
        </blockquote>
    </div>
    """

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
    task_id = request.get("id", "unknown_id")
    task_name = request.get("task", "unknown_task")
    argsrepr = request.get("argsrepr", "no_args")

    logger.error(f"DLQ Tripwire activated for {task_name} [{task_id}]. Formulating alert payload.")

    try:
        asyncio.run(_dispatch_error_alert(task_id, task_name, str(exc), argsrepr))
        logger.info(f"DLQ Alert successfully dispatched to UNG for task {task_id}.")
    except Exception as e:
        logger.critical(f"FATAL: Failed to send DLQ alert via UNG! Error: {e}", exc_info=True)
