"""Core enumerations for the Kuru copy trading bot."""

from enum import Enum


class OrderSide(str, Enum):
    """Order side (buy or sell)."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"
    GTC = "GTC"  # Good-Till-Cancelled (same as LIMIT but explicit)
    IOC = "IOC"  # Immediate-or-Cancel (same as MARKET but explicit)


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "PENDING"  # Order created but not yet submitted
    OPEN = "OPEN"  # Order submitted and active
    FILLED = "FILLED"  # Order completely filled
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Order partially filled
    CANCELLED = "CANCELLED"  # Order cancelled
    FAILED = "FAILED"  # Order failed to submit or execute
