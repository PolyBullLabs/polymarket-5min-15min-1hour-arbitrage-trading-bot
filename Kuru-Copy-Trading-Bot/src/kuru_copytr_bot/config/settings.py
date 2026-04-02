"""Settings configuration for the Kuru copy trading bot."""

from decimal import Decimal

from dotenv import load_dotenv
from eth_account import Account
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,  # Allow both alias and field name
    )

    # Wallet Configuration
    wallet_private_key: str = Field(
        ...,
        alias="private_key",  # Backward compatibility
        description="Private key for signing transactions (64 hex chars, with or without 0x prefix)",
    )
    wallet_address: str | None = Field(
        None, description="Wallet address (derived from private key)"
    )

    # Blockchain Configuration
    network: str = Field(
        default="testnet",
        description="Network to use: 'testnet' or 'mainnet'",
    )
    monad_rpc_url: str = Field(..., description="Monad blockchain RPC URL")

    # Trading Configuration
    source_wallets: str | list[str] = Field(
        ..., description="List of source trader wallet addresses to copy"
    )
    market_addresses: str | list[str] = Field(
        ..., description="List of Kuru market contract addresses to monitor"
    )
    copy_ratio: Decimal = Field(default=Decimal("1.0"), description="Copy ratio (1.0 = 100%)", gt=0)

    # Risk Management
    max_position_size: Decimal = Field(
        default=Decimal("1000.0"),
        # Accept MAX_ORDER_SIZE, MAX_POSITION_SIZE, or MAX_POSITION_SIZE_USD for backward compatibility
        validation_alias=AliasChoices(
            "max_order_size", "max_position_size", "max_position_size_usd"
        ),
        gt=0,
        description="Maximum order size in quote currency (e.g., USDC) - caps each individual order",
    )
    min_order_size: Decimal = Field(
        default=Decimal("10.0"), gt=0, description="Minimum order size (in quote currency)"
    )
    min_balance_threshold: Decimal = Field(
        default=Decimal("100.0"),
        ge=0,
        description="Minimum balance threshold - bot stops trading if balance falls below this",
    )
    max_total_exposure: Decimal = Field(
        default=Decimal("5000.0"),
        gt=0,
        description="Maximum total exposure across all markets (in quote currency)",
    )

    # Optional Market Filters
    market_whitelist: str | list[str] | None = Field(
        None, description="Only copy trades in these markets"
    )
    market_blacklist: str | list[str] | None = Field(
        None, description="Never copy trades in these markets"
    )

    # Operational Settings
    dry_run: bool = Field(default=False, description="Run in dry-run mode (no actual trades)")
    dry_run_track_all_market_orders: bool = Field(
        default=False,
        description=(
            "In dry-run mode, track ALL orders on the market (not just source wallets). "
            "Useful for testing the bot's monitoring and parsing capabilities."
        ),
    )
    log_level: str = Field(default="INFO", description="Logging level")
    strict_api_errors: bool = Field(
        default=False,
        description=(
            "Strict error handling for REST API calls. "
            "If True, raises exceptions on API errors. "
            "If False, returns empty results and logs warnings (default behavior)."
        ),
    )

    @field_validator("wallet_private_key")
    @classmethod
    def validate_private_key(cls, v: str) -> str:
        """Validate private key format."""
        if not v.startswith("0x") or len(v) != 66:
            raise ValueError("Private key must be a 66-character hex string starting with 0x")
        try:
            int(v, 16)
        except ValueError as e:
            raise ValueError("Private key must be a valid hexadecimal string") from e
        return v

    @field_validator("source_wallets", "market_addresses", mode="before")
    @classmethod
    def parse_address_list(cls, v: str | list[str]) -> list[str]:
        """Parse address list from string or list."""
        if isinstance(v, str):
            # Split comma-separated string and strip whitespace
            return [addr.strip() for addr in v.split(",") if addr.strip()]
        return v

    @field_validator("source_wallets")
    @classmethod
    def validate_source_wallets(cls, v: list[str]) -> list[str]:
        """Validate source wallet addresses.

        Note: Empty list is allowed and will be validated in model_validator
        based on dry_run_track_all_market_orders setting.
        """
        for addr in v:
            if not addr.startswith("0x") or len(addr) != 42:
                raise ValueError(f"Invalid Ethereum address format: {addr}")

        return v

    @field_validator("market_addresses")
    @classmethod
    def validate_market_addresses(cls, v: list[str]) -> list[str]:
        """Validate market contract addresses."""
        if not v:
            raise ValueError("At least one market address is required")

        for addr in v:
            if not addr.startswith("0x") or len(addr) != 42:
                raise ValueError(f"Invalid market address format: {addr}")

        return v

    @field_validator("monad_rpc_url")
    @classmethod
    def validate_http_url(cls, v: str) -> str:
        """Validate HTTP/HTTPS URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("network")
    @classmethod
    def validate_network(cls, v: str) -> str:
        """Validate network selection."""
        v_lower = v.lower()
        if v_lower not in ["testnet", "mainnet"]:
            raise ValueError("Network must be either 'testnet' or 'mainnet'")
        return v_lower

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper

    @field_validator(
        "copy_ratio",
        "max_position_size",
        "min_order_size",
        "min_balance_threshold",
        "max_total_exposure",
        mode="before",
    )
    @classmethod
    def parse_decimal(cls, v) -> Decimal:
        """Parse string or number to Decimal."""
        if isinstance(v, str):
            return Decimal(v)
        if isinstance(v, int | float):
            return Decimal(str(v))
        return v

    @field_validator("dry_run", "dry_run_track_all_market_orders", mode="before")
    @classmethod
    def parse_bool(cls, v) -> bool:
        """Parse string to boolean."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "y")
        return bool(v)

    @field_validator("market_whitelist", "market_blacklist", mode="before")
    @classmethod
    def parse_market_list(cls, v: str | list[str] | None) -> list[str] | None:
        """Parse market list from string or list."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return [market.strip() for market in v.split(",") if market.strip()]
        return v

    @model_validator(mode="after")
    def validate_constraints(self) -> "Settings":
        """Validate cross-field constraints and derive wallet address."""
        # Derive wallet address from private key
        if not self.wallet_address:
            try:
                account = Account.from_key(self.wallet_private_key)
                self.wallet_address = account.address
            except Exception as e:
                raise ValueError(f"Failed to derive wallet address from private key: {e}") from e

        # Validate source wallets requirement
        # In dry-run mode with track_all_market_orders, source wallets are optional (used only for reference)
        # Otherwise, at least one source wallet is required
        if not self.source_wallets:
            if self.dry_run and self.dry_run_track_all_market_orders:
                # Allow empty source wallets in dry-run + track_all mode
                pass
            else:
                raise ValueError(
                    "At least one source wallet is required. "
                    "To skip source wallets, enable both dry_run=True and "
                    "dry_run_track_all_market_orders=True"
                )

        # Validate risk management constraints
        if self.min_order_size >= self.max_position_size:
            raise ValueError(
                f"MIN_ORDER_SIZE ({self.min_order_size}) must be less than "
                f"MAX_ORDER_SIZE ({self.max_position_size})"
            )

        if self.max_position_size > self.max_total_exposure:
            raise ValueError(
                f"MAX_ORDER_SIZE ({self.max_position_size}) cannot exceed "
                f"MAX_TOTAL_EXPOSURE ({self.max_total_exposure})"
            )

        return self
