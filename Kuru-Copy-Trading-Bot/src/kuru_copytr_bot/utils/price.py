"""Price normalization utilities for order placement."""

from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Literal


def normalize_to_tick(
    price: Decimal,
    tick_size: Decimal,
    mode: Literal["round_up", "round_down"],
) -> Decimal:
    """Round price to nearest tick size.

    Args:
        price: Price to normalize
        tick_size: Tick size (minimum price increment)
        mode: Rounding mode - "round_up" or "round_down"

    Returns:
        Decimal: Price normalized to tick size

    Raises:
        ValueError: If price is negative, tick_size is not positive, or mode is invalid

    Examples:
        >>> normalize_to_tick(Decimal("2000.123"), Decimal("0.01"), "round_down")
        Decimal('2000.12')
        >>> normalize_to_tick(Decimal("2000.123"), Decimal("0.01"), "round_up")
        Decimal('2000.13')
        >>> normalize_to_tick(Decimal("2000.10"), Decimal("0.01"), "round_down")
        Decimal('2000.10')
    """
    # Validate inputs
    if price < 0:
        raise ValueError("price must be non-negative")

    if tick_size <= 0:
        raise ValueError("tick_size must be positive")

    if mode not in ("round_up", "round_down"):
        raise ValueError("mode must be 'round_up' or 'round_down'")

    # Handle zero price
    if price == 0:
        return Decimal("0")

    # Calculate number of ticks
    ticks = price / tick_size

    # Round according to mode
    if mode == "round_down":
        rounded_ticks = ticks.quantize(Decimal("1"), rounding=ROUND_DOWN)
    else:  # round_up
        rounded_ticks = ticks.quantize(Decimal("1"), rounding=ROUND_UP)

    # Convert back to price
    normalized_price = rounded_ticks * tick_size

    return normalized_price
