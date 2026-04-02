"""Tests for Wallet model."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

# These imports will fail initially - that's expected for TDD
from src.kuru_copytr_bot.models.wallet import Wallet


class TestWalletModel:
    """Test Wallet model creation and balance tracking."""

    def test_wallet_creation(self):
        """Wallet should be created with address and balances."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0"), "USDC": Decimal("5000.0")},
            allowances={"USDC": Decimal("1000.0")},
            margin_balance=Decimal("2000.0"),
        )

        assert wallet.address == "0x1234567890123456789012345678901234567890"
        assert wallet.balances["ETH"] == Decimal("10.0")
        assert wallet.balances["USDC"] == Decimal("5000.0")
        assert wallet.margin_balance == Decimal("2000.0")

    def test_wallet_validates_address_format(self):
        """Wallet should validate Ethereum address format."""
        with pytest.raises(ValidationError):
            Wallet(
                address="invalid_address",
                balances={},
                allowances={},
                margin_balance=Decimal("0"),
            )

    def test_wallet_get_balance(self):
        """Wallet should return balance for specific token."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0"), "USDC": Decimal("5000.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        assert wallet.get_balance("ETH") == Decimal("10.0")
        assert wallet.get_balance("USDC") == Decimal("5000.0")

    def test_wallet_get_balance_nonexistent_token(self):
        """Wallet should return zero for tokens not in balances."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        assert wallet.get_balance("BTC") == Decimal("0")

    def test_wallet_update_balance(self):
        """Wallet should update token balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        wallet.update_balance("ETH", Decimal("15.0"))
        assert wallet.get_balance("ETH") == Decimal("15.0")

    def test_wallet_update_balance_new_token(self):
        """Wallet should add new token when updating balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        wallet.update_balance("USDC", Decimal("1000.0"))
        assert wallet.get_balance("USDC") == Decimal("1000.0")

    def test_wallet_add_to_balance(self):
        """Wallet should add amount to existing balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        wallet.add_to_balance("ETH", Decimal("5.0"))
        assert wallet.get_balance("ETH") == Decimal("15.0")

    def test_wallet_subtract_from_balance(self):
        """Wallet should subtract amount from existing balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        wallet.subtract_from_balance("ETH", Decimal("3.0"))
        assert wallet.get_balance("ETH") == Decimal("7.0")

    def test_wallet_cannot_subtract_more_than_balance(self):
        """Wallet should reject subtraction that would result in negative balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        with pytest.raises(ValidationError) as exc_info:
            wallet.subtract_from_balance("ETH", Decimal("15.0"))

        assert "insufficient" in str(exc_info.value).lower()

    def test_wallet_get_allowance(self):
        """Wallet should return allowance for specific token."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"USDC": Decimal("5000.0")},
            allowances={"USDC": Decimal("1000.0")},
            margin_balance=Decimal("0"),
        )

        assert wallet.get_allowance("USDC") == Decimal("1000.0")

    def test_wallet_get_allowance_nonexistent(self):
        """Wallet should return zero for tokens without allowance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"USDC": Decimal("5000.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        assert wallet.get_allowance("USDC") == Decimal("0")

    def test_wallet_update_allowance(self):
        """Wallet should update token allowance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"USDC": Decimal("5000.0")},
            allowances={"USDC": Decimal("1000.0")},
            margin_balance=Decimal("0"),
        )

        wallet.update_allowance("USDC", Decimal("2000.0"))
        assert wallet.get_allowance("USDC") == Decimal("2000.0")

    def test_wallet_has_sufficient_balance(self):
        """Wallet should check if it has sufficient balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={},
            margin_balance=Decimal("0"),
        )

        assert wallet.has_sufficient_balance("ETH", Decimal("5.0")) is True
        assert wallet.has_sufficient_balance("ETH", Decimal("15.0")) is False
        assert wallet.has_sufficient_balance("BTC", Decimal("1.0")) is False

    def test_wallet_has_sufficient_allowance(self):
        """Wallet should check if it has sufficient allowance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"USDC": Decimal("5000.0")},
            allowances={"USDC": Decimal("1000.0")},
            margin_balance=Decimal("0"),
        )

        assert wallet.has_sufficient_allowance("USDC", Decimal("500.0")) is True
        assert wallet.has_sufficient_allowance("USDC", Decimal("1500.0")) is False

    def test_wallet_update_margin_balance(self):
        """Wallet should update margin balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={},
            allowances={},
            margin_balance=Decimal("1000.0"),
        )

        wallet.update_margin_balance(Decimal("1500.0"))
        assert wallet.margin_balance == Decimal("1500.0")

    def test_wallet_add_to_margin(self):
        """Wallet should add to margin balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={},
            allowances={},
            margin_balance=Decimal("1000.0"),
        )

        wallet.add_to_margin(Decimal("500.0"))
        assert wallet.margin_balance == Decimal("1500.0")

    def test_wallet_subtract_from_margin(self):
        """Wallet should subtract from margin balance."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={},
            allowances={},
            margin_balance=Decimal("1000.0"),
        )

        wallet.subtract_from_margin(Decimal("300.0"))
        assert wallet.margin_balance == Decimal("700.0")

    def test_wallet_has_sufficient_margin(self):
        """Wallet should check if it has sufficient margin."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={},
            allowances={},
            margin_balance=Decimal("1000.0"),
        )

        assert wallet.has_sufficient_margin(Decimal("500.0")) is True
        assert wallet.has_sufficient_margin(Decimal("1500.0")) is False

    def test_wallet_uses_decimal_for_all_amounts(self):
        """Wallet should use Decimal for all amounts."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0")},
            allowances={"USDC": Decimal("1000.0")},
            margin_balance=Decimal("500.0"),
        )

        assert isinstance(wallet.get_balance("ETH"), Decimal)
        assert isinstance(wallet.get_allowance("USDC"), Decimal)
        assert isinstance(wallet.margin_balance, Decimal)

    def test_wallet_total_balance_value(self):
        """Wallet should calculate total balance value in USD."""
        wallet = Wallet(
            address="0x1234567890123456789012345678901234567890",
            balances={"ETH": Decimal("10.0"), "USDC": Decimal("5000.0")},
            allowances={},
            margin_balance=Decimal("2000.0"),
        )

        # Assume we pass price oracle or prices dict
        prices = {"ETH": Decimal("2000.0"), "USDC": Decimal("1.0")}
        total_value = wallet.calculate_total_value(prices)

        # 10 ETH * 2000 + 5000 USDC * 1 = 25000
        assert total_value == Decimal("25000.0")
