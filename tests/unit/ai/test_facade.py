from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.facade import LLMServiceFacade
from src.domain.schemas.ai_response import AssetInsight, MacroAnalysis, SentimentEnum


@pytest.fixture
def mock_genai_client():
    with patch("src.ai.facade.genai.Client") as mock_client_class:
        mock_instance = MagicMock()
        mock_aio = AsyncMock()

        # Structure: client.aio.models.generate_content
        mock_instance.aio.models = mock_aio
        mock_client_class.return_value = mock_instance
        yield mock_aio


@pytest.mark.asyncio
@patch("src.ai.facade.settings.GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
async def test_generate_brief_success(mock_genai_client):
    # Setup our fake successful LLM response using your existing domain models
    fake_response = MagicMock()
    fake_candidate = MagicMock()
    fake_candidate.finish_reason = "STOP"
    fake_response.candidates = [fake_candidate]

    fake_response.parsed = MacroAnalysis(
        macro_sentiment=SentimentEnum.BULLISH,
        sector_rotation="Energy sector showing strength.",
        insights=[
            AssetInsight(
                sentiment=SentimentEnum.BULLISH,
                catalyst="Strong Q3 earnings and increased guidance.",
                actionable_edge="Consider accumulating on dips below 1400.",
            )
        ],
    )
    mock_genai_client.generate_content.return_value = fake_response

    # Run the facade
    facade = LLMServiceFacade()
    result = await facade.generate_brief({"ticker": "RELIANCE"}, "You are an expert analyst.")

    # Assertions
    assert isinstance(result, MacroAnalysis)
    assert result.macro_sentiment == SentimentEnum.BULLISH
    assert len(result.insights) == 1
    assert result.insights[0].catalyst == "Strong Q3 earnings and increased guidance."

    mock_genai_client.generate_content.assert_called_once()

    # Verify the config was passed to enforce JSON
    call_kwargs = mock_genai_client.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.1-flash-lite-preview"
    assert call_kwargs["config"].response_mime_type == "application/json"
    # Ensure the system prompt is safely isolated in the config
    assert call_kwargs["config"].system_instruction == "You are an expert analyst."
    # Ensure the contents ONLY contain the data payload
    assert call_kwargs["contents"] == '{"ticker": "RELIANCE"}'
