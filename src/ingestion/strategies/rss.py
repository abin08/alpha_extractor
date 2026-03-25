import asyncio
import logging
from typing import Any

import aiohttp
import feedparser

from src.core.config import settings
from src.ingestion.base import DataFetcher
from src.ingestion.factory import DataSource, FetcherFactory

logger = logging.getLogger(__name__)


@FetcherFactory.register(DataSource.RSS_FEED)
class RssFeedFetcher(DataFetcher):
    """Asynchronously fetches and parses multiple RSS feeds concurrently."""

    async def fetch_price_history(self, ticker: str, period: str = "1mo") -> dict[str, Any]:
        return {"ticker": ticker, "data": []}

    async def fetch_company_info(self, ticker: str) -> dict[str, Any]:
        return {}

    async def _fetch_single_feed(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            logger.info(f"Initiating RSS fetch from: {url}")
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")
            return ""

    async def fetch_news(self, ticker: str) -> list[dict[str, Any]]:
        """
        Uses asyncio.gather to pull all RSS feeds simultaneously,
        then parses them and filters articles containing the requested ticker.
        """
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single_feed(session, url) for url in settings.RSS_URLS]
            xml_responses = await asyncio.gather(*tasks)

        articles = []
        for xml_content in xml_responses:
            if not xml_content:
                continue

            feed = await asyncio.to_thread(feedparser.parse, xml_content)

            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")

                if (
                    ticker.lower() in title.lower()
                    or ticker.lower() in summary.lower()
                    or ticker == "MARKET"
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
