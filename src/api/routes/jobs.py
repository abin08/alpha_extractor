from celery.result import AsyncResult
from fastapi import APIRouter, status

from src.core.logger import get_logger
from src.domain.schemas.api_payloads import JobStatusResponse
from src.tasks.celery_app import celery_app
from src.tasks.workers.scheduler_tasks import dispatch_daily_pipeline_task

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["Pipeline Jobs"])


@router.post("/trigger-daily-dispatcher", status_code=status.HTTP_202_ACCEPTED)
async def trigger_daily_dispatcher():
    """
    Manually triggers the overarching morning fan-out pipeline for all ACTIVE targets.
    """
    logger.info("API Request received to manually trigger the daily dispatcher.")

    # Capture the AsyncResult returned by Celery
    result = dispatch_daily_pipeline_task.delay()

    return {
        "message": "Daily dispatcher initiated. Fanning out to all active targets.",
        "task_id": str(result.id),
    }


@router.get(
    "/{chain_id}/status",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_job_status(chain_id: str):
    """
    Checks the status of an asynchronous Celery job chain.
    """
    # Query the Celery backend (Redis) for the state of this specific Task ID
    result = AsyncResult(chain_id, app=celery_app)

    response_data = {
        "task_id": chain_id,
        "status": result.state,
    }

    if result.state == "SUCCESS":
        # If successful, extract the return value of the final task in the chain
        response_data["result"] = result.result

    elif result.state == "FAILURE":
        # If it failed, result.info contains the exception instance.
        # We stringify it to avoid sending raw python traces to the client.
        response_data["error_message"] = str(result.info)
        logger.warning(
            f"Client queried failed job {chain_id}",
            extra={"extra_data": {"error": response_data["error_message"]}},
        )

    return response_data
