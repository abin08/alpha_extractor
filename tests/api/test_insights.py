from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status


@pytest.mark.asyncio
@patch("src.api.routes.insights.BriefRepository")
async def test_search_insights_endpoint_success(mock_repo_class, async_client):
    """Test 1: Happy Path - Controller passes parameters and formats the response correctly."""
    mock_repo_instance = mock_repo_class.return_value
    mock_repo_instance.search_insights = AsyncMock(
        return_value={
            "total_results": 1,
            "data": [
                {
                    "target": {
                        "identifier": "TCS.NS",
                        "name": "Tata",
                        "asset_type": "EQUITY",
                    },
                    "insight": {
                        "insight_id": 142,
                        "sentiment": "BULLISH",
                        "catalyst": "Wins",
                        "actionable_edge": "Hold",
                    },
                    "macro_context": {
                        "job_id": 55,
                        "run_date": "2026-04-30T10:00:00Z",
                        "macro_sentiment": "NEUTRAL",
                        "sector_rotation": "IT",
                    },
                }
            ],
        }
    )

    response = await async_client.get(
        "/api/v1/insights/search?ticker=TCS.NS&sentiment=BULLISH&limit=10&offset=0"
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pagination"]["total_results"] == 1
    assert data["pagination"]["limit"] == 10
    assert len(data["data"]) == 1

    # Verify repository received exact parameters
    call_kwargs = mock_repo_instance.search_insights.call_args.kwargs
    assert call_kwargs["ticker"] == "TCS.NS"
    assert call_kwargs["sentiment"] == "BULLISH"
    assert call_kwargs["limit"] == 10


@pytest.mark.asyncio
@patch("src.api.routes.insights.BriefRepository")
async def test_search_insights_empty_results(mock_repo_class, async_client):
    """Test 2: Edge Case - Valid query but no matching records exist in the DB."""
    mock_repo_instance = mock_repo_class.return_value
    mock_repo_instance.search_insights = AsyncMock(return_value={"total_results": 0, "data": []})

    response = await async_client.get("/api/v1/insights/search?ticker=GHOST_TICKER")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["pagination"]["total_results"] == 0
    assert data["data"] == []  # Empty array, not null or error


@pytest.mark.asyncio
async def test_search_insights_pagination_boundaries(async_client):
    """Test 3: Edge Case - Pagination limits pushed past acceptable boundaries."""
    # Test Limit > 100
    resp_high_limit = await async_client.get("/api/v1/insights/search?limit=101")
    assert resp_high_limit.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "limit" in resp_high_limit.text

    # Test Limit < 1
    resp_low_limit = await async_client.get("/api/v1/insights/search?limit=0")
    assert resp_low_limit.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Test Offset < 0
    resp_negative_offset = await async_client.get("/api/v1/insights/search?offset=-5")
    assert resp_negative_offset.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_search_insights_invalid_dates(async_client):
    """Test 4: Edge Case - Malformed date strings."""
    # Pass a completely invalid date (Month 13, Day 45)
    response = await async_client.get("/api/v1/insights/search?date_from=2026-13-45")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Check that FastAPI specifically flagged the date_from field
    errors = response.json()["detail"]
    failed_fields = [error["loc"][-1] for error in errors]
    assert "date_from" in failed_fields


@pytest.mark.asyncio
@patch("src.api.routes.insights.BriefRepository")
async def test_search_insights_database_error(mock_repo_class, async_client):
    """Test 5: Edge Case - Underlying database/repository throws an unexpected error."""
    mock_repo_instance = mock_repo_class.return_value

    # Simulate a catastrophic database timeout
    mock_repo_instance.search_insights.side_effect = Exception("DB Connection Timeout")

    response = await async_client.get("/api/v1/insights/search?ticker=TCS.NS")

    # FastAPI automatically catches unhandled exceptions and returns a 500 Internal Server Error
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
