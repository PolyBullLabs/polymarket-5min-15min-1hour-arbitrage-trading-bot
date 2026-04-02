"""Unit tests for Kuru Exchange client."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.kuru_copytr_bot.connectors.platforms.kuru import KuruClient
from src.kuru_copytr_bot.core.enums import OrderSide
from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientBalanceError,
    InvalidMarketError,
    OrderExecutionError,
)
from src.kuru_copytr_bot.models.market import MarketParams


def create_test_market_params(**overrides) -> MarketParams:
    """Helper to create test MarketParams with defaults."""
    defaults = {
        "price_precision": 1000,
        "size_precision": 1000000,
        "base_asset": "0x0000000000000000000000000000000000000001",
        "base_asset_decimals": 18,
        "quote_asset": "0x0000000000000000000000000000000000000002",
        "quote_asset_decimals": 6,
        "tick_size": Decimal("0.01"),
        "min_size": Decimal("0.001"),
        "max_size": Decimal("1000"),
        "taker_fee_bps": 50,
        "maker_fee_bps": 20,
    }
    defaults.update(overrides)
    return MarketParams(**defaults)


@pytest.fixture
def mock_blockchain():
    """Create a mock blockchain client."""
    blockchain = MagicMock()
    blockchain.wallet_address = "0x1234567890123456789012345678901234567890"
    blockchain.send_transaction.return_value = "0x" + "a" * 64  # 66 chars total
    blockchain.get_balance.return_value = Decimal("100.0")
    blockchain.get_token_balance.return_value = Decimal("10000.0")  # USDC balance
    blockchain.wait_for_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 1000000,
        "transactionHash": "0x" + "b" * 64,  # 66 chars total
        "logs": [],
    }
    return blockchain


@pytest.fixture
def kuru_client(mock_blockchain):
    """Create KuruClient with mocked blockchain."""
    return KuruClient(
        blockchain=mock_blockchain,
        contract_address="0x4444444444444444444444444444444444444444",
    )


class TestKuruClientInitialization:
    """Test KuruClient initialization."""

    def test_kuru_client_initializes_successfully(self, mock_blockchain):
        """KuruClient should initialize with blockchain."""
        client = KuruClient(
            blockchain=mock_blockchain,
            contract_address="0x4444444444444444444444444444444444444444",
        )

        assert client is not None
        assert client.blockchain == mock_blockchain
        assert client.contract_address == "0x4444444444444444444444444444444444444444"

    def test_kuru_client_validates_contract_address(self, mock_blockchain):
        """KuruClient should validate contract address format."""
        with pytest.raises(ValueError):
            KuruClient(
                blockchain=mock_blockchain,
                contract_address="invalid_address",
            )


class TestKuruClientMarginDeposit:
    """Test Kuru margin deposit functionality."""

    def test_kuru_client_deposits_margin(self, kuru_client, mock_blockchain):
        """Client should deposit margin to Kuru contract."""
        # Use valid USDC testnet address
        usdc_address = "0x9A29e9Bab1f0B599d1c6C39b60a79596b3875f56"
        tx_hash = kuru_client.deposit_margin(
            token=usdc_address,
            amount=Decimal("100.0"),
        )

        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66
        # ERC20 deposits require 2 transactions: approve + deposit
        assert mock_blockchain.send_transaction.call_count == 2

        # Verify approve transaction was sent to token contract
        first_call = mock_blockchain.send_transaction.call_args_list[0]
        assert first_call[1]["to"] == usdc_address
        assert first_call[1]["data"] != "0x"  # Should have encoded data

        # Verify deposit transaction was sent to margin account
        second_call = mock_blockchain.send_transaction.call_args_list[1]
        assert second_call[1]["to"] == kuru_client.margin_account_address
        assert second_call[1]["data"] != "0x"  # Should have encoded data

    def test_kuru_client_deposits_native_token(self, kuru_client, mock_blockchain):
        """Client should deposit native token (ETH/MON) to margin."""
        tx_hash = kuru_client.deposit_margin(
            token="0x0000000000000000000000000000000000000000",  # Native token
            amount=Decimal("1.0"),
        )

        assert tx_hash.startswith("0x")
        # Should send only one transaction (no approve needed for native)
        assert mock_blockchain.send_transaction.call_count == 1

        # Should send transaction with value
        call_args = mock_blockchain.send_transaction.call_args
        assert call_args[1]["value"] > 0
        assert call_args[1]["to"] == kuru_client.margin_account_address
        assert call_args[1]["data"] != "0x"  # Should have encoded deposit data

    def test_kuru_client_checks_balance_before_deposit(self, kuru_client, mock_blockchain):
        """Client should check balance before deposit."""
        mock_blockchain.get_token_balance.return_value = Decimal("50.0")

        usdc_address = "0x9A29e9Bab1f0B599d1c6C39b60a79596b3875f56"
        with pytest.raises(InsufficientBalanceError):
            kuru_client.deposit_margin(
                token=usdc_address,
                amount=Decimal("100.0"),
            )

    def test_kuru_client_approves_erc20_before_deposit(self, kuru_client, mock_blockchain):
        """Client should approve ERC20 tokens before deposit."""
        usdc_address = "0x9A29e9Bab1f0B599d1c6C39b60a79596b3875f56"
        kuru_client.deposit_margin(
            token=usdc_address,
            amount=Decimal("100.0"),
        )

        # Should call send_transaction twice (approve + deposit)
        assert mock_blockchain.send_transaction.call_count == 2

        # First call should be approve to token contract
        first_call = mock_blockchain.send_transaction.call_args_list[0]
        assert first_call[1]["to"] == usdc_address

        # Second call should be deposit to margin account
        second_call = mock_blockchain.send_transaction.call_args_list[1]
        assert second_call[1]["to"] == kuru_client.margin_account_address


class TestKuruClientLimitOrders:
    """Test Kuru limit order placement."""

    def test_kuru_client_places_limit_order(self, kuru_client, mock_blockchain):
        """Client should place GTC limit order."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            order_id = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("2000.0"),
                size=Decimal("1.0"),
                post_only=True,
            )

            assert order_id is not None
            assert isinstance(order_id, str)
            mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_places_sell_limit_order(self, kuru_client, mock_blockchain):
        """Client should place sell limit order."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            order_id = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.SELL,
                price=Decimal("2100.0"),
                size=Decimal("0.5"),
                post_only=False,
            )

            assert order_id is not None
            mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_validates_limit_order_price(self, kuru_client, mock_blockchain):
        """Client should validate limit order price is positive."""
        with pytest.raises(ValueError):
            kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("0"),
                size=Decimal("1.0"),
            )

    def test_kuru_client_validates_limit_order_size(self, kuru_client, mock_blockchain):
        """Client should validate limit order size is positive."""
        with pytest.raises(ValueError):
            kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("2000.0"),
                size=Decimal("0"),
            )

    def test_kuru_client_validates_market_exists(self, kuru_client, mock_blockchain):
        """Client should validate market exists."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.side_effect = InvalidMarketError("Market not found")

            with pytest.raises(InvalidMarketError):
                kuru_client.place_limit_order(
                    market="INVALID-MARKET",
                    side=OrderSide.BUY,
                    price=Decimal("2000.0"),
                    size=Decimal("1.0"),
                )

    def test_kuru_client_places_limit_order_async(self, kuru_client, mock_blockchain):
        """Client should place limit order asynchronously and return tx_hash."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            tx_hash = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("2000.0"),
                size=Decimal("1.0"),
                post_only=True,
                async_execution=True,
            )

            # Should return tx_hash
            assert tx_hash == mock_blockchain.send_transaction.return_value
            assert tx_hash.startswith("0x")
            assert len(tx_hash) == 66

            # Should not wait for receipt
            mock_blockchain.wait_for_transaction_receipt.assert_not_called()
            mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_places_limit_order_sync(self, kuru_client, mock_blockchain):
        """Client should place limit order synchronously and return order_id."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            order_id = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("2000.0"),
                size=Decimal("1.0"),
                post_only=True,
                async_execution=False,
            )

            # Should wait for receipt and return order_id
            assert order_id is not None
            mock_blockchain.send_transaction.assert_called_once()
            mock_blockchain.wait_for_transaction_receipt.assert_called_once()

    def test_kuru_client_normalizes_price_with_tick_round_down(self, kuru_client, mock_blockchain):
        """Client should normalize price down to tick size when requested."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            # Price not aligned to tick size
            order_id = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("2000.123"),  # Will be normalized to 2000.12
                size=Decimal("1.0"),
                tick_normalization="round_down",
            )

            assert order_id is not None
            mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_normalizes_price_with_tick_round_up(self, kuru_client, mock_blockchain):
        """Client should normalize price up to tick size when requested."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            # Price not aligned to tick size
            order_id = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("2000.123"),  # Will be normalized to 2000.13
                size=Decimal("1.0"),
                tick_normalization="round_up",
            )

            assert order_id is not None
            mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_does_not_normalize_when_set_to_none(self, kuru_client, mock_blockchain):
        """Client should not normalize price when tick_normalization is none."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            # Price aligned to tick size - should work fine
            order_id = kuru_client.place_limit_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                price=Decimal("2000.10"),
                size=Decimal("1.0"),
                tick_normalization="none",  # Default behavior
            )

            assert order_id is not None
            mock_blockchain.send_transaction.assert_called_once()


class TestKuruClientMarketOrders:
    """Test Kuru market order placement."""

    def test_kuru_client_places_market_order(self, kuru_client, mock_blockchain):
        """Client should place IOC market order."""
        with (
            patch.object(kuru_client, "get_market_params") as mock_get_market,
            patch.object(kuru_client, "get_best_price") as mock_get_best_price,
        ):
            mock_get_market.return_value = create_test_market_params()
            mock_get_best_price.return_value = Decimal("2000.0")

            order_id = kuru_client.place_market_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                size=Decimal("1.0"),
            )

            assert order_id is not None
            assert isinstance(order_id, str)
            mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_places_market_sell_order(self, kuru_client, mock_blockchain):
        """Client should place market sell order."""
        with (
            patch.object(kuru_client, "get_market_params") as mock_get_market,
            patch.object(kuru_client, "get_best_price") as mock_get_best_price,
        ):
            mock_get_market.return_value = create_test_market_params()
            mock_get_best_price.return_value = Decimal("2000.0")

            order_id = kuru_client.place_market_order(
                market="ETH-USDC",
                side=OrderSide.SELL,
                size=Decimal("0.5"),
                slippage=Decimal("0.01"),  # 1% slippage
            )

            assert order_id is not None
            mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_validates_market_order_size(self, kuru_client, mock_blockchain):
        """Client should validate market order size is positive."""
        with pytest.raises(ValueError):
            kuru_client.place_market_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                size=Decimal("-1.0"),
            )

    def test_kuru_client_places_market_order_async(self, kuru_client, mock_blockchain):
        """Client should place market order asynchronously and return tx_hash."""
        with (
            patch.object(kuru_client, "get_market_params") as mock_get_market,
            patch.object(kuru_client, "get_best_price") as mock_get_best_price,
        ):
            mock_get_market.return_value = create_test_market_params()
            mock_get_best_price.return_value = Decimal("2000.0")

            tx_hash = kuru_client.place_market_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                size=Decimal("1.0"),
                async_execution=True,
            )

            # Should return tx_hash
            assert tx_hash == mock_blockchain.send_transaction.return_value
            assert tx_hash.startswith("0x")
            assert len(tx_hash) == 66

            # Should not wait for receipt
            mock_blockchain.wait_for_transaction_receipt.assert_not_called()

    def test_kuru_client_places_market_order_with_fill_or_kill(self, kuru_client, mock_blockchain):
        """Client should support fill-or-kill market orders."""
        with (
            patch.object(kuru_client, "get_market_params") as mock_get_market,
            patch.object(kuru_client, "get_best_price") as mock_get_best_price,
        ):
            mock_get_market.return_value = create_test_market_params()
            mock_get_best_price.return_value = Decimal("2000.0")

            order_id = kuru_client.place_market_order(
                market="ETH-USDC",
                side=OrderSide.BUY,
                size=Decimal("1.0"),
                fill_or_kill=True,
            )

            assert order_id is not None
            # Verify transaction was sent
            mock_blockchain.send_transaction.assert_called_once()


class TestKuruClientOrderCancellation:
    """Test Kuru order cancellation."""

    def test_kuru_client_cancels_order(self, kuru_client, mock_blockchain):
        """Client should cancel order by ID."""
        tx_hash = kuru_client.cancel_order(order_id="order_123456")

        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66
        mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_cancels_multiple_orders(self, kuru_client, mock_blockchain):
        """Client should cancel multiple orders in batch."""
        order_ids = ["order_001", "order_002", "order_003"]
        tx_hash = kuru_client.cancel_orders(order_ids)

        assert tx_hash.startswith("0x")
        mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_validates_order_id_format(self, kuru_client, mock_blockchain):
        """Client should validate order ID format."""
        with pytest.raises(ValueError):
            kuru_client.cancel_order(order_id="")


class TestKuruClientBatchUpdate:
    """Test Kuru batch update orders functionality."""

    def test_kuru_client_batch_updates_orders(self, kuru_client, mock_blockchain):
        """Client should atomically cancel and place orders."""
        # Mock getMarketParams call
        mock_blockchain.call_contract_function.return_value = (
            1000,
            1000000,  # price/size precision
            "0x0000000000000000000000000000000000000001",
            18,
            "0x0000000000000000000000000000000000000002",
            6,
            1,
            1000,
            1000000000,
            50,
            20,
        )

        buy_orders = [(Decimal("2000.0"), Decimal("1.0")), (Decimal("1999.0"), Decimal("0.5"))]
        sell_orders = [(Decimal("2001.0"), Decimal("0.8"))]
        cancel_order_ids = ["order_001", "order_002"]

        tx_hash = kuru_client.batch_update_orders(
            market="ETH-USDC",
            buy_orders=buy_orders,
            sell_orders=sell_orders,
            cancel_order_ids=cancel_order_ids,
            post_only=True,
        )

        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66
        mock_blockchain.send_transaction.assert_called_once()

    def test_kuru_client_batch_update_async_mode(self, kuru_client, mock_blockchain):
        """Client should support async execution for batch updates."""
        # Mock getMarketParams call
        mock_blockchain.call_contract_function.return_value = (
            1000,
            1000000,
            "0x0000000000000000000000000000000000000001",
            18,
            "0x0000000000000000000000000000000000000002",
            6,
            1,
            1000,
            1000000000,
            50,
            20,
        )

        buy_orders = [(Decimal("2000.0"), Decimal("1.0"))]
        sell_orders = []
        cancel_order_ids = []

        tx_hash = kuru_client.batch_update_orders(
            market="ETH-USDC",
            buy_orders=buy_orders,
            sell_orders=sell_orders,
            cancel_order_ids=cancel_order_ids,
            async_execution=True,
        )

        assert tx_hash.startswith("0x")
        # Should not wait for receipt in async mode
        mock_blockchain.wait_for_transaction_receipt.assert_not_called()

    def test_kuru_client_batch_update_with_empty_lists(self, kuru_client, mock_blockchain):
        """Client should handle empty buy/sell lists."""
        # Mock getMarketParams call
        mock_blockchain.call_contract_function.return_value = (
            1000,
            1000000,
            "0x0000000000000000000000000000000000000001",
            18,
            "0x0000000000000000000000000000000000000002",
            6,
            1,
            1000,
            1000000000,
            50,
            20,
        )

        tx_hash = kuru_client.batch_update_orders(
            market="ETH-USDC", buy_orders=[], sell_orders=[], cancel_order_ids=["order_001"]
        )

        assert tx_hash.startswith("0x")
        mock_blockchain.send_transaction.assert_called_once()


class TestKuruClientMarketParams:
    """Test Kuru market parameter fetching."""

    def test_kuru_client_fetches_market_params(self, kuru_client, mock_blockchain):
        """Client should fetch market parameters from contract."""
        # Mock contract call return values (11 values from getMarketParams)
        mock_blockchain.call_contract_function.return_value = (
            1000,  # pricePrecision (uint32)
            1000000,  # sizePrecision (uint96)
            "0x0000000000000000000000000000000000000001",  # baseAsset
            18,  # baseAssetDecimals
            "0x0000000000000000000000000000000000000002",  # quoteAsset
            6,  # quoteAssetDecimals
            1,  # tickSize (uint32)
            1000,  # minSize (uint96)
            1000000000,  # maxSize (uint96)
            50,  # takerFeeBps (0.5%)
            20,  # makerFeeBps (0.2%)
        )

        params = kuru_client.get_market_params("ETH-USDC")

        # Should return a MarketParams object
        assert isinstance(params, MarketParams)
        assert params.price_precision == 1000
        assert params.size_precision == 1000000
        assert params.base_asset == "0x0000000000000000000000000000000000000001"
        assert params.base_asset_decimals == 18
        assert params.quote_asset == "0x0000000000000000000000000000000000000002"
        assert params.quote_asset_decimals == 6
        assert isinstance(params.tick_size, Decimal)
        assert isinstance(params.min_size, Decimal)
        assert isinstance(params.max_size, Decimal)
        assert params.taker_fee_bps == 50
        assert params.maker_fee_bps == 20

    def test_kuru_client_handles_contract_error(self, kuru_client, mock_blockchain):
        """Client should raise error when contract call fails."""
        mock_blockchain.call_contract_function.side_effect = Exception("Contract call failed")

        with pytest.raises(BlockchainConnectionError):
            kuru_client.get_market_params("ETH-USDC")

    def test_kuru_client_caches_market_params(self, kuru_client, mock_blockchain):
        """Client should cache market parameters."""
        mock_blockchain.call_contract_function.return_value = (
            1000,
            1000000,
            "0x0000000000000000000000000000000000000001",
            18,
            "0x0000000000000000000000000000000000000002",
            6,
            1,
            1000,
            1000000000,
            50,
            20,
        )

        # Fetch twice
        kuru_client.get_market_params("ETH-USDC")
        kuru_client.get_market_params("ETH-USDC")

        # Should only call contract once (cached)
        assert mock_blockchain.call_contract_function.call_count == 1


class TestKuruClientVaultParams:
    """Test Kuru vault parameter fetching."""

    def test_kuru_client_fetches_vault_params(self, kuru_client, mock_blockchain):
        """Client should fetch vault parameters from contract."""

        # Mock both getMarketParams() and getVaultParams() calls
        def mock_contract_call(contract_address, function_name, abi, args):
            if function_name == "getMarketParams":
                return (
                    1000,
                    1000000,  # price/size precision
                    "0x0000000000000000000000000000000000000001",
                    18,  # base asset
                    "0x0000000000000000000000000000000000000002",
                    6,  # quote asset
                    1,
                    1000,
                    1000000000,
                    50,
                    20,  # tick/min/max size, fees
                )
            elif function_name == "getVaultParams":
                return (
                    "0x0000000000000000000000000000000000000003",  # vaultAddress
                    1000000000000000000,  # baseBalance (1e18)
                    5000000,  # vaultAskOrderSize
                    5000000000,  # quoteBalance (5000 USDC with 6 decimals)
                    5000000,  # vaultBidOrderSize
                    2100,  # vaultAskPrice
                    2000,  # vaultBidPrice
                    10,  # spread
                )

        mock_blockchain.call_contract_function.side_effect = mock_contract_call

        params = kuru_client.get_vault_params("ETH-USDC")

        assert params["vault_address"] == "0x0000000000000000000000000000000000000003"
        assert isinstance(params["base_balance"], Decimal)
        assert isinstance(params["quote_balance"], Decimal)
        assert isinstance(params["vault_ask_order_size"], Decimal)
        assert isinstance(params["vault_bid_order_size"], Decimal)
        assert isinstance(params["vault_ask_price"], Decimal)
        assert isinstance(params["vault_bid_price"], Decimal)
        assert isinstance(params["spread"], Decimal)

    def test_kuru_client_handles_vault_params_error(self, kuru_client, mock_blockchain):
        """Client should raise error when vault params call fails."""
        mock_blockchain.call_contract_function.side_effect = Exception("Contract call failed")

        with pytest.raises(BlockchainConnectionError):
            kuru_client.get_vault_params("ETH-USDC")


class TestKuruClientOrderbook:
    """Test Kuru orderbook functionality."""

    def test_kuru_client_fetches_orderbook_from_contract(self, kuru_client, mock_blockchain):
        """Client should fetch orderbook data from contract."""
        # Mock getL2Book() returning encoded bytes
        # For simplicity, we'll mock it returning an empty bytes object
        # Real implementation would need to parse the contract's encoding format
        mock_blockchain.call_contract_function.return_value = b""

        orderbook = kuru_client.get_orderbook("ETH-USDC")

        assert "bids" in orderbook
        assert "asks" in orderbook
        # Contract call should have been made
        mock_blockchain.call_contract_function.assert_called_once()

    def test_kuru_client_fetches_best_prices_from_contract(self, kuru_client, mock_blockchain):
        """Client should fetch best bid/ask from contract."""
        # Mock bestBidAsk() returning (bestBid, bestAsk) as uint256
        mock_blockchain.call_contract_function.return_value = (
            2000000000,  # best bid (scaled)
            2001000000,  # best ask (scaled)
        )

        orderbook = kuru_client.get_orderbook("ETH-USDC")

        assert "bids" in orderbook
        assert "asks" in orderbook
        # Should have at least top of book
        if orderbook["bids"]:
            assert isinstance(orderbook["bids"][0]["price"], Decimal)
        if orderbook["asks"]:
            assert isinstance(orderbook["asks"][0]["price"], Decimal)

    def test_kuru_client_returns_empty_orderbook_on_error(self, kuru_client, mock_blockchain):
        """Client should return empty orderbook on contract call failure."""
        mock_blockchain.call_contract_function.side_effect = Exception("Contract call failed")

        orderbook = kuru_client.get_orderbook("ETH-USDC")

        assert orderbook == {"bids": [], "asks": []}

    @patch.object(KuruClient, "get_orderbook")
    def test_kuru_client_gets_best_bid_price(self, mock_orderbook, kuru_client):
        """Client should get best bid price for sell orders."""
        mock_orderbook.return_value = {
            "bids": [
                {"price": Decimal("2000.0"), "size": Decimal("1.5")},
                {"price": Decimal("1999.0"), "size": Decimal("2.0")},
            ],
            "asks": [
                {"price": Decimal("2001.0"), "size": Decimal("1.0")},
            ],
        }

        best_price = kuru_client.get_best_price("ETH-USDC", OrderSide.SELL)

        assert best_price == Decimal("2000.0")

    @patch.object(KuruClient, "get_orderbook")
    def test_kuru_client_gets_best_ask_price(self, mock_orderbook, kuru_client):
        """Client should get best ask price for buy orders."""
        mock_orderbook.return_value = {
            "bids": [
                {"price": Decimal("2000.0"), "size": Decimal("1.5")},
            ],
            "asks": [
                {"price": Decimal("2001.0"), "size": Decimal("1.0")},
                {"price": Decimal("2002.0"), "size": Decimal("0.5")},
            ],
        }

        best_price = kuru_client.get_best_price("ETH-USDC", OrderSide.BUY)

        assert best_price == Decimal("2001.0")

    @patch.object(KuruClient, "get_orderbook")
    def test_kuru_client_returns_none_for_empty_orderbook(self, mock_orderbook, kuru_client):
        """Client should return None when orderbook is empty."""
        mock_orderbook.return_value = {"bids": [], "asks": []}

        best_price_buy = kuru_client.get_best_price("ETH-USDC", OrderSide.BUY)
        best_price_sell = kuru_client.get_best_price("ETH-USDC", OrderSide.SELL)

        assert best_price_buy is None
        assert best_price_sell is None

    @patch.object(KuruClient, "get_orderbook")
    def test_kuru_client_handles_best_price_error(self, mock_orderbook, kuru_client):
        """Client should return None on error fetching best price."""
        mock_orderbook.side_effect = Exception("API error")

        best_price = kuru_client.get_best_price("ETH-USDC", OrderSide.BUY)

        assert best_price is None


class TestKuruClientCostEstimation:
    """Test Kuru cost estimation."""

    def test_kuru_client_estimates_trade_cost(self, kuru_client, mock_blockchain):
        """Client should estimate trade cost including fees."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params(taker_fee_bps=50)

            cost = kuru_client.estimate_cost(
                market="ETH-USDC",
                side=OrderSide.BUY,
                size=Decimal("1.0"),
                price=Decimal("2000.0"),
            )

            assert isinstance(cost, Decimal)
            assert cost > Decimal("2000.0")  # Should include fees

    @patch.object(KuruClient, "get_best_price")
    @patch.object(KuruClient, "get_market_params")
    def test_kuru_client_estimates_cost_from_orderbook(
        self, mock_get_market, mock_get_best_price, kuru_client
    ):
        """Client should fetch price from orderbook when not provided."""
        mock_get_market.return_value = create_test_market_params(taker_fee_bps=50)
        mock_get_best_price.return_value = Decimal("2001.0")

        cost = kuru_client.estimate_cost(
            market="ETH-USDC",
            side=OrderSide.BUY,
            size=Decimal("1.0"),
            price=None,  # Should fetch from orderbook
        )

        # Verify get_best_price was called
        mock_get_best_price.assert_called_once_with("ETH-USDC", OrderSide.BUY)

        # Cost should be based on orderbook price
        assert isinstance(cost, Decimal)
        expected = Decimal("2001.0") * Decimal("1.0") * (Decimal("1") + Decimal("0.005"))
        assert cost == expected

    @patch.object(KuruClient, "get_market_params")
    @patch.object(KuruClient, "get_best_price")
    def test_kuru_client_raises_error_for_empty_orderbook(
        self, mock_get_best_price, mock_get_market, kuru_client
    ):
        """Client should raise error when orderbook is empty."""
        mock_get_market.return_value = create_test_market_params(taker_fee_bps=50)
        mock_get_best_price.return_value = None

        with pytest.raises(OrderExecutionError, match="orderbook empty"):
            kuru_client.estimate_cost(
                market="ETH-USDC",
                side=OrderSide.BUY,
                size=Decimal("1.0"),
                price=None,
            )

    def test_kuru_client_estimates_market_order_cost(self, kuru_client):
        """Client should estimate market order cost with slippage."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params(taker_fee_bps=50)

            cost = kuru_client.estimate_market_order_cost(
                market="ETH-USDC",
                side=OrderSide.BUY,
                size=Decimal("1.0"),
                expected_price=Decimal("2000.0"),
                slippage=Decimal("0.01"),  # 1%
            )

            assert isinstance(cost, Decimal)
            # Should include slippage and fees
            assert cost > Decimal("2000.0")


class TestKuruClientErrorHandling:
    """Test Kuru client error handling."""

    def test_kuru_client_handles_transaction_failure(self, kuru_client, mock_blockchain):
        """Client should handle transaction failures."""
        from src.kuru_copytr_bot.core.exceptions import TransactionFailedError

        mock_blockchain.send_transaction.side_effect = TransactionFailedError("Transaction failed")

        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params()

            with pytest.raises(OrderExecutionError):
                kuru_client.place_limit_order(
                    market="ETH-USDC",
                    side=OrderSide.BUY,
                    price=Decimal("2000.0"),
                    size=Decimal("1.0"),
                )

    def test_kuru_client_handles_network_error(self, kuru_client):
        """Client should handle network errors gracefully."""
        from src.kuru_copytr_bot.core.exceptions import BlockchainConnectionError

        with patch("requests.get") as mock_get:
            mock_get.side_effect = BlockchainConnectionError("Network error")

            with pytest.raises(BlockchainConnectionError):
                kuru_client.get_market_params("ETH-USDC")

    def test_kuru_client_validates_minimum_order_size(self, kuru_client):
        """Client should enforce minimum order size."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params(min_size=Decimal("0.01"))

            with pytest.raises(ValueError):
                kuru_client.place_limit_order(
                    market="ETH-USDC",
                    side=OrderSide.BUY,
                    price=Decimal("2000.0"),
                    size=Decimal("0.001"),  # Below minimum
                )

    def test_kuru_client_validates_maximum_order_size(self, kuru_client):
        """Client should enforce maximum order size."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.return_value = create_test_market_params(
                min_size=Decimal("0.01"), max_size=Decimal("1000.0")
            )

            with pytest.raises(ValueError):
                kuru_client.place_limit_order(
                    market="ETH-USDC",
                    side=OrderSide.BUY,
                    price=Decimal("2000.0"),
                    size=Decimal("10000.0"),  # Above maximum
                )

    def test_kuru_client_rejects_inactive_market(self, kuru_client):
        """Client should reject orders on inactive markets."""
        with patch.object(kuru_client, "get_market_params") as mock_get_market:
            mock_get_market.side_effect = InvalidMarketError("Market not found or inactive")

            with pytest.raises(InvalidMarketError):
                kuru_client.place_limit_order(
                    market="INACTIVE-MARKET",
                    side=OrderSide.BUY,
                    price=Decimal("2000.0"),
                    size=Decimal("1.0"),
                )


class TestKuruClientBalance:
    """Tests for balance queries."""

    def test_kuru_client_gets_native_balance(self, kuru_client, mock_blockchain):
        """Client should get native token balance."""
        mock_blockchain.get_balance.return_value = Decimal("100.5")
        mock_blockchain.wallet_address = "0x1234567890123456789012345678901234567890"

        balance = kuru_client.get_balance()

        assert balance == Decimal("100.5")
        mock_blockchain.get_balance.assert_called_once_with(
            "0x1234567890123456789012345678901234567890"
        )

    def test_kuru_client_gets_token_balance(self, kuru_client, mock_blockchain):
        """Client should get ERC20 token balance."""
        token_address = "0xUSDC000000000000000000000000000000000000"
        mock_blockchain.get_token_balance.return_value = Decimal("500.25")
        mock_blockchain.wallet_address = "0x1234567890123456789012345678901234567890"

        balance = kuru_client.get_balance(token=token_address)

        assert balance == Decimal("500.25")
        mock_blockchain.get_token_balance.assert_called_once_with(
            token_address=token_address, wallet_address="0x1234567890123456789012345678901234567890"
        )

    def test_kuru_client_handles_balance_check_failure(self, kuru_client, mock_blockchain):
        """Client should handle balance check failures."""
        mock_blockchain.get_balance.side_effect = Exception("Connection error")

        with pytest.raises(BlockchainConnectionError, match="Failed to get balance"):
            kuru_client.get_balance()
