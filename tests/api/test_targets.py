from unittest.mock import patch

import pytest
from fastapi import status


@pytest.mark.asyncio
# MOCK THE CELERY TASK DELAY METHOD
@patch("src.api.routes.target_config.resolve_asset_symbols_task.delay")
async def test_create_target(mock_delay, async_client):
    """Test that we can successfully add a new target config and trigger resolution."""
    payload = {
        "asset_type": "EQUITY",
        "identifier": "RELIANCE.NS",
        "name": "Reliance Industries",
        "is_active": True,
    }

    response = await async_client.post("/api/v1/targets/", json=payload)

    # EXPECT 202 ACCEPTED
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()

    assert data["identifier"] == "RELIANCE.NS"
    assert "id" in data
    # ASSERT DEFAULT DB STATE IS EXPOSED
    assert data["status"] == "PENDING_RESOLUTION"

    # VERIFY THE BACKGROUND TASK WAS DISPATCHED WITH THE NEW DB ID
    mock_delay.assert_called_once_with(data["id"])


@pytest.mark.asyncio
async def test_get_all_targets(async_client):
    """Test that we can retrieve a list of targets."""
    # First, inject a target
    payload = {
        "asset_type": "MUTUAL_FUND",
        "identifier": "PPFAS",
        "name": "Parag Parikh",
    }
    await async_client.post("/api/v1/targets/", json=payload)

    # Now, fetch them all
    response = await async_client.get("/api/v1/targets/")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["identifier"] == "PPFAS"
    # Verify the GET request also exposes the status
    assert data[0]["status"] == "PENDING_RESOLUTION"
