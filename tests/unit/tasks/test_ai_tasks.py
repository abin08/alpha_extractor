from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.ai_tasks import _process_ai_brief


@pytest.mark.asyncio
@patch("src.tasks.workers.ai_tasks.BriefRepository")
@patch("src.tasks.workers.ai_tasks.LLMServiceFacade")
@patch("src.tasks.workers.ai_tasks.get_system_prompt")
@patch("src.tasks.workers.ai_tasks.ContextBuilder.build")
@patch("src.tasks.workers.ai_tasks.AsyncS3Client")
async def test_process_ai_brief_success(
    mock_s3_class, mock_builder, mock_prompt, mock_facade_class, mock_repo_class
):
    """Test the async AI processing engine coordinates all components successfully."""

    # 1. Setup Mocks
    mock_s3_instance = AsyncMock()
    mock_s3_instance.download_json.return_value = {"raw": "data"}
    mock_s3_class.return_value = mock_s3_instance

    mock_builder.return_value = {"clean": "data"}
    mock_prompt.return_value = "System prompt"

    mock_facade_instance = AsyncMock()
    mock_fake_analysis = MagicMock()  # Simulating the MacroAnalysis pydantic object
    mock_facade_instance.generate_brief.return_value = mock_fake_analysis
    mock_facade_class.return_value = mock_facade_instance

    mock_repo_instance = AsyncMock()
    mock_repo_instance.save_brief.return_value = "db-uuid-1234"
    mock_repo_class.return_value = mock_repo_instance

    # 2. Execute
    s3_uri = "s3://fake-bucket/payload.json"
    result = await _process_ai_brief(s3_uri)

    # 3. Assertions
    assert result == "db-uuid-1234"
    mock_s3_instance.download_json.assert_called_with(s3_uri)
    mock_builder.assert_called_with({"raw": "data"})
    mock_facade_instance.generate_brief.assert_called_with(
        sanitized_context={"clean": "data"}, system_prompt="System prompt"
    )
    mock_repo_instance.save_brief.assert_called_with(mock_fake_analysis)
