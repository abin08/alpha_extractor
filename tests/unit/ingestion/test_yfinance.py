from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.domain.models import AssetContext
from src.ingestion.strategies.yfinance import YFinanceFetcher


@pytest.fixture
def fetcher():
    return YFinanceFetcher()


@pytest.mark.asyncio
@patch("src.ingestion.strategies.yfinance.yf.Ticker")
async def test_fetch_price_history(mock_ticker, fetcher):
    # 1. Arrange: Setup the mock to return a fake Pandas DataFrame
    mock_instance = MagicMock()
    mock_ticker.return_value = mock_instance

    mock_df = pd.DataFrame(
        {
            "Open": [2500.0],
            "High": [2550.0],
            "Low": [2490.0],
            "Close": [2540.0],
            "Volume": [1500000],
        },
        index=pd.DatetimeIndex(["2026-03-25"]),
    )
    mock_df.index.name = "Date"

    mock_instance.history.return_value = mock_df

    # 2. Act: Call our async wrapper
    asset = AssetContext(
        internal_symbol="RELIANCE.NS",
        company_name="Reliance",
        yfinance_symbol="RELIANCE.NS",
    )
    result = await fetcher.fetch_price_history(asset, period="1d")

    # 3. Assert: Verify it correctly converted the DataFrame to a JSON-serializable dict
    assert result["ticker"] == "RELIANCE.NS"
    assert len(result["data"]) == 1
    assert result["data"][0]["Close"] == 2540.0
    assert result["data"][0]["Date"] == "2026-03-25"
    mock_instance.history.assert_called_once_with(period="1d")


@pytest.mark.asyncio
@patch("src.ingestion.strategies.yfinance.yf.Ticker")
async def test_fetch_company_info(mock_ticker, fetcher):
    # 1. Arrange
    mock_instance = MagicMock()
    mock_ticker.return_value = mock_instance
    mock_instance.info = {"shortName": "Reliance Industries", "sector": "Energy"}

    # 2. Act
    asset = AssetContext(
        internal_symbol="RELIANCE.NS",
        company_name="Reliance",
        yfinance_symbol="RELIANCE.NS",
    )
    result = await fetcher.fetch_company_info(asset)

    # 3. Assert
    assert result["shortName"] == "Reliance Industries"
    assert result["sector"] == "Energy"
