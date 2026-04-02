"""Unit tests for price normalization utilities."""

from decimal import Decimal

import pytest

from src.kuru_copytr_bot.utils.price import normalize_to_tick


class TestPriceNormalization:
    """Test price normalization to tick size."""

    def test_normalize_to_tick_round_down(self):
        """Should round price down to nearest tick."""
        price = Decimal("2000.123")
        tick_size = Decimal("0.01")

        result = normalize_to_tick(price, tick_size, mode="round_down")

        assert result == Decimal("2000.12")

    def test_normalize_to_tick_round_up(self):
        """Should round price up to nearest tick."""
        price = Decimal("2000.123")
        tick_size = Decimal("0.01")

        result = normalize_to_tick(price, tick_size, mode="round_up")

        assert result == Decimal("2000.13")

    def test_normalize_to_tick_exact_match(self):
        """Should return same price if already aligned to tick."""
        price = Decimal("2000.10")
        tick_size = Decimal("0.01")

        result_down = normalize_to_tick(price, tick_size, mode="round_down")
        result_up = normalize_to_tick(price, tick_size, mode="round_up")

        assert result_down == Decimal("2000.10")
        assert result_up == Decimal("2000.10")

    def test_normalize_to_tick_small_tick_size(self):
        """Should handle very small tick sizes."""
        price = Decimal("2000.123456789")
        tick_size = Decimal("0.00001")

        result = normalize_to_tick(price, tick_size, mode="round_down")

        assert result == Decimal("2000.12345")

    def test_normalize_to_tick_large_tick_size(self):
        """Should handle large tick sizes."""
        price = Decimal("2347.50")
        tick_size = Decimal("10")

        result_down = normalize_to_tick(price, tick_size, mode="round_down")
        result_up = normalize_to_tick(price, tick_size, mode="round_up")

        assert result_down == Decimal("2340")
        assert result_up == Decimal("2350")

    def test_normalize_to_tick_zero_price(self):
        """Should handle zero price."""
        price = Decimal("0")
        tick_size = Decimal("0.01")

        result = normalize_to_tick(price, tick_size, mode="round_down")

        assert result == Decimal("0")

    def test_normalize_to_tick_raises_on_invalid_mode(self):
        """Should raise ValueError for invalid mode."""
        price = Decimal("2000.123")
        tick_size = Decimal("0.01")

        with pytest.raises(ValueError, match="mode must be"):
            normalize_to_tick(price, tick_size, mode="invalid")

    def test_normalize_to_tick_raises_on_zero_tick_size(self):
        """Should raise ValueError for zero tick size."""
        price = Decimal("2000.123")
        tick_size = Decimal("0")

        with pytest.raises(ValueError, match="tick_size must be positive"):
            normalize_to_tick(price, tick_size, mode="round_down")

    def test_normalize_to_tick_raises_on_negative_tick_size(self):
        """Should raise ValueError for negative tick size."""
        price = Decimal("2000.123")
        tick_size = Decimal("-0.01")

        with pytest.raises(ValueError, match="tick_size must be positive"):
            normalize_to_tick(price, tick_size, mode="round_down")

    def test_normalize_to_tick_raises_on_negative_price(self):
        """Should raise ValueError for negative price."""
        price = Decimal("-2000.123")
        tick_size = Decimal("0.01")

        with pytest.raises(ValueError, match="price must be non-negative"):
            normalize_to_tick(price, tick_size, mode="round_down")

    def test_normalize_to_tick_edge_case_very_close_to_tick(self):
        """Should handle prices very close to tick boundary."""
        # Price just slightly above a tick
        price = Decimal("2000.1000000001")
        tick_size = Decimal("0.01")

        result_down = normalize_to_tick(price, tick_size, mode="round_down")
        result_up = normalize_to_tick(price, tick_size, mode="round_up")

        assert result_down == Decimal("2000.10")
        assert result_up == Decimal("2000.11")

    def test_normalize_to_tick_preserves_precision(self):
        """Should maintain Decimal precision."""
        price = Decimal("1999.9876543210")
        tick_size = Decimal("0.0001")

        result = normalize_to_tick(price, tick_size, mode="round_down")

        # Result should be a Decimal, not float
        assert isinstance(result, Decimal)
        assert result == Decimal("1999.9876")
