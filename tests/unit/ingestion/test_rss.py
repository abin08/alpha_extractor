from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.strategies.rss import RssFeedFetcher

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Mock Financial News</title>
  <item>
    <title>Reliance Industries hits all time high</title>
    <link>http://example.com/reliance</link>
    <published>Tue, 24 Mar 2026 10:00:00 GMT</published>
    <summary>Reliance is doing great today in the markets.</summary>
  </item>
</channel>
</rss>
"""


@pytest.fixture
def fetcher():
    return RssFeedFetcher()


@pytest.mark.asyncio
@patch("src.ingestion.strategies.rss.aiohttp.ClientSession.get")
async def test_fetch_news(mock_get, fetcher):
    # 1. Arrange
    mock_response = AsyncMock()
    mock_response.text.return_value = MOCK_RSS_XML
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value.__aenter__.return_value = mock_response

    # 2. Act
    result = await fetcher.fetch_news("Reliance")

    # 3. Assert
    assert len(result) == 2  # Assuming 2 RSS URLs fetch the same mock
    assert "Reliance Industries hits all time high" in result[0]["title"]


@pytest.mark.asyncio
async def test_empty_methods(fetcher):
    price_data = await fetcher.fetch_price_history("RELIANCE.NS")
    info_data = await fetcher.fetch_company_info("RELIANCE.NS")

    assert price_data["data"] == []
    assert info_data == {}
