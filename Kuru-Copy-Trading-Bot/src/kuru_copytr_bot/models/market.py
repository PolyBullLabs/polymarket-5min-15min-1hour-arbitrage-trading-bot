"""Market data models."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class MarketParams(BaseModel):
    """Market parameters from Kuru OrderBook contract.

    Attributes:
        price_precision: Price precision multiplier (e.g., 1000000 for 6 decimals)
        size_precision: Size precision multiplier (e.g., 10**18)
        base_asset: Base asset token address
        base_asset_decimals: Base asset decimal places
        quote_asset: Quote asset token address
        quote_asset_decimals: Quote asset decimal places
        tick_size: Minimum price increment
        min_size: Minimum order size
        max_size: Maximum order size
        taker_fee_bps: Taker fee in basis points (1 bps = 0.01%)
        maker_fee_bps: Maker fee in basis points (1 bps = 0.01%)
    """

    price_precision: int
    size_precision: int
    base_asset: str
    base_asset_decimals: int
    quote_asset: str
    quote_asset_decimals: int
    tick_size: Decimal
    min_size: Decimal
    max_size: Decimal
    taker_fee_bps: int
    maker_fee_bps: int

    @field_validator("taker_fee_bps")
    @classmethod
    def validate_taker_fee_bps(cls, v: int) -> int:
        """Validate taker fee is in valid range."""
        if v < 0 or v > 10000:
            raise ValueError("taker_fee_bps must be between 0 and 10000")
        return v

    @field_validator("maker_fee_bps")
    @classmethod
    def validate_maker_fee_bps(cls, v: int) -> int:
        """Validate maker fee is in valid range."""
        if v < 0 or v > 10000:
            raise ValueError("maker_fee_bps must be between 0 and 10000")
        return v

    @field_validator("tick_size")
    @classmethod
    def validate_tick_size(cls, v: Decimal) -> Decimal:
        """Validate tick size is positive."""
        if v <= 0:
            raise ValueError("tick_size must be positive")
        return v

    @field_validator("min_size")
    @classmethod
    def validate_min_size(cls, v: Decimal) -> Decimal:
        """Validate min size is positive."""
        if v <= 0:
            raise ValueError("min_size must be positive")
        return v

    @field_validator("max_size")
    @classmethod
    def validate_max_size(cls, v: Decimal, info: Any) -> Decimal:
        """Validate max size is greater than min size."""
        # Check if min_size has been set
        if "min_size" in info.data and v <= info.data["min_size"]:
            raise ValueError("max_size must be greater than min_size")
        return v

    model_config = ConfigDict(
        # Allow arbitrary types (for Decimal)
        arbitrary_types_allowed=True
    )
