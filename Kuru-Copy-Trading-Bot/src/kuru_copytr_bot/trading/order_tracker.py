"""Order fill tracking system."""

import time
from dataclasses import dataclass, field
from decimal import Decimal

from src.kuru_copytr_bot.core.enums import OrderStatus
from src.kuru_copytr_bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OrderFillState:
    """State of an order's fill progress."""

    order_id: str
    size: Decimal
    filled_size: Decimal = Decimal("0")
    status: OrderStatus = OrderStatus.OPEN
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class OrderTracker:
    """Tracks order fill status and maintains order state."""

    def __init__(self, ttl_seconds: int = 3600):
        """Initialize order tracker.

        Args:
            ttl_seconds: Time to live for filled orders (default: 1 hour)
        """
        self._orders: dict[str, OrderFillState] = {}
        self._ttl_seconds = ttl_seconds

    def register_order(self, order_id: str, size: Decimal) -> None:
        """Register a new order for tracking.

        Args:
            order_id: Unique order identifier
            size: Total order size
        """
        self._orders[order_id] = OrderFillState(
            order_id=order_id,
            size=size,
            status=OrderStatus.OPEN,
        )
        logger.debug("Registered order for tracking", order_id=order_id, size=str(size))

    def on_fill(self, order_id: str, filled_size: Decimal) -> None:
        """Update order state on fill event.

        Args:
            order_id: Order identifier
            filled_size: Size of this fill (incremental)
        """
        if order_id not in self._orders:
            logger.warning("Received fill for unknown order", order_id=order_id)
            return

        order_state = self._orders[order_id]

        new_filled_size = order_state.filled_size + filled_size

        if new_filled_size > order_state.size:
            logger.warning(
                "Fill exceeds order size, capping",
                order_id=order_id,
                order_size=str(order_state.size),
                filled_size=str(new_filled_size),
            )
            new_filled_size = order_state.size

        order_state.filled_size = new_filled_size
        order_state.updated_at = time.time()

        if order_state.filled_size >= order_state.size:
            order_state.status = OrderStatus.FILLED
            logger.info("Order fully filled", order_id=order_id)
        elif order_state.filled_size > Decimal("0"):
            order_state.status = OrderStatus.PARTIALLY_FILLED
            logger.debug(
                "Order partially filled",
                order_id=order_id,
                filled=str(order_state.filled_size),
                total=str(order_state.size),
            )

    def get_order_state(self, order_id: str) -> OrderFillState | None:
        """Get current state of an order.

        Args:
            order_id: Order identifier

        Returns:
            OrderFillState if order is tracked, None otherwise
        """
        return self._orders.get(order_id)

    def get_all_orders(self) -> dict[str, OrderFillState]:
        """Get all tracked orders.

        Returns:
            Dictionary mapping order_id to OrderFillState
        """
        return self._orders.copy()

    def get_open_orders(self) -> dict[str, OrderFillState]:
        """Get all open or partially filled orders.

        Returns:
            Dictionary of orders not yet fully filled
        """
        return {
            order_id: state
            for order_id, state in self._orders.items()
            if state.status != OrderStatus.FILLED
        }

    def remove_order(self, order_id: str) -> None:
        """Remove order from tracking.

        Args:
            order_id: Order identifier
        """
        if order_id in self._orders:
            del self._orders[order_id]
            logger.debug("Removed order from tracking", order_id=order_id)

    def get_fill_rate(self) -> float:
        """Calculate percentage of orders that are filled.

        Returns:
            Fill rate as a decimal (0.0 to 1.0)
        """
        if not self._orders:
            return 0.0

        filled_count = sum(
            1 for state in self._orders.values() if state.status == OrderStatus.FILLED
        )
        return filled_count / len(self._orders)

    def cleanup_old_orders(self) -> None:
        """Remove filled orders older than TTL."""
        current_time = time.time()
        orders_to_remove = []

        for order_id, state in self._orders.items():
            if state.status == OrderStatus.FILLED:
                age = current_time - state.updated_at
                if age > self._ttl_seconds:
                    orders_to_remove.append(order_id)

        for order_id in orders_to_remove:
            self.remove_order(order_id)

        if orders_to_remove:
            logger.info("Cleaned up old filled orders", count=len(orders_to_remove))
