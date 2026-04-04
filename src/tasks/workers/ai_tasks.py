# src/tasks/workers/ai_tasks.py
import asyncio

from src.ai.context_builder import ContextBuilder
from src.ai.facade import LLMServiceFacade
from src.ai.prompt_loader import get_system_prompt
from src.core.exceptions import AlphaExtractorError, LLMGenerationError
from src.core.logger import get_logger
from src.delivery.formatter import MarkdownFormatter
from src.storage.db.repositories.briefs import BriefRepository
from src.storage.db.session import AsyncSessionLocal
from src.storage.object_store.s3_client import AsyncS3Client
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _process_ai_brief(s3_uri: str, celery_task_id: str) -> int:
    """
    Async engine for downloading context, calling Gemini, and persisting results.

    Args:
        s3_uri (str): Pointer to the raw ingestion data in MinIO/S3.
        celery_task_id (str): The unique ID of the current Celery job.

    Returns:
        int: The primary key (ID) of the saved JobRunMetadata in Postgres.
    """

    # 1. Download Payload
    logger.info(
        f"Downloading raw context from S3 pointer: {s3_uri}",
        extra={"task_id": celery_task_id},
    )
    s3_client = AsyncS3Client()
    try:
        raw_data = await s3_client.download_json(s3_uri)
    except Exception as e:
        logger.error(f"Failed to download S3 payload: {e}")
        raise AlphaExtractorError(f"S3 Download failed for {s3_uri}") from e

    # 2. Context Preparation
    # We use the recursive ContextBuilder to strip HTML/JS and compress the prompt
    sanitized_context = ContextBuilder.build(raw_data)
    system_prompt = get_system_prompt(version="v1")

    # Extract asset info for the Formatter and DB
    asset_info = raw_data.get("asset", {})
    target_ticker = asset_info.get("internal_symbol", "Unknown Asset")
    target_id = asset_info.get("id", 1)  # Defaulting to 1 for MVP/Initial testing

    # 3. LLM Orchestration
    # LLMServiceFacade already handles retries and circuit breaking internally
    ai_facade = LLMServiceFacade()
    ai_result = await ai_facade.generate_brief(
        sanitized_context=sanitized_context, system_prompt=system_prompt
    )

    # 4. Presentation Layer
    # Formats the structured Pydantic object into the Markdown used for Email/Telegram
    markdown_report = MarkdownFormatter.format_brief(ai_result, target_name=target_ticker)

    # 5. Database Persistence (AE34)
    # We open a scoped session to ensure the transaction is closed after the task
    async with AsyncSessionLocal() as session:
        repository = BriefRepository(session)

        job_run_id = await repository.save_brief(
            target_id=target_id,
            celery_task_id=celery_task_id,
            s3_uri=s3_uri,
            markdown_report=markdown_report,
            ai_result=ai_result,
        )

        # Log the final Markdown for visibility in the worker console
        print(
            f"\n\n{'=' * 60}\nFINAL AI BRIEF GENERATED (ID: {job_run_id})"
            f"\n{markdown_report}\n{'=' * 60}\n"
        )

        return job_run_id


@celery_app.task(
    name="tasks.generate_ai_brief",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_jitter=True,
)
def generate_ai_brief_task(self, s3_uri: str) -> int:
    """
    Celery entry point for the AI Brief generation.

    Bridges the synchronous Celery worker thread with the async pipeline.
    Captures the celery_task_id to maintain traceability in the DB.
    """
    task_id = self.request.id
    logger.info(f"AI Worker active. Processing job {task_id} for payload {s3_uri}")

    try:
        # Execute the async engine
        return asyncio.run(_process_ai_brief(s3_uri, task_id))

    except LLMGenerationError as lex:
        # LLMGenerationError usually implies a data/prompt issue (e.g. safety filters).
        # We log this specifically as it might not be solved by a simple retry.
        logger.error(f"Logic failure in LLM generation for {task_id}: {lex}")
        raise

    except Exception as exc:
        # Infrastructural failures (S3 down, Redis down, DB down) trigger Celery's
        # built-in retry mechanism with exponential backoff.
        logger.warning(
            f"Infrastructural failure in task {task_id}. "
            f"Retry {self.request.retries + 1}/{self.max_retries}. Error: {exc}"
        )
        raise
