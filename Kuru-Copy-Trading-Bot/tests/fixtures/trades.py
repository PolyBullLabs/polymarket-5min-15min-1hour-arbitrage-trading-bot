"""Sample trade data fixtures for testing."""

from datetime import datetime, timezone
from decimal import Decimal

# Sample valid trade data
SAMPLE_TRADE_BUY = {
    "id": "trade_001",
    "trader_address": "0x1234567890123456789012345678901234567890",
    "market": "ETH-USDC",
    "side": "BUY",
    "price": Decimal("2000.50"),
    "size": Decimal("1.5"),
    "timestamp": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
}

SAMPLE_TRADE_SELL = {
    "id": "trade_002",
    "trader_address": "0x1234567890123456789012345678901234567890",
    "market": "ETH-USDC",
    "side": "SELL",
    "price": Decimal("2010.75"),
    "size": Decimal("0.8"),
    "timestamp": datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
    "tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
}

# Large trade
SAMPLE_TRADE_LARGE = {
    "id": "trade_003",
    "trader_address": "0x1234567890123456789012345678901234567890",
    "market": "BTC-USDC",
    "side": "BUY",
    "price": Decimal("50000.00"),
    "size": Decimal("10.0"),
    "timestamp": datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
    "tx_hash": "0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
}

# Small trade
SAMPLE_TRADE_SMALL = {
    "id": "trade_004",
    "trader_address": "0x1234567890123456789012345678901234567890",
    "market": "ETH-USDC",
    "side": "BUY",
    "price": Decimal("2000.00"),
    "size": Decimal("0.01"),
    "timestamp": datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
    "tx_hash": "0x9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba",
}

# Different market
SAMPLE_TRADE_SOL = {
    "id": "trade_005",
    "trader_address": "0x9876543210987654321098765432109876543210",
    "market": "SOL-USDC",
    "side": "BUY",
    "price": Decimal("100.25"),
    "size": Decimal("50.0"),
    "timestamp": datetime(2025, 1, 1, 15, 0, 0, tzinfo=timezone.utc),
    "tx_hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
}

# Edge cases
SAMPLE_TRADE_ZERO_SIZE = {
    "id": "trade_006",
    "trader_address": "0x1234567890123456789012345678901234567890",
    "market": "ETH-USDC",
    "side": "BUY",
    "price": Decimal("2000.00"),
    "size": Decimal("0"),
    "timestamp": datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
    "tx_hash": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
}

SAMPLE_TRADE_NEGATIVE_PRICE = {
    "id": "trade_007",
    "trader_address": "0x1234567890123456789012345678901234567890",
    "market": "ETH-USDC",
    "side": "BUY",
    "price": Decimal("-100.00"),
    "size": Decimal("1.0"),
    "timestamp": datetime(2025, 1, 1, 17, 0, 0, tzinfo=timezone.utc),
    "tx_hash": "0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
}

SAMPLE_TRADE_EXTREME_PRICE = {
    "id": "trade_008",
    "trader_address": "0x1234567890123456789012345678901234567890",
    "market": "ETH-USDC",
    "side": "BUY",
    "price": Decimal("999999999.99"),
    "size": Decimal("0.001"),
    "timestamp": datetime(2025, 1, 1, 18, 0, 0, tzinfo=timezone.utc),
    "tx_hash": "0xdddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
}

# List of all valid trades
ALL_VALID_TRADES = [
    SAMPLE_TRADE_BUY,
    SAMPLE_TRADE_SELL,
    SAMPLE_TRADE_LARGE,
    SAMPLE_TRADE_SMALL,
    SAMPLE_TRADE_SOL,
]

# List of invalid trades (for error testing)
ALL_INVALID_TRADES = [
    SAMPLE_TRADE_ZERO_SIZE,
    SAMPLE_TRADE_NEGATIVE_PRICE,
]
