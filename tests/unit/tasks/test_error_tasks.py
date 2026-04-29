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
    """Test 1: Verifies the DLQ HTML is built and sent to UNG correctly."""
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
    mock_ung_instance.dispatch_brief.assert_called_once()
    args, kwargs = mock_ung_instance.dispatch_brief.call_args

    assert kwargs["ticker"] == "DLQ_ALERT"
    assert kwargs["recipients"] == ["admin_dlq@alpha.com"]

    # Assert specific HTML injection points
    html_payload = kwargs["html_payload"]
    assert (
        '<h2 style="color: #d9534f; margin-top: 0;">🚨 DEAD LETTER QUEUE (DLQ) ALERT</h2>'
        in html_payload
    )
    assert "<code>uuid-123</code>" in html_payload
    assert "<code>tasks.ingest_asset</code>" in html_payload
    assert "ValueError: Pydantic failed" in html_payload


@patch("src.tasks.workers.error_tasks._dispatch_error_alert", new_callable=MagicMock)
@patch("src.tasks.workers.error_tasks.asyncio.run")
def test_alert_failed_task_wrapper(mock_asyncio_run, mock_dispatch_core):
    """Test 2: Verifies Celery wrapper extracts request data and boots asyncio."""
    mock_request = {
        "id": "task-999",
        "task": "tasks.ai_gen",
        "argsrepr": "('payload_uri',)",
    }
    mock_exc = ValueError("Simulated Failure")

    alert_failed_task(mock_request, mock_exc, "trace")

    mock_asyncio_run.assert_called_once()
    mock_dispatch_core.assert_called_once_with(
        "task-999", "tasks.ai_gen", "Simulated Failure", "('payload_uri',)"
    )


@patch("src.tasks.workers.error_tasks.logger")
@patch("src.tasks.workers.error_tasks._dispatch_error_alert", new_callable=MagicMock)
@patch("src.tasks.workers.error_tasks.asyncio.run")
def test_alert_failed_task_final_safety_net(mock_asyncio_run, mock_dispatch_core, mock_logger):
    """Test 3: If dispatching the alert fails, it must log critically and not crash."""
    mock_asyncio_run.side_effect = Exception("UNG API is down")
    mock_request = {"id": "123", "task": "test"}

    alert_failed_task(mock_request, Exception("Original"), "trace")

    mock_logger.critical.assert_called_once()
    assert "FATAL: Failed to send DLQ alert" in mock_logger.critical.call_args[0][0]
