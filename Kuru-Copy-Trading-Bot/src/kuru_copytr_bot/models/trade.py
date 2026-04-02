"""Trade model."""

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from ..core.enums import OrderSide


class TradeResponse(BaseModel):
    """Raw trade data from Kuru API/blockchain events."""

    orderid: int = Field(..., description="Order ID from blockchain")
    market_address: str | None = Field(None, description="Market contract address")
    makeraddress: str = Field(..., description="Maker wallet address")
    takeraddress: str = Field(..., description="Taker wallet address")
    isbuy: bool = Field(..., description="True for buy trades, False for sell trades")
    price: str = Field(..., description="Execution price as string")
    filledsize: str = Field(..., description="Filled size as string")
    transactionhash: str = Field(..., description="Transaction hash")
    triggertime: int = Field(..., description="Unix timestamp when trade executed")
    cloid: str | None = Field(None, description="Optional client order ID")

    def to_trade(self, market: str) -> "Trade":
        """Convert API response format to internal Trade model.

        Args:
            market: Market identifier (e.g., "ETH-USDC")

        Returns:
            Trade: Internal trade model with proper types
        """
        # Determine side
        side = OrderSide.BUY if self.isbuy else OrderSide.SELL

        # Convert timestamp to datetime
        timestamp = datetime.fromtimestamp(self.triggertime, tz=timezone.utc)

        return Trade(
            id=str(self.orderid),
            trader_address=self.makeraddress,
            market=market,
            side=side,
            price=Decimal(self.price),
            size=Decimal(self.filledsize),
            timestamp=timestamp,
            tx_hash=self.transactionhash,
        )


class Trade(BaseModel):
    """Represents a trade execution."""

    id: str = Field(..., description="Unique trade identifier")
    trader_address: str = Field(..., description="Source trader wallet address")
    market: str = Field(..., description="Trading pair/market (e.g., ETH-USDC)")
    side: OrderSide = Field(..., description="Trade side (BUY or SELL)")
    price: Decimal = Field(..., description="Execution price", gt=0)
    size: Decimal = Field(..., description="Trade size", gt=0)
    timestamp: datetime = Field(..., description="Trade execution time")
    tx_hash: str = Field(..., description="Transaction hash")

    @field_validator("trader_address")
    @classmethod
    def validate_trader_address(cls, v: str) -> str:
        """Validate Ethereum address format."""
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Invalid Ethereum address format")
        return v

    @field_validator("tx_hash")
    @classmethod
    def validate_tx_hash(cls, v: str) -> str:
        """Validate transaction hash format."""
        if not v.startswith("0x") or len(v) != 66:
            raise ValueError("Invalid transaction hash format")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        return v

    @property
    def notional_value(self) -> Decimal:
        """Calculate notional value (price * size)."""
        return self.price * self.size

    def __str__(self) -> str:
        """String representation of trade."""
        return f"Trade({self.id}, {self.market}, {self.side.value}, {self.size}@{self.price})"
