import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_create_target(async_client):
    """Test that we can successfully add a new target config."""
    payload = {
        "asset_type": "EQUITY",
        "identifier": "RELIANCE.NS",
        "name": "Reliance Industries",
        "is_active": True,
    }

    response = await async_client.post("/targets/", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["identifier"] == "RELIANCE.NS"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_all_targets(async_client):
    """Test that we can retrieve a list of targets."""
    # First, inject a target
    payload = {
        "asset_type": "MUTUAL_FUND",
        "identifier": "PPFAS",
        "name": "Parag Parikh",
    }
    await async_client.post("/targets/", json=payload)

    # Now, fetch them all
    response = await async_client.get("/targets/")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["identifier"] == "PPFAS"
