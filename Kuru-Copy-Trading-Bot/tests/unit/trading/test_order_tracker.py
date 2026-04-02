"""Unit tests for OrderTracker."""

from decimal import Decimal

import pytest

from src.kuru_copytr_bot.core.enums import OrderStatus
from src.kuru_copytr_bot.trading.order_tracker import OrderTracker


class TestOrderTracker:
    """Test OrderTracker functionality."""

    def test_order_tracker_registers_new_order(self):
        """Test registering new order for tracking."""
        tracker = OrderTracker()

        tracker.register_order(order_id="order_123", size=Decimal("10.0"))

        state = tracker.get_order_state("order_123")
        assert state is not None
        assert state.order_id == "order_123"
        assert state.size == Decimal("10.0")
        assert state.filled_size == Decimal("0")
        assert state.status == OrderStatus.OPEN

    def test_order_tracker_updates_on_fill(self):
        """Test updating order on fill event."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_123", size=Decimal("10.0"))

        tracker.on_fill(order_id="order_123", filled_size=Decimal("3.0"))

        state = tracker.get_order_state("order_123")
        assert state.filled_size == Decimal("3.0")
        assert state.status == OrderStatus.PARTIALLY_FILLED

    def test_order_tracker_marks_fully_filled(self):
        """Test marking order as FILLED when complete."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_123", size=Decimal("10.0"))
        tracker.on_fill(order_id="order_123", filled_size=Decimal("8.0"))

        tracker.on_fill(order_id="order_123", filled_size=Decimal("2.0"))

        state = tracker.get_order_state("order_123")
        assert state.filled_size == Decimal("10.0")
        assert state.status == OrderStatus.FILLED

    def test_order_tracker_handles_partial_fill(self):
        """Test partial fill tracking."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_123", size=Decimal("10.0"))

        tracker.on_fill(order_id="order_123", filled_size=Decimal("3.0"))

        state = tracker.get_order_state("order_123")
        assert state.status == OrderStatus.PARTIALLY_FILLED
        assert state.filled_size == Decimal("3.0")

    def test_order_tracker_handles_overfill(self):
        """Test handling fill exceeding order size."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_123", size=Decimal("10.0"))
        tracker.on_fill(order_id="order_123", filled_size=Decimal("9.0"))

        tracker.on_fill(order_id="order_123", filled_size=Decimal("5.0"))

        state = tracker.get_order_state("order_123")
        assert state.filled_size == Decimal("10.0")
        assert state.status == OrderStatus.FILLED

    def test_order_tracker_ignores_unknown_orders(self):
        """Test handling fill for untracked order."""
        tracker = OrderTracker()

        tracker.on_fill(order_id="unknown_order", filled_size=Decimal("1.0"))

        state = tracker.get_order_state("unknown_order")
        assert state is None

    def test_order_tracker_accumulates_fills(self):
        """Test multiple fills accumulate correctly."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_123", size=Decimal("10.0"))

        tracker.on_fill(order_id="order_123", filled_size=Decimal("2.0"))
        tracker.on_fill(order_id="order_123", filled_size=Decimal("3.0"))
        tracker.on_fill(order_id="order_123", filled_size=Decimal("1.0"))

        state = tracker.get_order_state("order_123")
        assert state.filled_size == Decimal("6.0")
        assert state.status == OrderStatus.PARTIALLY_FILLED

    def test_order_tracker_get_all_orders(self):
        """Test retrieving all tracked orders."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_1", size=Decimal("10.0"))
        tracker.register_order(order_id="order_2", size=Decimal("20.0"))
        tracker.register_order(order_id="order_3", size=Decimal("30.0"))

        all_orders = tracker.get_all_orders()

        assert len(all_orders) == 3
        assert "order_1" in all_orders
        assert "order_2" in all_orders
        assert "order_3" in all_orders

    def test_order_tracker_get_open_orders(self):
        """Test retrieving only open/partially filled orders."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_1", size=Decimal("10.0"))
        tracker.register_order(order_id="order_2", size=Decimal("10.0"))
        tracker.register_order(order_id="order_3", size=Decimal("10.0"))

        tracker.on_fill(order_id="order_2", filled_size=Decimal("10.0"))

        open_orders = tracker.get_open_orders()

        assert len(open_orders) == 2
        assert "order_1" in open_orders
        assert "order_3" in open_orders
        assert "order_2" not in open_orders

    def test_order_tracker_remove_order(self):
        """Test removing order from tracking."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_123", size=Decimal("10.0"))

        tracker.remove_order(order_id="order_123")

        state = tracker.get_order_state("order_123")
        assert state is None

    def test_order_tracker_get_fill_rate(self):
        """Test calculating fill rate."""
        tracker = OrderTracker()
        tracker.register_order(order_id="order_1", size=Decimal("10.0"))
        tracker.register_order(order_id="order_2", size=Decimal("10.0"))
        tracker.register_order(order_id="order_3", size=Decimal("10.0"))

        tracker.on_fill(order_id="order_1", filled_size=Decimal("10.0"))
        tracker.on_fill(order_id="order_2", filled_size=Decimal("10.0"))

        fill_rate = tracker.get_fill_rate()

        assert fill_rate == pytest.approx(0.666, rel=0.01)

    def test_order_tracker_cleanup_old_filled_orders(self):
        """Test cleaning up old filled orders."""
        tracker = OrderTracker(ttl_seconds=0)
        tracker.register_order(order_id="order_1", size=Decimal("10.0"))
        tracker.on_fill(order_id="order_1", filled_size=Decimal("10.0"))

        tracker.cleanup_old_orders()

        state = tracker.get_order_state("order_1")
        assert state is None
