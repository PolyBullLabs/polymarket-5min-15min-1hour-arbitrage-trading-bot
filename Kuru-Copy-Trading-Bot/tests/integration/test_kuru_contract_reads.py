"""Integration tests for Kuru contract read operations.

These tests connect to the real Kuru testnet and require:
1. Valid Monad testnet RPC URL in .env
2. Valid private key
3. Network connectivity
4. Kuru testnet contracts deployed

Run with: pytest tests/integration/test_kuru_contract_reads.py -m integration
"""

from decimal import Decimal

import pytest

from src.kuru_copytr_bot.config.constants import KURU_CONTRACT_ADDRESS_TESTNET
from src.kuru_copytr_bot.config.settings import Settings
from src.kuru_copytr_bot.connectors.blockchain.monad import MonadClient
from src.kuru_copytr_bot.connectors.platforms.kuru import KuruClient


@pytest.mark.integration
class TestKuruContractReads:
    """Test reading data from Kuru smart contracts."""

    @pytest.fixture
    def settings(self):
        """Load settings from environment."""
        try:
            return Settings()
        except Exception as e:
            pytest.skip(f"Settings not configured: {e}")

    @pytest.fixture
    def blockchain(self, settings):
        """Create blockchain client connected to testnet."""
        try:
            client = MonadClient(
                rpc_url=settings.monad_rpc_url,
                private_key=settings.private_key,
            )
            if not client.is_connected():
                pytest.skip("Cannot connect to Monad testnet")
            return client
        except Exception as e:
            pytest.skip(f"Blockchain connection failed: {e}")

    @pytest.fixture
    def kuru_client(self, blockchain, settings):
        """Create KuruClient connected to testnet."""
        try:
            return KuruClient(
                blockchain=blockchain,
                contract_address=KURU_CONTRACT_ADDRESS_TESTNET,
            )
        except Exception as e:
            pytest.skip(f"KuruClient initialization failed: {e}")

    def test_get_market_params_returns_valid_data(self, kuru_client):
        """Test fetching real market params from testnet."""
        params = kuru_client.get_market_params("MON-USDC")

        assert params is not None
        assert params.price_precision > 0
        assert params.size_precision > 0
        assert params.base_asset.startswith("0x")
        assert len(params.base_asset) == 42
        assert params.quote_asset.startswith("0x")
        assert len(params.quote_asset) == 42
        assert params.tick_size > 0
        assert params.min_size > 0
        assert params.max_size > params.min_size
        assert params.taker_fee_bps >= 0
        assert params.maker_fee_bps >= 0

    def test_fetch_orderbook_returns_bids_and_asks(self, kuru_client):
        """Test fetching orderbook from contract."""
        orderbook = kuru_client.fetch_orderbook("MON-USDC")

        assert orderbook is not None
        assert hasattr(orderbook, "bids")
        assert hasattr(orderbook, "asks")
        assert isinstance(orderbook.bids, list)
        assert isinstance(orderbook.asks, list)

    def test_get_vault_params_returns_amm_data(self, kuru_client):
        """Test fetching AMM vault parameters."""
        vault_params = kuru_client.get_vault_params("MON-USDC")

        assert vault_params is not None
        assert "vault_address" in vault_params
        assert vault_params["vault_address"].startswith("0x")
        assert "base_balance" in vault_params
        assert isinstance(vault_params["base_balance"], Decimal)
        assert "quote_balance" in vault_params
        assert isinstance(vault_params["quote_balance"], Decimal)

    def test_call_contract_function_with_complex_return(self, blockchain, kuru_client):
        """Test call_contract_function with multiple return values."""
        result = blockchain.call_contract_function(
            contract_address=KURU_CONTRACT_ADDRESS_TESTNET,
            function_name="getMarketParams",
            abi=kuru_client.orderbook_abi,
            args=[],
        )

        assert result is not None
        assert len(result) == 11
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)
        assert isinstance(result[2], str)
        assert result[2].startswith("0x")
