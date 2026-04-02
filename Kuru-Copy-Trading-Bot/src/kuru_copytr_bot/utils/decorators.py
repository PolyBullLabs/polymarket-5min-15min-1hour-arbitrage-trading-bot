"""Utility decorators for error handling and retries."""

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    backoff: float = 0.1,
    exponential: bool = False,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Retry a function call on failure with configurable backoff.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff: Base backoff time in seconds (default: 0.1)
        exponential: Use exponential backoff if True (default: False)
        exceptions: Tuple of exceptions to retry on (default: all exceptions)

    Returns:
        Decorated function that will retry on failure

    Example:
        @retry(max_attempts=3, backoff=0.5, exponential=True)
        def unstable_api_call():
            # This will retry up to 3 times with exponential backoff
            response = requests.get("https://api.example.com")
            return response.json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            # Handle edge case of 0 max_attempts - execute once
            attempts = max(1, max_attempts)

            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # Don't sleep after the last attempt
                    if attempt < attempts - 1:
                        sleep_time = backoff * (2**attempt) if exponential else backoff

                        # Handle negative backoff (treat as 0)
                        sleep_time = max(0, sleep_time)

                        if sleep_time > 0:
                            time.sleep(sleep_time)

            # If we exhausted all attempts, raise the last exception
            if last_exception:
                raise last_exception

            # This should not be reached, but return None as fallback
            return None

        # For async functions, create an async wrapper
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                last_exception = None

                # Handle edge case of 0 max_attempts - execute once
                attempts = max(1, max_attempts)

                for attempt in range(attempts):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e

                        # Don't sleep after the last attempt
                        if attempt < attempts - 1:
                            sleep_time = backoff * (2**attempt) if exponential else backoff

                            # Handle negative backoff (treat as 0)
                            sleep_time = max(0, sleep_time)

                            if sleep_time > 0:
                                await asyncio.sleep(sleep_time)

                # If we exhausted all attempts, raise the last exception
                if last_exception:
                    raise last_exception

                # This should not be reached, but return None as fallback
                return None

            return async_wrapper

        return wrapper

    return decorator


def async_timeout(seconds: float):
    """Add a timeout to an async function.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorated async function with timeout

    Raises:
        asyncio.TimeoutError: If the function takes longer than specified timeout

    Example:
        @async_timeout(seconds=5.0)
        async def fetch_data():
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Handle negative or zero timeout
            timeout = max(0, seconds)

            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except TimeoutError:
                # Re-raise timeout error
                raise

        return wrapper

    return decorator
