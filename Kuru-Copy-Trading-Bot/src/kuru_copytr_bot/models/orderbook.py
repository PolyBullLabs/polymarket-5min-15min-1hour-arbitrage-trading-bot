"""Orderbook data models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PriceLevel(BaseModel):
    """A single price level in the orderbook.

    Attributes:
        price: Price at this level
        size: Total size available at this price
    """

    price: Decimal
    size: Decimal

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        """Validate price is positive."""
        if v <= 0:
            raise ValueError("price must be positive")
        return v

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: Decimal) -> Decimal:
        """Validate size is positive."""
        if v <= 0:
            raise ValueError("size must be positive")
        return v

    model_config = ConfigDict(arbitrary_types_allowed=True)


class L2Book(BaseModel):
    """Level 2 orderbook data.

    Attributes:
        block_num: Block number when orderbook was captured
        bids: List of bid price levels (sorted descending by price)
        asks: List of ask price levels (sorted ascending by price)
        timestamp: Timestamp when orderbook was captured
    """

    block_num: int
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_validator("block_num")
    @classmethod
    def validate_block_num(cls, v: int) -> int:
        """Validate block number is non-negative."""
        if v < 0:
            raise ValueError("block_num must be non-negative")
        return v

    @property
    def best_bid(self) -> Decimal | None:
        """Get the best (highest) bid price.

        Returns:
            Decimal: Best bid price, or None if no bids
        """
        if not self.bids:
            return None
        return self.bids[0].price

    @property
    def best_ask(self) -> Decimal | None:
        """Get the best (lowest) ask price.

        Returns:
            Decimal: Best ask price, or None if no asks
        """
        if not self.asks:
            return None
        return self.asks[0].price

    @property
    def spread(self) -> Decimal | None:
        """Calculate the spread between best bid and ask.

        Returns:
            Decimal: Spread (best_ask - best_bid), or None if incomplete
        """
        best_bid = self.best_bid
        best_ask = self.best_ask

        if best_bid is None or best_ask is None:
            return None

        return best_ask - best_bid

    @property
    def mid_price(self) -> Decimal | None:
        """Calculate the mid price between best bid and ask.

        Returns:
            Decimal: Mid price ((best_bid + best_ask) / 2), or None if incomplete
        """
        best_bid = self.best_bid
        best_ask = self.best_ask

        if best_bid is None or best_ask is None:
            return None

        return (best_bid + best_ask) / Decimal("2")

    model_config = ConfigDict(arbitrary_types_allowed=True)
