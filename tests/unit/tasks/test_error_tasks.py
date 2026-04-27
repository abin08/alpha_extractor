from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.error_tasks import _dispatch_error_alert, alert_failed_task


@pytest.fixture
def mock_db_session():
    """Fixture to mock the AsyncSessionLocal and SQLAlchemy execution."""
    with patch("src.tasks.workers.error_tasks.AsyncSessionLocal") as mock_session_class:
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        yield mock_session


@pytest.mark.asyncio
@patch("src.tasks.workers.error_tasks.UNGClient")
async def test_dispatch_error_alert_success(mock_ung_class, mock_db_session):
    """Test 1: Verifies the DLQ Markdown is built and sent to UNG correctly."""
    # Arrange DB Mock to return a fake admin email
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["admin_dlq@alpha.com"]
    mock_db_session.scalars.return_value = mock_scalars

    # Arrange UNG Mock
    mock_ung_instance = mock_ung_class.return_value
    mock_ung_instance.dispatch_brief = AsyncMock(return_value=True)

    # Act
    await _dispatch_error_alert(
        task_id="uuid-123",
        task_name="tasks.ingest_asset",
        exception="ValueError: Pydantic failed",
        argsrepr="{'ticker': 'RELIANCE.NS'}",
    )

    # Assert
    # Verify the client was called with the specific "DLQ_ALERT" ticker and the new recipients array
    mock_ung_instance.dispatch_brief.assert_called_once()
    args, kwargs = mock_ung_instance.dispatch_brief.call_args

    assert kwargs["ticker"] == "DLQ_ALERT"
    assert kwargs["recipients"] == ["admin_dlq@alpha.com"]
    assert "DEAD LETTER QUEUE (DLQ) ALERT" in kwargs["markdown_payload"]
    assert "tasks.ingest_asset" in kwargs["markdown_payload"]
    assert "ValueError: Pydantic failed" in kwargs["markdown_payload"]


@patch("src.tasks.workers.error_tasks._dispatch_error_alert", new_callable=MagicMock)
@patch("src.tasks.workers.error_tasks.asyncio.run")
def test_alert_failed_task_wrapper(mock_asyncio_run, mock_dispatch_core):
    """Test 2: Verifies Celery wrapper extracts request data and boots asyncio."""
    # Arrange
    mock_request = {
        "id": "task-999",
        "task": "tasks.ai_gen",
        "argsrepr": "('payload_uri',)",
    }
    mock_exc = ValueError("Simulated Failure")

    # Act
    alert_failed_task(mock_request, mock_exc, "trace")

    # Assert
    mock_asyncio_run.assert_called_once()
    # Verify the core was called with correct stringified exception
    mock_dispatch_core.assert_called_once_with(
        "task-999", "tasks.ai_gen", "Simulated Failure", "('payload_uri',)"
    )


@patch("src.tasks.workers.error_tasks.logger")
@patch("src.tasks.workers.error_tasks._dispatch_error_alert", new_callable=MagicMock)
@patch("src.tasks.workers.error_tasks.asyncio.run")
def test_alert_failed_task_final_safety_net(mock_asyncio_run, mock_dispatch_core, mock_logger):
    """Test 3: If dispatching the alert fails, it must log critically and not crash."""
    # Arrange
    mock_asyncio_run.side_effect = Exception("UNG API is down")
    mock_request = {"id": "123", "task": "test"}

    # Act
    alert_failed_task(mock_request, Exception("Original"), "trace")

    # Assert
    mock_logger.critical.assert_called_once()
    assert "FATAL: Failed to send DLQ alert" in mock_logger.critical.call_args[0][0]
