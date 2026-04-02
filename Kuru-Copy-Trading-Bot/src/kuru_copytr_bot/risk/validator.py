"""Trade validation for risk management."""

from dataclasses import dataclass
from decimal import Decimal

from src.kuru_copytr_bot.core.enums import OrderSide
from src.kuru_copytr_bot.models.order import Order
from src.kuru_copytr_bot.models.trade import Trade


@dataclass
class ValidationResult:
    """Result of trade validation."""

    is_valid: bool
    reason: str | None = None


class TradeValidator:
    """Validate trades against risk management rules."""

    def __init__(
        self,
        min_balance: Decimal | None = None,
        max_position_size: Decimal | None = None,
        min_order_size: Decimal | None = None,
        market_whitelist: list[str] | None = None,
        market_blacklist: list[str] | None = None,
        max_exposure_usd: Decimal | None = None,
    ):
        """Initialize trade validator.

        Args:
            min_balance: Minimum balance required
            max_position_size: Maximum position size allowed
            min_order_size: Minimum order size allowed
            market_whitelist: List of allowed markets (if set, only these markets allowed)
            market_blacklist: List of disallowed markets
            max_exposure_usd: Maximum total exposure in USD
        """
        self.min_balance = min_balance
        self.max_position_size = max_position_size
        self.min_order_size = min_order_size
        self.market_whitelist = market_whitelist
        self.market_blacklist = market_blacklist
        self.max_exposure_usd = max_exposure_usd

    def validate(
        self,
        trade: Trade,
        current_balance: Decimal,
    ) -> ValidationResult:
        """Validate a trade against all configured rules.

        Args:
            trade: Trade to validate
            current_balance: Current available balance (in quote currency, e.g., USDC)

        Returns:
            ValidationResult: Validation result with reason if invalid
        """
        # Check 1: Minimum balance threshold
        if self.min_balance is not None and current_balance < self.min_balance:
            return ValidationResult(
                is_valid=False,
                reason=f"Balance {current_balance} below minimum threshold {self.min_balance}",
            )

        # Check 2: Balance covers trade cost (for BUY orders)
        if trade.side == OrderSide.BUY:
            trade_cost = trade.notional_value  # price * size
            if current_balance < trade_cost:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Insufficient balance for trade: {current_balance} < {trade_cost}",
                )

        # Check 3: Minimum order size (in USD)
        if self.min_order_size is not None:
            trade_notional = trade.size * trade.price
            if trade_notional < self.min_order_size:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Order size ${trade_notional:.2f} below minimum ${self.min_order_size}",
                )

        # Check 4: Maximum position size in USD (interpret as max single order size for spot)
        if self.max_position_size is not None:
            trade_notional = trade.size * trade.price
            if trade_notional > self.max_position_size:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Order size ${trade_notional:.2f} exceeds maximum ${self.max_position_size}",
                )

        # Check 5: Maximum exposure (interpret as max notional value per order for spot)
        if self.max_exposure_usd is not None:
            trade_notional = trade.notional_value
            if trade_notional > self.max_exposure_usd:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Trade notional {trade_notional} exceeds max exposure {self.max_exposure_usd}",
                )

        # Check 6: Market whitelist (takes precedence over blacklist)
        if self.market_whitelist is not None:
            if trade.market not in self.market_whitelist:
                return ValidationResult(
                    is_valid=False, reason=f"Market {trade.market} not in whitelist"
                )

        # Check 7: Market blacklist (if no whitelist)
        elif self.market_blacklist is not None and trade.market in self.market_blacklist:
            return ValidationResult(is_valid=False, reason=f"Market {trade.market} is blacklisted")

        # All checks passed
        return ValidationResult(is_valid=True, reason=None)

    def validate_order(
        self,
        order: Order,
        current_balance: Decimal,
    ) -> ValidationResult:
        """Validate an order against all configured rules.

        Args:
            order: Order to validate
            current_balance: Current available balance (in quote currency, e.g., USDC)

        Returns:
            ValidationResult: Validation result with reason if invalid
        """
        # Check 1: Minimum balance threshold
        if self.min_balance is not None and current_balance < self.min_balance:
            return ValidationResult(
                is_valid=False,
                reason=f"Balance {current_balance} below minimum threshold {self.min_balance}",
            )

        # Check 2: Balance covers order cost (for BUY orders)
        if order.side == OrderSide.BUY:
            order_cost = order.notional_value  # price * size
            if current_balance < order_cost:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Insufficient balance for order: {current_balance} < {order_cost}",
                )

        # Check 3: Minimum order size (in USD)
        if self.min_order_size is not None:
            order_notional = order.size * order.price
            if order_notional < self.min_order_size:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Order size ${order_notional:.2f} below minimum ${self.min_order_size}",
                )

        # Check 4: Maximum position size in USD (interpret as max single order size for spot)
        if self.max_position_size is not None:
            order_notional = order.size * order.price
            if order_notional > self.max_position_size:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Order size ${order_notional:.2f} exceeds maximum ${self.max_position_size}",
                )

        # Check 5: Maximum exposure (interpret as max notional value per order for spot)
        if self.max_exposure_usd is not None:
            order_notional = order.notional_value
            if order_notional > self.max_exposure_usd:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Order notional {order_notional} exceeds max exposure {self.max_exposure_usd}",
                )

        # Check 6: Market whitelist (takes precedence over blacklist)
        if self.market_whitelist is not None:
            if order.market not in self.market_whitelist:
                return ValidationResult(
                    is_valid=False, reason=f"Market {order.market} not in whitelist"
                )

        # Check 7: Market blacklist (if no whitelist)
        elif self.market_blacklist is not None and order.market in self.market_blacklist:
            return ValidationResult(is_valid=False, reason=f"Market {order.market} is blacklisted")

        # All checks passed
        return ValidationResult(is_valid=True, reason=None)
