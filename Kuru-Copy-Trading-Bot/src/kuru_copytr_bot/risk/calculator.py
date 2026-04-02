"""Position size calculator for copy trading."""

from decimal import ROUND_DOWN, Decimal


class PositionSizeCalculator:
    """Calculate target position size for copy trading with risk management."""

    def __init__(
        self,
        copy_ratio: Decimal,
        max_position_size: Decimal | None = None,
        min_order_size: Decimal | None = None,
        tick_size: Decimal | None = None,
        margin_requirement: Decimal | None = None,
        respect_balance: bool = False,
        enforce_minimum: bool = True,
    ):
        """Initialize position size calculator.

        Args:
            copy_ratio: Ratio to apply to source position (e.g., 0.5 for 50%, 2.0 for 200%)
            max_position_size: Maximum position size allowed
            min_order_size: Minimum order size allowed
            tick_size: Tick size for rounding
            margin_requirement: Margin requirement as decimal (e.g., 0.1 for 10%)
            respect_balance: Whether to reduce size based on available balance
            enforce_minimum: Whether to round up to minimum or return 0

        Raises:
            ValueError: If parameters are invalid
        """
        if copy_ratio <= 0:
            raise ValueError("Copy ratio must be positive")
        if max_position_size is not None and max_position_size <= 0:
            raise ValueError("Max position size must be positive")
        if min_order_size is not None and min_order_size <= 0:
            raise ValueError("Min order size must be positive")

        self.copy_ratio = copy_ratio
        self.max_position_size = max_position_size
        self.min_order_size = min_order_size
        self.tick_size = tick_size
        self.margin_requirement = margin_requirement
        self.respect_balance = respect_balance
        self.enforce_minimum = enforce_minimum

    def calculate(
        self,
        source_size: Decimal,
        available_balance: Decimal,
        price: Decimal | None = None,
    ) -> Decimal:
        """Calculate target position size based on source and constraints.

        Args:
            source_size: Source position size to copy
            available_balance: Available balance for trading
            price: Price for cost calculation (required if checking balance)

        Returns:
            Decimal: Calculated target position size

        Raises:
            ValueError: If source_size is negative
        """
        if source_size < 0:
            raise ValueError("Source size cannot be negative")

        if source_size == 0:
            return Decimal("0")

        # Step 1: Apply copy ratio
        target_size = source_size * self.copy_ratio

        # Step 2: Enforce minimum order size (in quote currency)
        # Do this early so we know the actual order size before balance checks
        if self.min_order_size is not None:
            if price is not None:
                target_value = target_size * price
                if target_value < self.min_order_size:
                    if self.enforce_minimum:
                        # Calculate minimum size in base currency
                        target_size = self.min_order_size / price
                    else:
                        return Decimal("0")
            else:
                # If no price provided, compare sizes directly (assume same currency)
                if target_size < self.min_order_size:
                    if self.enforce_minimum:
                        target_size = self.min_order_size
                    else:
                        return Decimal("0")

        # Step 3: Apply maximum order size limit (in quote currency)
        if self.max_position_size is not None:
            if price is not None:
                target_value = target_size * price
                if target_value > self.max_position_size:
                    # Calculate maximum size in base currency
                    target_size = self.max_position_size / price
            else:
                # If no price provided, compare sizes directly (assume same currency)
                target_size = min(target_size, self.max_position_size)

        # Step 4: Check available balance if price provided
        if price is not None and available_balance >= 0:
            # Calculate required capital
            if self.margin_requirement is not None:
                # Margin trading: need margin_requirement * notional
                required_capital = target_size * price * self.margin_requirement
            else:
                # Spot trading: need full notional
                required_capital = target_size * price

            # Check if we have enough balance
            if required_capital > available_balance:
                if self.respect_balance:
                    # Reduce size to fit available balance
                    if self.margin_requirement is not None:
                        affordable_size = available_balance / (price * self.margin_requirement)
                    else:
                        affordable_size = available_balance / price
                    target_size = min(target_size, affordable_size)
                else:
                    # Insufficient balance, return 0
                    return Decimal("0")

        # Step 5: Final minimum check after balance adjustment
        # If we scaled down below minimum (due to balance), return 0 instead
        if self.min_order_size is not None and price is not None:
            final_value = target_size * price
            if final_value < self.min_order_size:
                return Decimal("0")

        # Step 6: Round to tick size if specified
        if self.tick_size is not None:
            target_size = (target_size / self.tick_size).quantize(
                Decimal("1"), rounding=ROUND_DOWN
            ) * self.tick_size

        return target_size
