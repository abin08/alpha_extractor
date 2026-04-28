from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import LLMGenerationError
from src.tasks.workers.ai_tasks import _process_ai_brief, generate_ai_brief_task


@pytest.mark.asyncio
@patch("src.tasks.workers.ai_tasks.AsyncSessionLocal")
@patch("src.tasks.workers.ai_tasks.BriefRepository")
@patch("src.tasks.workers.ai_tasks.MarkdownFormatter.format_brief")
@patch("src.tasks.workers.ai_tasks.LLMServiceFacade")
@patch("src.tasks.workers.ai_tasks.get_system_prompt")
@patch("src.tasks.workers.ai_tasks.ContextBuilder.build")
@patch("src.tasks.workers.ai_tasks.AsyncS3Client")
async def test_process_ai_brief_success(
    mock_s3_class,
    mock_builder,
    mock_prompt,
    mock_facade_class,
    mock_formatter,
    mock_repo_class,
    mock_session_local,
):
    """Test the async AI processing engine coordinates all components successfully."""

    # 1. Setup Data & Mocks
    s3_uri = "s3://fake-bucket/payload.json"
    fake_task_id = "celery-task-id-999"

    mock_s3_instance = AsyncMock()
    mock_s3_instance.download_json.return_value = {
        "raw": "data",
        "asset": {"id": 1, "internal_symbol": "TEST.NS"},
    }
    mock_s3_class.return_value = mock_s3_instance

    mock_builder.return_value = {"clean": "data"}
    mock_prompt.return_value = "System prompt"

    mock_facade_instance = AsyncMock()
    mock_fake_analysis = MagicMock()
    mock_facade_instance.generate_brief.return_value = mock_fake_analysis
    mock_facade_class.return_value = mock_facade_instance

    mock_formatter.return_value = "# Fake Markdown Report"

    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_repo_instance = AsyncMock()
    mock_repo_instance.save_brief.return_value = 42
    mock_repo_class.return_value = mock_repo_instance

    # 2. Execute
    result = await _process_ai_brief(s3_uri, fake_task_id)

    # 3. Assertions
    assert result == 42
    mock_s3_instance.download_json.assert_called_with(s3_uri)
    mock_builder.assert_called_with(mock_s3_instance.download_json.return_value)
    mock_facade_instance.generate_brief.assert_called_with(
        sanitized_context={"clean": "data"}, system_prompt="System prompt"
    )

    mock_repo_instance.save_brief.assert_called_with(
        ticker="TEST.NS",
        celery_task_id=fake_task_id,
        s3_uri=s3_uri,
        markdown_report="# Fake Markdown Report",
        ai_result=mock_fake_analysis,
    )


# --- WRAPPER TESTS ---


@patch("src.tasks.workers.ai_tasks._process_ai_brief", new_callable=MagicMock)
@patch("src.tasks.workers.ai_tasks.asyncio.run")
def test_generate_ai_brief_task_success(mock_run, mock_core):
    """Test the happy path of the Celery wrapper returning a graceful dict."""
    mock_self = MagicMock()
    mock_run.return_value = 100
    dummy_coro = MagicMock(name="coro")
    mock_core.return_value = dummy_coro

    # Act
    payload = {"status": "success", "ticker": "TEST.NS", "s3_uri": "s3://uri"}
    result = generate_ai_brief_task.run.__func__(mock_self, payload)

    # Assert
    assert result["status"] == "success"
    assert result["ticker"] == "TEST.NS"
    assert result["job_id"] == 100
    mock_run.assert_called_once_with(dummy_coro)


def test_generate_ai_brief_task_short_circuit():
    """Test that if the ingestion task passed an error, the AI task short-circuits."""
    mock_self = MagicMock()

    # Act
    error_payload = {
        "status": "error",
        "ticker": "TEST.NS",
        "error_msg": "Upstream failed",
    }
    result = generate_ai_brief_task.run.__func__(mock_self, error_payload)

    # Assert
    # It should immediately return the exact payload without running the AI engine
    assert result == error_payload


@patch("src.tasks.workers.ai_tasks._process_ai_brief", new_callable=MagicMock)
@patch("src.tasks.workers.ai_tasks.asyncio.run")
def test_generate_ai_brief_task_retry(mock_run, mock_core):
    """Test that transient errors still trigger a Celery retry."""
    mock_self = MagicMock()
    mock_self.request.retries = 0
    mock_self.max_retries = 3

    mock_run.side_effect = Exception("LLM Timeout")
    mock_self.retry.side_effect = Exception("Retry Invoked")

    payload = {"status": "success", "ticker": "TEST.NS", "s3_uri": "s3://uri"}

    # Act & Assert
    with pytest.raises(Exception, match="Retry Invoked"):
        generate_ai_brief_task.run.__func__(mock_self, payload)

    assert mock_self.retry.called
    args, kwargs = mock_self.retry.call_args
    assert kwargs["countdown"] == 60


@patch("src.tasks.workers.ai_tasks.alert_failed_task")
@patch("src.tasks.workers.ai_tasks._process_ai_brief", new_callable=MagicMock)
@patch("src.tasks.workers.ai_tasks.asyncio.run")
def test_generate_ai_brief_task_max_retries_exhausted(mock_run, mock_core, mock_alert):
    """Test that reaching max retries degrades gracefully and fires the DLQ."""
    mock_self = MagicMock()
    mock_self.request.retries = 3
    mock_self.max_retries = 3
    mock_run.side_effect = Exception("Permanent network failure")

    payload = {"status": "success", "ticker": "TEST.NS", "s3_uri": "s3://uri"}

    # Act
    result = generate_ai_brief_task.run.__func__(mock_self, payload)

    # Assert graceful dictionary
    assert result["status"] == "error"
    assert result["ticker"] == "TEST.NS"
    assert result["job_id"] is None
    assert result["error_msg"] == "Permanent network failure"

    # Assert the DLQ alert was manually tripped
    mock_alert.delay.assert_called_once()
    mock_self.retry.assert_not_called()


@patch("src.tasks.workers.ai_tasks.alert_failed_task")
@patch("src.tasks.workers.ai_tasks._process_ai_brief", new_callable=MagicMock)
@patch("src.tasks.workers.ai_tasks.asyncio.run")
def test_generate_ai_brief_task_llm_error(mock_run, mock_core, mock_alert):
    """Test that a deterministic LLM logic error fails fast and degrades gracefully."""
    mock_self = MagicMock()
    mock_run.side_effect = LLMGenerationError("Gemini API refused prompt")

    payload = {"status": "success", "ticker": "TEST.NS", "s3_uri": "s3://uri"}

    # Act
    result = generate_ai_brief_task.run.__func__(mock_self, payload)

    # Assert
    assert result["status"] == "error"
    assert result["ticker"] == "TEST.NS"
    assert "Gemini API refused prompt" in result["error_msg"]

    mock_alert.delay.assert_called_once()
    mock_self.retry.assert_not_called()
