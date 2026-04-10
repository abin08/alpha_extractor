from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.scheduler_tasks import (
    _dispatch_active_targets,
    dispatch_daily_pipeline_task,
)


class MockTargetConfig:
    """A simple mock class to represent the SQLAlchemy TargetConfig model."""

    def __init__(self, target_id, asset_type, identifier, name, is_active=True):
        self.id = target_id
        # Simulate an Enum with a .value attribute
        self.asset_type = MagicMock()
        self.asset_type.value = asset_type

        self.identifier = identifier
        self.name = name
        self.is_active = is_active


@pytest.fixture
def mock_db_session():
    """Fixture to mock the AsyncSessionLocal and SQLAlchemy execution."""
    with patch("src.tasks.workers.scheduler_tasks.AsyncSessionLocal") as mock_session_class:
        mock_session = AsyncMock()
        mock_scalars = MagicMock()

        # Setup the async context manager (__aenter__) to return our mock session
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_session.scalars.return_value = mock_scalars

        yield mock_scalars


@pytest.mark.asyncio
@patch("src.tasks.workers.scheduler_tasks.chain")
async def test_dispatch_empty_database(mock_chain, mock_db_session):
    """Test 1: If no active targets are found, it should idle and return 0."""
    # Arrange: DB returns empty list
    mock_db_session.all.return_value = []

    # Act
    count = await _dispatch_active_targets()

    # Assert
    assert count == 0
    mock_chain.assert_not_called()


@pytest.mark.asyncio
@patch("src.tasks.workers.scheduler_tasks.chain")
@patch("src.tasks.workers.scheduler_tasks.ingest_asset_task")
async def test_dispatch_successful_fan_out(mock_ingest, mock_chain, mock_db_session):
    """Test 2: Verifies schema translation and successful queueing of multiple targets."""
    # Arrange: DB returns 2 active targets
    target1 = MockTargetConfig(1, "EQUITY", "RELIANCE.NS", "Reliance Ind")
    target2 = MockTargetConfig(2, "EQUITY", "HDFCBANK.NS", "HDFC Bank")
    mock_db_session.all.return_value = [target1, target2]

    # Setup the mock chain to track apply_async calls
    mock_pipeline = MagicMock()
    mock_chain.return_value = mock_pipeline

    # Act
    count = await _dispatch_active_targets()

    # Assert
    assert count == 2
    assert mock_pipeline.apply_async.call_count == 2

    # Verify the bounded context translation (identifier -> internal_symbol)
    # Check the payload sent to the FIRST ingestion task
    expected_payload = {
        "id": 1,
        "asset_type": "EQUITY",
        "internal_symbol": "RELIANCE.NS",
        "company_name": "Reliance Ind",
        "is_active": True,
    }
    mock_ingest.s.assert_any_call(expected_payload)


@pytest.mark.asyncio
@patch("src.tasks.workers.scheduler_tasks.chain")
async def test_dispatch_resilience_loop(mock_chain, mock_db_session):
    """Test 3: If queueing one target raises an exception, the loop must continue."""
    # Arrange: DB returns 2 targets
    target1 = MockTargetConfig(1, "EQUITY", "POISON.NS", "Bad Data")
    target2 = MockTargetConfig(2, "EQUITY", "GOOD.NS", "Good Data")
    mock_db_session.all.return_value = [target1, target2]

    # Force the chain to raise an Exception on the FIRST call, but succeed on the SECOND
    mock_pipeline = MagicMock()
    mock_pipeline.apply_async.side_effect = [
        Exception("Redis connection dropped"),
        None,
    ]
    mock_chain.return_value = mock_pipeline

    # Act
    count = await _dispatch_active_targets()

    # Assert
    # It should only count 1 successfully dispatched pipeline
    assert count == 1
    # apply_async should still be called twice (the first crashed, the second passed)
    assert mock_pipeline.apply_async.call_count == 2


@patch("src.tasks.workers.scheduler_tasks._dispatch_active_targets", new_callable=MagicMock)
@patch("src.tasks.workers.scheduler_tasks.asyncio.run")
def test_sync_wrapper_task(mock_asyncio_run, mock_dispatch_core):
    """Test 4: Verify the Celery synchronous wrapper executes the async core."""
    # Arrange
    mock_asyncio_run.return_value = 5
    dummy_coro = MagicMock(name="dummy_coro")
    mock_dispatch_core.return_value = dummy_coro

    # Act
    result = dispatch_daily_pipeline_task()

    # Assert
    assert result == "Dispatched 5 pipelines"
    mock_asyncio_run.assert_called_once_with(dummy_coro)
