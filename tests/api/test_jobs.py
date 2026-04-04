from unittest.mock import MagicMock, patch

import pytest
from fastapi import status


@pytest.mark.asyncio
# We patch the 'chain' function exactly where it is imported in the router
@patch("src.api.routes.jobs.chain")
async def test_trigger_pipeline_success(mock_chain, async_client):
    """Test that the pipeline trigger endpoint accepts payloads and dispatches Celery jobs."""

    # 1. Setup the Celery Mock
    # Create a mock object representing the AsyncResult returned by pipeline.delay()
    mock_async_result = MagicMock()
    mock_async_result.id = "fake-celery-task-id-1234"

    # Make the chain().delay() return our mock result
    mock_pipeline = MagicMock()
    mock_pipeline.delay.return_value = mock_async_result
    mock_chain.return_value = mock_pipeline

    # 2. Define the Request Payload
    payload = {
        "internal_symbol": "RELIANCE.NS",
        "company_name": "Reliance Industries",
        "yfinance_symbol": "RELIANCE.NS",
        "screener_symbol": "RELIANCE",
        "nse_symbol": "RELIANCE",
        "amfi_code": "120503",
    }

    # 3. Execute the Request
    response = await async_client.post("/api/v1/jobs/trigger-pipeline", json=payload)

    # 4. Assertions
    assert response.status_code == status.HTTP_202_ACCEPTED

    data = response.json()
    assert data["status"] == "Accepted"
    assert data["chain_id"] == "fake-celery-task-id-1234"
    assert "RELIANCE.NS" in data["message"]

    # Verify that Celery was actually called to build the chain
    mock_chain.assert_called_once()
    mock_pipeline.delay.assert_called_once()
