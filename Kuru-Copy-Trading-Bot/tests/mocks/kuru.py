"""Mock Kuru client for testing."""

from decimal import Decimal
from typing import Any


class MockKuruClient:
    """Mock Kuru client implementing PlatformConnector interface."""

    def __init__(
        self,
        blockchain: Any,
    ) -> None:
        """Initialize mock Kuru client."""
        self.blockchain = blockchain

        # Track calls for testing
        self.deposits: list[dict[str, Any]] = []
        self.orders_placed: list[dict[str, Any]] = []
        self.orders_cancelled: list[str] = []
        self.market_params_fetched: list[str] = []

        # Mock order ID counter
        self._order_counter = 1

    def deposit_margin(self, token: str, amount: Decimal) -> str:
        """Deposit tokens to margin account (LEGACY - bot doesn't use margin)."""
        deposit = {
            "token": token,
            "amount": amount,
        }
        self.deposits.append(deposit)

        # Return mock transaction hash
        return f"0xmockdeposit{len(self.deposits):060x}"

    def place_limit_order(
        self,
        market: str,
        side: str,
        price: Decimal,
        size: Decimal,
        post_only: bool = False,
    ) -> str:
        """Place a GTC limit order."""
        order = {
            "market": market,
            "side": side,
            "price": price,
            "size": size,
            "post_only": post_only,
            "order_type": "LIMIT",
        }
        self.orders_placed.append(order)

        # Return mock order ID
        order_id = f"order_{self._order_counter:06d}"
        self._order_counter += 1
        return order_id

    def place_market_order(
        self,
        market: str,
        side: str,
        size: Decimal,
        slippage: Decimal | None = None,
    ) -> str:
        """Place an IOC market order (LEGACY - bot uses limit orders only)."""
        order = {
            "market": market,
            "side": side,
            "size": size,
            "slippage": slippage,
            "order_type": "MARKET",
        }
        self.orders_placed.append(order)

        # Return mock order ID
        order_id = f"order_{self._order_counter:06d}"
        self._order_counter += 1
        return order_id

    def cancel_order(self, order_id: str) -> str:
        """Cancel an order."""
        self.orders_cancelled.append(order_id)

        # Return mock transaction hash
        return f"0xmockcancel{len(self.orders_cancelled):060x}"

    def cancel_orders(self, order_ids: list[str]) -> str:
        """Cancel multiple orders."""
        self.orders_cancelled.extend(order_ids)

        # Return mock transaction hash
        return f"0xmockcancelbatch{len(order_ids):056x}"

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get order status."""
        # Return mock order status
        return {
            "order_id": order_id,
            "status": "OPEN",
            "filled_size": Decimal("0"),
            "remaining_size": Decimal("1.0"),
        }

    def get_market_params(self, market: str) -> dict[str, Any]:
        """Get market parameters."""
        self.market_params_fetched.append(market)

        # Return mock market parameters
        return {
            "market_id": market,
            "base_token": market.split("-")[0],
            "quote_token": market.split("-")[1],
            "min_order_size": Decimal("0.001"),
            "max_order_size": Decimal("1000.0"),
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "maker_fee": Decimal("0.0002"),
            "taker_fee": Decimal("0.0005"),
            "is_active": True,
        }

    def estimate_cost(
        self,
        market: str,
        side: str,
        size: Decimal,
    ) -> Decimal:
        """Estimate the cost of a trade."""
        # Simple mock estimation: size * average_price
        mock_price = Decimal("2000.0")  # Mock average price
        return size * mock_price

    def get_margin_balance(self) -> Decimal:
        """Get available margin balance (LEGACY - bot doesn't use margin)."""
        return Decimal("10000.0")

    def get_open_orders(self, market: str | None = None) -> list[dict[str, Any]]:
        """Get open orders."""
        # Return empty list by default
        return []

    def get_positions(self, market: str | None = None) -> list[dict[str, Any]]:
        """Get current positions."""
        # Return empty list by default
        return []
