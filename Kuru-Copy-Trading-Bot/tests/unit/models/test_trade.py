"""Tests for Trade model."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.kuru_copytr_bot.core.enums import OrderSide

# These imports will fail initially - that's expected for TDD
from src.kuru_copytr_bot.models.trade import Trade, TradeResponse


class TestTradeModel:
    """Test Trade model creation and validation."""

    def test_trade_creation_with_valid_data(self, sample_trade_buy):
        """Trade model should accept valid data."""
        trade = Trade(**sample_trade_buy)

        assert trade.id == sample_trade_buy["id"]
        assert trade.trader_address == sample_trade_buy["trader_address"]
        assert trade.market == sample_trade_buy["market"]
        assert trade.side == OrderSide.BUY
        assert trade.price == sample_trade_buy["price"]
        assert trade.size == sample_trade_buy["size"]
        assert trade.timestamp == sample_trade_buy["timestamp"]
        assert trade.tx_hash == sample_trade_buy["tx_hash"]

    def test_trade_creation_sell_side(self, sample_trade_sell):
        """Trade model should handle SELL side."""
        trade = Trade(**sample_trade_sell)

        assert trade.side == OrderSide.SELL
        assert trade.price == sample_trade_sell["price"]
        assert trade.size == sample_trade_sell["size"]

    def test_trade_rejects_negative_price(self, sample_trade_buy):
        """Trade model should reject negative prices."""
        sample_trade_buy["price"] = Decimal("-100.00")

        with pytest.raises(ValidationError) as exc_info:
            Trade(**sample_trade_buy)

        assert "price" in str(exc_info.value).lower()

    def test_trade_rejects_zero_price(self, sample_trade_buy):
        """Trade model should reject zero prices."""
        sample_trade_buy["price"] = Decimal("0")

        with pytest.raises(ValidationError) as exc_info:
            Trade(**sample_trade_buy)

        assert "price" in str(exc_info.value).lower()

    def test_trade_rejects_negative_size(self, sample_trade_buy):
        """Trade model should reject negative sizes."""
        sample_trade_buy["size"] = Decimal("-5.0")

        with pytest.raises(ValidationError) as exc_info:
            Trade(**sample_trade_buy)

        assert "size" in str(exc_info.value).lower()

    def test_trade_rejects_zero_size(self, sample_trade_buy):
        """Trade model should reject zero sizes."""
        sample_trade_buy["size"] = Decimal("0")

        with pytest.raises(ValidationError) as exc_info:
            Trade(**sample_trade_buy)

        assert "size" in str(exc_info.value).lower()

    def test_trade_validates_trader_address_format(self, sample_trade_buy):
        """Trade model should validate Ethereum address format."""
        sample_trade_buy["trader_address"] = "invalid_address"

        with pytest.raises(ValidationError) as exc_info:
            Trade(**sample_trade_buy)

        assert "address" in str(exc_info.value).lower()

    def test_trade_validates_tx_hash_format(self, sample_trade_buy):
        """Trade model should validate transaction hash format."""
        sample_trade_buy["tx_hash"] = "not_a_valid_tx_hash"

        with pytest.raises(ValidationError) as exc_info:
            Trade(**sample_trade_buy)

        assert "hash" in str(exc_info.value).lower()

    def test_trade_requires_all_fields(self):
        """Trade model should require all mandatory fields."""
        with pytest.raises(ValidationError) as exc_info:
            Trade(id="trade_001")

        error_msg = str(exc_info.value).lower()
        assert "trader_address" in error_msg or "required" in error_msg

    def test_trade_uses_decimal_for_price(self, sample_trade_buy):
        """Trade model should use Decimal for price (not float)."""
        trade = Trade(**sample_trade_buy)

        assert isinstance(trade.price, Decimal)
        assert not isinstance(trade.price, float)

    def test_trade_uses_decimal_for_size(self, sample_trade_buy):
        """Trade model should use Decimal for size (not float)."""
        trade = Trade(**sample_trade_buy)

        assert isinstance(trade.size, Decimal)
        assert not isinstance(trade.size, float)

    def test_trade_preserves_decimal_precision(self, sample_trade_buy):
        """Trade model should preserve decimal precision."""
        sample_trade_buy["price"] = Decimal("2000.123456789")
        trade = Trade(**sample_trade_buy)

        assert trade.price == Decimal("2000.123456789")

    def test_trade_serialization(self, sample_trade_buy):
        """Trade model should serialize to dict."""
        trade = Trade(**sample_trade_buy)
        trade_dict = trade.model_dump()

        assert isinstance(trade_dict, dict)
        assert trade_dict["id"] == sample_trade_buy["id"]
        assert trade_dict["market"] == sample_trade_buy["market"]

    def test_trade_deserialization(self, sample_trade_buy):
        """Trade model should deserialize from dict."""
        trade = Trade(**sample_trade_buy)
        trade_dict = trade.model_dump()

        # Recreate from dict
        trade2 = Trade(**trade_dict)
        assert trade2.id == trade.id
        assert trade2.price == trade.price

    def test_trade_timestamp_is_timezone_aware(self, sample_trade_buy):
        """Trade model timestamp should be timezone-aware."""
        trade = Trade(**sample_trade_buy)

        assert trade.timestamp.tzinfo is not None

    def test_trade_accepts_large_sizes(self, sample_trade_buy):
        """Trade model should handle large trade sizes."""
        sample_trade_buy["size"] = Decimal("999999.999999")
        trade = Trade(**sample_trade_buy)

        assert trade.size == Decimal("999999.999999")

    def test_trade_accepts_small_sizes(self, sample_trade_buy):
        """Trade model should handle small trade sizes."""
        sample_trade_buy["size"] = Decimal("0.000001")
        trade = Trade(**sample_trade_buy)

        assert trade.size == Decimal("0.000001")

    def test_trade_calculates_notional_value(self, sample_trade_buy):
        """Trade model should calculate notional value."""
        trade = Trade(**sample_trade_buy)

        # notional = price * size
        expected_notional = trade.price * trade.size
        assert trade.notional_value == expected_notional

    def test_trade_string_representation(self, sample_trade_buy):
        """Trade model should have readable string representation."""
        trade = Trade(**sample_trade_buy)
        trade_str = str(trade)

        assert sample_trade_buy["id"] in trade_str
        assert sample_trade_buy["market"] in trade_str


class TestTradeResponseModel:
    """Test TradeResponse model (API format with camelCase fields)."""

    def test_trade_response_creation_with_api_format(self):
        """TradeResponse should accept API format with camelCase fields."""
        response = TradeResponse(
            orderid=123456,
            makeraddress="0x1234567890123456789012345678901234567890",
            takeraddress="0x0987654321098765432109876543210987654321",
            isbuy=True,
            price="2000.50",
            filledsize="1.5",
            transactionhash="0xabc123def4567890123456789012345678901234567890123456789012345678",
            triggertime=1234567890,
        )

        assert response.orderid == 123456
        assert response.makeraddress == "0x1234567890123456789012345678901234567890"
        assert response.isbuy is True
        assert response.price == "2000.50"
        assert response.filledsize == "1.5"

    def test_trade_response_with_cloid(self):
        """TradeResponse should accept optional CLOID."""
        response = TradeResponse(
            orderid=123456,
            makeraddress="0x1234567890123456789012345678901234567890",
            takeraddress="0x0987654321098765432109876543210987654321",
            isbuy=True,
            price="2000.00",
            filledsize="1.0",
            transactionhash="0xabc123def4567890123456789012345678901234567890123456789012345678",
            triggertime=1234567890,
            cloid="custom-cloid-789",
        )

        assert response.cloid == "custom-cloid-789"

    def test_trade_response_converts_to_trade(self):
        """TradeResponse should convert to internal Trade model."""
        response = TradeResponse(
            orderid=123456,
            makeraddress="0x1234567890123456789012345678901234567890",
            takeraddress="0x0987654321098765432109876543210987654321",
            isbuy=True,
            price="2000.00",
            filledsize="2.5",
            transactionhash="0xabc123def4567890123456789012345678901234567890123456789012345678",
            triggertime=1234567890,
        )

        trade = response.to_trade(market="ETH-USDC")

        assert trade.id == "123456"
        assert trade.trader_address == "0x1234567890123456789012345678901234567890"
        assert trade.market == "ETH-USDC"
        assert trade.side == OrderSide.BUY
        assert trade.price == Decimal("2000.00")
        assert trade.size == Decimal("2.5")
        assert trade.tx_hash == "0xabc123def4567890123456789012345678901234567890123456789012345678"
        assert isinstance(trade.timestamp, datetime)
        assert trade.timestamp.tzinfo is not None

    def test_trade_response_converts_sell_trade(self):
        """TradeResponse should correctly convert sell trades."""
        response = TradeResponse(
            orderid=789,
            makeraddress="0x1234567890123456789012345678901234567890",
            takeraddress="0x0987654321098765432109876543210987654321",
            isbuy=False,
            price="2100.00",
            filledsize="1.0",
            transactionhash="0xdef4567890123456789012345678901234567890123456789012345678901234",
            triggertime=1234567900,
        )

        trade = response.to_trade(market="ETH-USDC")

        assert trade.side == OrderSide.SELL
        assert trade.price == Decimal("2100.00")

    def test_trade_response_uses_maker_address_as_trader(self):
        """TradeResponse should use maker address as trader address."""
        response = TradeResponse(
            orderid=999,
            makeraddress="0x1111111111111111111111111111111111111111",
            takeraddress="0x2222222222222222222222222222222222222222",
            isbuy=True,
            price="2000.00",
            filledsize="1.0",
            transactionhash="0x123abc456def78901234567890123456789012345678901234567890123456ab",
            triggertime=1234567890,
        )

        trade = response.to_trade(market="BTC-USDC")

        assert trade.trader_address == "0x1111111111111111111111111111111111111111"
