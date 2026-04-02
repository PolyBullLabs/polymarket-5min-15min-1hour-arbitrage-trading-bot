"""Wallet model."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator
from pydantic_core import InitErrorDetails
from pydantic_core import ValidationError as CoreValidationError


class Wallet(BaseModel):
    """Represents a wallet with token balances and allowances."""

    address: str = Field(..., description="Wallet address")
    balances: dict[str, Decimal] = Field(default_factory=dict, description="Token balances")
    allowances: dict[str, Decimal] = Field(default_factory=dict, description="Token allowances")
    margin_balance: Decimal = Field(..., description="Available margin balance", ge=0)

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate Ethereum address format."""
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Invalid Ethereum address format")
        return v

    def get_balance(self, token: str) -> Decimal:
        """Get balance for a specific token."""
        return self.balances.get(token, Decimal("0"))

    def update_balance(self, token: str, amount: Decimal) -> None:
        """Set balance for a specific token."""
        self.balances[token] = amount

    def add_to_balance(self, token: str, amount: Decimal) -> None:
        """Add to balance for a specific token."""
        current = self.get_balance(token)
        self.balances[token] = current + amount

    def subtract_from_balance(self, token: str, amount: Decimal) -> None:
        """Subtract from balance for a specific token."""
        current = self.get_balance(token)
        new_balance = current - amount

        if new_balance < 0:
            raise CoreValidationError.from_exception_data(
                "Wallet",
                [
                    InitErrorDetails(
                        type="value_error",
                        loc=("balances", token),
                        input=amount,
                        ctx={
                            "error": f"Insufficient balance for {token}: {current} - {amount} < 0"
                        },
                    )
                ],
            )

        self.balances[token] = new_balance

    def has_sufficient_balance(self, token: str, amount: Decimal) -> bool:
        """Check if wallet has sufficient balance."""
        return self.get_balance(token) >= amount

    def get_allowance(self, token: str) -> Decimal:
        """Get allowance for a specific token."""
        return self.allowances.get(token, Decimal("0"))

    def update_allowance(self, token: str, amount: Decimal) -> None:
        """Set allowance for a specific token."""
        self.allowances[token] = amount

    def has_sufficient_allowance(self, token: str, amount: Decimal) -> bool:
        """Check if wallet has sufficient allowance."""
        return self.get_allowance(token) >= amount

    def update_margin_balance(self, amount: Decimal) -> None:
        """Set margin balance."""
        self.margin_balance = amount

    def add_to_margin(self, amount: Decimal) -> None:
        """Add to margin balance."""
        self.margin_balance += amount

    def subtract_from_margin(self, amount: Decimal) -> None:
        """Subtract from margin balance."""
        self.margin_balance -= amount

    def has_sufficient_margin(self, amount: Decimal) -> bool:
        """Check if wallet has sufficient margin."""
        return self.margin_balance >= amount

    def calculate_total_value(self, prices: dict[str, Decimal]) -> Decimal:
        """Calculate total value of all balances in USD."""
        total = Decimal("0")
        for token, balance in self.balances.items():
            price = prices.get(token, Decimal("0"))
            total += balance * price
        return total
