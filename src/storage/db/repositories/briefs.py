# src/storage/db/repositories/briefs.py
import uuid

from src.core.logger import get_logger
from src.domain.schemas.ai_response import MacroAnalysis

logger = get_logger(__name__)


class BriefRepository:
    """
    Repository pattern for AI Briefs.
    Currently mocked for AE23 to decouple AI development from Database infrastructure.
    Will be wired to Postgres/SQLAlchemy in Epic Ticket AE34.
    """

    async def save_brief(self, brief: MacroAnalysis) -> str:
        """
        Saves the structured AI output to the database.
        """
        # Generate a fake database primary key
        brief_id = str(uuid.uuid4())

        logger.info("[MOCK DB] Simulating Postgres INSERT for MacroAnalysis...")
        logger.debug(f"[MOCK DB] Overall Macro Sentiment: {brief.macro_sentiment}")
        logger.debug(f"[MOCK DB] Sector Rotation: {brief.sector_rotation}")

        for insight in brief.insights:
            logger.debug(f"  -> Insight Catalyst: {insight.catalyst}")
            logger.debug(f"  -> Insight Edge: {insight.actionable_edge}")

        logger.info(f"[MOCK DB] Successfully saved AI Brief to database with ID: {brief_id}")

        return brief_id
