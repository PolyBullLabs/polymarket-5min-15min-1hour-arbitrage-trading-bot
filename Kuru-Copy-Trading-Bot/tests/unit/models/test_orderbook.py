"""Unit tests for orderbook data models."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.kuru_copytr_bot.models.orderbook import L2Book, PriceLevel


class TestPriceLevel:
    """Test PriceLevel model."""

    def test_price_level_creates_with_valid_data(self):
        """Should create PriceLevel with valid price and size."""
        level = PriceLevel(price=Decimal("2000.50"), size=Decimal("1.5"))

        assert level.price == Decimal("2000.50")
        assert level.size == Decimal("1.5")

    def test_price_level_validates_positive_price(self):
        """Should reject non-positive price."""
        with pytest.raises(ValidationError, match="price must be positive"):
            PriceLevel(price=Decimal("0"), size=Decimal("1.0"))

    def test_price_level_validates_negative_price(self):
        """Should reject negative price."""
        with pytest.raises(ValidationError, match="price must be positive"):
            PriceLevel(price=Decimal("-1.0"), size=Decimal("1.0"))

    def test_price_level_validates_positive_size(self):
        """Should reject non-positive size."""
        with pytest.raises(ValidationError, match="size must be positive"):
            PriceLevel(price=Decimal("2000"), size=Decimal("0"))

    def test_price_level_validates_negative_size(self):
        """Should reject negative size."""
        with pytest.raises(ValidationError, match="size must be positive"):
            PriceLevel(price=Decimal("2000"), size=Decimal("-0.5"))

    def test_price_level_preserves_decimal_precision(self):
        """Should preserve Decimal precision."""
        level = PriceLevel(price=Decimal("2000.123456"), size=Decimal("1.000001"))

        assert isinstance(level.price, Decimal)
        assert isinstance(level.size, Decimal)
        assert level.price == Decimal("2000.123456")
        assert level.size == Decimal("1.000001")


class TestL2Book:
    """Test L2Book model."""

    def test_l2book_creates_with_valid_data(self):
        """Should create L2Book with valid data."""
        bids = [
            PriceLevel(price=Decimal("2000"), size=Decimal("1.5")),
            PriceLevel(price=Decimal("1999"), size=Decimal("2.0")),
        ]
        asks = [
            PriceLevel(price=Decimal("2001"), size=Decimal("1.0")),
            PriceLevel(price=Decimal("2002"), size=Decimal("0.5")),
        ]

        book = L2Book(block_num=12345, bids=bids, asks=asks)

        assert book.block_num == 12345
        assert len(book.bids) == 2
        assert len(book.asks) == 2
        assert book.bids[0].price == Decimal("2000")
        assert book.asks[0].price == Decimal("2001")

    def test_l2book_has_timestamp(self):
        """Should have timestamp field."""
        book = L2Book(block_num=12345, bids=[], asks=[])

        assert isinstance(book.timestamp, datetime)

    def test_l2book_allows_custom_timestamp(self):
        """Should allow custom timestamp."""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        book = L2Book(block_num=12345, bids=[], asks=[], timestamp=custom_time)

        assert book.timestamp == custom_time

    def test_l2book_best_bid_returns_highest_bid(self):
        """Should return highest bid price."""
        bids = [
            PriceLevel(price=Decimal("2000"), size=Decimal("1.5")),
            PriceLevel(price=Decimal("1999"), size=Decimal("2.0")),
        ]
        asks = [PriceLevel(price=Decimal("2001"), size=Decimal("1.0"))]

        book = L2Book(block_num=12345, bids=bids, asks=asks)

        assert book.best_bid == Decimal("2000")

    def test_l2book_best_ask_returns_lowest_ask(self):
        """Should return lowest ask price."""
        bids = [PriceLevel(price=Decimal("2000"), size=Decimal("1.5"))]
        asks = [
            PriceLevel(price=Decimal("2001"), size=Decimal("1.0")),
            PriceLevel(price=Decimal("2002"), size=Decimal("0.5")),
        ]

        book = L2Book(block_num=12345, bids=bids, asks=asks)

        assert book.best_ask == Decimal("2001")

    def test_l2book_best_bid_returns_none_when_empty(self):
        """Should return None when no bids."""
        book = L2Book(
            block_num=12345,
            bids=[],
            asks=[PriceLevel(price=Decimal("2001"), size=Decimal("1.0"))],
        )

        assert book.best_bid is None

    def test_l2book_best_ask_returns_none_when_empty(self):
        """Should return None when no asks."""
        book = L2Book(
            block_num=12345,
            bids=[PriceLevel(price=Decimal("2000"), size=Decimal("1.5"))],
            asks=[],
        )

        assert book.best_ask is None

    def test_l2book_spread_calculates_correctly(self):
        """Should calculate spread between best bid and ask."""
        bids = [PriceLevel(price=Decimal("2000"), size=Decimal("1.5"))]
        asks = [PriceLevel(price=Decimal("2001"), size=Decimal("1.0"))]

        book = L2Book(block_num=12345, bids=bids, asks=asks)

        assert book.spread == Decimal("1")

    def test_l2book_spread_returns_none_when_no_bids(self):
        """Should return None spread when no bids."""
        book = L2Book(
            block_num=12345,
            bids=[],
            asks=[PriceLevel(price=Decimal("2001"), size=Decimal("1.0"))],
        )

        assert book.spread is None

    def test_l2book_spread_returns_none_when_no_asks(self):
        """Should return None spread when no asks."""
        book = L2Book(
            block_num=12345,
            bids=[PriceLevel(price=Decimal("2000"), size=Decimal("1.5"))],
            asks=[],
        )

        assert book.spread is None

    def test_l2book_spread_returns_none_when_empty(self):
        """Should return None spread when orderbook is empty."""
        book = L2Book(block_num=12345, bids=[], asks=[])

        assert book.spread is None

    def test_l2book_mid_price_calculates_correctly(self):
        """Should calculate mid price between best bid and ask."""
        bids = [PriceLevel(price=Decimal("2000"), size=Decimal("1.5"))]
        asks = [PriceLevel(price=Decimal("2002"), size=Decimal("1.0"))]

        book = L2Book(block_num=12345, bids=bids, asks=asks)

        assert book.mid_price == Decimal("2001")

    def test_l2book_mid_price_returns_none_when_incomplete(self):
        """Should return None mid price when bids or asks missing."""
        book = L2Book(block_num=12345, bids=[], asks=[])

        assert book.mid_price is None

    def test_l2book_validates_positive_block_num(self):
        """Should reject negative block number."""
        with pytest.raises(ValidationError, match="block_num must be non-negative"):
            L2Book(block_num=-1, bids=[], asks=[])

    def test_l2book_allows_zero_block_num(self):
        """Should allow zero block number."""
        book = L2Book(block_num=0, bids=[], asks=[])

        assert book.block_num == 0

    def test_l2book_can_be_serialized(self):
        """Should be able to serialize to dict."""
        bids = [PriceLevel(price=Decimal("2000"), size=Decimal("1.5"))]
        asks = [PriceLevel(price=Decimal("2001"), size=Decimal("1.0"))]

        book = L2Book(block_num=12345, bids=bids, asks=asks)

        data = book.model_dump()

        assert data["block_num"] == 12345
        assert len(data["bids"]) == 1
        assert len(data["asks"]) == 1
