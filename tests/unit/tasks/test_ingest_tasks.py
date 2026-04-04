from unittest.mock import AsyncMock, patch

import pytest

from src.domain.models import AssetContext
from src.tasks.workers.ingest_tasks import _gather_and_upload


@pytest.fixture
def mock_asset_dict():
    return {
        "internal_symbol": "RELIANCE.NS",
        "company_name": "Reliance Industries",
        "yfinance_symbol": "RELIANCE.NS",
        "screener_symbol": "RELIANCE",
        "nse_symbol": "RELIANCE",
        "amfi_code": "120503",
    }


@pytest.mark.asyncio
@patch("src.tasks.workers.ingest_tasks.AsyncS3Client")
@patch("src.tasks.workers.ingest_tasks.FetcherFactory")
@patch("src.tasks.workers.ingest_tasks.register_strategies")
async def test_gather_and_upload_success(
    mock_register, mock_factory, mock_s3_class, mock_asset_dict
):
    """Test that the async engine gathers data from all sources and uploads to S3."""
    asset = AssetContext(**mock_asset_dict)

    # 1. Mock the Fetchers
    mock_fetcher = AsyncMock()
    mock_fetcher.fetch_price_history.return_value = {"price": "data"}
    mock_fetcher.fetch_company_info.return_value = {"info": "data"}
    mock_fetcher.fetch_news.return_value = [{"news": "item"}]
    mock_factory.create.return_value = mock_fetcher

    # 2. Mock S3 Client
    mock_s3_instance = AsyncMock()
    mock_s3_instance.upload_json.return_value = "s3://fake-bucket/payload.json"
    mock_s3_class.return_value = mock_s3_instance

    # 3. Execute
    result = await _gather_and_upload(asset)

    # 4. Assertions
    assert result == "s3://fake-bucket/payload.json"
    mock_register.assert_called_once()
    mock_s3_instance.upload_json.assert_called_once()

    # Verify payload structure passed to S3
    uploaded_payload = mock_s3_instance.upload_json.call_args[0][0]
    assert uploaded_payload["price_action"] == {"price": "data"}
    assert "mutual_fund_info" in uploaded_payload
