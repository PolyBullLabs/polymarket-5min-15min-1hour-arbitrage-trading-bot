"""
Fetch data from HTTP endpoints with retry logic
"""
import asyncio
import httpx
from typing import Any
from ..config.env import ENV


def is_network_error(error: Exception) -> bool:
    """Check if error is a network-related error"""
    if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return True
    return False


async def fetch_data_async(url: str) -> Any:
    """Fetch data from URL with retry logic (async)"""
    retries = ENV.NETWORK_RETRY_LIMIT
    timeout_seconds = ENV.REQUEST_TIMEOUT_MS / 1000.0  # Convert to seconds
    retry_delay = 1.0  # 1 second base delay
    
    # Create timeout object for httpx
    timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)

    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as error:
            is_last_attempt = attempt == retries

            if is_network_error(error) and not is_last_attempt:
                delay = retry_delay * (2 ** (attempt - 1))  # Exponential backoff: 1s, 2s, 4s
                print(f'\033[33m[WARNING]\033[0m Network error (attempt {attempt}/{retries}), retrying in {delay}s...')
                await asyncio.sleep(delay)
                continue

            # If it's the last attempt or not a network error, raise
            if is_last_attempt and is_network_error(error):
                print(f'\033[31m[ERROR]\033[0m Network timeout after {retries} attempts - {type(error).__name__}')
            raise


def fetch_data(url: str) -> Any:
    """Fetch data from URL with retry logic (sync wrapper)"""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we need to use a different approach
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(fetch_data_async(url))
        else:
            return loop.run_until_complete(fetch_data_async(url))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(fetch_data_async(url))

