import asyncio
from typing import Any

import yfinance as yf

from src.core.exceptions import SourceOfflineError
from src.core.logger import get_logger
from src.domain.models import AssetContext
from src.ingestion.base import DataFetcher
from src.ingestion.circuit_breaker import circuit_breaker
from src.ingestion.factory import DataSource, FetcherFactory
from src.ingestion.resilience import with_retry_and_jitter

logger = get_logger(__name__)


@FetcherFactory.register(DataSource.YFINANCE)
class YFinanceFetcher(DataFetcher):
    """
    Concrete implementation of DataFetcher using the yfinance library.
    Wraps blocking network I/O in asyncio.to_thread and ensures JSON serialization.
    """

    def _get_history_sync(self, yfinance_symbol: str, period: str) -> dict[str, Any]:
        """Synchronous method to execute the yfinance API call and parse pandas data."""
        logger.info(
            f"Initiating yfinance history fetch for ticker: {yfinance_symbol}, period: {period}"
        )
        try:
            stock = yf.Ticker(yfinance_symbol)
            df = stock.history(period=period)
        except Exception as e:
            # yfinance throws generic exceptions on network failure
            raise SourceOfflineError(source="yfinance") from e

        if df.empty:
            logger.warning(f"yfinance returned empty historical data for ticker: {yfinance_symbol}")
            return {"ticker": yfinance_symbol, "data": []}

        logger.info(f"Successfully retrieved {len(df)} historical records for {yfinance_symbol}")

        # Reset index so 'Date' or 'Datetime' becomes a standard column
        df.reset_index(inplace=True)

        # Convert datetime objects to strings so Celery can serialize it to JSON
        time_col = "Date" if "Date" in df.columns else "Datetime"
        if time_col in df.columns:
            df[time_col] = df[time_col].astype(str)

        return {"ticker": yfinance_symbol, "data": df.to_dict(orient="records")}

    @circuit_breaker(source_name="YFinance", failure_threshold=5, recovery_timeout=900)
    @with_retry_and_jitter()
    async def fetch_price_history(self, asset: AssetContext, period: str = "1mo") -> dict[str, Any]:
        """Asynchronously fetch historical price data."""
        if not asset.yfinance_symbol:
            return {"ticker": asset.internal_symbol, "data": []}

        return await asyncio.to_thread(self._get_history_sync, asset.yfinance_symbol, period)

    def _get_info_sync(self, asset: AssetContext) -> dict[str, Any]:
        """Synchronous method to fetch company metadata."""
        logger.info(f"Initiating yfinance company info fetch for ticker: {asset.yfinance_symbol}")
        stock = yf.Ticker(asset.yfinance_symbol)
        info = stock.info

        if not info:
            logger.warning(
                f"yfinance returned empty company info for ticker: {asset.yfinance_symbol}"
            )

        return info

    async def fetch_company_info(self, asset: AssetContext) -> dict[str, Any]:
        """Asynchronously fetch fundamental company information."""
        if not asset.yfinance_symbol:
            return {}

        return await asyncio.to_thread(self._get_info_sync, asset)

    def _get_news_sync(self, asset: AssetContext) -> list[dict[str, Any]]:
        """Synchronous method to fetch news from yfinance."""
        stock = yf.Ticker(asset.yfinance_symbol)
        return stock.news

    @circuit_breaker(source_name="YFinance", failure_threshold=5, recovery_timeout=900)
    @with_retry_and_jitter()
    async def fetch_news(self, asset: AssetContext) -> list[dict[str, Any]]:
        """Asynchronously fetch recent news articles related to the ticker."""
        logger.info(f"Initiating yfinance news fetch for ticker: {asset.yfinance_symbol}")
        if not asset.yfinance_symbol:
            return {}

        return await asyncio.to_thread(self._get_info_sync, asset)
