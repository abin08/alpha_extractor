import asyncio
from typing import Any

import aiohttp
import feedparser

from src.core.config import settings
from src.core.exceptions import RateLimitExceeded, SourceOfflineError
from src.core.logger import get_logger
from src.ingestion.base import DataFetcher
from src.ingestion.circuit_breaker import circuit_breaker
from src.ingestion.factory import DataSource, FetcherFactory
from src.ingestion.resilience import with_retry_and_jitter

logger = get_logger(__name__)


@FetcherFactory.register(DataSource.RSS_FEED)
class RssFeedFetcher(DataFetcher):
    """Asynchronously fetches and parses multiple RSS feeds concurrently."""

    async def fetch_price_history(self, ticker: str, period: str = "1mo") -> dict[str, Any]:
        return {"ticker": ticker, "data": []}

    async def fetch_company_info(self, ticker: str) -> dict[str, Any]:
        return {}

    @circuit_breaker(source_name="RSS", failure_threshold=5, recovery_timeout=300)
    @with_retry_and_jitter()
    async def _fetch_single_feed(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            logger.info(f"Initiating RSS fetch from: {url}")
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                logger.warning(f"Rate limited by {url}")
                raise RateLimitExceeded(source=url)
            logger.error(f"HTTP error fetching {url}: {e.status}")
            raise SourceOfflineError(source=url, status_code=e.status)
        except TimeoutError:
            logger.error(f"Timeout fetching {url}")
            raise SourceOfflineError(source=url)
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")
            return ""

    async def fetch_news(self, ticker: str, company_name: str = "") -> list[dict[str, Any]]:
        """
        Uses asyncio.gather to pull all RSS feeds simultaneously,
        then parses them and filters articles containing the requested ticker.
        """
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single_feed(session, url) for url in settings.RSS_URLS]
            xml_responses = await asyncio.gather(*tasks)

        articles = []
        search_terms = [ticker.split(".")[0].lower()]
        if company_name:
            search_terms.append(company_name.lower())
            # Also add the first word of the company name as a fallback
            # (e.g., "Reliance" from "Reliance Industries")
            first_word = company_name.split()[0].lower()
            if first_word not in search_terms and len(first_word) > 3:
                search_terms.append(first_word)

        for xml_content in xml_responses:
            if not xml_content:
                continue

            feed = await asyncio.to_thread(feedparser.parse, xml_content)

            if feed.bozo and not feed.entries:
                logger.warning("Malformed RSS XML detected.")
                # We log it instead of raising to allow other concurrent feeds to succeed
                continue

            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")

                title_lower = title.lower()
                summary_lower = summary.lower()

                if ticker == "MARKET" or any(
                    term in title_lower or term in summary_lower for term in search_terms
                ):
                    articles.append(
                        {
                            "title": title,
                            "link": entry.get("link", ""),
                            "published": entry.get("published", ""),
                            "summary": summary,
                        }
                    )

        logger.info(f"Aggregated {len(articles)} relevant news articles for {ticker}")
        return articles[:50]
