"""Tests for Order model."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.kuru_copytr_bot.core.enums import OrderSide, OrderStatus, OrderType
from src.kuru_copytr_bot.core.exceptions import InvalidStateTransitionError

# These imports will fail initially - that's expected for TDD
from src.kuru_copytr_bot.models.order import Order, OrderResponse


class TestOrderModel:
    """Test Order model creation and validation."""

    def test_order_creation_with_valid_data(self):
        """Order model should accept valid data."""
        order = Order(
            order_id="order_001",
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.5"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert order.order_id == "order_001"
        assert order.order_type == OrderType.LIMIT
        assert order.status == OrderStatus.PENDING
        assert order.side == OrderSide.BUY
        assert order.price == Decimal("2000.00")
        assert order.size == Decimal("1.5")
        assert order.filled_size == Decimal("0")

    def test_order_creation_market_order(self):
        """Order model should handle market orders (no price)."""
        order = Order(
            order_id="order_002",
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            side=OrderSide.SELL,
            price=None,  # Market orders have no price
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert order.order_type == OrderType.MARKET
        assert order.price is None

    def test_order_requires_price_for_limit_orders(self):
        """Limit orders must have a price."""
        with pytest.raises(ValidationError):
            Order(
                order_id="order_003",
                order_type=OrderType.LIMIT,
                status=OrderStatus.PENDING,
                side=OrderSide.BUY,
                price=None,  # Invalid for limit orders
                size=Decimal("1.0"),
                filled_size=Decimal("0"),
                market="ETH-USDC",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_order_status_transition_pending_to_open(self):
        """Order should transition from PENDING to OPEN."""
        order = Order(
            order_id="order_004",
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        order.transition_to(OrderStatus.OPEN)
        assert order.status == OrderStatus.OPEN

    def test_order_status_transition_open_to_filled(self):
        """Order should transition from OPEN to FILLED."""
        order = Order(
            order_id="order_005",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("1.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        order.transition_to(OrderStatus.FILLED)
        assert order.status == OrderStatus.FILLED

    def test_order_cannot_transition_from_filled_to_cancelled(self):
        """Filled orders cannot be cancelled."""
        order = Order(
            order_id="order_006",
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("1.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(InvalidStateTransitionError):
            order.transition_to(OrderStatus.CANCELLED)

    def test_order_cannot_transition_from_cancelled_to_open(self):
        """Cancelled orders cannot be reopened."""
        order = Order(
            order_id="order_007",
            order_type=OrderType.LIMIT,
            status=OrderStatus.CANCELLED,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(InvalidStateTransitionError):
            order.transition_to(OrderStatus.OPEN)

    def test_order_partial_fill_updates_filled_size(self):
        """Order should track partial fills."""
        order = Order(
            order_id="order_008",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("2.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        order.add_fill(Decimal("0.5"))
        assert order.filled_size == Decimal("0.5")
        assert order.status == OrderStatus.PARTIALLY_FILLED

        order.add_fill(Decimal("0.3"))
        assert order.filled_size == Decimal("0.8")
        assert order.status == OrderStatus.PARTIALLY_FILLED

    def test_order_fully_filled_updates_status(self):
        """Order should update status to FILLED when fully filled."""
        order = Order(
            order_id="order_009",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        order.add_fill(Decimal("1.0"))
        assert order.filled_size == Decimal("1.0")
        assert order.status == OrderStatus.FILLED
        assert order.is_fully_filled

    def test_order_cannot_overfill(self):
        """Order should reject fills that exceed size."""
        order = Order(
            order_id="order_010",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with pytest.raises(ValidationError):
            order.add_fill(Decimal("1.5"))

    def test_order_remaining_size_calculation(self):
        """Order should calculate remaining size correctly."""
        order = Order(
            order_id="order_011",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("2.0"),
            filled_size=Decimal("0.7"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert order.remaining_size == Decimal("1.3")

    def test_order_fill_percentage_calculation(self):
        """Order should calculate fill percentage."""
        order = Order(
            order_id="order_012",
            order_type=OrderType.LIMIT,
            status=OrderStatus.PARTIALLY_FILLED,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("2.0"),
            filled_size=Decimal("1.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert order.fill_percentage == Decimal("50.0")

    def test_order_is_active_property(self):
        """Order should report if it's active."""
        order_open = Order(
            order_id="order_013",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        order_filled = Order(
            order_id="order_014",
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("1.0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert order_open.is_active is True
        assert order_filled.is_active is False

    def test_order_uses_decimal_for_amounts(self):
        """Order should use Decimal for all amounts."""
        order = Order(
            order_id="order_015",
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert isinstance(order.price, Decimal)
        assert isinstance(order.size, Decimal)
        assert isinstance(order.filled_size, Decimal)


class TestOrderCLOIDSupport:
    """Test Client Order ID (CLOID) support."""

    def test_order_creation_with_explicit_cloid(self):
        """Order should accept explicit client order ID."""
        order = Order(
            order_id="order_001",
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.5"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            cloid="custom-cloid-12345",
        )

        assert order.cloid == "custom-cloid-12345"

    def test_order_creation_without_cloid_generates_uuid(self):
        """Order should auto-generate UUID if CLOID not provided."""
        order = Order(
            order_id="order_002",
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.5"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert order.cloid is not None
        assert len(order.cloid) == 36  # UUID4 format: 8-4-4-4-12
        assert order.cloid.count("-") == 4  # UUID has 4 dashes

    def test_order_cloid_validation_max_length(self):
        """CLOID should not exceed 36 characters."""
        with pytest.raises(ValidationError):
            Order(
                order_id="order_003",
                order_type=OrderType.LIMIT,
                status=OrderStatus.PENDING,
                side=OrderSide.BUY,
                price=Decimal("2000.00"),
                size=Decimal("1.0"),
                filled_size=Decimal("0"),
                market="ETH-USDC",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                cloid="a" * 37,  # Too long
            )

    def test_order_cloid_validation_format(self):
        """CLOID should be alphanumeric with dash/underscore."""
        # Valid CLOID formats
        valid_cloids = [
            "simple123",
            "with-dash-456",
            "with_underscore_789",
            "mix-123_abc",
            "12345678-1234-1234-1234-123456789012",  # UUID format (36 chars)
        ]

        for cloid in valid_cloids:
            order = Order(
                order_id=f"order_{cloid}",
                order_type=OrderType.LIMIT,
                status=OrderStatus.PENDING,
                side=OrderSide.BUY,
                price=Decimal("2000.00"),
                size=Decimal("1.0"),
                filled_size=Decimal("0"),
                market="ETH-USDC",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                cloid=cloid,
            )
            assert order.cloid == cloid

    def test_order_cloid_rejects_invalid_characters(self):
        """CLOID should reject special characters other than dash and underscore."""
        invalid_cloids = [
            "with spaces",
            "with@symbol",
            "with#hash",
            "with$dollar",
            "with%percent",
        ]

        for cloid in invalid_cloids:
            with pytest.raises(ValidationError):
                Order(
                    order_id="order_004",
                    order_type=OrderType.LIMIT,
                    status=OrderStatus.PENDING,
                    side=OrderSide.BUY,
                    price=Decimal("2000.00"),
                    size=Decimal("1.0"),
                    filled_size=Decimal("0"),
                    market="ETH-USDC",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    cloid=cloid,
                )

    def test_order_cloid_is_immutable_after_creation(self):
        """CLOID should not change after order creation."""
        order = Order(
            order_id="order_005",
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
            side=OrderSide.BUY,
            price=Decimal("2000.00"),
            size=Decimal("1.0"),
            filled_size=Decimal("0"),
            market="ETH-USDC",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            cloid="original-cloid",
        )

        original_cloid = order.cloid

        # Attempting to change cloid
        with pytest.raises(ValidationError):
            order.cloid = "modified-cloid"

        assert order.cloid == original_cloid


class TestOrderResponseModel:
    """Test OrderResponse model (API format)."""

    def test_order_response_creation_with_api_format(self):
        """OrderResponse should accept API format fields."""
        response = OrderResponse(
            order_id=123456,
            market_address="0x4444444444444444444444444444444444444444",
            owner="0x1234567890123456789012345678901234567890",
            price="2000.50",
            size="1.5",
            remaining_size="0.5",
            is_buy=True,
            is_canceled=False,
            transaction_hash="0xabc123def456",
            trigger_time=1234567890,
        )

        assert response.order_id == 123456
        assert response.market_address == "0x4444444444444444444444444444444444444444"
        assert response.price == "2000.50"
        assert response.is_buy is True
        assert response.is_canceled is False

    def test_order_response_with_cloid(self):
        """OrderResponse should accept optional CLOID."""
        response = OrderResponse(
            order_id=123456,
            market_address="0x4444444444444444444444444444444444444444",
            owner="0x1234567890123456789012345678901234567890",
            price="2000.00",
            size="1.0",
            remaining_size="0.0",
            is_buy=True,
            is_canceled=False,
            transaction_hash="0xabc123",
            trigger_time=1234567890,
            cloid="custom-cloid-123",
        )

        assert response.cloid == "custom-cloid-123"

    def test_order_response_converts_to_order(self):
        """OrderResponse should convert to internal Order model."""
        response = OrderResponse(
            order_id=123456,
            market_address="0x4444444444444444444444444444444444444444",
            owner="0x1234567890123456789012345678901234567890",
            price="2000.00",
            size="2.0",
            remaining_size="0.5",
            is_buy=True,
            is_canceled=False,
            transaction_hash="0xabc123",
            trigger_time=1234567890,
            cloid="test-cloid",
        )

        order = response.to_order()

        assert order.order_id == "123456"
        assert order.market == "0x4444444444444444444444444444444444444444"
        assert order.side == OrderSide.BUY
        assert order.price == Decimal("2000.00")
        assert order.size == Decimal("2.0")
        assert order.filled_size == Decimal("1.5")  # size - remaining_size
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.cloid == "test-cloid"
        assert order.order_type == OrderType.LIMIT

    def test_order_response_converts_sell_order(self):
        """OrderResponse should correctly convert sell orders."""
        response = OrderResponse(
            order_id=789,
            market_address="0x4444444444444444444444444444444444444444",
            owner="0x1234567890123456789012345678901234567890",
            price="2100.00",
            size="1.0",
            remaining_size="1.0",
            is_buy=False,
            is_canceled=False,
            transaction_hash="0xdef456",
            trigger_time=1234567900,
        )

        order = response.to_order()

        assert order.side == OrderSide.SELL
        assert order.status == OrderStatus.OPEN  # remaining_size == size

    def test_order_response_converts_canceled_order(self):
        """OrderResponse should convert canceled orders correctly."""
        response = OrderResponse(
            order_id=999,
            market_address="0x4444444444444444444444444444444444444444",
            owner="0x1234567890123456789012345678901234567890",
            price="2000.00",
            size="1.0",
            remaining_size="0.3",
            is_buy=True,
            is_canceled=True,
            transaction_hash="0x123abc",
            trigger_time=1234567890,
        )

        order = response.to_order()

        assert order.status == OrderStatus.CANCELLED
        assert order.filled_size == Decimal("0.7")

    def test_order_response_converts_filled_order(self):
        """OrderResponse should convert fully filled orders correctly."""
        response = OrderResponse(
            order_id=555,
            market_address="0x4444444444444444444444444444444444444444",
            owner="0x1234567890123456789012345678901234567890",
            price="2000.00",
            size="1.0",
            remaining_size="0.0",
            is_buy=True,
            is_canceled=False,
            transaction_hash="0x789xyz",
            trigger_time=1234567890,
        )

        order = response.to_order()

        assert order.status == OrderStatus.FILLED
        assert order.filled_size == Decimal("1.0")
