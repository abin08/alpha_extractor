from celery import chain
from fastapi import APIRouter, status
from pydantic import BaseModel

from src.core.logger import get_logger
from src.domain.models import AssetContext
from src.tasks.workers.ai_tasks import generate_ai_brief_task
from src.tasks.workers.ingest_tasks import ingest_asset_task

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["Pipeline Jobs"])


class ManualTriggerRequest(BaseModel):
    """Payload for manually triggering the pipeline from the UI/API."""

    internal_symbol: str
    company_name: str
    yfinance_symbol: str
    screener_symbol: str
    nse_symbol: str
    amfi_code: str | None = None


@router.post("/trigger-pipeline", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis_pipeline(request: ManualTriggerRequest):
    """
    Manually triggers the end-to-end Alpha Extractor pipeline (Ingestion -> AI).
    Returns the async Job ID immediately.
    """
    logger.info(f"API Request received to manually trigger pipeline for {request.internal_symbol}")

    # 1. Map request to our Domain Model
    asset = AssetContext(
        internal_symbol=request.internal_symbol,
        company_name=request.company_name,
        yfinance_symbol=request.yfinance_symbol,
        screener_symbol=request.screener_symbol,
        nse_symbol=request.nse_symbol,
        amfi_code=request.amfi_code,
    )

    # 2. Build the Celery Canvas Chain
    # The output of Ingestion (S3 URI) is automatically piped to the AI Task
    pipeline_chain = chain(ingest_asset_task.s(asset.model_dump()), generate_ai_brief_task.s())

    # 3. Dispatch the job asynchronously
    result = pipeline_chain.delay()
    logger.info(f"Pipeline dispatched successfully. Chain ID: {result.id}")

    return {
        "status": "Accepted",
        "message": f"Pipeline triggered for {asset.internal_symbol}",
        "chain_id": str(result.id),
    }
