from datetime import datetime
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


@pytest.fixture
def mock_search_row():
    """Fixture representing a single joined row returned by the search query."""
    mock_brief = MagicMock(spec=AIBriefResult)
    mock_brief.id = 1
    mock_brief.sentiment = "BULLISH"
    mock_brief.catalyst = "Earnings beat expectations by 12%."
    mock_brief.actionable_edge = "Buy calls at open."

    mock_target = MagicMock(spec=TargetConfig)
    mock_target.identifier = "TEST.NS"
    mock_target.name = "Test Corp"
    mock_target.asset_type.value = "EQUITY"

    mock_job = MagicMock(spec=JobRunMetadata)
    mock_job.id = 55
    mock_job.run_date = datetime(2026, 4, 30, 10, 0, 0)
    mock_job.macro_sentiment = "NEUTRAL"
    mock_job.sector_rotation = "Capital shifting to defensives."

    # Return as a tuple exactly as session.execute(stmt).all() would yield
    return (mock_brief, mock_target, mock_job)


# --- Existing Save Brief Tests ---


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


# --- New Search API Tests ---


@pytest.mark.asyncio
async def test_search_insights_mapping(mock_session, mock_search_row):
    """Test 5: Verify the 3-way JOIN results correctly map to the nested dictionary."""
    repo = BriefRepository(mock_session)

    # Mock the count query
    mock_session.scalar.return_value = 100

    # Mock the data query
    mock_result = MagicMock()
    mock_result.all.return_value = [mock_search_row]
    mock_session.execute.return_value = mock_result

    # Act
    result = await repo.search_insights(limit=10, offset=0)

    # Assert
    assert result["total_results"] == 100
    assert len(result["data"]) == 1

    data = result["data"][0]

    # Check Target Mapping
    assert data["target"]["identifier"] == "TEST.NS"
    assert data["target"]["name"] == "Test Corp"
    assert data["target"]["asset_type"] == "EQUITY"

    # Check Insight Mapping
    assert data["insight"]["insight_id"] == 1
    assert data["insight"]["sentiment"] == "BULLISH"
    assert data["insight"]["catalyst"] == "Earnings beat expectations by 12%."
    assert data["insight"]["actionable_edge"] == "Buy calls at open."

    # Check Macro Context Mapping
    assert data["macro_context"]["job_id"] == 55
    assert data["macro_context"]["macro_sentiment"] == "NEUTRAL"
    assert data["macro_context"]["sector_rotation"] == "Capital shifting to defensives."


@pytest.mark.asyncio
async def test_search_insights_dynamic_filters(mock_session):
    """Test 6: Verify the dynamic query builder executes
    without crashing when all filters are applied."""
    repo = BriefRepository(mock_session)

    # Empty mocks
    mock_session.scalar.return_value = 0
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute.return_value = mock_result

    # Act: Pass every possible filter
    await repo.search_insights(
        ticker="TCS.NS",
        asset_type="EQUITY",
        sentiment="BEARISH",
        macro_sentiment="BULLISH",
        date_from=datetime(2026, 1, 1),
        date_to=datetime(2026, 12, 31),
        keyword="FDA approval",
        limit=5,
        offset=10,
    )

    # Assert that the methods were called successfully (no SQLAlchemy build errors)
    assert mock_session.scalar.call_count == 1
    assert mock_session.execute.call_count == 1
