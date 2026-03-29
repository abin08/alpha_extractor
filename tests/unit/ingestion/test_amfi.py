from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import AssetContext
from src.ingestion.strategies.amfi import AMFIFetcher

# A tiny slice of what the real AMFI text file looks like
MOCK_AMFI_TEXT = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;
Scheme Name;Net Asset Value;Date
Open Ended Schemes (Equity Scheme - Large Cap Fund)
HDFC Mutual Fund
120503;INF179K01518;INF179K01526;HDFC Top 100 Fund - Direct Plan - Dividend;55.1234;24-Mar-2026
120504;INF179K01534;INF179K01542;HDFC Top 100 Fund - Direct Plan - Growth;950.5678;24-Mar-2026
"""


@pytest.fixture
def fetcher():
    return AMFIFetcher()


@pytest.mark.asyncio
@patch("src.ingestion.strategies.amfi.aiohttp.ClientSession.get")
async def test_fetch_price_history(mock_get, fetcher):
    # 1. Arrange: Mock the aiohttp response object
    mock_response = AsyncMock()
    mock_response.text.return_value = MOCK_AMFI_TEXT
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()

    # Setup the context manager (__aenter__ and __aexit__) for the async with block
    mock_get.return_value.__aenter__.return_value = mock_response

    # 2. Act: Fetch the latest NAV for the Growth fund (Scheme Code: 120504)
    # Note: AMFI daily file only has the latest date, so period is ignored here.
    asset = AssetContext(
        internal_symbol="120504_MF", company_name="Growth Fund", amfi_code="120504"
    )
    result = await fetcher.fetch_price_history(asset)

    # 3. Assert
    assert result["ticker"] == "120504_MF"
    assert len(result["data"]) == 1
    assert result["data"][0]["Close"] == 950.5678  # NAV maps to "Close"
    assert result["data"][0]["Date"] == "24-Mar-2026"


@pytest.mark.asyncio
@patch("src.ingestion.strategies.amfi.aiohttp.ClientSession.get")
async def test_fetch_company_info(mock_get, fetcher):
    # 1. Arrange
    mock_response = AsyncMock()
    mock_response.text.return_value = MOCK_AMFI_TEXT
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value.__aenter__.return_value = mock_response

    # 2. Act: Fetch metadata for the Growth fund
    asset = AssetContext(internal_symbol="120504", company_name="Growth Fund", amfi_code="120504")
    result = await fetcher.fetch_company_info(asset)

    # 3. Assert
    assert result["shortName"] == "HDFC Top 100 Fund - Direct Plan - Growth"
    assert result["symbol"] == "120504"
    assert result["isin"] == "INF179K01534"
