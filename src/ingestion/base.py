from abc import ABC, abstractmethod
from typing import Any

from src.domain.models import AssetContext


class DataFetcher(ABC):
    """
    Abstract base class for all ingestion strategies.
    """

    @abstractmethod
    async def fetch_price_history(self, asset: AssetContext, period: str = "1mo") -> dict[str, Any]:
        """
        Fetches historical price data using the vendor-specific symbol.
        """
        pass

    @abstractmethod
    async def fetch_company_info(self, asset: AssetContext) -> dict[str, Any]:
        """
        Fetches fundamental company data using the vendor-specific symbol.
        """
        pass

    @abstractmethod
    async def fetch_news(asset: AssetContext) -> list[dict[str, Any]]:
        """Fetch unstructured news articles or context for a given ticker
        and optional company name."""
        pass
