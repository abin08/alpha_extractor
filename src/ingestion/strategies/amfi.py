from typing import Any

import aiohttp

from src.core.config import settings
from src.core.exceptions import DataParsingError, RateLimitExceeded, SourceOfflineError
from src.core.logger import get_logger
from src.ingestion.base import DataFetcher
from src.ingestion.factory import DataSource, FetcherFactory

logger = get_logger(__name__)


@FetcherFactory.register(DataSource.AMFI)
class AMFIFetcher(DataFetcher):
    """
    Downloads and parses the daily NAV text file from AMFI.
    File format is semicolon-delimited:
    Scheme Code;ISIN Div;ISIN Reinv;Scheme Name;Net Asset Value;Date
    """

    async def _download_amfi_data(self) -> str:
        """Asynchronously downloads the raw text file."""
        logger.info(f"Downloading raw AMFI data from {settings.AMFI_URL}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(settings.AMFI_URL) as response:
                    response.raise_for_status()
                    return await response.text()
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                raise RateLimitExceeded(source="AMFI")
            raise SourceOfflineError(source="AMFI", status_code=e.status)
        except aiohttp.ClientError:
            raise SourceOfflineError(source="AMFI")

    async def fetch_price_history(self, ticker: str, period: str = "latest") -> dict[str, Any]:
        """
        Parses the daily file to find the latest NAV for a specific Scheme Code.
        Maps the NAV to the 'Close' key to maintain compatibility with equities.
        """
        raw_text = await self._download_amfi_data()

        if not raw_text or "Scheme Code" not in raw_text:
            raise DataParsingError(
                source="AMFI", details="Raw text is empty or missing expected headers."
            )

        for line in raw_text.splitlines():
            # Skip empty lines and headers
            if not line or line.startswith("Scheme Code") or ";" not in line:
                continue

            parts = line.split(";")
            if len(parts) >= 6 and parts[0] == ticker:
                logger.info(f"Found NAV data for Scheme Code: {ticker}")
                return {
                    "ticker": ticker,
                    "data": [
                        {
                            "Date": parts[5].strip(),
                            "Close": (float(parts[4].strip()) if parts[4].strip() else None),
                        }
                    ],
                }

        logger.warning(f"Scheme Code {ticker} not found in AMFI data.")
        return {"ticker": ticker, "data": []}

    async def fetch_company_info(self, ticker: str) -> dict[str, Any]:
        """
        Parses the daily file to extract fundamental scheme details.
        """
        raw_text = await self._download_amfi_data()

        if not raw_text or "Scheme Code" not in raw_text:
            raise DataParsingError(
                source="AMFI", details="Raw text is empty or missing expected headers."
            )

        for line in raw_text.splitlines():
            if not line or line.startswith("Scheme Code") or ";" not in line:
                continue

            parts = line.split(";")
            if len(parts) >= 6 and parts[0] == ticker:
                return {
                    "symbol": parts[0].strip(),
                    "isin": parts[1].strip() or parts[2].strip(),  # Use whichever ISIN is available
                    "shortName": parts[3].strip(),
                    "assetClass": "Mutual Fund",
                }

        return {}

    async def fetch_news(self, ticker: str) -> list[dict[str, Any]]:
        """Mutual funds do not have direct news feeds in AMFI. Returns empty list."""
        logger.debug(f"News requested from AMFI strategy for {ticker}. Returning empty list.")
        return []
