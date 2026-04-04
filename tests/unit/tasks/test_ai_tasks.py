from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.ai_tasks import _process_ai_brief


@pytest.mark.asyncio
@patch("src.tasks.workers.ai_tasks.AsyncSessionLocal")  # Added mock for DB Session
@patch("src.tasks.workers.ai_tasks.BriefRepository")
@patch("src.tasks.workers.ai_tasks.MarkdownFormatter.format_brief")  # Added mock for Formatter
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

    # Mock the DB Session Context Manager
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    # Mock the Repository
    mock_repo_instance = AsyncMock()
    mock_repo_instance.save_brief.return_value = 42  # Integer DB ID
    mock_repo_class.return_value = mock_repo_instance

    # 2. Execute (Now passing the required task ID!)
    result = await _process_ai_brief(s3_uri, fake_task_id)

    # 3. Assertions
    assert result == 42
    mock_s3_instance.download_json.assert_called_with(s3_uri)
    mock_builder.assert_called_with(mock_s3_instance.download_json.return_value)
    mock_facade_instance.generate_brief.assert_called_with(
        sanitized_context={"clean": "data"}, system_prompt="System prompt"
    )

    # Verify the Repository was called with the exact right data mapped
    mock_repo_instance.save_brief.assert_called_with(
        target_id=1,
        celery_task_id=fake_task_id,
        s3_uri=s3_uri,
        markdown_report="# Fake Markdown Report",
        ai_result=mock_fake_analysis,
    )
