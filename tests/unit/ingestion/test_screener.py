from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import DataParsingError
from src.ingestion.strategies.screener import ScreenerFetcher

MOCK_HTML = """
<html>
    <div class="company-profile-wrapper">
        <div class="sub about"><p>Reliance is a diversified conglomerate.</p></div>
    </div>
    <ul id="top-ratios">
        <li><span class="name">Market Cap</span><span class="number">₹ 20,00,000</span></li>
        <li><span class="name">Stock P/E</span><span class="number">28.5</span></li>
    </ul>
    <div class="pros"><ul><li>Company has reduced debt.</li></ul></div>
    <div class="cons"><ul><li>Stock is trading at 3 times its book value.</li></ul></div>
</html>
"""


@pytest.fixture
def fetcher():
    return ScreenerFetcher()


@pytest.mark.asyncio
@patch("src.ingestion.strategies.screener.aiohttp.ClientSession.get")
async def test_fetch_company_info_success(mock_get, fetcher):
    # 1. Arrange: Mock successful HTML response
    mock_response = AsyncMock()
    mock_response.text.return_value = MOCK_HTML
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value.__aenter__.return_value = mock_response

    # 2. Act: We pass 'RELIANCE.NS' to test the ticker normalization
    result = await fetcher.fetch_company_info("RELIANCE.NS")

    # 3. Assert
    assert result["ticker"] == "RELIANCE"
    assert result["about"] == "Reliance is a diversified conglomerate."
    assert result["ratios"]["Market Cap"] == "₹ 20,00,000"
    assert result["ratios"]["Stock P/E"] == "28.5"
    assert "Company has reduced debt." in result["pros"]
    assert "Stock is trading at 3 times its book value." in result["cons"]


@pytest.mark.asyncio
@patch("src.ingestion.strategies.screener.aiohttp.ClientSession.get")
async def test_fetch_company_info_parsing_error(mock_get, fetcher):
    # 1. Arrange: Return completely invalid HTML (e.g., website changed)
    mock_response = AsyncMock()
    mock_response.text.return_value = "<html><body><h1>Not Found</h1></body></html>"
    mock_response.status = 200  # Soft 404 scenario
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value.__aenter__.return_value = mock_response

    # 2 & 3. Act & Assert: Should raise our custom DataParsingError
    with pytest.raises(DataParsingError) as exc_info:
        await fetcher.fetch_company_info("TCS")

    assert "Screener" in str(exc_info.value)
    assert "Missing ul#top-ratios" in str(exc_info.value)
