"""Sample market parameter fixtures for testing."""

from decimal import Decimal

# ETH-USDC market parameters
SAMPLE_MARKET_ETH_USDC = {
    "market_id": "ETH-USDC",
    "base_token": "ETH",
    "quote_token": "USDC",
    "min_order_size": Decimal("0.001"),
    "max_order_size": Decimal("1000.0"),
    "tick_size": Decimal("0.01"),  # Price increments
    "step_size": Decimal("0.001"),  # Size increments
    "maker_fee": Decimal("0.0002"),  # 0.02%
    "taker_fee": Decimal("0.0005"),  # 0.05%
    "is_active": True,
}

# BTC-USDC market parameters
SAMPLE_MARKET_BTC_USDC = {
    "market_id": "BTC-USDC",
    "base_token": "BTC",
    "quote_token": "USDC",
    "min_order_size": Decimal("0.0001"),
    "max_order_size": Decimal("100.0"),
    "tick_size": Decimal("0.01"),
    "step_size": Decimal("0.0001"),
    "maker_fee": Decimal("0.0002"),
    "taker_fee": Decimal("0.0005"),
    "is_active": True,
}

# SOL-USDC market parameters
SAMPLE_MARKET_SOL_USDC = {
    "market_id": "SOL-USDC",
    "base_token": "SOL",
    "quote_token": "USDC",
    "min_order_size": Decimal("0.1"),
    "max_order_size": Decimal("10000.0"),
    "tick_size": Decimal("0.01"),
    "step_size": Decimal("0.1"),
    "maker_fee": Decimal("0.0002"),
    "taker_fee": Decimal("0.0005"),
    "is_active": True,
}

# Inactive market (for testing market validation)
SAMPLE_MARKET_INACTIVE = {
    "market_id": "INACTIVE-USDC",
    "base_token": "INACTIVE",
    "quote_token": "USDC",
    "min_order_size": Decimal("1.0"),
    "max_order_size": Decimal("1000.0"),
    "tick_size": Decimal("0.01"),
    "step_size": Decimal("0.01"),
    "maker_fee": Decimal("0.0002"),
    "taker_fee": Decimal("0.0005"),
    "is_active": False,
}

# Market with large minimum size (for testing size validation)
SAMPLE_MARKET_LARGE_MIN = {
    "market_id": "LARGE-USDC",
    "base_token": "LARGE",
    "quote_token": "USDC",
    "min_order_size": Decimal("100.0"),  # Very large minimum
    "max_order_size": Decimal("1000.0"),
    "tick_size": Decimal("1.0"),
    "step_size": Decimal("1.0"),
    "maker_fee": Decimal("0.0002"),
    "taker_fee": Decimal("0.0005"),
    "is_active": True,
}

# List of all active markets
ALL_ACTIVE_MARKETS = [
    SAMPLE_MARKET_ETH_USDC,
    SAMPLE_MARKET_BTC_USDC,
    SAMPLE_MARKET_SOL_USDC,
]

# List of all markets (including inactive)
ALL_MARKETS = [
    SAMPLE_MARKET_ETH_USDC,
    SAMPLE_MARKET_BTC_USDC,
    SAMPLE_MARKET_SOL_USDC,
    SAMPLE_MARKET_INACTIVE,
    SAMPLE_MARKET_LARGE_MIN,
]

# Market lookup dictionary
MARKETS_BY_ID = {market["market_id"]: market for market in ALL_MARKETS}
