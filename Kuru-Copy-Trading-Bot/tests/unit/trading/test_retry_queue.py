"""Unit tests for RetryQueue."""

import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.kuru_copytr_bot.core.enums import OrderSide
from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientBalanceError,
    InvalidOrderError,
    OrderPlacementError,
)
from src.kuru_copytr_bot.models.trade import Trade
from src.kuru_copytr_bot.trading.retry_queue import RetryQueue


@pytest.fixture
def sample_trade():
    """Sample trade for testing."""
    return Trade(
        id="trade_123",
        trader_address="0x1111111111111111111111111111111111111111",
        market="ETH-USDC",
        side=OrderSide.BUY,
        price=Decimal("2000.0"),
        size=Decimal("5.0"),
        timestamp=datetime.now(timezone.utc),
        tx_hash="0x" + "a" * 64,
    )


class TestRetryQueueEnqueue:
    """Test enqueuing failed orders."""

    def test_retry_queue_enqueues_failed_order(self, sample_trade):
        """Test adding failed order to retry queue."""
        queue = RetryQueue()
        error = BlockchainConnectionError("Connection failed")

        queue.enqueue(sample_trade, error)

        assert queue.size() == 1
        item = queue.peek()
        assert item["trade"] == sample_trade
        assert item["retry_count"] == 0

    def test_retry_queue_stores_error_info(self, sample_trade):
        """Test queue stores error information."""
        queue = RetryQueue()
        error = BlockchainConnectionError("Network timeout")

        queue.enqueue(sample_trade, error)

        item = queue.peek()
        assert item["error"] == "Network timeout"
        assert item["error_type"] == "BlockchainConnectionError"

    def test_retry_queue_sets_next_retry_time(self, sample_trade):
        """Test queue calculates next retry time."""
        queue = RetryQueue()
        error = BlockchainConnectionError("Connection failed")

        before_time = time.time()
        queue.enqueue(sample_trade, error)
        after_time = time.time()

        item = queue.peek()
        assert item["next_retry_time"] >= before_time + 1.0
        assert item["next_retry_time"] <= after_time + 1.5


class TestRetryQueueExponentialBackoff:
    """Test exponential backoff calculations."""

    def test_retry_queue_exponential_backoff_first_retry(self):
        """Test first retry delay is 1 second."""
        queue = RetryQueue()

        delay = queue.calculate_backoff(retry_count=0)

        assert delay == 1.0

    def test_retry_queue_exponential_backoff_second_retry(self):
        """Test second retry delay is 2 seconds."""
        queue = RetryQueue()

        delay = queue.calculate_backoff(retry_count=1)

        assert delay == 2.0

    def test_retry_queue_exponential_backoff_third_retry(self):
        """Test third retry delay is 4 seconds."""
        queue = RetryQueue()

        delay = queue.calculate_backoff(retry_count=2)

        assert delay == 4.0

    def test_retry_queue_respects_custom_base_delay(self):
        """Test custom base delay configuration."""
        queue = RetryQueue(base_delay=2.0)

        delay = queue.calculate_backoff(retry_count=0)

        assert delay == 2.0

    def test_retry_queue_respects_custom_multiplier(self):
        """Test custom backoff multiplier."""
        queue = RetryQueue(backoff_multiplier=3.0)

        delay = queue.calculate_backoff(retry_count=1)

        assert delay == 3.0


class TestRetryQueueMaxRetries:
    """Test maximum retry limit."""

    def test_retry_queue_max_retries_exceeded(self, sample_trade):
        """Test order marked dead after max retries."""
        queue = RetryQueue(max_retries=3)

        assert queue.should_retry(retry_count=3) is False

    def test_retry_queue_allows_retry_below_max(self, sample_trade):
        """Test retry allowed below max attempts."""
        queue = RetryQueue(max_retries=3)

        assert queue.should_retry(retry_count=2) is True

    def test_retry_queue_moves_to_dead_letter_queue(self, sample_trade):
        """Test failed order moved to dead letter queue."""
        queue = RetryQueue(max_retries=3)
        error = BlockchainConnectionError("Persistent failure")

        queue.enqueue(sample_trade, error)

        for _ in range(3):
            item = queue.dequeue()
            if item:
                queue.mark_failed(item)

        assert queue.dead_letter_size() == 1
        assert queue.size() == 0

    def test_retry_queue_respects_custom_max_retries(self):
        """Test custom max retries configuration."""
        queue = RetryQueue(max_retries=5)

        assert queue.should_retry(retry_count=4) is True
        assert queue.should_retry(retry_count=5) is False


class TestRetryQueueErrorTypeDistinction:
    """Test distinguishing error types."""

    def test_is_retriable_network_error(self):
        """Test network errors are retriable."""
        queue = RetryQueue()
        error = BlockchainConnectionError("Network error")

        assert queue.is_retriable(error) is True

    def test_is_retriable_timeout_error(self):
        """Test timeout errors are retriable."""
        queue = RetryQueue()
        error = TimeoutError("Request timeout")

        assert queue.is_retriable(error) is True

    def test_is_retriable_order_placement_error(self):
        """Test order placement errors are retriable."""
        queue = RetryQueue()
        error = OrderPlacementError("Gas spike")

        assert queue.is_retriable(error) is True

    def test_is_not_retriable_insufficient_balance(self):
        """Test insufficient balance errors are not retriable."""
        queue = RetryQueue()
        error = InsufficientBalanceError("Not enough funds")

        assert queue.is_retriable(error) is False

    def test_is_not_retriable_invalid_order(self):
        """Test invalid order errors are not retriable."""
        queue = RetryQueue()
        error = InvalidOrderError("Invalid parameters")

        assert queue.is_retriable(error) is False

    def test_is_not_retriable_generic_exception(self):
        """Test generic exceptions are not retriable by default."""
        queue = RetryQueue()
        error = Exception("Unknown error")

        assert queue.is_retriable(error) is False


class TestRetryQueueCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_retry_queue_circuit_breaker_open_after_threshold(self, sample_trade):
        """Test circuit breaker opens after many failures."""
        queue = RetryQueue(circuit_breaker_threshold=3, circuit_breaker_window=60)

        for _ in range(3):
            queue.record_failure()

        assert queue.is_circuit_open() is True

    def test_retry_queue_circuit_breaker_prevents_retry(self, sample_trade):
        """Test circuit breaker prevents retry when open."""
        queue = RetryQueue(circuit_breaker_threshold=3, circuit_breaker_window=60)

        for _ in range(3):
            queue.record_failure()

        assert queue.should_retry(retry_count=0) is False

    def test_retry_queue_circuit_breaker_closes_after_timeout(self, sample_trade):
        """Test circuit breaker closes after cooldown period."""
        queue = RetryQueue(
            circuit_breaker_threshold=3, circuit_breaker_window=60, circuit_breaker_cooldown=0.1
        )

        for _ in range(3):
            queue.record_failure()

        assert queue.is_circuit_open() is True

        time.sleep(0.2)

        assert queue.is_circuit_open() is False

    def test_retry_queue_circuit_breaker_resets_on_success(self, sample_trade):
        """Test circuit breaker resets failure count on success."""
        queue = RetryQueue(circuit_breaker_threshold=3, circuit_breaker_window=60)

        queue.record_failure()
        queue.record_failure()
        queue.record_success()

        assert queue.is_circuit_open() is False


class TestRetryQueueDueItems:
    """Test retrieving items ready for retry."""

    def test_retry_queue_get_due_retries_empty_queue(self):
        """Test empty queue returns no items."""
        queue = RetryQueue()

        due_items = queue.get_due_retries()

        assert len(due_items) == 0

    def test_retry_queue_get_due_retries_not_ready(self, sample_trade):
        """Test queue doesn't return items not yet due."""
        queue = RetryQueue(base_delay=10.0)
        error = BlockchainConnectionError("Connection failed")

        queue.enqueue(sample_trade, error)
        due_items = queue.get_due_retries()

        assert len(due_items) == 0

    def test_retry_queue_get_due_retries_ready(self, sample_trade):
        """Test queue returns items past retry time."""
        queue = RetryQueue(base_delay=0.0)
        error = BlockchainConnectionError("Connection failed")

        queue.enqueue(sample_trade, error)
        time.sleep(0.1)

        due_items = queue.get_due_retries()

        assert len(due_items) == 1
        assert due_items[0]["trade"] == sample_trade

    def test_retry_queue_get_due_retries_mixed(self, sample_trade):
        """Test queue returns only due items from mixed set."""
        queue = RetryQueue()
        error = BlockchainConnectionError("Connection failed")

        trade2 = Trade(
            id="trade_456",
            trader_address="0x2222222222222222222222222222222222222222",
            market="BTC-USDC",
            side=OrderSide.SELL,
            price=Decimal("50000.0"),
            size=Decimal("0.5"),
            timestamp=datetime.now(timezone.utc),
            tx_hash="0x" + "b" * 64,
        )

        queue.enqueue(sample_trade, error, retry_count=0, next_retry_time=time.time() - 1)
        queue.enqueue(trade2, error, retry_count=0, next_retry_time=time.time() + 100)

        due_items = queue.get_due_retries()

        assert len(due_items) == 1
        assert due_items[0]["trade"] == sample_trade


class TestRetryQueueStatistics:
    """Test queue statistics."""

    def test_retry_queue_tracks_size(self, sample_trade):
        """Test queue tracks number of items."""
        queue = RetryQueue()
        error = BlockchainConnectionError("Connection failed")

        assert queue.size() == 0

        queue.enqueue(sample_trade, error)

        assert queue.size() == 1

    def test_retry_queue_tracks_dead_letter_size(self, sample_trade):
        """Test queue tracks dead letter queue size."""
        queue = RetryQueue(max_retries=1)
        error = BlockchainConnectionError("Connection failed")

        queue.enqueue(sample_trade, error)
        item = queue.dequeue()
        queue.mark_failed(item)

        assert queue.dead_letter_size() == 1

    def test_retry_queue_get_statistics(self, sample_trade):
        """Test retrieving queue statistics."""
        queue = RetryQueue(max_retries=1)
        error = BlockchainConnectionError("Connection failed")

        queue.enqueue(sample_trade, error)
        item = queue.dequeue()
        queue.mark_failed(item)

        stats = queue.get_statistics()

        assert stats["queue_size"] == 0
        assert stats["dead_letter_size"] == 1
        assert "circuit_open" in stats
