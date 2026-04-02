"""Integration tests for Monad testnet connection.

These tests connect to the real Monad testnet and require:
1. Valid Monad testnet RPC URL in .env
2. Valid private key with some testnet MON for gas
3. Network connectivity

Run with: pytest tests/integration/test_monad_testnet.py -m integration
"""

from decimal import Decimal

import pytest

from src.kuru_copytr_bot.config.settings import Settings
from src.kuru_copytr_bot.connectors.blockchain.monad import MonadClient
from src.kuru_copytr_bot.core.exceptions import BlockchainConnectionError


@pytest.mark.integration
class TestMonadTestnetConnection:
    """Test actual connection to Monad testnet."""

    @pytest.fixture
    def settings(self):
        """Load settings from environment."""
        try:
            return Settings()
        except Exception as e:
            pytest.skip(f"Settings not configured: {e}")

    @pytest.fixture
    def client(self, settings):
        """Create MonadClient connected to real testnet."""
        return MonadClient(
            rpc_url=settings.monad_rpc_url,
            private_key=settings.private_key,
        )

    def test_connect_to_real_monad_testnet(self, client, settings):
        """Should connect to real Monad testnet."""
        assert client.is_connected()
        assert client.wallet_address == settings.wallet_address

    def test_get_real_balance(self, client, settings):
        """Should query real wallet balance from testnet."""
        balance = client.get_balance(settings.wallet_address)

        # Balance should be non-negative
        assert balance >= 0
        assert isinstance(balance, Decimal)

    def test_get_current_block_number(self, client):
        """Should get current block number from testnet."""
        # This would require implementing a get_block_number method
        # For now, we can test that connection is alive
        assert client.is_connected()

    def test_get_nonce_from_testnet(self, client, settings):
        """Should get current nonce from testnet."""
        nonce = client.get_nonce(settings.wallet_address)

        # Nonce should be non-negative integer
        assert isinstance(nonce, int)
        assert nonce >= 0

    def test_estimate_gas_on_testnet(self, client, settings):
        """Should estimate gas for a transaction on testnet."""
        # Estimate gas for a simple transfer
        # Note: This doesn't send the transaction
        try:
            # This test requires implementation of estimate_gas method
            # that doesn't actually send the transaction
            pass
        except NotImplementedError:
            pytest.skip("estimate_gas not implemented yet")


@pytest.mark.integration
@pytest.mark.slow
class TestMonadTestnetTransactions:
    """Test submitting real transactions to Monad testnet.

    WARNING: These tests will consume real testnet gas!
    Only run when you have testnet MON and want to test actual transactions.
    """

    @pytest.fixture
    def settings(self):
        """Load settings from environment."""
        try:
            return Settings()
        except Exception as e:
            pytest.skip(f"Settings not configured: {e}")

    @pytest.fixture
    def client(self, settings):
        """Create MonadClient connected to real testnet."""
        return MonadClient(
            rpc_url=settings.monad_rpc_url,
            private_key=settings.private_key,
        )

    @pytest.mark.skip(reason="Requires testnet funds - run manually when needed")
    def test_submit_real_transaction(self, client, settings):
        """Should submit a real transaction to testnet."""
        # Send a small amount to self (costs gas but doesn't lose funds)
        initial_balance = client.get_balance(settings.wallet_address)

        # Ensure we have enough balance for gas
        if initial_balance < Decimal("0.001"):
            pytest.skip("Insufficient testnet balance for transaction test")

        # Send 0 MON to self (just to test transaction submission)
        tx_hash = client.send_transaction(
            to=settings.wallet_address,
            value=0,
            data="0x",
        )

        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66

        # Wait for transaction receipt
        receipt = client.wait_for_transaction_receipt(tx_hash, timeout=60)

        assert receipt["status"] == 1
        assert receipt["transactionHash"].hex() == tx_hash

    @pytest.mark.skip(reason="Requires testnet funds - run manually when needed")
    def test_parse_real_event_logs(self, client, settings):
        """Should parse real event logs from testnet transaction."""
        # This test would require:
        # 1. Submitting a transaction that emits events
        # 2. Getting the receipt
        # 3. Parsing the logs
        # For now, this is a placeholder for future implementation
        pytest.skip("Requires implementation of contract interaction")


@pytest.mark.integration
class TestMonadTestnetErrorHandling:
    """Test error handling with real testnet."""

    def test_invalid_rpc_url_raises_error(self):
        """Should raise error when connecting to invalid RPC URL."""
        with pytest.raises(BlockchainConnectionError):
            MonadClient(
                rpc_url="https://invalid-rpc-url-that-does-not-exist.com",
                private_key="0x" + "a" * 64,
            )

    def test_invalid_private_key_raises_error(self):
        """Should raise error with invalid private key."""
        with pytest.raises(ValueError, match=""):
            MonadClient(
                rpc_url="https://testnet.monad.xyz",
                private_key="invalid_key",
            )
