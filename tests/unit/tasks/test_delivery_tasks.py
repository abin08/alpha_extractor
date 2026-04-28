from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.delivery_tasks import (
    _process_daily_digest,
    _process_delivery,
    deliver_ai_brief_task,
    deliver_daily_digest_task,
)


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

    mock_job = MockJobRun("# Bullish Market Update")
    mock_db_session.scalar.side_effect = [mock_job, "RELIANCE.NS"]

    # Mock the return for session.scalars().all() for the emails
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["trader_one@alpha.com", "analyst@alpha.com"]
    mock_db_session.scalars.return_value = mock_scalars

    mock_ung_instance = mock_ung_class.return_value
    mock_ung_instance.dispatch_brief = AsyncMock()

    result = await _process_delivery(job_run_id=7)

    assert result == "Delivered RELIANCE.NS to 2 recipients"
    mock_ung_instance.dispatch_brief.assert_called_once_with(
        ticker="RELIANCE.NS",
        markdown_payload="# Bullish Market Update",
        recipients=["trader_one@alpha.com", "analyst@alpha.com"],
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


@pytest.mark.asyncio
@patch("src.tasks.workers.delivery_tasks.UNGClient")
@patch("src.tasks.workers.delivery_tasks.MarkdownFormatter.format_daily_digest")
async def test_process_daily_digest_success(mock_format, mock_ung_class, mock_db_session):
    """Test that the digest engine correctly filters failures and stitches successes."""
    # Arrange: Pass a mixed array of successes and failures
    chord_results = [
        {"status": "success", "ticker": "RELIANCE.NS", "job_id": 10},
        {
            "status": "error",
            "ticker": "HDFCBANK.NS",
            "job_id": None,
            "error_msg": "Timeout",
        },
    ]

    # Mock the DB scalar for the 1 successful markdown fetch
    mock_db_session.scalar.side_effect = ["# Reliance MD"]

    # Mock the DB scalars for fetching active emails
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["admin@alpha.com"]
    mock_db_session.scalars.return_value = mock_scalars

    mock_format.return_value = "# MEGA DIGEST"

    mock_ung_instance = mock_ung_class.return_value
    mock_ung_instance.dispatch_brief = AsyncMock()

    # Act
    result = await _process_daily_digest(chord_results)

    # Assert
    assert "Delivered Daily Digest (1 assets)" in result

    # Ensure formatter was ONLY passed the successful job
    mock_format.assert_called_once_with({"RELIANCE.NS": "# Reliance MD"})

    mock_ung_instance.dispatch_brief.assert_called_once_with(
        ticker="DAILY_DIGEST",
        markdown_payload="# MEGA DIGEST",
        recipients=["admin@alpha.com"],
    )


@patch("src.tasks.workers.delivery_tasks._process_daily_digest", new_callable=MagicMock)
@patch("src.tasks.workers.delivery_tasks.asyncio.run")
def test_deliver_daily_digest_task_wrapper(mock_asyncio_run, mock_process):
    """Verify the new fan-in Celery wrapper executes correctly."""
    mock_asyncio_run.return_value = "Delivered Digest"
    dummy_coro = MagicMock(name="dummy_coroutine")
    mock_process.return_value = dummy_coro

    chord_results = [{"status": "success", "ticker": "RELIANCE.NS", "job_id": 10}]

    result = deliver_daily_digest_task(chord_results)

    assert result == "Delivered Digest"
    mock_process.assert_called_once_with(chord_results)
    mock_asyncio_run.assert_called_once_with(dummy_coro)
