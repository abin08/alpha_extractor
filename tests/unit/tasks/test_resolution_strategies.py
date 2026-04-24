from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import ResolutionError
from src.tasks.workers.resolution_strategies import (
    _sanitize_ticker,
    resolve_equity_symbols,
    resolve_mutual_fund_symbols,
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


DUMMY_AMFI_DATA = """
Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
122594;INF204KB1613;-;Parag Parikh Flexi Cap Fund - Direct Plan - Growth;75.50;23-Apr-2024
122595;INF204KB1621;-;Parag Parikh Flexi Cap Fund - Regular Plan - Growth;70.10;23-Apr-2024
119062;INF174KA1LK2;-;SBI Small Cap Fund - Direct Plan - Growth;150.25;23-Apr-2024
"""


@pytest.fixture
def mock_amfi_client():
    """Provides a mocked httpx client that returns our dummy AMFI text data."""
    with patch("src.tasks.workers.resolution_strategies.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = DUMMY_AMFI_DATA
        mock_client.get.return_value = mock_resp

        yield mock_client


@pytest.mark.asyncio
async def test_resolve_mf_exact_code_match(mock_amfi_client):
    """Test that providing the exact 6-digit scheme code works."""
    result = await resolve_mutual_fund_symbols("122594")
    assert result["amfi_code"] == "122594"


@pytest.mark.asyncio
async def test_resolve_mf_exact_isin_match(mock_amfi_client):
    """Test that providing the exact ISIN code works."""
    result = await resolve_mutual_fund_symbols("INF174KA1LK2")
    assert result["amfi_code"] == "119062"


@pytest.mark.asyncio
async def test_resolve_mf_single_name_match(mock_amfi_client):
    """Test that a partial name matching exactly ONE fund works."""
    # "SBI Small Cap" only appears once in our dummy data
    result = await resolve_mutual_fund_symbols("SBI Small Cap")
    assert result["amfi_code"] == "119062"


@pytest.mark.asyncio
async def test_resolve_mf_ambiguous_match(mock_amfi_client):
    """Test that a generic name matching multiple variants raises an error."""
    # "Parag Parikh Flexi Cap" matches both Direct and Regular in our dummy data
    with pytest.raises(ResolutionError, match="Ambiguous identifier. Found 2 funds"):
        await resolve_mutual_fund_symbols("Parag Parikh Flexi Cap")


@pytest.mark.asyncio
async def test_resolve_mf_no_match(mock_amfi_client):
    """Test that a garbage identifier raises a standard ResolutionError."""
    with pytest.raises(ResolutionError, match="No mutual fund found matching"):
        await resolve_mutual_fund_symbols("NON_EXISTENT_FUND")
