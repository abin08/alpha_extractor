from abc import ABC, abstractmethod
from typing import Any


class DataFetcher(ABC):
    """
    Abstract Base Class defining the standard contract for all Big Data ingestion scrapers.
    """

    @abstractmethod
    async def fetch_price_history(self, ticker: str, period: str = "1mo") -> dict[str, Any]:
        """
        Fetch historical price data (OHLCV) for a given ticker.
        """
        pass

    @abstractmethod
    async def fetch_company_info(self, ticker: str) -> dict[str, Any]:
        """
        Fetch fundamental company information and metadata.
        """
        pass

    @abstractmethod
    async def fetch_news(self, ticker: str, company_name: str = "") -> list[dict[str, Any]]:
        """Fetch unstructured news articles or context for a given ticker
        and optional company name."""
        pass
