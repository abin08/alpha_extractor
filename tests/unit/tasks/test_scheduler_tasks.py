from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.db.orm_models import TargetStatus
from src.tasks.workers.scheduler_tasks import (
    _dispatch_active_targets,
    dispatch_daily_pipeline_task,
)


class MockVendorMapping:
    """Mock the relational mapping table."""

    def __init__(self, yf_symbol=None, screener_symbol=None, nse_symbol=None, amfi_code=None):
        self.yfinance_symbol = yf_symbol
        self.screener_symbol = screener_symbol
        self.nse_symbol = nse_symbol
        self.amfi_code = amfi_code


class MockTargetConfig:
    """A simple mock class to represent the SQLAlchemy TargetConfig model."""

    def __init__(self, target_id, asset_type, identifier, name, is_active=True, has_mapping=True):
        self.id = target_id
        # Simulate an Enum with a .value attribute
        self.asset_type = MagicMock()
        self.asset_type.value = asset_type

        self.identifier = identifier
        self.name = name
        self.is_active = is_active
        self.status = TargetStatus.ACTIVE

        # Inject the mock relational data
        if has_mapping:
            self.vendor_mapping = MockVendorMapping(
                yf_symbol=f"{identifier}.NS",
                screener_symbol=identifier,
                nse_symbol=identifier,
            )
        else:
            self.vendor_mapping = None


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
    """Test 2: Verifies schema translation and successful queueing with vendor mappings."""
    # Arrange: DB returns 2 active targets with valid mappings
    target1 = MockTargetConfig(1, "EQUITY", "RELIANCE", "Reliance Ind")
    target2 = MockTargetConfig(2, "EQUITY", "HDFCBANK", "HDFC Bank")
    mock_db_session.all.return_value = [target1, target2]

    mock_pipeline = MagicMock()
    mock_chain.return_value = mock_pipeline

    # Act
    count = await _dispatch_active_targets()

    # Assert
    assert count == 2
    assert mock_pipeline.apply_async.call_count == 2

    # Verify the bounded context translation includes the new vendor routing symbols
    expected_payload = {
        "internal_symbol": "RELIANCE",
        "company_name": "Reliance Ind",
        "yfinance_symbol": "RELIANCE.NS",
        "screener_symbol": "RELIANCE",
        "nse_symbol": "RELIANCE",
        "amfi_code": None,
    }
    mock_ingest.s.assert_any_call(expected_payload)


@pytest.mark.asyncio
@patch("src.tasks.workers.scheduler_tasks.chain")
async def test_dispatch_skips_missing_mapping(mock_chain, mock_db_session):
    """Test 3: If an ACTIVE target has no mapping (DB anomaly), it skips it securely."""
    # Arrange: Target 1 is broken (no mapping), Target 2 is good
    target1 = MockTargetConfig(1, "EQUITY", "POISON", "Bad Data", has_mapping=False)
    target2 = MockTargetConfig(2, "EQUITY", "GOOD", "Good Data", has_mapping=True)
    mock_db_session.all.return_value = [target1, target2]

    mock_pipeline = MagicMock()
    mock_chain.return_value = mock_pipeline

    # Act
    count = await _dispatch_active_targets()

    # Assert
    # It should only queue the good target
    assert count == 1
    assert mock_pipeline.apply_async.call_count == 1


@pytest.mark.asyncio
@patch("src.tasks.workers.scheduler_tasks.chain")
async def test_dispatch_resilience_loop(mock_chain, mock_db_session):
    """Test 4: If queueing one target raises an exception, the loop must continue."""
    # Arrange: DB returns 2 targets
    target1 = MockTargetConfig(1, "EQUITY", "POISON", "Bad Queue")
    target2 = MockTargetConfig(2, "EQUITY", "GOOD", "Good Queue")
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
    assert count == 1
    assert mock_pipeline.apply_async.call_count == 2


@patch("src.tasks.workers.scheduler_tasks._dispatch_active_targets", new_callable=MagicMock)
@patch("src.tasks.workers.scheduler_tasks.asyncio.run")
def test_sync_wrapper_task(mock_asyncio_run, mock_dispatch_core):
    """Test 5: Verify the Celery synchronous wrapper executes the async core."""
    mock_asyncio_run.return_value = 5
    dummy_coro = MagicMock(name="dummy_coro")
    mock_dispatch_core.return_value = dummy_coro

    result = dispatch_daily_pipeline_task()

    assert result == "Dispatched 5 pipelines"
    mock_asyncio_run.assert_called_once_with(dummy_coro)
