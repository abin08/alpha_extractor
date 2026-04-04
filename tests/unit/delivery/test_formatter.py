from src.delivery.formatter import MarkdownFormatter
from src.domain.schemas.ai_response import AssetInsight, MacroAnalysis, SentimentEnum


def test_format_brief_with_insights():
    """Test that a fully populated MacroAnalysis object formats correctly."""
    analysis = MacroAnalysis(
        macro_sentiment=SentimentEnum.BEARISH,
        sector_rotation="Tech is struggling, utilities are safe.",
        insights=[
            AssetInsight(
                sentiment=SentimentEnum.BULLISH,
                catalyst="Stellar Q4 Earnings.",
                actionable_edge="Buy the dip at 150.",
            )
        ],
    )

    result = MarkdownFormatter.format_brief(analysis, target_name="Test Asset")

    # Assert Header
    assert "🦅 Alpha Extractor: Test Asset" in result

    # Assert Macro Section (Should map BEARISH to the red circle)
    assert "🔴 **BEARISH**" in result
    assert "Tech is struggling, utilities are safe." in result

    # Assert Insights Section (Should map BULLISH to the green circle)
    assert "🟢 **BULLISH**" in result
    assert "**Catalyst:** Stellar Q4 Earnings." in result
    assert "> **Actionable Edge:** Buy the dip at 150." in result


def test_format_brief_empty_insights():
    """Test that the formatter safely handles an analysis with no specific asset insights."""
    analysis = MacroAnalysis(
        macro_sentiment=SentimentEnum.NEUTRAL,
        sector_rotation="Flat market.",
        insights=[],
    )

    result = MarkdownFormatter.format_brief(analysis, target_name="Boring Asset")

    assert "⚪ **NEUTRAL**" in result
    assert "*No actionable asset insights detected in this run.*" in result
