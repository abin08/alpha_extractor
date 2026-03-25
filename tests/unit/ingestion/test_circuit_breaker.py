from unittest.mock import AsyncMock, patch

import pytest

from src.core.exceptions import CircuitBreakerOpenError, SourceOfflineError
from src.ingestion.circuit_breaker import circuit_breaker


# A dummy async function to apply our decorator to
@circuit_breaker(source_name="TestAPI", failure_threshold=3, recovery_timeout=60)
async def dummy_fetch(should_fail=False):
    if should_fail:
        raise SourceOfflineError(source="TestAPI")
    return {"data": "success"}


@pytest.fixture
def mock_redis():
    """Mocks the Redis client and its async methods."""
    with patch("src.ingestion.circuit_breaker.get_redis") as mock_get_redis:
        mock_client = AsyncMock()
        mock_get_redis.return_value = mock_client

        # Simulate an empty Redis database to start
        mock_client.get.return_value = None
        mock_client.incr.return_value = 1

        yield mock_client


@pytest.mark.asyncio
async def test_successful_call_resets_failures(mock_redis):
    result = await dummy_fetch(should_fail=False)

    assert result == {"data": "success"}
    # Assert it checked the state and reset failures to 0
    mock_redis.get.assert_called_with("cb:state:TestAPI")
    mock_redis.set.assert_called_with("cb:failures:TestAPI", 0)


@pytest.mark.asyncio
async def test_circuit_trips_after_threshold(mock_redis):
    # Simulate Redis returning incremented failure counts
    mock_redis.incr.side_effect = [1, 2, 3]

    # First two fail normally
    for _ in range(2):
        with pytest.raises(SourceOfflineError):
            await dummy_fetch(should_fail=True)

    # Third failure should trip the breaker
    with pytest.raises(SourceOfflineError):
        await dummy_fetch(should_fail=True)

    # Assert the circuit was set to OPEN with the 60s TTL
    mock_redis.setex.assert_called_once_with("cb:state:TestAPI", 60, "OPEN")


@pytest.mark.asyncio
async def test_open_circuit_raises_immediately(mock_redis):
    # Simulate Redis saying the circuit is already OPEN
    mock_redis.get.return_value = "OPEN"

    with pytest.raises(CircuitBreakerOpenError):
        # Even if should_fail is False, the network call is never attempted
        await dummy_fetch(should_fail=False)
