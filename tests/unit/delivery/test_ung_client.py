from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest

from src.delivery.ung_client import UNGClient


@pytest.fixture
def mock_settings():
    """Fixture to safely patch the settings used by UNGClient."""
    with patch("src.delivery.ung_client.settings") as mock_set:
        mock_set.UNG_API_URL = "https://api.fake-ung.com/v1/notify"
        mock_set.UNG_API_KEY = "test_super_secret_key"
        # config.py no longer holds the emails!
        yield mock_set


@pytest.mark.asyncio
async def test_dispatch_brief_mock_bypass(mock_settings):
    """Test 1: Verify the MOCK_UNG_DELIVERY flag completely bypasses network calls."""
    mock_settings.MOCK_UNG_DELIVERY = True
    client = UNGClient()

    with patch("src.delivery.ung_client.httpx.AsyncClient") as mock_httpx_class:
        result = await client.dispatch_brief("TEST.NS", "<h1>HTML Report</h1>", ["test@test.com"])

    assert result is True
    mock_httpx_class.assert_not_called()


@pytest.mark.asyncio
@patch("src.delivery.ung_client.httpx.AsyncClient")
async def test_dispatch_brief_success(mock_httpx_class, mock_settings):
    """Test 2: Verify successful payload formatting, HTML conversion, and HTTP POST."""
    mock_settings.MOCK_UNG_DELIVERY = False
    client = UNGClient()

    mock_httpx_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None  # Simulates HTTP 200 OK
    mock_httpx_instance.post.return_value = mock_response

    mock_httpx_class.return_value.__aenter__.return_value = mock_httpx_instance

    recipients = ["trader_one@alpha.com", "analyst@alpha.com"]
    result = await client.dispatch_brief("TEST.NS", "<h1>HTML Report</h1>", recipients)

    assert result is True
    mock_httpx_instance.post.assert_called_once_with(
        "https://api.fake-ung.com/v1/notify",
        json={
            "channel": "email",
            "recipient": {
                "bcc": [
                    "trader_one@alpha.com",
                    "analyst@alpha.com",
                ]
            },
            "content": {
                "subject": "Alpha Extractor: TEST.NS Brief",
                "html_body": "<h1>HTML Report</h1>",
            },
            "metadata": {
                "source_service": "alpha-extractor",
                "trace_id": ANY,
            },
        },
        headers={"X-API-Key": "test_super_secret_key"},
        timeout=15.0,
    )


@pytest.mark.asyncio
@patch("src.delivery.ung_client.httpx.AsyncClient")
async def test_dispatch_brief_http_error(mock_httpx_class, mock_settings):
    """Test 3: Verify HTTP status errors (400, 500) are raised properly."""
    mock_settings.MOCK_UNG_DELIVERY = False
    client = UNGClient()

    mock_httpx_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    http_error = httpx.HTTPStatusError("500 Error", request=MagicMock(), response=mock_response)
    mock_response.raise_for_status.side_effect = http_error

    mock_httpx_instance.post.return_value = mock_response
    mock_httpx_class.return_value.__aenter__.return_value = mock_httpx_instance

    with pytest.raises(httpx.HTTPStatusError):
        await client.dispatch_brief("TEST.NS", "<h1>HTML Report</h1>", ["test@test.com"])


@pytest.mark.asyncio
@patch("src.delivery.ung_client.httpx.AsyncClient")
async def test_dispatch_brief_network_error(mock_httpx_class, mock_settings):
    """Test 4: Verify physical network drops (RequestError) are raised for Celery to retry."""
    mock_settings.MOCK_UNG_DELIVERY = False
    client = UNGClient()

    mock_httpx_instance = AsyncMock()
    mock_httpx_instance.post.side_effect = httpx.RequestError(
        "DNS resolution failed", request=MagicMock()
    )
    mock_httpx_class.return_value.__aenter__.return_value = mock_httpx_instance

    with pytest.raises(httpx.RequestError):
        await client.dispatch_brief("TEST.NS", "<h1>HTML Report</h1>", ["test@test.com"])
