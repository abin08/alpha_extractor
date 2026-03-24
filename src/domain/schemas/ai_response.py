import enum

from pydantic import BaseModel, Field


class SentimentEnum(enum.StrEnum):
    """Enforces a strict set of sentiments so the AI doesn't hallucinate new ones."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class AssetInsight(BaseModel):
    """
    The exact JSON contract we expect Google Gemini to return
    after analyzing the raw market data for a specific asset.
    """

    sentiment: SentimentEnum = Field(
        ..., description="The extracted market sentiment for the target asset."
    )
    catalyst: str = Field(
        ...,
        description="""The specific news event, earnings metric, or
        market driver causing this sentiment.""",
    )
    actionable_edge: str = Field(
        ..., description="The tactical, actionable takeaway based on the catalyst."
    )


class MacroAnalysis(BaseModel):
    """
    The JSON contract for the overarching market sentiment
    during a specific job run.
    """

    macro_sentiment: SentimentEnum = Field(
        ..., description="The overall market sentiment across all analyzed data."
    )
    sector_rotation: str = Field(
        ...,
        description="A brief summary of any observed sector rotations or macro trends.",
    )
    insights: list[AssetInsight] = Field(
        default_factory=list,
        description="A list of specific insights for the requested target assets.",
    )
