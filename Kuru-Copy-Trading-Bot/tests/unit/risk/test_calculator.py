"""Unit tests for position size calculator."""

from decimal import Decimal

import pytest

from src.kuru_copytr_bot.risk.calculator import PositionSizeCalculator


class TestPositionSizeCalculatorBasic:
    """Test basic position size calculation."""

    def test_calculator_initializes_with_copy_ratio(self):
        """Calculator should initialize with copy ratio."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("0.5"))
        assert calc.copy_ratio == Decimal("0.5")

    def test_calculator_applies_copy_ratio(self):
        """Calculator should apply copy ratio to source size."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("0.5"))
        source_size = Decimal("10.0")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("5.0")

    def test_calculator_applies_double_ratio(self):
        """Calculator should apply 2x copy ratio correctly."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("2.0"))
        source_size = Decimal("10.0")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("10000.0"),
        )
        assert target_size == Decimal("20.0")

    def test_calculator_applies_one_to_one_ratio(self):
        """Calculator should apply 1:1 ratio (1.0x)."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("1.0"))
        source_size = Decimal("7.5")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("7.5")


class TestPositionSizeCalculatorMaxLimits:
    """Test maximum position size enforcement."""

    def test_calculator_respects_max_position_size(self):
        """Calculator should not exceed max position size."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            max_position_size=Decimal("5.0"),
        )
        source_size = Decimal("10.0")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("5.0")

    def test_calculator_respects_max_position_size_with_ratio(self):
        """Calculator should apply max limit after ratio."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("2.0"),
            max_position_size=Decimal("10.0"),
        )
        source_size = Decimal("8.0")  # Would be 16.0 with 2x ratio
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("10000.0"),
        )
        assert target_size == Decimal("10.0")

    def test_calculator_allows_size_below_max(self):
        """Calculator should allow sizes below maximum."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            max_position_size=Decimal("100.0"),
        )
        source_size = Decimal("5.0")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("5.0")


class TestPositionSizeCalculatorMinLimits:
    """Test minimum order size enforcement."""

    def test_calculator_enforces_minimum_order_size(self):
        """Calculator should enforce minimum order size."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("0.1"),
            min_order_size=Decimal("1.0"),
        )
        source_size = Decimal("5.0")  # Would be 0.5 with 0.1x ratio
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        # Should round up to minimum
        assert target_size == Decimal("1.0")

    def test_calculator_returns_zero_if_below_minimum(self):
        """Calculator should return zero if calculated size is too small."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("0.01"),
            min_order_size=Decimal("1.0"),
            enforce_minimum=False,  # Don't round up, return 0
        )
        source_size = Decimal("10.0")  # Would be 0.1 with 0.01x ratio
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("0")

    def test_calculator_allows_size_above_minimum(self):
        """Calculator should allow sizes above minimum."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            min_order_size=Decimal("0.1"),
        )
        source_size = Decimal("5.0")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("5.0")


class TestPositionSizeCalculatorBalanceChecks:
    """Test balance-based size calculations."""

    def test_calculator_returns_zero_for_insufficient_balance(self):
        """Calculator should return zero if insufficient balance."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("1.0"))
        source_size = Decimal("10.0")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("5.0"),
            price=Decimal("1.0"),
        )
        # Need 10 units but only have 5
        assert target_size == Decimal("0")

    def test_calculator_reduces_size_for_limited_balance(self):
        """Calculator should reduce size based on available balance."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            respect_balance=True,
        )
        source_size = Decimal("10.0")
        price = Decimal("100.0")
        # Can only afford 5 units at price 100
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("500.0"),
            price=price,
        )
        assert target_size == Decimal("5.0")

    def test_calculator_handles_zero_balance(self):
        """Calculator should return zero for zero balance."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("1.0"))
        target_size = calc.calculate(
            source_size=Decimal("10.0"),
            available_balance=Decimal("0"),
            price=Decimal("100.0"),
        )
        assert target_size == Decimal("0")

    def test_calculator_handles_sufficient_balance(self):
        """Calculator should use full size with sufficient balance."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("1.0"))
        target_size = calc.calculate(
            source_size=Decimal("5.0"),
            available_balance=Decimal("10000.0"),
            price=Decimal("100.0"),
        )
        assert target_size == Decimal("5.0")


class TestPositionSizeCalculatorTickSize:
    """Test rounding to tick size."""

    def test_calculator_rounds_to_tick_size(self):
        """Calculator should round size to tick size."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            tick_size=Decimal("0.1"),
        )
        source_size = Decimal("5.55")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        # Should round down to 5.5
        assert target_size == Decimal("5.5")

    def test_calculator_rounds_down_to_tick_size(self):
        """Calculator should round down to nearest tick."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            tick_size=Decimal("0.5"),
        )
        source_size = Decimal("7.3")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        # Should round down to 7.0
        assert target_size == Decimal("7.0")

    def test_calculator_no_rounding_without_tick_size(self):
        """Calculator should not round without tick size."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("1.0"))
        source_size = Decimal("5.123456")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("5.123456")


class TestPositionSizeCalculatorMarginCalculation:
    """Test margin-based calculations."""

    def test_calculator_applies_margin_requirement(self):
        """Calculator should account for margin requirements."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            margin_requirement=Decimal("0.1"),  # 10% margin
        )
        source_size = Decimal("10.0")
        price = Decimal("100.0")
        # Need 10% of 1000 = 100 margin
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("100.0"),
            price=price,
        )
        assert target_size == Decimal("10.0")

    def test_calculator_limits_size_by_margin(self):
        """Calculator should limit size based on margin available."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            margin_requirement=Decimal("0.1"),  # 10% margin
            respect_balance=True,
        )
        source_size = Decimal("10.0")
        price = Decimal("100.0")
        # Only have 50 margin, can afford 5 units at 10% margin
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("50.0"),
            price=price,
        )
        assert target_size == Decimal("5.0")


class TestPositionSizeCalculatorEdgeCases:
    """Test edge cases and error handling."""

    def test_calculator_handles_zero_source_size(self):
        """Calculator should handle zero source size."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("1.0"))
        target_size = calc.calculate(
            source_size=Decimal("0"),
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("0")

    def test_calculator_handles_negative_source_size(self):
        """Calculator should reject negative source size."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("1.0"))
        with pytest.raises(ValueError):
            calc.calculate(
                source_size=Decimal("-10.0"),
                available_balance=Decimal("1000.0"),
            )

    def test_calculator_preserves_decimal_precision(self):
        """Calculator should maintain decimal precision."""
        calc = PositionSizeCalculator(copy_ratio=Decimal("0.333"))
        source_size = Decimal("9.0")
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
        )
        assert target_size == Decimal("2.997")

    def test_calculator_validates_copy_ratio(self):
        """Calculator should validate copy ratio is positive."""
        with pytest.raises(ValueError):
            PositionSizeCalculator(copy_ratio=Decimal("-1.0"))

    def test_calculator_validates_max_position_size(self):
        """Calculator should validate max position size is positive."""
        with pytest.raises(ValueError):
            PositionSizeCalculator(
                copy_ratio=Decimal("1.0"),
                max_position_size=Decimal("-10.0"),
            )


class TestPositionSizeCalculatorIntegration:
    """Test combinations of features."""

    def test_calculator_applies_all_limits(self):
        """Calculator should apply ratio, max, min, balance, and rounding."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("0.5"),
            max_position_size=Decimal("2000.0"),  # $2000 USD max
            min_order_size=Decimal("0.1"),  # $0.1 USD min
            tick_size=Decimal("0.5"),
            respect_balance=True,
        )
        source_size = Decimal("50.0")  # 50 * 0.5 = 25 tokens
        # At price $100, that's $2500, which exceeds $2000 max
        # So should be capped to $2000 / $100 = 20 tokens
        # Rounded down to tick size 0.5 → 20.0 tokens
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("10000.0"),
            price=Decimal("100.0"),
        )
        assert target_size == Decimal("20.0")

    def test_calculator_respects_balance_over_max(self):
        """Calculator should respect balance even with high max."""
        calc = PositionSizeCalculator(
            copy_ratio=Decimal("1.0"),
            max_position_size=Decimal("10000.0"),  # $10000 USD max (high, won't limit)
            respect_balance=True,
        )
        source_size = Decimal("50.0")  # 50 tokens at $100 = $5000
        price = Decimal("100.0")
        # Available balance is $1000, so can only afford $1000 / $100 = 10 tokens
        target_size = calc.calculate(
            source_size=source_size,
            available_balance=Decimal("1000.0"),
            price=price,
        )
        assert target_size == Decimal("10.0")
