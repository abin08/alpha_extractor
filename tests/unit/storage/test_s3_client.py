import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.s3_client import AsyncS3Client


@pytest.fixture
def mock_aioboto3_session():
    with patch("src.storage.s3_client.aioboto3.Session") as mock_session_class:
        mock_session = MagicMock()
        mock_client = AsyncMock()

        # Setup the async context manager mock: async with session.client(...) as client:
        mock_client.__aenter__.return_value = mock_client
        mock_session.client.return_value = mock_client

        mock_session_class.return_value = mock_session
        yield mock_client


@pytest.mark.asyncio
async def test_upload_json(mock_aioboto3_session):
    client = AsyncS3Client()
    test_data = {"ticker": "RELIANCE.NS", "price": 1400}

    uri = await client.upload_json(data=test_data, key="test_context.json")

    assert uri == "s3://alpha-extractor-raw/test_context.json"
    mock_aioboto3_session.put_object.assert_called_once()

    # Verify it was serialized properly
    call_kwargs = mock_aioboto3_session.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "alpha-extractor-raw"
    assert call_kwargs["Key"] == "test_context.json"
    assert call_kwargs["Body"] == json.dumps(test_data)
    assert call_kwargs["ContentType"] == "application/json"


@pytest.mark.asyncio
async def test_download_json(mock_aioboto3_session):
    client = AsyncS3Client()

    # Create the mock stream that will be returned by the 'async with'
    mock_stream = AsyncMock()
    mock_stream.read.return_value = b'{"ticker": "RELIANCE.NS", "price": 1400}'

    # Create the mock body and tell its async context manager to return our stream
    mock_body = MagicMock()
    mock_body.__aenter__.return_value = mock_stream

    mock_aioboto3_session.get_object.return_value = {"Body": mock_body}

    result = await client.download_json("s3://alpha-extractor-raw/test_context.json")

    assert result == {"ticker": "RELIANCE.NS", "price": 1400}
    mock_aioboto3_session.get_object.assert_called_once_with(
        Bucket="alpha-extractor-raw", Key="test_context.json"
    )
