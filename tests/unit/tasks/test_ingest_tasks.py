from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import AssetContext
from src.tasks.workers.ingest_tasks import _gather_and_upload, ingest_asset_task


@pytest.fixture
def mock_asset_dict():
    """Valid asset dictionary including required AssetType for rehydration."""
    return {
        "internal_symbol": "RELIANCE.NS",
        "company_name": "Reliance Industries",
        "asset_type": "EQUITY",
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


# --- WRAPPER TESTS ---


@patch("src.tasks.workers.ingest_tasks._gather_and_upload", new_callable=MagicMock)
@patch("src.tasks.workers.ingest_tasks.asyncio.run")
def test_ingest_asset_task_success(mock_run, mock_core, mock_asset_dict):
    """Test the happy path of the Ingestion Celery wrapper."""
    # Arrange
    mock_self = MagicMock()
    mock_run.return_value = "s3://success-path"
    dummy_coro = MagicMock(name="coro")
    mock_core.return_value = dummy_coro

    # Act
    result = ingest_asset_task.run.__func__(mock_self, mock_asset_dict)

    # Assert
    assert result == "s3://success-path"
    mock_run.assert_called_once_with(dummy_coro)


@patch("src.tasks.workers.ingest_tasks._gather_and_upload", new_callable=MagicMock)
@patch("src.tasks.workers.ingest_tasks.asyncio.run")
def test_ingest_asset_task_fail_fast_validation(mock_run, mock_core):
    """Test that deterministic ValueError (Pydantic) fails immediately without retry."""
    # Arrange
    mock_self = MagicMock()
    # Passing an invalid dict (missing internal_symbol) to trigger the rehydration catch
    invalid_dict = {"bad_key": "will_fail_pydantic"}

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid asset payload format"):
        ingest_asset_task.run.__func__(mock_self, invalid_dict)

    # CRITICAL: Verify retry was NOT called for validation errors
    mock_self.retry.assert_not_called()


@patch("src.tasks.workers.ingest_tasks._gather_and_upload", new_callable=MagicMock)
@patch("src.tasks.workers.ingest_tasks.asyncio.run")
def test_ingest_asset_task_retry_infra(mock_run, mock_core, mock_asset_dict):
    """Test that transient infra errors trigger a Celery retry."""
    # Arrange
    mock_self = MagicMock()
    mock_self.request.retries = 0
    mock_self.max_retries = 3

    # Simulate a transient network failure (e.g., S3 or DataSource down)
    mock_run.side_effect = Exception("S3 Connection Refused")
    mock_self.retry.side_effect = Exception("Retry Invoked")

    # Act & Assert
    with pytest.raises(Exception, match="Retry Invoked"):
        ingest_asset_task.run.__func__(mock_self, mock_asset_dict)

    # Verify retry logic: 30 * (2 ** 0) = 30
    assert mock_self.retry.called
    args, kwargs = mock_self.retry.call_args
    assert kwargs["countdown"] == 30


@patch("src.tasks.workers.ingest_tasks._gather_and_upload", new_callable=MagicMock)
@patch("src.tasks.workers.ingest_tasks.asyncio.run")
def test_ingest_asset_task_max_retries_exhausted(mock_run, mock_core, mock_asset_dict):
    """Test that reaching max retries results in a final raise (no more retries)."""
    # Arrange
    mock_self = MagicMock()
    mock_self.request.retries = 3
    mock_self.max_retries = 3
    mock_run.side_effect = Exception("Permanent failure")

    # Act & Assert
    with pytest.raises(Exception, match="Permanent failure"):
        ingest_asset_task.run.__func__(mock_self, mock_asset_dict)

    # Retry should NOT be called since we are at the limit
    mock_self.retry.assert_not_called()
