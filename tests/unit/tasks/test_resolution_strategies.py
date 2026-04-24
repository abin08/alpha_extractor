from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import ResolutionError
from src.tasks.workers.resolution_strategies import (
    _sanitize_ticker,
    resolve_equity_symbols,
)


def test_sanitize_ticker():
    """Test that the sanitization logic correctly cleans dirty user inputs."""
    assert _sanitize_ticker("RELIANCE EQ") == "RELIANCE"
    assert _sanitize_ticker("TCS-BE") == "TCS"
    assert _sanitize_ticker("TATA MOTORS") == "TATAMOTORS"
    assert _sanitize_ticker("  INFY.NS  ") == "INFY"
    assert _sanitize_ticker("HDFC.BO") == "HDFC"


@pytest.mark.asyncio
async def test_resolve_equity_index_bypass():
    """Test that known indices return immediately without making network calls."""
    result = await resolve_equity_symbols("NIFTY 50")

    assert result["nse_symbol"] == "NIFTY 50"
    assert result["yfinance_symbol"] == "^NSEI"
    assert result["screener_symbol"] is None


@pytest.mark.asyncio
@patch("src.tasks.workers.resolution_strategies.httpx.AsyncClient")
async def test_resolve_equity_happy_path(mock_client_class):
    """Test a successful resolution where both APIs return exact matches."""
    # 1. Setup the Async Context Manager Mock
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client_class.return_value = mock_client

    # 2. Mock Yahoo Finance Response (Status 200)
    yf_resp = MagicMock()
    yf_resp.status_code = 200

    # 3. Mock Screener Response (Exact match in the URL slug)
    screener_resp = MagicMock()
    screener_resp.status_code = 200
    screener_resp.json.return_value = [{"url": "/company/TATAMOTORS/consolidated/"}]

    # Instruct the mock client to return YF first, then Screener
    mock_client.get.side_effect = [yf_resp, screener_resp]

    # 4. Execute
    result = await resolve_equity_symbols("TATA MOTORS")

    # 5. Assert
    assert result["nse_symbol"] == "TATAMOTORS"
    assert result["yfinance_symbol"] == "TATAMOTORS.NS"
    assert result["screener_symbol"] == "TATAMOTORS"
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
@patch("src.tasks.workers.resolution_strategies.httpx.AsyncClient")
async def test_resolve_equity_yfinance_404(mock_client_class):
    """Test that a 404 from Yahoo Finance (BSE-only or invalid) raises a ResolutionError."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client_class.return_value = mock_client

    # Mock YF returning a 404
    yf_resp = MagicMock()
    yf_resp.status_code = 404
    mock_client.get.return_value = yf_resp

    # Execute & Assert
    with pytest.raises(ResolutionError, match="Yahoo Finance returned 404"):
        await resolve_equity_symbols("FAKE_TICKER")

    # Verify we didn't waste an API call to Screener
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
@patch("src.tasks.workers.resolution_strategies.httpx.AsyncClient")
async def test_resolve_equity_screener_no_match(mock_client_class):
    """Test that Screener results without an EXACT match raise a ResolutionError."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client_class.return_value = mock_client

    yf_resp = MagicMock()
    yf_resp.status_code = 200

    screener_resp = MagicMock()
    screener_resp.status_code = 200
    # Screener returns a result, but the slug is 'RELIANCEPOWER', not 'RELIANCE'
    screener_resp.json.return_value = [{"url": "/company/RELIANCEPOWER/"}]

    mock_client.get.side_effect = [yf_resp, screener_resp]

    # Execute & Assert
    with pytest.raises(ResolutionError, match="No exact match found on Screener"):
        await resolve_equity_symbols("RELIANCE")
