from datetime import datetime

from src.core.logger import get_logger
from src.domain.schemas.ai_response import MacroAnalysis, SentimentEnum

logger = get_logger(__name__)


class MarkdownFormatter:
    """
    Translates the structured MacroAnalysis AI output into highly readable,
    executive-level Markdown. This isolates the Presentation Layer from the
    AI generation and database persistence layers.
    """

    # Map sentiments to instant visual indicators for quick scannability
    SENTIMENT_ICONS = {
        SentimentEnum.BULLISH: "🟢 **BULLISH**",
        SentimentEnum.BEARISH: "🔴 **BEARISH**",
        SentimentEnum.NEUTRAL: "⚪ **NEUTRAL**",
    }

    @classmethod
    def format_brief(cls, analysis: MacroAnalysis, target_name: str = "Market Update") -> str:
        """
        Compiles the MacroAnalysis object into a stylized Markdown string.

        Args:
            analysis (MacroAnalysis): The validated JSON output from the Gemini LLM.
            target_name (str): The name of the primary asset or index analyzed.

        Returns:
            str: The fully formatted Markdown report.
        """
        logger.debug("Formatting MacroAnalysis into Markdown presentation...")

        # 1. Header & Timestamp
        date_str = datetime.now().strftime("%B %d, %Y - %H:%M %Z").strip()
        md_lines = [
            f"# 🦅 Alpha Extractor: {target_name}",
            f"**Generated:** {date_str}",
            "---",
        ]

        # 2. Macro Market Overview
        macro_icon = cls.SENTIMENT_ICONS.get(analysis.macro_sentiment, "⚪ **UNKNOWN**")
        md_lines.extend([f"## 🌍 Macro Overview [{macro_icon}]", f"{analysis.sector_rotation}", ""])

        # 3. Individual Asset Insights
        if not analysis.insights:
            md_lines.append("> *No actionable asset insights detected in this run.*")
        else:
            md_lines.append("## 📊 Actionable Asset Insights")

            # Iterate through the list of AssetInsight objects
            for index, insight in enumerate(analysis.insights, start=1):
                asset_icon = cls.SENTIMENT_ICONS.get(insight.sentiment, "⚪ **UNKNOWN**")

                md_lines.extend(
                    [
                        f"### Insight {index} [{asset_icon}]",
                        f"**Catalyst:** {insight.catalyst}",
                        f"> **Actionable Edge:** {insight.actionable_edge}",
                        "",
                    ]
                )

        # 4. Footer
        md_lines.extend(["---", "*Generated autonomously by the Alpha Extractor AI Engine.*"])

        return "\n".join(md_lines)
