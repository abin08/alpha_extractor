import functools
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis

from src.core.config import settings
from src.core.exceptions import CircuitBreakerOpenError
from src.core.logger import get_logger

logger = get_logger(__name__)

# Global, lazy-loaded Redis client connection pool
_redis_client = None


def get_redis() -> redis.Redis:
    """Instantiates a singleton async Redis client."""
    global _redis_client
    if _redis_client is None:
        # Fallback to localhost if REDIS_URL isn't in .env yet
        url = settings.REDIS_URL or "redis://localhost:6379/0"
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def circuit_breaker(
    source_name: str, failure_threshold: int = 5, recovery_timeout: int = 900
) -> Callable:
    """
    Distributed Circuit Breaker pattern backed by Redis.
    Prevents workers from hanging on dead data sources.

    :param source_name: Unique identifier for the API (e.g., 'yfinance')
    :param failure_threshold: Number of consecutive failures before tripping OPEN
    :param recovery_timeout: Seconds to keep the circuit OPEN before Half-Open retry (TTL)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            r = get_redis()
            state_key = f"cb:state:{source_name}"
            failures_key = f"cb:failures:{source_name}"

            # 1. Fast-path: Check if the circuit is currently OPEN
            state = await r.get(state_key)
            if state == "OPEN":
                logger.warning(f"Circuit breaker is OPEN for {source_name}. Halting request.")
                raise CircuitBreakerOpenError(source=source_name)

            try:
                # 2. Attempt the network operation (This wraps our Retry decorator!)
                result = await func(*args, **kwargs)

                # 3. Success! Reset the consecutive failure count
                await r.set(failures_key, 0)
                return result

            except Exception as e:
                # 4. Failure occurred. Increment the counter.
                failures = await r.incr(failures_key)
                logger.warning(
                    f"Circuit breaker recorded failure "
                    f"{failures}/{failure_threshold} for {source_name}"
                )

                if failures >= failure_threshold:
                    logger.error(
                        f"Circuit breaker TRIPPED for {source_name}! "
                        f"Opening circuit for {recovery_timeout} seconds."
                    )
                    # Set the OPEN state with an automatic Redis TTL expiration
                    await r.setex(state_key, recovery_timeout, "OPEN")

                # Re-raise the original exception so Celery knows the task failed
                raise e

        return wrapper

    return decorator
