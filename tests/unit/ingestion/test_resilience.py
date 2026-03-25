from unittest.mock import AsyncMock, patch

import pytest

from src.core.exceptions import DataParsingError, RateLimitExceeded, SourceOfflineError
from src.ingestion.resilience import with_retry_and_jitter


# A dummy async function to apply our decorator to
@with_retry_and_jitter(max_retries=3, base_delay=1.0, max_delay=10.0)
async def dummy_fetch(mock_func):
    return await mock_func()


@pytest.mark.asyncio
@patch("src.ingestion.resilience.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_success_first_try(mock_sleep):
    mock_func = AsyncMock(return_value={"data": "success"})

    result = await dummy_fetch(mock_func)

    assert result == {"data": "success"}
    assert mock_func.call_count == 1
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch("src.ingestion.resilience.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_success_after_failures(mock_sleep):
    # Fails twice, succeeds on the third attempt
    mock_func = AsyncMock(
        side_effect=[
            SourceOfflineError(source="Test"),
            RateLimitExceeded(source="Test"),
            {"data": "success"},
        ]
    )

    result = await dummy_fetch(mock_func)

    assert result == {"data": "success"}
    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2  # Slept twice between the 3 calls


@pytest.mark.asyncio
@patch("src.ingestion.resilience.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_max_attempts_exceeded(mock_sleep):
    # Always fails
    mock_func = AsyncMock(side_effect=SourceOfflineError(source="Test"))

    with pytest.raises(SourceOfflineError):
        await dummy_fetch(mock_func)

    assert mock_func.call_count == 4  # 1 initial try + 3 retries
    assert mock_sleep.call_count == 3


@pytest.mark.asyncio
@patch("src.ingestion.resilience.asyncio.sleep", new_callable=AsyncMock)
async def test_no_retry_on_unhandled_exception(mock_sleep):
    # Fails with a DataParsingError (which shouldn't be retried)
    mock_func = AsyncMock(side_effect=DataParsingError(source="Test", details="HTML changed"))

    with pytest.raises(DataParsingError):
        await dummy_fetch(mock_func)

    # Should fail fast on the very first try!
    assert mock_func.call_count == 1
    mock_sleep.assert_not_called()
