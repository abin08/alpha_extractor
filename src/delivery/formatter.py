from datetime import datetime
from zoneinfo import ZoneInfo

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
        ist_tz = ZoneInfo("Asia/Kolkata")
        date_str = datetime.now().strftime("%B %d, %Y - %H:%M %Z").strip()
        date_str = datetime.now(ist_tz).strftime("%B %d, %Y - %H:%M %Z").strip()
        md_lines = [
            f"#Alpha Extractor: {target_name}",
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

    @staticmethod
    def format_daily_digest(brief_map: dict[str, str]) -> str:
        """
        Stitches multiple individual asset briefs into a single Daily Digest Markdown payload.
        Handles the fallback gracefully if all assets failed in the pipeline.
        """
        if not brief_map:
            return (
                "# Alpha Extractor: Daily Digest\n\n"
                "*System Alert: The pipeline ran, but no data could be "
                "extracted or processed today. "
                "Please check the system logs for details.*"
            )

        lines = ["# Alpha Extractor: Daily Digest\n"]
        lines.append("## Table of Contents")

        # 1. Build the Table of Contents
        for ticker in brief_map.keys():
            # Create URL-safe anchors for Markdown
            anchor = ticker.lower().replace(".", "").replace(" ", "-")
            lines.append(f"* [{ticker}](#{anchor})")

        lines.append("\n---\n")

        # 2. Append each individual brief
        for ticker, markdown in brief_map.items():
            # Inject the invisible HTML anchor target so the ToC links work
            lines.append(f'<a id="{ticker.lower().replace(".", "").replace(" ", "-")}"></a>')
            lines.append(markdown)
            lines.append("\n---\n")

        return "\n".join(lines)
