"""Tests for Constants configuration."""

from web3 import Web3

# These imports will fail initially - that's expected for TDD
from src.kuru_copytr_bot.config.constants import (
    DEFAULT_GAS_LIMIT,
    DEFAULT_GAS_PRICE_GWEI,
    KURU_CONTRACT_ADDRESS_MAINNET,
    KURU_CONTRACT_ADDRESS_TESTNET,
    KURU_DEPLOYER_ADDRESS_TESTNET,
    KURU_FORWARDER_ADDRESS_TESTNET,
    KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET,
    KURU_ROUTER_ADDRESS_TESTNET,
    KURU_UTILS_ADDRESS_TESTNET,
    MAX_RETRIES,
    MON_USDC_MARKET_ADDRESS,
    MONAD_CHAIN_ID,
    MONAD_TESTNET_CHAIN_ID,
    RETRY_BACKOFF_SECONDS,
    USDC_ADDRESS_TESTNET,
)


class TestConstants:
    """Test that constants are properly defined."""

    def test_monad_chain_id_is_defined(self):
        """MONAD_CHAIN_ID should be defined."""
        assert MONAD_CHAIN_ID is not None
        assert isinstance(MONAD_CHAIN_ID, int)

    def test_monad_testnet_chain_id_is_defined(self):
        """MONAD_TESTNET_CHAIN_ID should be defined."""
        assert MONAD_TESTNET_CHAIN_ID is not None
        assert isinstance(MONAD_TESTNET_CHAIN_ID, int)

    def test_kuru_contract_addresses_are_valid_ethereum_addresses(self):
        """Kuru contract addresses should be valid Ethereum addresses."""
        assert KURU_CONTRACT_ADDRESS_TESTNET.startswith("0x")
        assert len(KURU_CONTRACT_ADDRESS_TESTNET) == 42

        if KURU_CONTRACT_ADDRESS_MAINNET:
            assert KURU_CONTRACT_ADDRESS_MAINNET.startswith("0x")
            assert len(KURU_CONTRACT_ADDRESS_MAINNET) == 42

    def test_kuru_router_address_is_valid_and_checksummed(self):
        """Kuru router address should be valid and checksummed."""
        assert KURU_ROUTER_ADDRESS_TESTNET.startswith("0x")
        assert len(KURU_ROUTER_ADDRESS_TESTNET) == 42
        # Verify it's checksummed by comparing to Web3's checksum version
        assert Web3.to_checksum_address(KURU_ROUTER_ADDRESS_TESTNET) == KURU_ROUTER_ADDRESS_TESTNET

    def test_kuru_margin_account_address_is_valid_and_checksummed(self):
        """Kuru margin account address should be valid and checksummed."""
        assert KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET.startswith("0x")
        assert len(KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET) == 42
        assert (
            Web3.to_checksum_address(KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET)
            == KURU_MARGIN_ACCOUNT_ADDRESS_TESTNET
        )

    def test_kuru_forwarder_address_is_valid_and_checksummed(self):
        """Kuru forwarder address should be valid and checksummed."""
        assert KURU_FORWARDER_ADDRESS_TESTNET.startswith("0x")
        assert len(KURU_FORWARDER_ADDRESS_TESTNET) == 42
        assert (
            Web3.to_checksum_address(KURU_FORWARDER_ADDRESS_TESTNET)
            == KURU_FORWARDER_ADDRESS_TESTNET
        )

    def test_kuru_deployer_address_is_valid_and_checksummed(self):
        """Kuru deployer address should be valid and checksummed."""
        assert KURU_DEPLOYER_ADDRESS_TESTNET.startswith("0x")
        assert len(KURU_DEPLOYER_ADDRESS_TESTNET) == 42
        assert (
            Web3.to_checksum_address(KURU_DEPLOYER_ADDRESS_TESTNET) == KURU_DEPLOYER_ADDRESS_TESTNET
        )

    def test_kuru_utils_address_is_valid_and_checksummed(self):
        """Kuru utils address should be valid and checksummed."""
        assert KURU_UTILS_ADDRESS_TESTNET.startswith("0x")
        assert len(KURU_UTILS_ADDRESS_TESTNET) == 42
        assert Web3.to_checksum_address(KURU_UTILS_ADDRESS_TESTNET) == KURU_UTILS_ADDRESS_TESTNET

    def test_token_addresses_are_valid_and_checksummed(self):
        """Token addresses should be valid and checksummed."""
        assert USDC_ADDRESS_TESTNET.startswith("0x")
        assert len(USDC_ADDRESS_TESTNET) == 42
        assert Web3.to_checksum_address(USDC_ADDRESS_TESTNET) == USDC_ADDRESS_TESTNET

    def test_market_addresses_are_valid_and_checksummed(self):
        """Market addresses should be valid and checksummed."""
        assert MON_USDC_MARKET_ADDRESS.startswith("0x")
        assert len(MON_USDC_MARKET_ADDRESS) == 42
        assert Web3.to_checksum_address(MON_USDC_MARKET_ADDRESS) == MON_USDC_MARKET_ADDRESS

    def test_monad_testnet_chain_id_correct(self):
        """Monad testnet chain ID should be 10143."""
        assert MONAD_TESTNET_CHAIN_ID == 10143

    def test_no_placeholder_addresses(self):
        """Ensure no placeholder addresses remain."""
        assert "placeholder" not in KURU_CONTRACT_ADDRESS_TESTNET.lower()
        assert "0xKuru" not in KURU_CONTRACT_ADDRESS_TESTNET
        assert KURU_CONTRACT_ADDRESS_TESTNET != "0x0000000000000000000000000000000000000000"

    def test_default_gas_limit_is_reasonable(self):
        """Default gas limit should be reasonable (100k-10M)."""
        assert DEFAULT_GAS_LIMIT > 100_000
        assert DEFAULT_GAS_LIMIT < 10_000_000

    def test_default_gas_price_is_positive(self):
        """Default gas price should be positive."""
        assert DEFAULT_GAS_PRICE_GWEI > 0

    def test_max_retries_is_positive(self):
        """Max retries should be positive."""
        assert MAX_RETRIES > 0
        assert MAX_RETRIES <= 10  # Reasonable upper bound

    def test_retry_backoff_is_positive(self):
        """Retry backoff should be positive."""
        assert RETRY_BACKOFF_SECONDS > 0
        assert RETRY_BACKOFF_SECONDS <= 60  # Reasonable upper bound
