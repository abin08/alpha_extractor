from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AlphaExtractorError
from src.core.logger import get_logger
from src.domain.schemas.ai_response import MacroAnalysis
from src.storage.db.orm_models import (
    AIBriefResult,
    AssetType,
    JobRunMetadata,
    JobStatus,
    TargetConfig,
)

logger = get_logger(__name__)


class DatabasePersistenceError(AlphaExtractorError):
    """Custom exception for repository-level failures."""

    pass


class BriefRepository:
    """Repository pattern for managing AI Briefs in PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_brief(
        self,
        ticker: str,
        celery_task_id: str,
        s3_uri: str,
        ai_result: MacroAnalysis,
    ) -> int:
        """
        Saves the structured AI output and raw JSONB to the database.
        """
        logger.info(f"Saving AI brief to Postgres for Ticker: {ticker}")

        try:
            stmt = select(TargetConfig).where(TargetConfig.identifier == ticker)
            target = await self.session.scalar(stmt)

            if not target:
                logger.warning(f"Target {ticker} not found in DB. Auto-creating it.")
                target = TargetConfig(
                    asset_type=AssetType.EQUITY,
                    identifier=ticker,
                    name=ticker,
                    is_active=True,
                )
                self.session.add(target)
                await self.session.flush()

            target_id = target.id
            logger.info(f"Saving AI brief to Postgres for Target: {ticker} (ID: {target_id})")

            # Extract clean JSON from the Pydantic model
            raw_json_payload = ai_result.model_dump(mode="json")

            # Create the parent Job Run Metadata (The Document / Summary)
            job_run = JobRunMetadata(
                status=JobStatus.COMPLETED,
                celery_task_id=celery_task_id,
                s3_raw_uri=s3_uri,
                macro_sentiment=ai_result.macro_sentiment,
                sector_rotation=ai_result.sector_rotation,
                brief_markdown=None,  # Explicitly nullified
                raw_response=raw_json_payload,
            )
            self.session.add(job_run)
            await self.session.flush()

            # Create the child AIBriefResults (The Relational / Searchable Insights)
            for insight in ai_result.insights:
                brief_record = AIBriefResult(
                    job_run_id=job_run.id,
                    target_id=target_id,
                    sentiment=insight.sentiment,
                    catalyst=insight.catalyst,
                    actionable_edge=insight.actionable_edge,
                )
                self.session.add(brief_record)

            await self.session.commit()
            logger.info(f"Successfully saved JobRunMetadata ID: {job_run.id}")

            return job_run.id

        except SQLAlchemyError as db_exc:
            await self.session.rollback()
            logger.error(f"Database transaction failed for {ticker}: {db_exc}")
            raise DatabasePersistenceError(f"Failed to save brief for {ticker}") from db_exc
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error persisting brief for {ticker}: {e}")
            raise DatabasePersistenceError(f"Unexpected persistence error for {ticker}") from e
