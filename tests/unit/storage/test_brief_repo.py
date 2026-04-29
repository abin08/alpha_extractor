from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.schemas.ai_response import MacroAnalysis, SentimentEnum
from src.storage.db.orm_models import AIBriefResult, JobRunMetadata, TargetConfig
from src.storage.db.repositories.briefs import BriefRepository, DatabasePersistenceError


@pytest.fixture
def mock_session():
    """Fixture to provide a mocked AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_ai_result():
    """Fixture to provide a structured MacroAnalysis mock."""
    insight = MagicMock()
    insight.sentiment = SentimentEnum.BULLISH
    insight.catalyst = "High earnings"
    insight.actionable_edge = "Long position"

    result = MagicMock(spec=MacroAnalysis)
    result.macro_sentiment = SentimentEnum.NEUTRAL
    result.sector_rotation = "Tech leading"
    result.insights = [insight, insight]  # Test with 2 insights
    result.model_dump.return_value = {"mock": "data"}
    return result


@pytest.mark.asyncio
async def test_save_brief_target_exists(mock_session, mock_ai_result):
    """Test 1: Verify logic when the ticker already exists in TargetConfig."""
    repo = BriefRepository(mock_session)
    mock_target = MagicMock(spec=TargetConfig)
    mock_target.id = 101
    mock_session.scalar.return_value = mock_target

    await repo.save_brief(
        ticker="RELIANCE.NS",
        celery_task_id="task-123",
        s3_uri="s3://path",
        ai_result=mock_ai_result,
    )

    assert mock_session.add.call_count == 3
    calls = mock_session.add.call_args_list
    assert isinstance(calls[0][0][0], JobRunMetadata)
    # Ensure markdown was explicitly nullified by the repo
    assert calls[0][0][0].brief_markdown is None
    assert isinstance(calls[1][0][0], AIBriefResult)
    assert isinstance(calls[2][0][0], AIBriefResult)

    mock_session.flush.assert_called()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_save_brief_auto_create_target(mock_session, mock_ai_result):
    """Test 2: Verify logic when ticker is missing (Auto-creation)."""
    repo = BriefRepository(mock_session)
    mock_session.scalar.return_value = None

    await repo.save_brief(
        ticker="NEW_TICKER",
        celery_task_id="task-456",
        s3_uri="s3://path",
        ai_result=mock_ai_result,
    )

    added_objects = [call[0][0] for call in mock_session.add.call_args_list]
    targets = [obj for obj in added_objects if isinstance(obj, TargetConfig)]

    assert len(targets) == 1
    assert targets[0].identifier == "NEW_TICKER"
    assert mock_session.flush.call_count == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_save_brief_relational_mapping(mock_session, mock_ai_result):
    """Test 3: Verify that every insight in the AI result becomes a DB record."""
    repo = BriefRepository(mock_session)
    mock_target = MagicMock(spec=TargetConfig)
    mock_target.id = 50
    mock_session.scalar.return_value = mock_target

    await repo.save_brief(
        ticker="TCS.NS",
        celery_task_id="task-789",
        s3_uri="s3://path",
        ai_result=mock_ai_result,
    )

    added_objects = [call[0][0] for call in mock_session.add.call_args_list]
    brief_results = [obj for obj in added_objects if isinstance(obj, AIBriefResult)]

    assert len(brief_results) == 2
    for record in brief_results:
        assert record.target_id == 50


@pytest.mark.asyncio
async def test_save_brief_db_exception(mock_session, mock_ai_result):
    """Test 4: Verify DB exceptions are caught, rolled back, and re-raised cleanly."""
    repo = BriefRepository(mock_session)
    mock_session.scalar.side_effect = SQLAlchemyError("DB Connection Lost")

    with pytest.raises(DatabasePersistenceError, match="Failed to save brief"):
        await repo.save_brief(
            ticker="FAIL.NS",
            celery_task_id="task-fail",
            s3_uri="s3://path",
            ai_result=mock_ai_result,
        )

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
