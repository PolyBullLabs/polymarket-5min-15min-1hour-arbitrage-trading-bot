"""Tests for TradeCopier retry queue integration."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.kuru_copytr_bot.core.enums import OrderSide
from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientBalanceError,
    InvalidOrderError,
    OrderPlacementError,
)
from src.kuru_copytr_bot.models.trade import Trade
from src.kuru_copytr_bot.trading.copier import TradeCopier


@pytest.fixture
def mock_kuru_client():
    """Mock Kuru client."""
    client = Mock()
    client.get_margin_balance.return_value = Decimal("10000.0")
    client.place_limit_order.return_value = "order_123"
    client.place_market_order.return_value = "order_456"
    return client


@pytest.fixture
def mock_calculator():
    """Mock position size calculator."""
    calc = Mock()
    calc.calculate.return_value = Decimal("1.0")
    return calc


@pytest.fixture
def mock_validator():
    """Mock trade validator."""
    from src.kuru_copytr_bot.risk.validator import ValidationResult

    validator = Mock()
    validator.validate.return_value = ValidationResult(is_valid=True, reason=None)
    return validator


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


class TestCopierRetryEnqueue:
    """Test copier enqueues failed orders."""

    def test_copier_enqueues_failed_order_on_network_error(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier adds failed orders to retry queue on network error."""
        mock_kuru_client.place_limit_order.side_effect = BlockchainConnectionError("Network error")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None
        assert copier.retry_queue.size() == 1

    def test_copier_enqueues_failed_order_on_timeout(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier enqueues order on timeout error."""
        mock_kuru_client.place_limit_order.side_effect = TimeoutError("Request timeout")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None
        assert copier.retry_queue.size() == 1

    def test_copier_enqueues_failed_order_on_placement_error(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier enqueues order on placement error."""
        mock_kuru_client.place_limit_order.side_effect = OrderPlacementError("Gas spike")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None
        assert copier.retry_queue.size() == 1

    def test_copier_does_not_enqueue_insufficient_balance(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier doesn't retry validation errors."""
        mock_kuru_client.place_limit_order.side_effect = InsufficientBalanceError(
            "Insufficient balance"
        )

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None
        assert copier.retry_queue.size() == 0

    def test_copier_does_not_enqueue_invalid_order(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier doesn't enqueue invalid order errors."""
        mock_kuru_client.place_limit_order.side_effect = InvalidOrderError("Invalid parameters")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None
        assert copier.retry_queue.size() == 0


class TestCopierRetryProcessing:
    """Test copier processes retry queue."""

    def test_copier_retries_queued_order(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier processes retry queue."""
        from src.kuru_copytr_bot.trading.retry_queue import RetryQueue

        mock_kuru_client.place_limit_order.side_effect = [
            BlockchainConnectionError("Network error"),
            "order_123",
        ]

        retry_queue = RetryQueue(base_delay=0.0)
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
            retry_queue=retry_queue,
        )

        first_result = copier.process_trade(sample_trade)
        assert first_result is None
        assert copier.retry_queue.size() == 1

        copier.process_retry_queue()

        assert mock_kuru_client.place_limit_order.call_count == 2

    def test_copier_records_success_on_retry(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier records success after retry."""
        from src.kuru_copytr_bot.trading.retry_queue import RetryQueue

        mock_kuru_client.place_limit_order.side_effect = [
            BlockchainConnectionError("Network error"),
            "order_123",
        ]

        retry_queue = RetryQueue(base_delay=0.0)
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
            retry_queue=retry_queue,
        )

        copier.process_trade(sample_trade)
        copier.process_retry_queue()

        assert copier.retry_queue.size() == 0
        stats = copier.get_statistics()
        assert stats["successful_trades"] == 1

    def test_copier_respects_circuit_breaker(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier respects circuit breaker."""
        from src.kuru_copytr_bot.trading.retry_queue import RetryQueue

        mock_kuru_client.place_limit_order.side_effect = BlockchainConnectionError("Network error")

        retry_queue = RetryQueue(base_delay=0.0, circuit_breaker_threshold=3)
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
            retry_queue=retry_queue,
        )

        for _ in range(5):
            copier.process_trade(sample_trade)

        assert copier.retry_queue.is_circuit_open() is True

        copier.process_retry_queue()

        assert mock_kuru_client.place_limit_order.call_count == 5

    def test_copier_processes_only_due_retries(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier only processes retries that are due."""
        mock_kuru_client.place_limit_order.side_effect = BlockchainConnectionError("Network error")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        assert copier.retry_queue.size() == 1

        copier.process_retry_queue()

        assert copier.retry_queue.size() == 1


class TestCopierRetryStatistics:
    """Test retry statistics tracking."""

    def test_copier_includes_retry_statistics(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier statistics include retry queue info."""
        mock_kuru_client.place_limit_order.side_effect = BlockchainConnectionError("Network error")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        stats = copier.get_statistics()

        assert "retry_queue_size" in stats
        assert stats["retry_queue_size"] == 1
        assert "dead_letter_size" in stats
        assert "circuit_open" in stats

    def test_copier_tracks_retried_orders(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier tracks number of retried orders."""
        from src.kuru_copytr_bot.trading.retry_queue import RetryQueue

        mock_kuru_client.place_limit_order.side_effect = [
            BlockchainConnectionError("Network error"),
            "order_123",
        ]

        retry_queue = RetryQueue(base_delay=0.0)
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
            retry_queue=retry_queue,
        )

        copier.process_trade(sample_trade)
        copier.process_retry_queue()

        stats = copier.get_statistics()
        assert stats["retried_orders"] >= 1


class TestCopierRetryMaxAttempts:
    """Test max retry attempts handling."""

    def test_copier_moves_to_dead_letter_after_max_retries(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test order moved to dead letter queue after max retries."""
        from src.kuru_copytr_bot.trading.retry_queue import RetryQueue

        mock_kuru_client.place_limit_order.side_effect = BlockchainConnectionError(
            "Persistent failure"
        )

        retry_queue = RetryQueue(base_delay=0.0, max_retries=3)
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
            retry_queue=retry_queue,
        )

        copier.process_trade(sample_trade)

        for _ in range(4):
            copier.process_retry_queue()

        stats = copier.get_statistics()
        assert stats["dead_letter_size"] >= 1
        assert stats["retry_queue_size"] == 0

    def test_copier_logs_dead_letter_items(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Test copier logs orders that exceed max retries."""
        from src.kuru_copytr_bot.trading.retry_queue import RetryQueue

        mock_kuru_client.place_limit_order.side_effect = BlockchainConnectionError(
            "Persistent failure"
        )

        retry_queue = RetryQueue(base_delay=0.0, max_retries=3)
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
            retry_queue=retry_queue,
        )

        copier.process_trade(sample_trade)

        for _ in range(4):
            copier.process_retry_queue()

        stats = copier.get_statistics()
        assert stats["dead_letter_size"] >= 1
