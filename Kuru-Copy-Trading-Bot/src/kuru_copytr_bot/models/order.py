"""Order model."""

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import InitErrorDetails
from pydantic_core import ValidationError as CoreValidationError

from ..core.enums import OrderSide, OrderStatus, OrderType
from ..core.exceptions import InvalidStateTransitionError


class OrderResponse(BaseModel):
    """Raw order data from Kuru API (matches API spec format)."""

    order_id: int = Field(..., description="Order ID from blockchain")
    market_address: str = Field(..., description="Market contract address")
    owner: str = Field(..., description="Owner wallet address")
    price: str = Field(..., description="Order price as string")
    size: str = Field(..., description="Order size as string")
    remaining_size: str = Field(..., description="Remaining unfilled size as string")
    is_buy: bool = Field(..., description="True for buy orders, False for sell orders")
    is_canceled: bool = Field(..., description="True if order is canceled")
    transaction_hash: str = Field(..., description="Transaction hash")
    trigger_time: int = Field(..., description="Unix timestamp when order was created")
    cloid: str | None = Field(None, description="Optional client order ID")

    def to_order(self) -> "Order":
        """Convert API response format to internal Order model.

        Returns:
            Order: Internal order model with proper types
        """
        # Calculate filled size
        size_decimal = Decimal(self.size)
        remaining_decimal = Decimal(self.remaining_size)
        filled_size = size_decimal - remaining_decimal

        # Determine status
        if self.is_canceled:
            status = OrderStatus.CANCELLED
        elif remaining_decimal == Decimal("0"):
            status = OrderStatus.FILLED
        elif filled_size > 0:
            status = OrderStatus.PARTIALLY_FILLED
        else:
            status = OrderStatus.OPEN

        # Determine side
        side = OrderSide.BUY if self.is_buy else OrderSide.SELL

        # Convert timestamp to datetime
        created_at = datetime.fromtimestamp(self.trigger_time, tz=timezone.utc)

        return Order(
            order_id=str(self.order_id),
            order_type=OrderType.LIMIT,  # API orders are limit orders
            status=status,
            side=side,
            price=Decimal(self.price),
            size=size_decimal,
            filled_size=filled_size,
            market=self.market_address,
            created_at=created_at,
            updated_at=created_at,
            cloid=self.cloid if self.cloid else str(uuid.uuid4()),
        )


class Order(BaseModel):
    """Represents an order."""

    order_id: str = Field(..., description="Unique order identifier")
    order_type: OrderType = Field(..., description="Order type (LIMIT, MARKET, etc.)")
    status: OrderStatus = Field(..., description="Order status")
    side: OrderSide = Field(..., description="Order side (BUY or SELL)")
    price: Decimal | None = Field(None, description="Order price (None for market orders)")
    size: Decimal = Field(..., description="Order size", gt=0)
    filled_size: Decimal = Field(..., description="Amount filled so far", ge=0)
    market: str = Field(..., description="Trading pair/market")
    created_at: datetime = Field(..., description="Order creation time")
    updated_at: datetime = Field(..., description="Last update time")
    cloid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Client Order ID for tracking",
        frozen=True,
    )

    @field_validator("cloid")
    @classmethod
    def validate_cloid_format(cls, v: str) -> str:
        """Validate CLOID format and length."""
        # Check max length
        if len(v) > 36:
            raise ValueError("CLOID must not exceed 36 characters")

        # Check format: alphanumeric with dash and underscore only
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "CLOID must contain only alphanumeric characters, dashes, and underscores"
            )

        return v

    @model_validator(mode="after")
    def validate_order(self) -> "Order":
        """Validate order constraints."""
        # Limit orders must have a price
        if self.order_type in (OrderType.LIMIT, OrderType.GTC) and self.price is None:
            raise ValueError("Limit orders must have a price")

        # Filled size cannot exceed total size
        if self.filled_size > self.size:
            raise ValueError("Filled size cannot exceed total size")

        return self

    @property
    def remaining_size(self) -> Decimal:
        """Calculate remaining unfilled size."""
        return self.size - self.filled_size

    @property
    def fill_percentage(self) -> Decimal:
        """Calculate fill percentage."""
        if self.size == 0:
            return Decimal("0")
        return (self.filled_size / self.size) * Decimal("100")

    @property
    def is_fully_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.filled_size >= self.size

    @property
    def is_active(self) -> bool:
        """Check if order is active (can still be filled or cancelled)."""
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)

    @property
    def notional_value(self) -> Decimal:
        """Calculate notional value (price * size).

        Returns:
            Decimal: Notional value, or 0 if price is None (market orders)
        """
        if self.price is None:
            return Decimal("0")
        return self.price * self.size

    def transition_to(self, new_status: OrderStatus) -> None:
        """Transition order to a new status."""
        # Define valid transitions
        valid_transitions = {
            OrderStatus.PENDING: {OrderStatus.OPEN, OrderStatus.FAILED, OrderStatus.CANCELLED},
            OrderStatus.OPEN: {
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
            },
            OrderStatus.PARTIALLY_FILLED: {OrderStatus.FILLED, OrderStatus.CANCELLED},
            OrderStatus.FILLED: set(),  # Terminal state
            OrderStatus.CANCELLED: set(),  # Terminal state
            OrderStatus.FAILED: set(),  # Terminal state
        }

        if new_status not in valid_transitions.get(self.status, set()):
            raise InvalidStateTransitionError(
                f"Cannot transition from {self.status.value} to {new_status.value}"
            )

        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

    def add_fill(self, fill_size: Decimal) -> None:
        """Add a fill to the order."""
        new_filled_size = self.filled_size + fill_size

        if new_filled_size > self.size:
            # Raise pydantic ValidationError
            raise CoreValidationError.from_exception_data(
                "Order",
                [
                    InitErrorDetails(
                        type="value_error",
                        loc=("filled_size",),
                        input=new_filled_size,
                        ctx={
                            "error": f"Fill would exceed order size: {new_filled_size} > {self.size}"
                        },
                    )
                ],
            )

        self.filled_size = new_filled_size
        self.updated_at = datetime.now(timezone.utc)

        # Update status based on fill
        if self.is_fully_filled:
            self.status = OrderStatus.FILLED
        elif self.filled_size > 0 and self.status == OrderStatus.OPEN:
            self.status = OrderStatus.PARTIALLY_FILLED
