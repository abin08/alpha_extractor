from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.delivery_tasks import _process_delivery, deliver_ai_brief_task


class MockJobRun:
    """Mock representation of the SQLAlchemy JobRunMetadata model."""

    def __init__(self, markdown_content):
        self.brief_markdown = markdown_content


@pytest.fixture
def mock_db_session():
    """Fixture to mock the AsyncSessionLocal and SQLAlchemy execution."""
    with patch("src.tasks.workers.delivery_tasks.AsyncSessionLocal") as mock_session_class:
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        yield mock_session


@pytest.mark.asyncio
@patch("src.tasks.workers.delivery_tasks.UNGClient")
async def test_process_delivery_success(mock_ung_class, mock_db_session):
    """Test 1: Verifies correct database extraction and UNG Client dispatch."""
    # Arrange
    # The async function calls session.scalar() twice.
    # 1st call: Fetch JobRun. 2nd call: Fetch Ticker.
    mock_job = MockJobRun("# Bullish Market Update")
    mock_db_session.scalar.side_effect = [mock_job, "RELIANCE.NS"]

    # Setup the mocked UNG Client instance
    mock_ung_instance = mock_ung_class.return_value
    mock_ung_instance.dispatch_brief = AsyncMock()

    # Act
    result = await _process_delivery(job_run_id=7)

    # Assert
    assert result == "Delivered RELIANCE.NS"
    mock_ung_instance.dispatch_brief.assert_called_once_with(
        ticker="RELIANCE.NS", markdown_payload="# Bullish Market Update"
    )


@pytest.mark.asyncio
@patch("src.tasks.workers.delivery_tasks.UNGClient")
async def test_process_delivery_missing_job(mock_ung_class, mock_db_session):
    """Test 2: Verifies it aborts if the JobRun ID does not exist in Postgres."""
    # Arrange: Database returns None when querying for the job
    mock_db_session.scalar.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid JobRun state for ID: 99"):
        await _process_delivery(job_run_id=99)

    # Ensure the delivery client was never triggered
    mock_ung_class.return_value.dispatch_brief.assert_not_called()


@pytest.mark.asyncio
@patch("src.tasks.workers.delivery_tasks.UNGClient")
async def test_process_delivery_empty_markdown(mock_ung_class, mock_db_session):
    """Test 3: Verifies it aborts if the JobRun exists but markdown generation failed."""
    # Arrange: Database returns a Job, but the markdown field is None
    mock_job = MockJobRun(None)
    mock_db_session.scalar.return_value = mock_job

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid JobRun state for ID: 88"):
        await _process_delivery(job_run_id=88)


@patch(
    "src.tasks.workers.delivery_tasks._process_delivery", new_callable=MagicMock
)  # Change to MagicMock
@patch("src.tasks.workers.delivery_tasks.asyncio.run")
def test_sync_wrapper_task_success(mock_asyncio_run, mock_process_delivery):
    """Test 4: Verifies the Celery wrapper successfully triggers the async loop."""
    # Arrange
    mock_asyncio_run.return_value = "Delivered HDFCBANK.NS"
    # We create a specific dummy object to represent the "coroutine"
    dummy_coro = MagicMock(name="dummy_coroutine")
    mock_process_delivery.return_value = dummy_coro

    # Act
    result = deliver_ai_brief_task(7)

    # Assert
    assert result == "Delivered HDFCBANK.NS"
    # Now we verify that asyncio.run was called with our dummy object
    mock_asyncio_run.assert_called_once_with(dummy_coro)
    mock_process_delivery.assert_called_once_with(7)
