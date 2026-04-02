"""Unit tests for market data models."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.kuru_copytr_bot.models.market import MarketParams


class TestMarketParams:
    """Test MarketParams model."""

    def test_market_params_creates_with_valid_data(self):
        """Should create MarketParams with valid data."""
        params = MarketParams(
            price_precision=1000,
            size_precision=1000000,
            base_asset="0x0000000000000000000000000000000000000001",
            base_asset_decimals=18,
            quote_asset="0x0000000000000000000000000000000000000002",
            quote_asset_decimals=6,
            tick_size=Decimal("0.01"),
            min_size=Decimal("0.001"),
            max_size=Decimal("1000000"),
            taker_fee_bps=50,
            maker_fee_bps=20,
        )

        assert params.price_precision == 1000
        assert params.size_precision == 1000000
        assert params.base_asset == "0x0000000000000000000000000000000000000001"
        assert params.base_asset_decimals == 18
        assert params.quote_asset == "0x0000000000000000000000000000000000000002"
        assert params.quote_asset_decimals == 6
        assert params.tick_size == Decimal("0.01")
        assert params.min_size == Decimal("0.001")
        assert params.max_size == Decimal("1000000")
        assert params.taker_fee_bps == 50
        assert params.maker_fee_bps == 20

    def test_market_params_validates_negative_taker_fee(self):
        """Should reject negative taker fee."""
        with pytest.raises(ValidationError, match="taker_fee_bps must be between 0 and 10000"):
            MarketParams(
                price_precision=1000,
                size_precision=1000000,
                base_asset="0x0000000000000000000000000000000000000001",
                base_asset_decimals=18,
                quote_asset="0x0000000000000000000000000000000000000002",
                quote_asset_decimals=6,
                tick_size=Decimal("0.01"),
                min_size=Decimal("0.001"),
                max_size=Decimal("1000000"),
                taker_fee_bps=-1,
                maker_fee_bps=20,
            )

    def test_market_params_validates_excessive_taker_fee(self):
        """Should reject taker fee above 10000 bps (100%)."""
        with pytest.raises(ValidationError, match="taker_fee_bps must be between 0 and 10000"):
            MarketParams(
                price_precision=1000,
                size_precision=1000000,
                base_asset="0x0000000000000000000000000000000000000001",
                base_asset_decimals=18,
                quote_asset="0x0000000000000000000000000000000000000002",
                quote_asset_decimals=6,
                tick_size=Decimal("0.01"),
                min_size=Decimal("0.001"),
                max_size=Decimal("1000000"),
                taker_fee_bps=10001,
                maker_fee_bps=20,
            )

    def test_market_params_validates_negative_maker_fee(self):
        """Should reject negative maker fee."""
        with pytest.raises(ValidationError, match="maker_fee_bps must be between 0 and 10000"):
            MarketParams(
                price_precision=1000,
                size_precision=1000000,
                base_asset="0x0000000000000000000000000000000000000001",
                base_asset_decimals=18,
                quote_asset="0x0000000000000000000000000000000000000002",
                quote_asset_decimals=6,
                tick_size=Decimal("0.01"),
                min_size=Decimal("0.001"),
                max_size=Decimal("1000000"),
                taker_fee_bps=50,
                maker_fee_bps=-1,
            )

    def test_market_params_validates_excessive_maker_fee(self):
        """Should reject maker fee above 10000 bps (100%)."""
        with pytest.raises(ValidationError, match="maker_fee_bps must be between 0 and 10000"):
            MarketParams(
                price_precision=1000,
                size_precision=1000000,
                base_asset="0x0000000000000000000000000000000000000001",
                base_asset_decimals=18,
                quote_asset="0x0000000000000000000000000000000000000002",
                quote_asset_decimals=6,
                tick_size=Decimal("0.01"),
                min_size=Decimal("0.001"),
                max_size=Decimal("1000000"),
                taker_fee_bps=50,
                maker_fee_bps=10001,
            )

    def test_market_params_validates_positive_tick_size(self):
        """Should reject non-positive tick size."""
        with pytest.raises(ValidationError, match="tick_size must be positive"):
            MarketParams(
                price_precision=1000,
                size_precision=1000000,
                base_asset="0x0000000000000000000000000000000000000001",
                base_asset_decimals=18,
                quote_asset="0x0000000000000000000000000000000000000002",
                quote_asset_decimals=6,
                tick_size=Decimal("0"),
                min_size=Decimal("0.001"),
                max_size=Decimal("1000000"),
                taker_fee_bps=50,
                maker_fee_bps=20,
            )

    def test_market_params_validates_positive_min_size(self):
        """Should reject non-positive min size."""
        with pytest.raises(ValidationError, match="min_size must be positive"):
            MarketParams(
                price_precision=1000,
                size_precision=1000000,
                base_asset="0x0000000000000000000000000000000000000001",
                base_asset_decimals=18,
                quote_asset="0x0000000000000000000000000000000000000002",
                quote_asset_decimals=6,
                tick_size=Decimal("0.01"),
                min_size=Decimal("0"),
                max_size=Decimal("1000000"),
                taker_fee_bps=50,
                maker_fee_bps=20,
            )

    def test_market_params_validates_max_size_greater_than_min(self):
        """Should reject max_size less than min_size."""
        with pytest.raises(ValidationError, match="max_size must be greater than min_size"):
            MarketParams(
                price_precision=1000,
                size_precision=1000000,
                base_asset="0x0000000000000000000000000000000000000001",
                base_asset_decimals=18,
                quote_asset="0x0000000000000000000000000000000000000002",
                quote_asset_decimals=6,
                tick_size=Decimal("0.01"),
                min_size=Decimal("100"),
                max_size=Decimal("50"),
                taker_fee_bps=50,
                maker_fee_bps=20,
            )

    def test_market_params_allows_zero_maker_fee(self):
        """Should allow zero maker fee (maker rebate markets)."""
        params = MarketParams(
            price_precision=1000,
            size_precision=1000000,
            base_asset="0x0000000000000000000000000000000000000001",
            base_asset_decimals=18,
            quote_asset="0x0000000000000000000000000000000000000002",
            quote_asset_decimals=6,
            tick_size=Decimal("0.01"),
            min_size=Decimal("0.001"),
            max_size=Decimal("1000000"),
            taker_fee_bps=50,
            maker_fee_bps=0,
        )

        assert params.maker_fee_bps == 0

    def test_market_params_preserves_decimal_precision(self):
        """Should preserve Decimal precision for price values."""
        params = MarketParams(
            price_precision=1000,
            size_precision=1000000,
            base_asset="0x0000000000000000000000000000000000000001",
            base_asset_decimals=18,
            quote_asset="0x0000000000000000000000000000000000000002",
            quote_asset_decimals=6,
            tick_size=Decimal("0.00001"),
            min_size=Decimal("0.0001"),
            max_size=Decimal("999999.999999"),
            taker_fee_bps=50,
            maker_fee_bps=20,
        )

        assert isinstance(params.tick_size, Decimal)
        assert isinstance(params.min_size, Decimal)
        assert isinstance(params.max_size, Decimal)
        assert params.tick_size == Decimal("0.00001")

    def test_market_params_can_be_serialized(self):
        """Should be able to serialize to dict."""
        params = MarketParams(
            price_precision=1000,
            size_precision=1000000,
            base_asset="0x0000000000000000000000000000000000000001",
            base_asset_decimals=18,
            quote_asset="0x0000000000000000000000000000000000000002",
            quote_asset_decimals=6,
            tick_size=Decimal("0.01"),
            min_size=Decimal("0.001"),
            max_size=Decimal("1000000"),
            taker_fee_bps=50,
            maker_fee_bps=20,
        )

        data = params.model_dump()

        assert data["price_precision"] == 1000
        assert data["taker_fee_bps"] == 50
