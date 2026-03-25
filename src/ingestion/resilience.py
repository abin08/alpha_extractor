import asyncio
import functools
import random
from collections.abc import Callable
from typing import Any

from src.core.exceptions import RateLimitExceeded, SourceOfflineError
from src.core.logger import get_logger

logger = get_logger(__name__)

# The exceptions we deem "transient" and worth retrying
TRANSIENT_EXCEPTIONS = (RateLimitExceeded, SourceOfflineError)


def with_retry_and_jitter(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = TRANSIENT_EXCEPTIONS,
) -> Callable:
    """
    An async decorator that retries a function using exponential backoff with jitter.
    Only catches specific transient exceptions to avoid masking logical errors.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while attempt <= max_retries:
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) reached for {func.__name__}. "
                            f"Final error: {str(e)}"
                        )
                        raise  # Bubble up the exception after max retries

                    # Calculate exponential backoff (e.g., 1s, 2s, 4s...)
                    backoff = min(max_delay, base_delay * (2**attempt))

                    # Add Full Jitter (randomize between 0 and the backoff max)
                    # This prevents the "Thundering Herd" problem
                    sleep_time = random.uniform(0, backoff)

                    # If the API explicitly told us how long to wait, respect it!
                    if isinstance(e, RateLimitExceeded) and e.retry_after > 0:
                        sleep_time = max(sleep_time, float(e.retry_after))

                    logger.warning(
                        f"Transient error in {func.__name__}: {str(e)}. "
                        f"Retrying {attempt + 1}/{max_retries} in {sleep_time:.2f} seconds."
                    )

                    await asyncio.sleep(sleep_time)
                    attempt += 1

        return wrapper

    return decorator
