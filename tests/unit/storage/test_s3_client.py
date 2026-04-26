import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.object_store.s3_client import AsyncS3Client


@pytest.fixture
def mock_httpx_client():
    """Mocks httpx.AsyncClient for both PUT and GET requests."""
    with patch("src.storage.object_store.s3_client.httpx.AsyncClient") as mock_class:
        mock_client = AsyncMock()
        mock_class.return_value.__aenter__.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
async def test_upload_json(mock_httpx_client):
    mock_httpx_client.put.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

    client = AsyncS3Client()
    test_data = {"ticker": "RELIANCE.NS", "price": 1400}

    uri = await client.upload_json(data=test_data, key="test_context.json")

    assert uri == f"s3://{client.bucket}/test_context.json"
    mock_httpx_client.put.assert_called_once()

    call_kwargs = mock_httpx_client.put.call_args.kwargs
    assert call_kwargs["content"] == json.dumps(test_data).encode("utf-8")
    assert call_kwargs["headers"]["Content-Type"] == "application/json"
    assert call_kwargs["headers"]["Content-Length"] == str(
        len(json.dumps(test_data).encode("utf-8"))
    )
    # Verify SigV4 headers are present
    assert "Authorization" in call_kwargs["headers"]
    assert "x-amz-date" in call_kwargs["headers"]
    assert "x-amz-content-sha256" in call_kwargs["headers"]


@pytest.mark.asyncio
async def test_download_json(mock_httpx_client):
    test_data = {"ticker": "RELIANCE.NS", "price": 1400}
    mock_httpx_client.get.return_value = MagicMock(
        status_code=200,
        content=json.dumps(test_data).encode("utf-8"),
        raise_for_status=MagicMock(),
    )

    client = AsyncS3Client()
    result = await client.download_json(f"s3://{client.bucket}/test_context.json")

    assert result == test_data
    mock_httpx_client.get.assert_called_once()

    call_kwargs = mock_httpx_client.get.call_args.kwargs
    # Verify SigV4 headers are present
    assert "Authorization" in call_kwargs["headers"]
    assert "x-amz-date" in call_kwargs["headers"]
    assert "x-amz-content-sha256" in call_kwargs["headers"]


@pytest.mark.asyncio
async def test_download_json_invalid_uri():
    client = AsyncS3Client()
    with pytest.raises(ValueError, match="Invalid S3 URI format"):
        await client.download_json("not-a-valid-uri")
