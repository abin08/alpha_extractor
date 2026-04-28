from unittest.mock import MagicMock, patch

import pytest
from fastapi import status


@pytest.mark.asyncio
@patch("src.api.routes.jobs.AsyncResult")
async def test_get_job_status_success(mock_async_result_class, async_client):
    """Test that a successful job returns its result cleanly."""

    # 1. Setup the AsyncResult mock
    mock_result_instance = MagicMock()
    mock_result_instance.state = "SUCCESS"
    mock_result_instance.result = "Delivered RELIANCE.NS"
    mock_async_result_class.return_value = mock_result_instance

    # 2. Execute Request
    response = await async_client.get("/api/v1/jobs/fake-task-123/status")

    # 3. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["task_id"] == "fake-task-123"
    assert data["status"] == "SUCCESS"
    assert data["result"] == "Delivered RELIANCE.NS"
    assert data["error_message"] is None


@pytest.mark.asyncio
@patch("src.api.routes.jobs.AsyncResult")
async def test_get_job_status_failure(mock_async_result_class, async_client):
    """Test that a failed job safely sanitizes and exposes the error message."""

    # 1. Setup the AsyncResult mock with a simulated Exception
    mock_result_instance = MagicMock()
    mock_result_instance.state = "FAILURE"
    mock_result_instance.info = Exception("RateLimitExceeded: Screener blocked request")
    mock_async_result_class.return_value = mock_result_instance

    # 2. Execute Request
    response = await async_client.get("/api/v1/jobs/fake-task-999/status")

    # 3. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["task_id"] == "fake-task-999"
    assert data["status"] == "FAILURE"
    assert data["result"] is None
    # Verify the exception was converted to a safe string
    assert data["error_message"] == "RateLimitExceeded: Screener blocked request"


@pytest.mark.asyncio
@patch("src.api.routes.jobs.dispatch_daily_pipeline_task.delay")
async def test_trigger_daily_dispatcher_success(mock_delay, async_client):
    """Test that an admin can manually trigger the overarching daily dispatcher."""

    # 1. Setup the mock to return an object with an 'id' attribute
    mock_result = MagicMock()
    mock_result.id = "dispatcher-task-id-777"
    mock_delay.return_value = mock_result

    # 2. Execute an empty POST request
    response = await async_client.post("/api/v1/jobs/trigger-daily-dispatcher")

    # 3. Assert correct status code
    assert response.status_code == status.HTTP_202_ACCEPTED

    # 4. Assert exact message payload returned
    data = response.json()
    assert data["message"] == "Daily dispatcher initiated. Fanning out to all active targets."
    assert data["task_id"] == "dispatcher-task-id-777"

    # 5. Verify the Celery task was actually queued
    mock_delay.assert_called_once()
