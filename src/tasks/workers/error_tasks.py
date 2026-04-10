import asyncio
from datetime import datetime

from src.core.logger import get_logger
from src.delivery.ung_client import UNGClient
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
        f"**Timestamp:** {date_str}\n"
        f"---\n"
        f"### Task Failure Details\n"
        f"* **Task Name:** `{task_name}`\n"
        f"* **Task ID:** `{task_id}`\n"
        f"* **Input Args:** `{argsrepr}`\n\n"
        f"### Exception Trace\n"
        f"```python\n"
        f"{exception}\n"
        f"```\n"
        f"---\n"
        f"> *Action Required: Please check the worker container logs for the full stack trace.*"
    )

    # We use "DLQ_ALERT" as the ticker name so it's easily identifiable in the logs/deliveries
    await client.dispatch_brief(ticker="DLQ_ALERT", markdown_payload=markdown_payload)


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
