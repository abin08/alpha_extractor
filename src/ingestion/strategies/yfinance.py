import asyncio
from typing import Any

import yfinance as yf

from src.core.exceptions import SourceOfflineError
from src.core.logger import get_logger
from src.ingestion.base import DataFetcher
from src.ingestion.factory import DataSource, FetcherFactory

logger = get_logger(__name__)


@FetcherFactory.register(DataSource.YFINANCE)
class YFinanceFetcher(DataFetcher):
    """
    Concrete implementation of DataFetcher using the yfinance library.
    Wraps blocking network I/O in asyncio.to_thread and ensures JSON serialization.
    """

    def _get_history_sync(self, ticker: str, period: str) -> dict[str, Any]:
        """Synchronous method to execute the yfinance API call and parse pandas data."""
        logger.info(f"Initiating yfinance history fetch for ticker: {ticker}, period: {period}")
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
        except Exception as e:
            # yfinance throws generic exceptions on network failure
            raise SourceOfflineError(source="yfinance") from e

        if df.empty:
            logger.warning(f"yfinance returned empty historical data for ticker: {ticker}")
            return {"ticker": ticker, "data": []}

        logger.info(f"Successfully retrieved {len(df)} historical records for {ticker}")

        # Reset index so 'Date' or 'Datetime' becomes a standard column
        df.reset_index(inplace=True)

        # Convert datetime objects to strings so Celery can serialize it to JSON
        time_col = "Date" if "Date" in df.columns else "Datetime"
        if time_col in df.columns:
            df[time_col] = df[time_col].astype(str)

        return {"ticker": ticker, "data": df.to_dict(orient="records")}

    async def fetch_price_history(self, ticker: str, period: str = "1mo") -> dict[str, Any]:
        """Asynchronously fetch historical price data."""
        return await asyncio.to_thread(self._get_history_sync, ticker, period)

    def _get_info_sync(self, ticker: str) -> dict[str, Any]:
        """Synchronous method to fetch company metadata."""
        logger.info(f"Initiating yfinance company info fetch for ticker: {ticker}")
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info:
            logger.warning(f"yfinance returned empty company info for ticker: {ticker}")

        return info

    async def fetch_company_info(self, ticker: str) -> dict[str, Any]:
        """Asynchronously fetch fundamental company information."""
        return await asyncio.to_thread(self._get_info_sync, ticker)

    def _get_news_sync(self, ticker: str) -> list[dict[str, Any]]:
        """Synchronous method to fetch news from yfinance."""
        stock = yf.Ticker(ticker)
        return stock.news

    async def fetch_news(self, ticker: str) -> list[dict[str, Any]]:
        """Asynchronously fetch recent news articles related to the ticker."""
        logger.info(f"Initiating yfinance news fetch for ticker: {ticker}")
        return await asyncio.to_thread(self._get_news_sync, ticker)
