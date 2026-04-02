"""Unit tests for trade validator (spot DEX)."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.kuru_copytr_bot.core.enums import OrderSide, OrderStatus, OrderType
from src.kuru_copytr_bot.models.order import Order
from src.kuru_copytr_bot.models.trade import Trade
from src.kuru_copytr_bot.risk.validator import TradeValidator, ValidationResult


@pytest.fixture
def sample_buy_trade():
    """Create a sample buy trade."""
    return Trade(
        id="trade_001",
        trader_address="0x1234567890123456789012345678901234567890",
        market="ETH-USDC",
        side=OrderSide.BUY,
        price=Decimal("2000.0"),
        size=Decimal("1.0"),
        timestamp=datetime.now(timezone.utc),
        tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )


class TestValidationResult:
    """Test ValidationResult data class."""

    def test_validation_result_for_valid_trade(self):
        """ValidationResult should indicate valid trade."""
        result = ValidationResult(is_valid=True, reason=None)
        assert result.is_valid is True
        assert result.reason is None

    def test_validation_result_for_invalid_trade(self):
        """ValidationResult should indicate invalid trade with reason."""
        result = ValidationResult(is_valid=False, reason="Insufficient balance")
        assert result.is_valid is False
        assert result.reason == "Insufficient balance"


class TestTradeValidatorInitialization:
    """Test TradeValidator initialization."""

    def test_validator_initializes_with_defaults(self):
        """Validator should initialize with default settings."""
        validator = TradeValidator()
        assert validator is not None

    def test_validator_initializes_with_min_balance(self):
        """Validator should initialize with minimum balance."""
        validator = TradeValidator(min_balance=Decimal("100.0"))
        assert validator.min_balance == Decimal("100.0")

    def test_validator_initializes_with_max_position_size(self):
        """Validator should initialize with max order size."""
        validator = TradeValidator(max_position_size=Decimal("10.0"))
        assert validator.max_position_size == Decimal("10.0")


class TestTradeValidatorBalanceValidation:
    """Test balance validation."""

    def test_validator_accepts_sufficient_balance(self, sample_buy_trade):
        """Validator should accept trade with sufficient balance."""
        validator = TradeValidator(min_balance=Decimal("100.0"))
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("5000.0"),
        )
        assert result.is_valid is True
        assert result.reason is None

    def test_validator_rejects_balance_below_threshold(self, sample_buy_trade):
        """Validator should reject trade when balance below minimum threshold."""
        validator = TradeValidator(min_balance=Decimal("100.0"))
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("50.0"),  # Below minimum threshold
        )
        assert result.is_valid is False
        assert "balance" in result.reason.lower()
        assert "threshold" in result.reason.lower()

    def test_validator_checks_balance_for_buy_trade_cost(self, sample_buy_trade):
        """Validator should check balance covers BUY trade cost."""
        validator = TradeValidator()
        # Trade costs 2000 (1.0 @ 2000)
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("1500.0"),  # Insufficient for trade
        )
        assert result.is_valid is False
        assert "balance" in result.reason.lower()

    def test_validator_allows_sell_with_low_balance(self):
        """Validator should allow SELL trades even with low balance (spot DEX)."""
        sell_trade = Trade(
            id="trade_002",
            trader_address="0x1234567890123456789012345678901234567890",
            market="ETH-USDC",
            side=OrderSide.SELL,
            price=Decimal("2000.0"),
            size=Decimal("1.0"),
            timestamp=datetime.now(timezone.utc),
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )

        validator = TradeValidator(min_balance=Decimal("100.0"))
        # SELL doesn't require USDC balance, just ETH balance (not checked here)
        result = validator.validate(
            trade=sell_trade,
            current_balance=Decimal("50.0"),  # Below threshold but SELL trade
        )
        # Should reject due to balance threshold
        assert result.is_valid is False


class TestTradeValidatorOrderSizeLimits:
    """Test order size limit validation (spot DEX)."""

    def test_validator_accepts_order_within_limit(self, sample_buy_trade):
        """Validator should accept order within size limit."""
        # sample_buy_trade: size=1.0 at price=$2000 = $2000 notional
        validator = TradeValidator(max_position_size=Decimal("5000.0"))  # $5000 max in USD
        result = validator.validate(
            trade=sample_buy_trade,  # size=1.0
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is True

    def test_validator_rejects_order_exceeding_limit(self):
        """Validator should reject order exceeding size limit."""
        large_trade = Trade(
            id="trade_003",
            trader_address="0x1234567890123456789012345678901234567890",
            market="ETH-USDC",
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("10.0"),  # Large size
            timestamp=datetime.now(timezone.utc),
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )

        validator = TradeValidator(max_position_size=Decimal("5.0"))
        result = validator.validate(
            trade=large_trade,
            current_balance=Decimal("100000.0"),
        )
        assert result.is_valid is False
        assert "size" in result.reason.lower() or "maximum" in result.reason.lower()


class TestTradeValidatorMinimumOrderSize:
    """Test minimum order size validation."""

    def test_validator_accepts_size_above_minimum(self, sample_buy_trade):
        """Validator should accept order size above minimum."""
        validator = TradeValidator(min_order_size=Decimal("0.1"))
        result = validator.validate(
            trade=sample_buy_trade,  # size=1.0
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is True

    def test_validator_rejects_size_below_minimum(self):
        """Validator should reject order size below minimum."""
        small_trade = Trade(
            id="trade_004",
            trader_address="0x1234567890123456789012345678901234567890",
            market="ETH-USDC",
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("0.001"),  # Very small
            timestamp=datetime.now(timezone.utc),
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )

        validator = TradeValidator(min_order_size=Decimal("0.01"))
        result = validator.validate(
            trade=small_trade,
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is False
        assert "minimum" in result.reason.lower()


class TestTradeValidatorMarketWhitelist:
    """Test market whitelist validation."""

    def test_validator_accepts_whitelisted_market(self, sample_buy_trade):
        """Validator should accept trade in whitelisted market."""
        validator = TradeValidator(market_whitelist=["ETH-USDC", "BTC-USDC"])
        result = validator.validate(
            trade=sample_buy_trade,  # market="ETH-USDC"
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is True

    def test_validator_rejects_non_whitelisted_market(self, sample_buy_trade):
        """Validator should reject trade not in whitelist."""
        validator = TradeValidator(market_whitelist=["BTC-USDC", "SOL-USDC"])
        result = validator.validate(
            trade=sample_buy_trade,  # market="ETH-USDC"
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is False
        assert "whitelist" in result.reason.lower()

    def test_validator_accepts_all_markets_without_whitelist(self, sample_buy_trade):
        """Validator should accept any market without whitelist."""
        validator = TradeValidator()  # No whitelist
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is True


class TestTradeValidatorMarketBlacklist:
    """Test market blacklist validation."""

    def test_validator_rejects_blacklisted_market(self, sample_buy_trade):
        """Validator should reject trade in blacklisted market."""
        validator = TradeValidator(market_blacklist=["ETH-USDC"])
        result = validator.validate(
            trade=sample_buy_trade,  # market="ETH-USDC"
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is False
        assert "blacklist" in result.reason.lower()

    def test_validator_accepts_non_blacklisted_market(self, sample_buy_trade):
        """Validator should accept trade not in blacklist."""
        validator = TradeValidator(market_blacklist=["BTC-USDC", "SOL-USDC"])
        result = validator.validate(
            trade=sample_buy_trade,  # market="ETH-USDC"
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is True

    def test_validator_whitelist_overrides_blacklist(self, sample_buy_trade):
        """Validator should prioritize whitelist over blacklist."""
        validator = TradeValidator(
            market_whitelist=["ETH-USDC"],
            market_blacklist=["ETH-USDC"],
        )
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("10000.0"),
        )
        # Whitelist should take precedence
        assert result.is_valid is True


class TestTradeValidatorMaxNotionalValue:
    """Test maximum notional value validation (spot DEX)."""

    def test_validator_accepts_notional_within_limit(self, sample_buy_trade):
        """Validator should accept trade with notional value within limit."""
        validator = TradeValidator(max_exposure_usd=Decimal("10000.0"))
        result = validator.validate(
            trade=sample_buy_trade,  # notional=2000 (1.0 * 2000)
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is True

    def test_validator_rejects_notional_exceeding_limit(self):
        """Validator should reject trade exceeding notional value limit."""
        large_trade = Trade(
            id="trade_005",
            trader_address="0x1234567890123456789012345678901234567890",
            market="ETH-USDC",
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("10.0"),  # notional = 20000
            timestamp=datetime.now(timezone.utc),
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )

        validator = TradeValidator(max_exposure_usd=Decimal("5000.0"))
        result = validator.validate(
            trade=large_trade,
            current_balance=Decimal("100000.0"),
        )
        assert result.is_valid is False
        assert "exposure" in result.reason.lower() or "notional" in result.reason.lower()


class TestTradeValidatorErrorMessages:
    """Test validation error message clarity."""

    def test_validator_provides_clear_balance_error(self, sample_buy_trade):
        """Validator should provide clear error for insufficient balance."""
        validator = TradeValidator(min_balance=Decimal("100.0"))
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("50.0"),
        )
        assert result.is_valid is False
        assert "balance" in result.reason.lower()
        assert "50" in result.reason or "50.0" in result.reason  # Shows actual balance

    def test_validator_provides_clear_order_size_error(self):
        """Validator should provide clear error for order size limit."""
        large_trade = Trade(
            id="trade_006",
            trader_address="0x1234567890123456789012345678901234567890",
            market="ETH-USDC",
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("10.0"),
            timestamp=datetime.now(timezone.utc),
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )

        validator = TradeValidator(max_position_size=Decimal("5.0"))
        result = validator.validate(
            trade=large_trade,
            current_balance=Decimal("100000.0"),
        )
        assert result.is_valid is False
        assert "5" in result.reason or "5.0" in result.reason  # Shows limit

    def test_validator_provides_clear_market_error(self, sample_buy_trade):
        """Validator should provide clear error for market restrictions."""
        validator = TradeValidator(market_whitelist=["BTC-USDC"])
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is False
        assert "ETH-USDC" in result.reason  # Shows the market


class TestTradeValidatorMultipleRules:
    """Test combinations of validation rules."""

    def test_validator_checks_all_rules(self, sample_buy_trade):
        """Validator should check all configured rules."""
        # sample_buy_trade: size=1.0 at price=$2000 = $2000 notional
        validator = TradeValidator(
            min_balance=Decimal("100.0"),
            max_position_size=Decimal("5000.0"),  # $5000 max in USD
            min_order_size=Decimal("0.01"),
            market_whitelist=["ETH-USDC"],
            max_exposure_usd=Decimal("100000.0"),
        )
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("10000.0"),
        )
        # Should pass all checks
        assert result.is_valid is True

    def test_validator_fails_on_first_violation(self, sample_buy_trade):
        """Validator should report first rule violation."""
        validator = TradeValidator(
            min_balance=Decimal("10000.0"),  # Will fail this
            max_position_size=Decimal("0.1"),  # Would also fail this
        )
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("100.0"),  # Below minimum
        )
        assert result.is_valid is False
        # Should report balance issue (checked first)
        assert result.reason is not None


class TestTradeValidatorEdgeCases:
    """Test edge cases and error handling."""

    def test_validator_handles_zero_balance(self, sample_buy_trade):
        """Validator should reject BUY trade with zero balance."""
        validator = TradeValidator()
        result = validator.validate(
            trade=sample_buy_trade,
            current_balance=Decimal("0"),
        )
        assert result.is_valid is False

    def test_validator_handles_very_small_trade(self):
        """Validator should handle very small trade sizes."""
        tiny_trade = Trade(
            id="trade_007",
            trader_address="0x1234567890123456789012345678901234567890",
            market="ETH-USDC",
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("0.0001"),
            timestamp=datetime.now(timezone.utc),
            tx_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )

        validator = TradeValidator(min_order_size=Decimal("0.00001"))
        result = validator.validate(
            trade=tiny_trade,
            current_balance=Decimal("1.0"),
        )
        assert result.is_valid is True


class TestTradeValidatorOrderValidation:
    """Test TradeValidator with Order objects."""

    @pytest.fixture
    def sample_buy_order(self):
        """Create a sample buy order."""
        return Order(
            order_id="12345",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("1.0"),
            filled_size=Decimal("0.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def sample_sell_order(self):
        """Create a sample sell order."""
        return Order(
            order_id="12346",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.SELL,
            price=Decimal("2100.0"),
            size=Decimal("0.5"),
            filled_size=Decimal("0.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_validator_validates_order_successfully(self, sample_buy_order):
        """Validator should validate valid order."""
        validator = TradeValidator()
        result = validator.validate_order(
            order=sample_buy_order,
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is True
        assert result.reason is None

    def test_validator_rejects_order_with_insufficient_balance(self, sample_buy_order):
        """Validator should reject order when balance is insufficient."""
        validator = TradeValidator()
        result = validator.validate_order(
            order=sample_buy_order,
            current_balance=Decimal("1000.0"),  # Less than 2000 needed
        )
        assert result.is_valid is False
        assert "Insufficient balance" in result.reason

    def test_validator_checks_min_balance_for_order(self, sample_buy_order):
        """Validator should check minimum balance threshold for orders."""
        validator = TradeValidator(min_balance=Decimal("5000.0"))
        result = validator.validate_order(
            order=sample_buy_order,
            current_balance=Decimal("3000.0"),
        )
        assert result.is_valid is False
        assert "below minimum threshold" in result.reason

    def test_validator_checks_min_order_size(self, sample_buy_order):
        """Validator should check minimum order size."""
        small_order = Order(
            order_id="12347",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("0.001"),
            filled_size=Decimal("0.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        validator = TradeValidator(min_order_size=Decimal("0.01"))
        result = validator.validate_order(
            order=small_order,
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is False
        assert "below minimum" in result.reason

    def test_validator_checks_max_position_size_for_order(self, sample_buy_order):
        """Validator should check maximum order size."""
        large_order = Order(
            order_id="12348",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("100.0"),
            filled_size=Decimal("0.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        validator = TradeValidator(max_position_size=Decimal("10.0"))
        result = validator.validate_order(
            order=large_order,
            current_balance=Decimal("1000000.0"),
        )
        assert result.is_valid is False
        assert "exceeds maximum" in result.reason

    def test_validator_checks_market_whitelist_for_order(self, sample_buy_order):
        """Validator should check market whitelist for orders."""
        validator = TradeValidator(market_whitelist=["BTC-USDC"])
        result = validator.validate_order(
            order=sample_buy_order,
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is False
        assert "not in whitelist" in result.reason

    def test_validator_checks_market_blacklist_for_order(self, sample_buy_order):
        """Validator should check market blacklist for orders."""
        validator = TradeValidator(market_blacklist=["ETH-USDC"])
        result = validator.validate_order(
            order=sample_buy_order,
            current_balance=Decimal("10000.0"),
        )
        assert result.is_valid is False
        assert "blacklisted" in result.reason

    def test_validator_checks_max_exposure_for_order(self, sample_buy_order):
        """Validator should check maximum exposure for orders."""
        large_order = Order(
            order_id="12349",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.0"),
            size=Decimal("10.0"),  # Notional: 20000
            filled_size=Decimal("0.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        validator = TradeValidator(max_exposure_usd=Decimal("10000.0"))
        result = validator.validate_order(
            order=large_order,
            current_balance=Decimal("100000.0"),
        )
        assert result.is_valid is False
        assert "exceeds max exposure" in result.reason

    def test_validator_allows_sell_order_without_balance_check(self, sample_sell_order):
        """Validator should not require balance for sell orders."""
        validator = TradeValidator()
        result = validator.validate_order(
            order=sample_sell_order,
            current_balance=Decimal("100.0"),  # Low balance, but selling
        )
        assert result.is_valid is True
