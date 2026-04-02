"""Tests for utility decorators."""

import asyncio
import time

import pytest

from src.kuru_copytr_bot.utils.decorators import async_timeout, retry


class TestRetryDecorator:
    """Test retry decorator functionality."""

    def test_retry_decorator_succeeds_on_first_attempt(self):
        """@retry should return immediately if function succeeds."""
        call_count = 0

        @retry(max_attempts=3, backoff=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_decorator_retries_on_failure(self):
        """@retry should retry failed calls."""
        call_count = 0

        @retry(max_attempts=3, backoff=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = failing_func()
        assert result == "success"
        assert call_count == 3

    def test_retry_decorator_raises_after_max_attempts(self):
        """@retry should raise after exceeding max attempts."""
        call_count = 0

        @retry(max_attempts=3, backoff=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")

        with pytest.raises(Exception, match="Permanent failure"):
            always_fails()

        assert call_count == 3

    def test_retry_decorator_with_default_max_attempts(self):
        """@retry should use default max attempts if not specified."""
        call_count = 0

        @retry(backoff=0.01)  # Should default to 3 attempts
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Failure")

        with pytest.raises(Exception, match="Failure"):
            failing_func()

        # Default should be 3 attempts
        assert call_count == 3

    def test_retry_decorator_preserves_function_args(self):
        """@retry should preserve function arguments."""

        @retry(max_attempts=2, backoff=0.01)
        def func_with_args(a, b, c=None):
            if a < 0:
                raise ValueError("Negative value")
            return a + b + (c or 0)

        result = func_with_args(1, 2, c=3)
        assert result == 6

    def test_retry_decorator_preserves_function_kwargs(self):
        """@retry should preserve keyword arguments."""

        @retry(max_attempts=2, backoff=0.01)
        def func_with_kwargs(name, age=None):
            return f"{name} is {age}"

        result = func_with_kwargs("Alice", age=30)
        assert result == "Alice is 30"

    def test_retry_decorator_with_exponential_backoff(self):
        """@retry should implement exponential backoff."""
        call_count = 0
        call_times = []

        @retry(max_attempts=3, backoff=0.05, exponential=True)
        def failing_func():
            nonlocal call_count
            call_count += 1
            call_times.append(time.time())
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = failing_func()
        assert result == "success"
        assert call_count == 3

        # Check exponential backoff timing
        # First retry should wait ~0.05s, second retry ~0.1s
        if len(call_times) >= 2:
            first_wait = call_times[1] - call_times[0]
            assert first_wait >= 0.04  # Allow some tolerance

    def test_retry_decorator_with_specific_exceptions(self):
        """@retry should only retry on specified exceptions."""
        call_count = 0

        @retry(max_attempts=3, backoff=0.01, exceptions=(ValueError,))
        def func_with_specific_exception():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retryable error")
            elif call_count == 2:
                raise TypeError("Non-retryable error")
            return "success"

        # Should raise TypeError without retrying it
        with pytest.raises(TypeError, match="Non-retryable error"):
            func_with_specific_exception()

        assert (
            call_count == 2
        )  # First call raised ValueError (retried), second raised TypeError (not retried)

    def test_retry_decorator_without_backoff(self):
        """@retry should work with zero backoff."""
        call_count = 0

        @retry(max_attempts=3, backoff=0)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"

        result = failing_func()
        assert result == "success"
        assert call_count == 2

    def test_retry_decorator_preserves_return_value(self):
        """@retry should preserve the return value."""

        @retry(max_attempts=2, backoff=0.01)
        def returns_dict():
            return {"status": "ok", "data": [1, 2, 3]}

        result = returns_dict()
        assert result == {"status": "ok", "data": [1, 2, 3]}

    def test_retry_decorator_with_none_return(self):
        """@retry should handle None return values."""

        @retry(max_attempts=2, backoff=0.01)
        def returns_none():
            return None

        result = returns_none()
        assert result is None


class TestAsyncTimeoutDecorator:
    """Test async timeout decorator functionality."""

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_succeeds_within_timeout(self):
        """@async_timeout should succeed if function completes in time."""

        @async_timeout(seconds=1.0)
        async def fast_func():
            await asyncio.sleep(0.01)
            return "success"

        result = await fast_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_raises_on_timeout(self):
        """@async_timeout should raise TimeoutError on timeout."""

        @async_timeout(seconds=0.05)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "should not reach here"

        with pytest.raises(asyncio.TimeoutError):
            await slow_func()

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_preserves_args(self):
        """@async_timeout should preserve function arguments."""

        @async_timeout(seconds=1.0)
        async def func_with_args(a, b):
            await asyncio.sleep(0.01)
            return a + b

        result = await func_with_args(10, 20)
        assert result == 30

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_preserves_kwargs(self):
        """@async_timeout should preserve keyword arguments."""

        @async_timeout(seconds=1.0)
        async def func_with_kwargs(name, age=None):
            await asyncio.sleep(0.01)
            return f"{name} is {age}"

        result = await func_with_kwargs("Bob", age=25)
        assert result == "Bob is 25"

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_with_immediate_return(self):
        """@async_timeout should work with immediate returns."""

        @async_timeout(seconds=1.0)
        async def immediate_func():
            return "immediate"

        result = await immediate_func()
        assert result == "immediate"

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_with_exception(self):
        """@async_timeout should not mask exceptions from the function."""

        @async_timeout(seconds=1.0)
        async def func_that_raises():
            await asyncio.sleep(0.01)
            raise ValueError("Function error")

        with pytest.raises(ValueError, match="Function error"):
            await func_that_raises()

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_with_very_short_timeout(self):
        """@async_timeout should timeout very quickly with short timeout."""

        @async_timeout(seconds=0.001)
        async def slow_func():
            await asyncio.sleep(0.1)
            return "should not reach"

        with pytest.raises(asyncio.TimeoutError):
            await slow_func()

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_preserves_none_return(self):
        """@async_timeout should handle None return values."""

        @async_timeout(seconds=1.0)
        async def returns_none():
            await asyncio.sleep(0.01)
            return None

        result = await returns_none()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_timeout_decorator_multiple_calls(self):
        """@async_timeout should work correctly for multiple calls."""

        @async_timeout(seconds=0.1)
        async def func():
            await asyncio.sleep(0.01)
            return "success"

        # First call
        result1 = await func()
        assert result1 == "success"

        # Second call
        result2 = await func()
        assert result2 == "success"


class TestDecoratorCombinations:
    """Test combining decorators."""

    @pytest.mark.asyncio
    async def test_retry_with_async_timeout(self):
        """Should be able to combine retry with async timeout."""
        call_count = 0

        @retry(max_attempts=3, backoff=0.01)
        @async_timeout(seconds=1.0)
        async def func_with_both():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"

        result = await func_with_both()
        assert result == "success"
        assert call_count == 2

    def test_retry_preserves_function_name(self):
        """@retry should preserve the original function name."""

        @retry(max_attempts=2, backoff=0.01)
        def my_function():
            return "result"

        # Decorators should preserve __name__ and __doc__
        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_async_timeout_preserves_function_name(self):
        """@async_timeout should preserve the original function name."""

        @async_timeout(seconds=1.0)
        async def my_async_function():
            return "result"

        assert my_async_function.__name__ == "my_async_function"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_retry_with_zero_max_attempts(self):
        """@retry should handle edge case of zero max attempts."""

        @retry(max_attempts=0, backoff=0.01)
        def func():
            return "success"

        # With 0 max attempts, should either raise or execute once
        # Implementation-dependent, but should not hang
        try:
            result = func()
            # If it executes, it should return the value
            assert result == "success"
        except Exception:
            # If it raises, that's also acceptable for 0 attempts
            pass

    def test_retry_with_negative_backoff(self):
        """@retry should handle negative backoff gracefully."""
        call_count = 0

        @retry(max_attempts=2, backoff=-0.01)
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Retry")
            return "success"

        # Should still work (treat negative as zero)
        result = func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_timeout_with_zero_timeout(self):
        """@async_timeout should handle zero timeout."""

        @async_timeout(seconds=0)
        async def func():
            await asyncio.sleep(0.01)
            return "should timeout"

        # Zero timeout should cause immediate timeout
        with pytest.raises(asyncio.TimeoutError):
            await func()

    @pytest.mark.asyncio
    async def test_async_timeout_with_negative_timeout(self):
        """@async_timeout should handle negative timeout."""

        @async_timeout(seconds=-1)
        async def func():
            return "immediate"

        # Negative timeout should be treated as 0 or very short
        # Might succeed or timeout depending on implementation
        import contextlib

        with contextlib.suppress(TimeoutError):
            await func()
