from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_circuit_breaker_redis():
    """
    Automatically mocks the Redis client for all ingestion tests
    so they don't attempt real network connections and crash the event loop.
    """
    with patch("src.ingestion.circuit_breaker.get_redis") as mock_get:
        mock_client = AsyncMock()
        # Simulate that the circuit is always CLOSED for standard tests
        mock_client.get.return_value = None
        mock_get.return_value = mock_client

        yield mock_client
