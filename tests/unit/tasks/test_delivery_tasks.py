from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.delivery_tasks import (
    _process_daily_digest,
    deliver_daily_digest_task,
)


@pytest.fixture
def mock_db_session():
    """Fixture to mock the AsyncSessionLocal and SQLAlchemy execution."""
    with patch("src.tasks.workers.delivery_tasks.AsyncSessionLocal") as mock_session_class:
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        yield mock_session


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
