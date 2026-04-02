"""Tests for Settings configuration."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

# These imports will fail initially - that's expected for TDD
from src.kuru_copytr_bot.config.settings import Settings


class TestSettingsConfiguration:
    """Test Settings configuration loading and validation."""

    def test_settings_loads_from_environment_variables(self, monkeypatch):
        """Settings should load from environment variables."""
        monkeypatch.setenv("WALLET_PRIVATE_KEY", "0x" + "a" * 64)
        monkeypatch.setenv("MONAD_RPC_URL", "https://testnet.monad.xyz")
        monkeypatch.setenv("SOURCE_WALLETS", "0x1234567890123456789012345678901234567890")
        monkeypatch.setenv("MARKET_ADDRESSES", "0x4444444444444444444444444444444444444444")

        settings = Settings()

        assert settings.wallet_private_key == "0x" + "a" * 64
        assert settings.monad_rpc_url == "https://testnet.monad.xyz"
        assert "0x1234567890123456789012345678901234567890" in settings.source_wallets
        assert "0x4444444444444444444444444444444444444444" in settings.market_addresses

    def test_settings_requires_private_key(self):
        """Settings should require private key."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                wallet_private_key=None,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
            )

        assert (
            "wallet_private_key" in str(exc_info.value).lower()
            or "private_key" in str(exc_info.value).lower()
        )

    def test_settings_validates_private_key_format(self):
        """Settings should validate private key is 66 characters hex string."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="invalid_key",
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
            )

    def test_settings_derives_wallet_address_from_private_key(self):
        """Settings should derive wallet address from private key."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
        )

        assert settings.wallet_address is not None
        assert settings.wallet_address.startswith("0x")
        assert len(settings.wallet_address) == 42

    def test_settings_validates_wallet_address_format(self):
        """Settings should validate Ethereum address format for source wallets."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["invalid_address"],
            )

    def test_settings_validates_source_wallets_is_list(self):
        """Settings should validate source_wallets is a list."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets="not_a_list",
            )

    def test_settings_requires_at_least_one_source_wallet(self):
        """Settings should require at least one source wallet in normal mode."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=[],
                market_addresses=["0x4444444444444444444444444444444444444444"],
                dry_run=False,
                dry_run_track_all_market_orders=False,
            )

        assert "source wallet" in str(exc_info.value).lower()

    def test_settings_allows_empty_source_wallets_in_dry_run_track_all_mode(self):
        """Settings should allow empty source wallets when dry_run and track_all are enabled."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=[],
            market_addresses=["0x4444444444444444444444444444444444444444"],
            dry_run=True,
            dry_run_track_all_market_orders=True,
        )

        assert settings.source_wallets == []
        assert settings.dry_run is True
        assert settings.dry_run_track_all_market_orders is True

    def test_settings_requires_source_wallets_in_dry_run_mode_without_track_all(self):
        """Settings should require source wallets in dry_run mode if track_all is disabled."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=[],
                market_addresses=["0x4444444444444444444444444444444444444444"],
                dry_run=True,
                dry_run_track_all_market_orders=False,
            )

        assert "source wallet" in str(exc_info.value).lower()

    def test_settings_requires_source_wallets_in_track_all_mode_without_dry_run(self):
        """Settings should require source wallets if track_all is enabled but not dry_run."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=[],
                market_addresses=["0x4444444444444444444444444444444444444444"],
                dry_run=False,
                dry_run_track_all_market_orders=True,
            )

        assert "source wallet" in str(exc_info.value).lower()

    def test_settings_copy_ratio_must_be_positive(self):
        """Copy ratio must be > 0."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                copy_ratio=Decimal("-0.5"),
            )

    def test_settings_copy_ratio_cannot_be_zero(self):
        """Copy ratio cannot be zero."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                copy_ratio=Decimal("0"),
            )

    def test_settings_max_position_size_must_be_positive(self):
        """Max position size must be > 0."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                max_position_size=Decimal("-1000"),
            )

    def test_settings_has_default_copy_ratio(self):
        """Settings should have default copy ratio of 1.0."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
        )

        assert settings.copy_ratio == Decimal("1.0")

    def test_settings_has_default_dry_run_false(self):
        """Settings should have default dry_run = False."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
        )

        assert settings.dry_run is False

    def test_settings_has_default_log_level_info(self):
        """Settings should have default log_level = INFO."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
        )

        assert settings.log_level == "INFO"

    def test_settings_accepts_valid_log_levels(self):
        """Settings should accept valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                log_level=level,
            )
            assert settings.log_level == level

    def test_settings_validates_rpc_url_format(self):
        """Settings should validate RPC URL format."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="not_a_url",
                source_wallets=["0x1234567890123456789012345678901234567890"],
            )

    def test_settings_parses_source_wallets_from_comma_separated_string(self, monkeypatch):
        """Settings should parse comma-separated source wallets from env."""
        monkeypatch.setenv("WALLET_PRIVATE_KEY", "0x" + "a" * 64)
        monkeypatch.setenv("MONAD_RPC_URL", "https://testnet.monad.xyz")
        monkeypatch.setenv(
            "SOURCE_WALLETS",
            "0x1234567890123456789012345678901234567890,0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        )

        settings = Settings()

        assert len(settings.source_wallets) == 2
        assert "0x1234567890123456789012345678901234567890" in settings.source_wallets
        assert "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd" in settings.source_wallets

    def test_settings_uses_decimal_for_financial_values(self):
        """Settings should use Decimal for copy_ratio and max_position_size."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
            max_position_size=Decimal("1000"),
            max_total_exposure=Decimal("5000"),
            copy_ratio=Decimal("0.5"),
        )

        assert isinstance(settings.copy_ratio, Decimal)
        assert isinstance(settings.max_position_size, Decimal)

    def test_settings_supports_optional_market_whitelist(self):
        """Settings should support optional market whitelist."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
            market_whitelist=["ETH-USDC", "BTC-USDC"],
        )

        assert settings.market_whitelist == ["ETH-USDC", "BTC-USDC"]

    def test_settings_supports_optional_market_blacklist(self):
        """Settings should support optional market blacklist."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
            market_blacklist=["SCAM-USDC"],
        )

        assert settings.market_blacklist == ["SCAM-USDC"]

    def test_settings_loads_from_dotenv_file(self, tmp_path, monkeypatch):
        """Settings should load from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            f"""
WALLET_PRIVATE_KEY=0x{"a" * 64}
MONAD_RPC_URL=https://testnet.monad.xyz
SOURCE_WALLETS=0x1234567890123456789012345678901234567890
COPY_RATIO=0.75
DRY_RUN=true
LOG_LEVEL=DEBUG
"""
        )

        monkeypatch.chdir(tmp_path)
        settings = Settings()

        assert settings.copy_ratio == Decimal("0.75")
        assert settings.dry_run is True
        assert settings.log_level == "DEBUG"

    def test_settings_has_default_values_for_new_fields(self):
        """Settings should have default values for new risk management fields."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
        )

        assert settings.max_position_size == Decimal("1000.0")
        assert settings.min_order_size == Decimal("10.0")
        assert settings.min_balance_threshold == Decimal("100.0")
        assert settings.max_total_exposure == Decimal("5000.0")
        assert settings.poll_interval_seconds == 5

    def test_settings_validates_min_order_size_less_than_max_position_size(self):
        """min_order_size must be less than max_position_size."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                min_order_size=Decimal("1000"),
                max_position_size=Decimal("500"),
            )

    def test_settings_validates_max_position_size_not_exceeds_max_total_exposure(self):
        """max_position_size cannot exceed max_total_exposure."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                max_position_size=Decimal("10000"),
                max_total_exposure=Decimal("5000"),
            )

    def test_settings_validates_poll_interval_positive(self):
        """poll_interval_seconds must be greater than 0."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                poll_interval_seconds=0,
            )

    def test_settings_validates_poll_interval_max_limit(self):
        """poll_interval_seconds must be <= 3600."""
        with pytest.raises(ValidationError):
            Settings(
                wallet_private_key="0x" + "a" * 64,
                monad_rpc_url="https://testnet.monad.xyz",
                source_wallets=["0x1234567890123456789012345678901234567890"],
                poll_interval_seconds=3601,
            )

    def test_settings_backward_compatibility_with_private_key_alias(self, monkeypatch):
        """Settings should accept PRIVATE_KEY environment variable (backward compatibility)."""
        monkeypatch.setenv("PRIVATE_KEY", "0x" + "a" * 64)
        monkeypatch.setenv("MONAD_RPC_URL", "https://testnet.monad.xyz")
        monkeypatch.setenv("SOURCE_WALLETS", "0x1234567890123456789012345678901234567890")

        settings = Settings()

        assert settings.wallet_private_key == "0x" + "a" * 64

    def test_settings_backward_compatibility_with_max_position_size_usd_alias(self, monkeypatch):
        """Settings should accept MAX_POSITION_SIZE_USD environment variable (backward compatibility)."""
        monkeypatch.setenv("WALLET_PRIVATE_KEY", "0x" + "a" * 64)
        monkeypatch.setenv("MONAD_RPC_URL", "https://testnet.monad.xyz")
        monkeypatch.setenv("SOURCE_WALLETS", "0x1234567890123456789012345678901234567890")
        # Unset MAX_ORDER_SIZE if it exists (from .env file) to test backward compatibility
        monkeypatch.delenv("MAX_ORDER_SIZE", raising=False)
        monkeypatch.delenv("MAX_POSITION_SIZE", raising=False)
        monkeypatch.setenv("MAX_POSITION_SIZE_USD", "2000.0")
        # Set MAX_TOTAL_EXPOSURE high enough to allow the test value
        monkeypatch.setenv("MAX_TOTAL_EXPOSURE", "5000.0")

        settings = Settings()

        assert settings.max_position_size == Decimal("2000.0")

    def test_settings_min_balance_threshold_can_be_zero(self):
        """min_balance_threshold can be zero (>= 0)."""
        settings = Settings(
            wallet_private_key="0x" + "a" * 64,
            monad_rpc_url="https://testnet.monad.xyz",
            source_wallets=["0x1234567890123456789012345678901234567890"],
            min_balance_threshold=Decimal("0"),
        )

        assert settings.min_balance_threshold == Decimal("0")
