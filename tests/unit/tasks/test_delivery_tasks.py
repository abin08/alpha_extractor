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
@patch("src.tasks.workers.delivery_tasks.EmailRenderer")
@patch("src.tasks.workers.delivery_tasks.markdown.markdown")
@patch("src.tasks.workers.delivery_tasks.UNGClient")
@patch("src.tasks.workers.delivery_tasks.MarkdownFormatter.format_daily_digest")
async def test_process_daily_digest_success(
    mock_format, mock_ung_class, mock_markdown, mock_renderer_class, mock_db_session
):
    """Test that the digest engine correctly filters failures, renders HTML, and dispatches."""

    chord_results = [
        {"status": "success", "ticker": "RELIANCE.NS", "job_id": 10},
        {"status": "error", "ticker": "HDFCBANK.NS", "job_id": None},
    ]

    mock_db_session.scalar.side_effect = ["# Reliance MD"]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["admin@alpha.com"]
    mock_db_session.scalars.return_value = mock_scalars

    mock_format.return_value = "# MEGA DIGEST"
    mock_markdown.return_value = "<h1>MEGA DIGEST</h1>"

    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render_template.return_value = "<html><h1>MEGA DIGEST</h1></html>"
    mock_renderer_class.return_value = mock_renderer_instance

    mock_ung_instance = mock_ung_class.return_value
    mock_ung_instance.dispatch_brief = AsyncMock()

    result = await _process_daily_digest(chord_results)

    assert "Delivered Daily Digest (1 assets)" in result
    mock_format.assert_called_once_with({"RELIANCE.NS": "# Reliance MD"})
    mock_markdown.assert_called_once_with("# MEGA DIGEST", extensions=["fenced_code", "tables"])

    mock_renderer_instance.render_template.assert_called_once()
    context_passed = mock_renderer_instance.render_template.call_args[0][1]
    assert context_passed["target_count"] == 1
    assert context_passed["markdown_content"] == "<h1>MEGA DIGEST</h1>"

    mock_ung_instance.dispatch_brief.assert_called_once()
    kwargs = mock_ung_instance.dispatch_brief.call_args[1]
    assert kwargs["ticker"] == "DAILY_DIGEST"
    assert kwargs["html_payload"] == "<html><h1>MEGA DIGEST</h1></html>"


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
