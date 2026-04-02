"""Integration tests for Kuru testnet.

These tests connect to the real Kuru testnet and require:
1. Valid Monad testnet RPC URL in .env
2. Valid private key with testnet MON and USDC
3. Network connectivity
4. Kuru testnet API availability

Run with: pytest tests/integration/test_kuru_testnet.py -m integration
"""

from decimal import Decimal

import pytest

from src.kuru_copytr_bot.config.settings import Settings
from src.kuru_copytr_bot.connectors.blockchain.monad import MonadClient
from src.kuru_copytr_bot.connectors.platforms.kuru import KuruClient
from src.kuru_copytr_bot.core.enums import OrderSide
from src.kuru_copytr_bot.core.exceptions import InvalidMarketError


@pytest.mark.integration
class TestKuruTestnetConnection:
    """Test connection to Kuru testnet."""

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
        return MonadClient(
            rpc_url=settings.monad_rpc_url,
            private_key=settings.private_key,
        )

    @pytest.fixture
    def kuru_client(self, blockchain, settings):
        """Create KuruClient connected to testnet."""
        # Assuming Kuru contract address is in settings or constants
        from src.kuru_copytr_bot.config.constants import KURU_CONTRACT_ADDRESS_TESTNET

        return KuruClient(
            blockchain=blockchain,
            contract_address=KURU_CONTRACT_ADDRESS_TESTNET,
        )

    def test_connect_to_kuru_testnet_api(self, kuru_client):
        """Should connect to Kuru testnet API."""
        # Try to fetch market params
        try:
            params = kuru_client.get_market_params("ETH-USDC")
            assert params is not None
            assert params["market_id"] == "ETH-USDC"
        except InvalidMarketError:
            pytest.skip("ETH-USDC market not available on testnet")

    def test_get_testnet_market_list(self, kuru_client):
        """Should get list of available markets on testnet."""
        # This would require implementing a get_markets() method
        # For now, just verify we can query a known market
        try:
            params = kuru_client.get_market_params("ETH-USDC")
            assert "base_token" in params
            assert "quote_token" in params
        except InvalidMarketError:
            pytest.skip("No markets available on testnet")


@pytest.mark.integration
@pytest.mark.slow
class TestKuruTestnetOrders:
    """Test order placement on Kuru testnet.

    WARNING: These tests will use real testnet funds!
    Only run when you have testnet tokens and want to test actual orders.
    """

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
        return MonadClient(
            rpc_url=settings.monad_rpc_url,
            private_key=settings.private_key,
        )

    @pytest.fixture
    def kuru_client(self, blockchain, settings):
        """Create KuruClient connected to testnet."""
        from src.kuru_copytr_bot.config.constants import KURU_CONTRACT_ADDRESS_TESTNET

        return KuruClient(
            blockchain=blockchain,
            contract_address=KURU_CONTRACT_ADDRESS_TESTNET,
        )

    @pytest.mark.skip(reason="Requires testnet funds - run manually when needed")
    def test_place_and_cancel_limit_order_on_testnet(self, kuru_client, blockchain, settings):
        """Should place and cancel a limit order on real testnet."""
        # Check balance first
        usdc_balance = blockchain.get_token_balance(
            settings.wallet_address,
            "0xUSDCTestnetAddress00000000000000000000000",  # USDC testnet address
        )

        if usdc_balance < Decimal("10.0"):
            pytest.skip("Insufficient USDC balance for test")

        # Place a limit order far from market price to avoid fill
        order_id = kuru_client.place_limit_order(
            market="ETH-USDC",
            side=OrderSide.BUY,
            price=Decimal("1000.0"),  # Far below market to avoid fill
            size=Decimal("0.01"),  # Small size
            post_only=True,
        )

        assert order_id is not None
        assert isinstance(order_id, str)

        # Verify order is open
        status = kuru_client.get_order_status(order_id)
        assert status["status"] in ["OPEN", "PENDING"]

        # Cancel the order
        tx_hash = kuru_client.cancel_order(order_id)

        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66

        # Wait for cancellation to confirm
        receipt = blockchain.wait_for_transaction_receipt(tx_hash, timeout=60)
        assert receipt["status"] == 1

    @pytest.mark.skip(reason="Requires testnet funds - run manually when needed")
    def test_batch_cancel_orders_on_testnet(self, kuru_client, blockchain):
        """Should batch cancel multiple orders on testnet."""
        # Place multiple orders
        order_ids = []
        for i in range(3):
            order_id = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("1000.0") + Decimal(i),
                size=Decimal("0.01"),
                post_only=True,
            )
            order_ids.append(order_id)

        # Cancel all orders in batch
        tx_hash = kuru_client.cancel_orders(order_ids)

        assert tx_hash.startswith("0x")

        # Wait for batch cancellation
        receipt = blockchain.wait_for_transaction_receipt(tx_hash, timeout=60)
        assert receipt["status"] == 1


@pytest.mark.integration
class TestKuruTestnetDataQueries:
    """Test data queries from Kuru testnet (read-only, no funds needed)."""

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
        return MonadClient(
            rpc_url=settings.monad_rpc_url,
            private_key=settings.private_key,
        )

    @pytest.fixture
    def kuru_client(self, blockchain, settings):
        """Create KuruClient connected to testnet."""
        from src.kuru_copytr_bot.config.constants import KURU_CONTRACT_ADDRESS_TESTNET

        return KuruClient(
            blockchain=blockchain,
            contract_address=KURU_CONTRACT_ADDRESS_TESTNET,
        )

    def test_query_market_parameters_from_testnet(self, kuru_client):
        """Should query real market parameters from testnet."""
        try:
            params = kuru_client.get_market_params("ETH-USDC")

            assert "market_id" in params
            assert "base_token" in params
            assert "quote_token" in params
            assert "min_order_size" in params
            assert "tick_size" in params
            assert "maker_fee" in params
            assert "taker_fee" in params
        except InvalidMarketError:
            pytest.skip("ETH-USDC market not available on testnet")

    def test_query_open_orders_from_testnet(self, kuru_client):
        """Should query open orders from testnet."""
        # This should not fail even if there are no open orders
        orders = kuru_client.get_open_orders()

        assert isinstance(orders, list)
        # May be empty if no open orders

    def test_query_positions_from_testnet(self, kuru_client):
        """Should query positions from testnet."""
        # This should not fail even if there are no positions
        positions = kuru_client.get_positions()

        assert isinstance(positions, list)
        # May be empty if no positions


@pytest.mark.integration
class TestKuruTestnetErrorHandling:
    """Test error handling with real testnet."""

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
        return MonadClient(
            rpc_url=settings.monad_rpc_url,
            private_key=settings.private_key,
        )

    @pytest.fixture
    def kuru_client(self, blockchain, settings):
        """Create KuruClient connected to testnet."""
        from src.kuru_copytr_bot.config.constants import KURU_CONTRACT_ADDRESS_TESTNET

        return KuruClient(
            blockchain=blockchain,
            contract_address=KURU_CONTRACT_ADDRESS_TESTNET,
        )

    def test_invalid_market_raises_error(self, kuru_client):
        """Should raise error for invalid market on testnet."""
        with pytest.raises(InvalidMarketError):
            kuru_client.get_market_params("INVALID-NONEXISTENT-MARKET")

    def test_invalid_order_id_raises_error(self, kuru_client):
        """Should handle invalid order ID gracefully."""
        # Querying status of non-existent order should raise or return None
        try:
            status = kuru_client.get_order_status("nonexistent_order_id_12345")
            # If it doesn't raise, it should return None or empty
            assert status is None or status.get("status") == "NOT_FOUND"
        except Exception:
            # Expected to raise an error for invalid order ID
            pass
