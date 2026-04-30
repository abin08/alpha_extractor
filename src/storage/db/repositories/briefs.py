from datetime import datetime

from sqlalchemy import func, or_, select
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

    async def search_insights(
        self,
        ticker: str | None = None,
        asset_type: str | None = None,
        sentiment: str | None = None,
        macro_sentiment: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        Dynamically searches historical AI insights across
        TargetConfig, AIBriefResult, and JobRunMetadata.
        Returns a dictionary containing the mapped 'data' and
        'total_results' for pagination.
        """
        logger.info(f"Executing historical insight search. Keyword: {keyword}, Ticker: {ticker}")

        # 1. Base Query with 3-Way JOIN
        stmt = (
            select(AIBriefResult, TargetConfig, JobRunMetadata)
            .join(TargetConfig, AIBriefResult.target_id == TargetConfig.id)
            .join(JobRunMetadata, AIBriefResult.job_run_id == JobRunMetadata.id)
        )

        # 2. Apply Dynamic Filters
        if ticker:
            stmt = stmt.where(TargetConfig.identifier == ticker)

        if asset_type:
            stmt = stmt.where(TargetConfig.asset_type == asset_type)

        if sentiment:
            # SQLAlchemy ilike is case-insensitive
            stmt = stmt.where(AIBriefResult.sentiment.ilike(sentiment))

        if macro_sentiment:
            stmt = stmt.where(JobRunMetadata.macro_sentiment.ilike(macro_sentiment))

        if date_from:
            stmt = stmt.where(JobRunMetadata.run_date >= date_from)

        if date_to:
            stmt = stmt.where(JobRunMetadata.run_date <= date_to)

        if keyword:
            # Search both the catalyst and the actionable edge
            search_term = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    AIBriefResult.catalyst.ilike(search_term),
                    AIBriefResult.actionable_edge.ilike(search_term),
                )
            )

        # 3. Get Total Count (for pagination math)
        # We wrap the filtered statement in a subquery to count the total rows ignoring limit/offset
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_results = await self.session.scalar(count_stmt) or 0

        # 4. Apply Sorting and Pagination
        stmt = stmt.order_by(JobRunMetadata.run_date.desc())
        stmt = stmt.limit(limit).offset(offset)

        # 5. Execute Data Query
        result = await self.session.execute(stmt)
        rows = result.all()

        # 6. Map SQL Rows to Pydantic-ready dictionaries
        mapped_data = []
        for brief, target, job in rows:
            mapped_data.append(
                {
                    "target": {
                        "identifier": target.identifier,
                        "name": target.name,
                        "asset_type": target.asset_type.value,
                    },
                    "insight": {
                        "insight_id": brief.id,
                        "sentiment": brief.sentiment,
                        "catalyst": brief.catalyst,
                        "actionable_edge": brief.actionable_edge,
                    },
                    "macro_context": {
                        "job_id": job.id,
                        "run_date": job.run_date,
                        "macro_sentiment": job.macro_sentiment,
                        "sector_rotation": job.sector_rotation,
                    },
                }
            )

        return {"total_results": total_results, "data": mapped_data}
