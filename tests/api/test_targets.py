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
@patch("src.api.routes.target_config.resolve_asset_symbols_task.delay")
async def test_get_all_targets(mock_delay, async_client):
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


@pytest.mark.asyncio
@patch("src.api.routes.target_config.resolve_asset_symbols_task.delay")
async def test_manual_update_vendor_mapping_success(mock_delay, async_client):
    """Test that an admin can manually patch symbols and rescue a target to ACTIVE."""
    # 1. Create a "stuck" target
    payload = {
        "asset_type": "EQUITY",
        "identifier": "STUCK.NS",
        "name": "Stuck Corp",
    }
    create_resp = await async_client.post("/api/v1/targets/", json=payload)
    target_id = create_resp.json()["id"]

    # 2. Hit the backdoor to patch the mapping
    patch_payload = {"screener_symbol": "STUCK_CORP_NEW", "yfinance_symbol": "STUCK.NS"}
    response = await async_client.patch(f"/api/v1/targets/{target_id}/mapping", json=patch_payload)

    # 3. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == target_id

    # CRITICAL: The endpoint must have flipped the state to ACTIVE
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_manual_update_vendor_mapping_not_found(async_client):
    """Test that trying to patch a non-existent target returns a 404."""
    patch_payload = {"screener_symbol": "GHOST"}
    response = await async_client.patch("/api/v1/targets/99999/mapping", json=patch_payload)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Target not found."


@pytest.mark.asyncio
@patch("src.api.routes.target_config.resolve_asset_symbols_task.delay")
async def test_get_vendor_mapping_success(mock_delay, async_client):
    """Test that a client can successfully fetch an existing vendor mapping."""
    # 1. Create a target
    payload = {
        "asset_type": "EQUITY",
        "identifier": "GETMAP.NS",
        "name": "Get Map Corp",
    }
    create_resp = await async_client.post("/api/v1/targets/", json=payload)
    target_id = create_resp.json()["id"]

    # 2. Patch a mapping so it exists in the database
    patch_payload = {"yfinance_symbol": "GETMAP.NS", "screener_symbol": "GETMAP"}
    await async_client.patch(f"/api/v1/targets/{target_id}/mapping", json=patch_payload)

    # 3. GET the mapping using our new endpoint
    response = await async_client.get(f"/api/v1/targets/{target_id}/mapping")

    # 4. Assertions
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["yfinance_symbol"] == "GETMAP.NS"
    assert data["screener_symbol"] == "GETMAP"
    assert "updated_at" in data  # Ensure our datetime field serialized correctly


@pytest.mark.asyncio
async def test_get_vendor_mapping_not_found(async_client):
    """Test that fetching a mapping for a non-existent or pending target returns a 404."""
    # Try fetching a mapping for an ID that definitely does not exist
    response = await async_client.get("/api/v1/targets/99999/mapping")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert (
        response.json()["detail"]
        == "Vendor mapping not found or target is still pending resolution."
    )
