import asyncio

from src.ai.context_builder import ContextBuilder
from src.ai.facade import LLMServiceFacade
from src.ai.prompt_loader import get_system_prompt
from src.core.logger import get_logger
from src.storage.db.repositories.briefs import BriefRepository
from src.storage.object_store.s3_client import AsyncS3Client
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _process_ai_brief(s3_uri: str) -> str:
    """Async engine for downloading context, calling Gemini, and saving the brief."""

    # 1. Download the massive raw context from MinIO
    logger.info(f"Downloading raw context from S3 pointer: {s3_uri}")
    s3_client = AsyncS3Client()
    raw_data = await s3_client.download_json(s3_uri)

    # 2. Sanitize and compress the payload using your recursive ContextBuilder
    sanitized_context = ContextBuilder.build(raw_data)

    # 3. Load the versioned system prompt
    system_prompt = get_system_prompt(version="v1")

    # 4. Call the LLM Facade (handles retries, circuit breaking, and Pydantic validation)
    ai_facade = LLMServiceFacade()
    ai_result = await ai_facade.generate_brief(
        sanitized_context=sanitized_context, system_prompt=system_prompt
    )

    # 5. Save the validated MacroAnalysis result to the Database
    repository = BriefRepository()
    brief_id = await repository.save_brief(ai_result)

    return brief_id


@celery_app.task(
    name="tasks.generate_ai_brief",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,
)
def generate_ai_brief_task(self, s3_uri: str) -> str:
    """
    Celery worker task that acts as the entry point for AI processing.
    """
    logger.info(f"Received Celery AI task for S3 payload: {s3_uri}")

    try:
        # Block the Celery thread while the async event loop runs
        brief_id = asyncio.run(_process_ai_brief(s3_uri))
        logger.info(f"AI task completed successfully. DB Record ID: {brief_id}")
        return brief_id

    except Exception as exc:
        logger.error(f"CRITICAL: AI processing failed for {s3_uri}. Reason: {exc}")
        raise
