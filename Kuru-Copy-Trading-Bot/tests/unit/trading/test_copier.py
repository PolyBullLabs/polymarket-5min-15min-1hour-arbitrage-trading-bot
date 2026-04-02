"""Tests for trade copier."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.kuru_copytr_bot.core.enums import OrderSide, OrderType
from src.kuru_copytr_bot.core.exceptions import (
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
    client.get_positions.return_value = []
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


class TestTradeCopierInitialization:
    """Test trade copier initialization."""

    def test_copier_initializes_with_required_components(
        self, mock_kuru_client, mock_calculator, mock_validator
    ):
        """Copier should initialize with required components."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        assert copier.kuru_client == mock_kuru_client
        assert copier.calculator == mock_calculator
        assert copier.validator == mock_validator

    def test_copier_initializes_with_default_order_type(
        self, mock_kuru_client, mock_calculator, mock_validator
    ):
        """Copier should default to limit orders."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        assert copier.default_order_type == OrderType.LIMIT


class TestTradeCopierProcessing:
    """Test trade processing."""

    def test_copier_processes_valid_trade(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should process valid trade successfully."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id == "order_123"
        mock_calculator.calculate.assert_called_once()
        mock_validator.validate.assert_called_once()
        mock_kuru_client.place_limit_order.assert_called_once()

    def test_copier_calculates_position_size(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should calculate position size using calculator."""
        mock_calculator.calculate.return_value = Decimal("2.5")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        # Verify calculator was called with correct parameters
        call_args = mock_calculator.calculate.call_args
        assert call_args[1]["source_size"] == Decimal("5.0")
        assert call_args[1]["available_balance"] == Decimal("10000.0")
        assert call_args[1]["price"] == Decimal("2000.0")

    def test_copier_validates_trade_before_execution(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should validate trade before execution."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        # Verify validator was called
        mock_validator.validate.assert_called_once()
        call_args = mock_validator.validate.call_args
        # Should create a new trade with calculated size
        trade_arg = call_args.kwargs["trade"]
        assert trade_arg.market == "ETH-USDC"
        assert trade_arg.side == OrderSide.BUY

    def test_copier_rejects_invalid_trade(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should reject invalid trades."""
        from src.kuru_copytr_bot.risk.validator import ValidationResult

        mock_validator.validate.return_value = ValidationResult(
            is_valid=False, reason="Insufficient balance"
        )

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None
        mock_kuru_client.place_limit_order.assert_not_called()

    def test_copier_skips_zero_size_orders(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should skip orders with zero calculated size."""
        mock_calculator.calculate.return_value = Decimal("0")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None
        mock_validator.validate.assert_not_called()
        mock_kuru_client.place_limit_order.assert_not_called()

    def test_copier_passes_market_address_to_kuru_client(
        self, mock_kuru_client, mock_calculator, mock_validator
    ):
        """Copier should pass market address from trade to KuruClient."""
        # Create trade with specific market address (contract address)
        trade = Trade(
            id="trade_1",
            trader_address="0x1111111111111111111111111111111111111111",
            market="0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # Contract address
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("5.0"),
            timestamp=datetime.now(timezone.utc),
            tx_hash="0x" + "a" * 64,
        )

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(trade)

        # Verify KuruClient was called with the market address from the trade
        mock_kuru_client.place_limit_order.assert_called_once()
        call_kwargs = mock_kuru_client.place_limit_order.call_args[1]
        assert call_kwargs["market"] == "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


class TestTradeCopierOrderTypes:
    """Test different order types."""

    def test_copier_places_limit_order_by_default(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should place limit order by default."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        mock_kuru_client.place_limit_order.assert_called_once_with(
            market="ETH-USDC",
            side=OrderSide.BUY,
            size=Decimal("1.0"),
            price=Decimal("2000.0"),
        )

    def test_copier_places_market_order_when_specified(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should place market order when order type is MARKET."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
            default_order_type=OrderType.MARKET,
        )

        copier.process_trade(sample_trade)

        mock_kuru_client.place_market_order.assert_called_once_with(
            market="ETH-USDC",
            side=OrderSide.BUY,
            size=Decimal("1.0"),
        )

    def test_copier_handles_sell_orders(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should handle sell orders correctly."""
        sample_trade.side = OrderSide.SELL

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        mock_kuru_client.place_limit_order.assert_called_once()
        call_args = mock_kuru_client.place_limit_order.call_args
        assert call_args[1]["side"] == OrderSide.SELL


class TestTradeCopierErrorHandling:
    """Test error handling."""

    def test_copier_handles_insufficient_balance(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should handle insufficient balance errors."""
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

    def test_copier_handles_invalid_order_error(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should handle invalid order errors."""
        mock_kuru_client.place_limit_order.side_effect = InvalidOrderError(
            "Invalid order parameters"
        )

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None

    def test_copier_handles_order_placement_error(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should handle order placement errors."""
        mock_kuru_client.place_limit_order.side_effect = OrderPlacementError("Network error")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None

    def test_copier_handles_balance_check_failure(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should handle balance check failures."""
        mock_kuru_client.get_margin_balance.side_effect = Exception("Connection error")

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_id = copier.process_trade(sample_trade)

        assert order_id is None


class TestTradeCopierBatchProcessing:
    """Test batch trade processing."""

    def test_copier_processes_multiple_trades(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should process multiple trades in batch."""
        trade2 = Trade(
            id="trade_456",
            trader_address="0x1111111111111111111111111111111111111111",
            market="BTC-USDC",
            side=OrderSide.SELL,
            price=Decimal("50000.0"),
            size=Decimal("0.5"),
            timestamp=datetime.now(timezone.utc),
            tx_hash="0x" + "b" * 64,
        )

        mock_kuru_client.place_limit_order.side_effect = ["order_1", "order_2"]

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_ids = copier.process_trades([sample_trade, trade2])

        assert len(order_ids) == 2
        assert order_ids[0] == "order_1"
        assert order_ids[1] == "order_2"

    def test_copier_continues_on_individual_trade_failure(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should continue processing trades even if one fails."""
        trade2 = Trade(
            id="trade_456",
            trader_address="0x1111111111111111111111111111111111111111",
            market="BTC-USDC",
            side=OrderSide.SELL,
            price=Decimal("50000.0"),
            size=Decimal("0.5"),
            timestamp=datetime.now(timezone.utc),
            tx_hash="0x" + "b" * 64,
        )

        # First trade fails, second succeeds
        mock_kuru_client.place_limit_order.side_effect = [
            InsufficientBalanceError("Insufficient balance"),
            "order_2",
        ]

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        order_ids = copier.process_trades([sample_trade, trade2])

        assert len(order_ids) == 1
        assert order_ids[0] == "order_2"


class TestTradeCopierStatistics:
    """Test trade statistics tracking."""

    def test_copier_tracks_successful_trades(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should track successful trade count."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)
        copier.process_trade(sample_trade)

        stats = copier.get_statistics()
        assert stats["successful_trades"] == 2

    def test_copier_tracks_failed_trades(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should track failed trade count."""
        mock_kuru_client.place_limit_order.side_effect = InsufficientBalanceError(
            "Insufficient balance"
        )

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        stats = copier.get_statistics()
        assert stats["failed_trades"] == 1

    def test_copier_tracks_rejected_trades(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should track rejected trade count."""
        from src.kuru_copytr_bot.risk.validator import ValidationResult

        mock_validator.validate.return_value = ValidationResult(
            is_valid=False, reason="Max position exceeded"
        )

        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)

        stats = copier.get_statistics()
        assert stats["rejected_trades"] == 1

    def test_copier_resets_statistics(
        self, mock_kuru_client, mock_calculator, mock_validator, sample_trade
    ):
        """Copier should reset statistics."""
        copier = TradeCopier(
            kuru_client=mock_kuru_client,
            calculator=mock_calculator,
            validator=mock_validator,
        )

        copier.process_trade(sample_trade)
        copier.reset_statistics()

        stats = copier.get_statistics()
        assert stats["successful_trades"] == 0
        assert stats["failed_trades"] == 0
        assert stats["rejected_trades"] == 0
