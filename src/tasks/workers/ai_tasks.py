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
    sanitized_context = ContextBuilder.build(raw_data)
    system_prompt = get_system_prompt(version="v1")

    # Extract asset info for the Formatter and DB
    asset_info = raw_data.get("asset", {})
    target_ticker = asset_info.get("internal_symbol", "Unknown Asset")

    # 3. LLM Orchestration
    ai_facade = LLMServiceFacade()
    ai_result = await ai_facade.generate_brief(
        sanitized_context=sanitized_context, system_prompt=system_prompt
    )

    # 4. Presentation Layer
    markdown_report = MarkdownFormatter.format_brief(ai_result, target_name=target_ticker)

    # 5. Database Persistence
    async with AsyncSessionLocal() as session:
        repository = BriefRepository(session)

        # FIX: Replaced target_id with ticker to match the updated repository signature
        job_run_id = await repository.save_brief(
            ticker=target_ticker,
            celery_task_id=celery_task_id,
            s3_uri=s3_uri,
            markdown_report=markdown_report,
            ai_result=ai_result,
        )

        print(
            f"\n\n{'=' * 60}\nFINAL AI BRIEF GENERATED (ID: {job_run_id})"
            f"\n{markdown_report}\n{'=' * 60}\n"
        )

        return job_run_id


@celery_app.task(name="tasks.generate_ai_brief", bind=True, max_retries=3, rate_limit="10/m")
def generate_ai_brief_task(self, s3_uri: str) -> int:
    """
    Celery entry point for the AI Brief generation.
    """
    task_id = self.request.id
    current_attempt = self.request.retries + 1

    logger.info(
        f"AI Worker active. Processing job {task_id} for payload {s3_uri}. "
        f"(Attempt {current_attempt}/{self.max_retries + 1})"
    )

    try:
        return asyncio.run(_process_ai_brief(s3_uri, task_id))

    except LLMGenerationError as lex:
        logger.error(
            f"FATAL: Logic failure in LLM generation for {task_id}. "
            f"Halting retries to conserve API quota. Reason: {lex}"
        )
        raise

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.critical(
                f"CRITICAL: Max retries exhausted for task {task_id}. "
                f"Failed processing payload: {s3_uri}. Final Error: {exc}",
                exc_info=True,
            )
            raise exc

        backoff_delay = 60 * (2**self.request.retries)

        logger.warning(
            f"Transient failure in task {task_id}. "
            f"Retrying in {backoff_delay}s ({current_attempt}/{self.max_retries}). Error: {exc}"
        )

        raise self.retry(exc=exc, countdown=backoff_delay)
