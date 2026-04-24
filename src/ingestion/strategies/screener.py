# src/ingestion/strategies/screener.py
import asyncio
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from src.core.config import settings
from src.core.exceptions import DataParsingError, RateLimitExceeded, SourceOfflineError
from src.core.logger import get_logger
from src.domain.models import AssetContext
from src.ingestion.base import DataFetcher
from src.ingestion.circuit_breaker import circuit_breaker
from src.ingestion.factory import DataSource, FetcherFactory
from src.ingestion.resilience import with_retry_and_jitter

logger = get_logger(__name__)


@FetcherFactory.register(DataSource.SCREENER)
class ScreenerFetcher(DataFetcher):
    """
    Scrapes Screener.in for deep corporate fundamentals and qualitative insights.
    Relies on HTML DOM parsing using BeautifulSoup4.
    """

    # Use a standard browser User-Agent to prevent basic bot-blocking
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    @circuit_breaker(source_name="Screener", failure_threshold=3, recovery_timeout=900)
    @with_retry_and_jitter()
    async def _fetch_html(self, screener_symbol: str) -> str:
        # Target the consolidated financials page by default
        url = f"{settings.SCREENER_BASE_URL}/company/{screener_symbol}/consolidated/"
        fallback_url = f"{settings.SCREENER_BASE_URL}/company/{screener_symbol}/"

        logger.info(f"Downloading Screener HTML for {screener_symbol} from {url}")
        try:
            async with aiohttp.ClientSession(headers=self.HEADERS) as session:
                async with session.get(url, timeout=15) as response:
                    # Some companies don't have consolidated data, Screener redirects to standalone
                    if response.status == 404 and "consolidated" in url:
                        logger.info(
                            f"Consolidated not found for {screener_symbol}, "
                            f"falling back to {fallback_url}"
                        )
                        async with session.get(fallback_url, timeout=15) as fallback_resp:
                            fallback_resp.raise_for_status()
                            return await fallback_resp.text()

                    response.raise_for_status()
                    return await response.text()

        except aiohttp.ClientResponseError as e:
            if e.status in (429, 403):  # 403 is often used by WAFs to block bots
                raise RateLimitExceeded(source="Screener")
            raise SourceOfflineError(source="Screener", status_code=e.status)
        except TimeoutError:
            raise SourceOfflineError(source="Screener")

    def _parse_html_sync(self, html: str, screener_symbol: str) -> dict[str, Any]:
        """Synchronous CPU-bound method to extract data using BeautifulSoup."""
        soup = BeautifulSoup(html, "lxml")

        # 1. Verify page structure (Fail-Fast)
        ratios_ul = soup.find("ul", id="top-ratios")
        if not ratios_ul:
            raise DataParsingError(
                source="Screener",
                details=f"Missing ul#top-ratios for {screener_symbol}",
            )

        # 2. Extract Ratios
        ratios = {}
        for li in ratios_ul.find_all("li"):  # type: ignore
            name = li.find("span", class_="name")
            number = li.find("span", class_="number")
            if name and number:
                # Clean up whitespace and newlines
                clean_name = " ".join(name.text.split())
                clean_number = " ".join(number.text.split())
                ratios[clean_name] = clean_number

        # 3. Extract Pros & Cons
        pros = [li.text.strip() for li in soup.select("div.pros ul li")]
        cons = [li.text.strip() for li in soup.select("div.cons ul li")]

        # 4. Extract About section
        about_div = soup.select_one("div.company-profile-wrapper div.sub.about p")
        about_text = about_div.text.strip() if about_div else ""

        return {
            "ticker": screener_symbol,
            "about": about_text,
            "ratios": ratios,
            "pros": pros,
            "cons": cons,
        }

    async def fetch_company_info(self, asset: AssetContext) -> dict[str, Any]:
        # Fail-fast if this asset doesn't support Screener
        if not asset.screener_symbol:
            logger.info(f"Skipping Screener for {asset.internal_symbol} - No mapping provided.")
            return {}

        html = await self._fetch_html(asset.screener_symbol)
        return await asyncio.to_thread(self._parse_html_sync, html, asset.screener_symbol)

    async def fetch_price_history(self, asset: AssetContext, period: str = "1mo") -> dict[str, Any]:
        return {"ticker": asset.screener_symbol, "data": []}

    async def fetch_news(self, asset: AssetContext) -> list[dict[str, Any]]:
        return []
