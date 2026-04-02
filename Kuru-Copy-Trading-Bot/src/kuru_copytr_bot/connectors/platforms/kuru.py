"""Kuru Exchange Python SDK wrapper."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar, Literal

from web3 import Web3

from src.kuru_copytr_bot.config.constants import get_kuru_margin_account_address
from src.kuru_copytr_bot.core.enums import OrderSide
from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientBalanceError,
    InvalidMarketError,
    OrderExecutionError,
    TransactionFailedError,
)
from src.kuru_copytr_bot.core.interfaces import BlockchainConnector
from src.kuru_copytr_bot.models.market import MarketParams
from src.kuru_copytr_bot.models.orderbook import L2Book, PriceLevel
from src.kuru_copytr_bot.utils.logger import get_logger
from src.kuru_copytr_bot.utils.price import normalize_to_tick

logger = get_logger(__name__)


class KuruClient:
    """Python wrapper for Kuru Exchange SDK."""

    # Standard ERC20 ABI for approve
    ERC20_APPROVE_ABI: ClassVar[list[dict[str, Any]]] = [
        {
            "constant": False,
            "inputs": [
                {"name": "spender", "type": "address"},
                {"name": "value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function",
        }
    ]

    def __init__(
        self,
        blockchain: BlockchainConnector,
        contract_address: str,
        network: str = "testnet",
        strict_api_errors: bool = False,
    ):
        """Initialize Kuru client.

        Args:
            blockchain: Blockchain connector instance
            contract_address: Kuru contract address (OrderBook)
            network: Network to use ('testnet' or 'mainnet')
            strict_api_errors: If True, raise exceptions on API errors. If False, return empty results and log warnings.

        Raises:
            ValueError: If contract address is invalid
        """
        self.blockchain = blockchain
        self.contract_address = contract_address
        self.network = network
        self.margin_account_address = get_kuru_margin_account_address(network)
        self.strict_api_errors = strict_api_errors

        # Validate contract address
        if not self._is_valid_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        # Load ABIs
        self._load_abis()

        # Create Web3 instance for encoding (no provider needed)
        self.w3 = Web3()

        # Convert addresses to checksum format
        margin_checksum = Web3.to_checksum_address(self.margin_account_address)
        orderbook_checksum = Web3.to_checksum_address(self.contract_address)

        # Create Web3 contract instances for encoding
        self.margin_account_contract = self.w3.eth.contract(
            address=margin_checksum, abi=self.margin_account_abi
        )
        self.orderbook_contract = self.w3.eth.contract(
            address=orderbook_checksum, abi=self.orderbook_abi
        )

        # Cache for market parameters
        self._market_cache: dict[str, dict[str, Any]] = {}

    def _load_abis(self) -> None:
        """Load contract ABIs from JSON files."""
        abi_dir = Path(__file__).parent.parent.parent / "config" / "abis"

        # Load MarginAccount ABI
        margin_abi_path = abi_dir / "MarginAccount.json"
        with open(margin_abi_path) as f:
            self.margin_account_abi = json.load(f)

        # Load OrderBook ABI
        orderbook_abi_path = abi_dir / "OrderBook.json"
        with open(orderbook_abi_path) as f:
            self.orderbook_abi = json.load(f)

    def _encode_price(self, price: Decimal, price_precision: int = 1000000) -> int:
        """Encode price to uint32 format.

        Args:
            price: Decimal price
            price_precision: Price precision multiplier (e.g., 10000000 for 1e7)

        Returns:
            int: Encoded price as uint32
        """
        return int(price * Decimal(price_precision))

    def _encode_size(self, size: Decimal, size_precision: int = 10**18) -> int:
        """Encode size to uint96 format.

        Args:
            size: Decimal size
            size_precision: Size precision multiplier (e.g., 100000000000 for 1e11)

        Returns:
            int: Encoded size as uint96
        """
        return int(size * Decimal(size_precision))

    def deposit_margin(self, token: str, amount: Decimal) -> str:
        """Deposit tokens to Kuru margin account.

        Args:
            token: Token contract address (0x0...0 for native token)
            amount: Amount to deposit

        Returns:
            str: Transaction hash

        Raises:
            InsufficientBalanceError: If insufficient balance
            TransactionFailedError: If transaction fails
        """
        # Check balance
        if token == "0x" + "0" * 40:  # Native token
            balance = self.blockchain.get_balance(self.blockchain.wallet_address)
            if balance < amount:
                raise InsufficientBalanceError(f"Insufficient balance: {balance} < {amount}")

            # Send native token with deposit function call
            value_wei = int(amount * Decimal(10**18))

            # Encode deposit function call: deposit(user, token, amount)
            deposit_data = self.margin_account_contract.functions.deposit(
                Web3.to_checksum_address(self.blockchain.wallet_address),  # _user
                Web3.to_checksum_address(token),  # _token (native token address)
                value_wei,  # _amount
            )._encode_transaction_data()

            try:
                tx_hash = self.blockchain.send_transaction(
                    to=self.margin_account_address,
                    data=deposit_data,
                    value=value_wei,
                )
                return tx_hash
            except Exception as e:
                raise OrderExecutionError(f"Margin deposit failed: {e}") from e
        else:
            # ERC20 token
            balance = self.blockchain.get_token_balance(self.blockchain.wallet_address, token)
            if balance < amount:
                raise InsufficientBalanceError(
                    f"Insufficient {token} balance: {balance} < {amount}"
                )

            # Approve token
            try:
                self._approve_token(token, amount)
            except Exception as e:
                raise OrderExecutionError(f"Token approval failed: {e}") from e

            # Deposit ERC20 token
            amount_wei = int(amount * Decimal(10**18))

            # Encode deposit function call: deposit(user, token, amount)
            deposit_data = self.margin_account_contract.functions.deposit(
                Web3.to_checksum_address(self.blockchain.wallet_address),  # _user
                Web3.to_checksum_address(token),  # _token (ERC20 address)
                amount_wei,  # _amount
            )._encode_transaction_data()

            try:
                tx_hash = self.blockchain.send_transaction(
                    to=self.margin_account_address,
                    data=deposit_data,
                )
                return tx_hash
            except Exception as e:
                raise OrderExecutionError(f"Margin deposit failed: {e}") from e

    def get_margin_balance(self, token: str | None = None, decimals: int = 18) -> Decimal:
        """Get margin account balance for a token.

        Args:
            token: Token address (None or 0x0...0 for native token)
            decimals: Token decimals (default: 18 for native, 6 for USDC)

        Returns:
            Decimal: Balance in token units

        Raises:
            BlockchainConnectionError: If contract call fails
            ValueError: If token address is invalid
        """
        if token is None or token == "0x0000000000000000000000000000000000000000":
            token_address = "0x0000000000000000000000000000000000000000"
        else:
            if not self._is_valid_address(token):
                raise ValueError(f"Invalid token address: {token}")
            token_address = token

        try:
            balance_wei = self.blockchain.call_contract_function(
                contract_address=self.margin_account_address,
                function_name="getBalance",
                abi=self.margin_account_abi,
                args=[self.blockchain.wallet_address, token_address],
            )

            return Decimal(balance_wei) / Decimal(10**decimals)

        except BlockchainConnectionError:
            raise
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to get margin balance: {e}") from e

    def get_wallet_balance(self) -> Decimal:
        """Get native token balance from wallet (not margin account).

        This is used for limit orders which pull funds directly from the wallet
        rather than from the margin account.

        Returns:
            Decimal: Balance in native token units (MON)

        Raises:
            BlockchainConnectionError: If balance query fails
        """
        try:
            return self.blockchain.get_balance(self.blockchain.wallet_address)
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to get wallet balance: {e}") from e

    def place_limit_order(
        self,
        market: str,
        side: OrderSide,
        price: Decimal,
        size: Decimal,
        post_only: bool = False,
        cloid: str | None = None,
        async_execution: bool = False,
        tick_normalization: Literal["round_up", "round_down", "none"] = "none",
    ) -> str:
        """Place a GTC limit order.

        Args:
            market: Market identifier (e.g., "ETH-USDC")
            side: Order side (BUY or SELL)
            price: Limit price
            size: Order size
            post_only: Post-only flag (maker-only)
            cloid: Optional client order ID for tracking (not sent to contract)
            async_execution: If True, return tx_hash immediately without waiting for confirmation.
                           If False (default), wait for confirmation and return order_id.
            tick_normalization: Price normalization mode:
                - "round_up": Round price up to next tick
                - "round_down": Round price down to previous tick
                - "none" (default): No normalization, reject if not aligned

        Returns:
            str: Transaction hash if async_execution=True, Order ID if async_execution=False

        Raises:
            ValueError: If validation fails or price not aligned to tick (when normalization is "none")
            InvalidMarketError: If market is invalid
            InsufficientBalanceError: If insufficient balance
            OrderExecutionError: If order fails

        Note:
            CLOID is for client-side tracking only and not stored on-chain.
            Use this to map bot orders to source trader orders.

            Async execution is useful when submitting multiple orders in parallel.
            Use wait_for_transaction() to manually wait for async transactions.

            Tick normalization ensures prices are aligned to the market's tick size.
            This prevents rejection due to invalid price precision.
        """
        # Validate parameters
        if price <= 0:
            raise ValueError("Price must be positive")
        if size <= 0:
            raise ValueError("Size must be positive")

        # Get and validate market parameters
        try:
            params = self.get_market_params(market)
        except Exception as e:
            raise InvalidMarketError(f"Failed to get market params: {e}") from e

        # Validate order size
        if size < params.min_size:
            raise ValueError(f"Order size {size} below minimum {params.min_size}")
        if size > params.max_size:
            raise ValueError(f"Order size {size} above maximum {params.max_size}")

        # Normalize price to tick size if requested
        if tick_normalization != "none":
            price = normalize_to_tick(price, params.tick_size, mode=tick_normalization)

        # Encode price and size using market-specific precision
        encoded_price = self._encode_price(price, price_precision=params.price_precision)
        encoded_size = self._encode_size(size, size_precision=params.size_precision)

        # Choose correct function based on side
        if side == OrderSide.BUY:
            order_data = self.orderbook_contract.functions.addBuyOrder(
                encoded_price,  # _price (uint32)
                encoded_size,  # size (uint96)
                post_only,  # _postOnly (bool)
            )._encode_transaction_data()
        else:  # SELL
            order_data = self.orderbook_contract.functions.addSellOrder(
                encoded_price,  # _price (uint32)
                encoded_size,  # size (uint96)
                post_only,  # _postOnly (bool)
            )._encode_transaction_data()

        # Place order via blockchain
        try:
            tx_hash = self.blockchain.send_transaction(
                to=market,  # Use market parameter (contract address) instead of hardcoded self.contract_address
                data=order_data,
            )

            # If async mode, return tx_hash immediately
            if async_execution:
                return tx_hash

            # Otherwise, wait for transaction receipt and extract order ID
            receipt = self.blockchain.wait_for_transaction_receipt(tx_hash)
            order_id = self._extract_order_id_from_receipt(receipt)

            return order_id

        except TransactionFailedError as e:
            raise OrderExecutionError(f"Failed to place limit order: {e}") from e
        except Exception as e:
            raise OrderExecutionError(f"Unexpected error placing order: {e}") from e

    def place_market_order(
        self,
        market: str,
        side: OrderSide,
        size: Decimal,
        slippage: Decimal | None = None,
        cloid: str | None = None,
        async_execution: bool = False,
        fill_or_kill: bool = False,
    ) -> str:
        """Place an IOC market order.

        Args:
            market: Market identifier
            side: Order side (BUY or SELL)
            size: Order size
            slippage: Maximum acceptable slippage
            cloid: Optional client order ID for tracking (not sent to contract)
            async_execution: If True, return tx_hash immediately without waiting for confirmation.
                           If False (default), wait for confirmation and return order_id.
            fill_or_kill: If True, order reverts if not fully filled. If False (default),
                         partial fills are accepted (IOC behavior).

        Returns:
            str: Transaction hash if async_execution=True, Order ID if async_execution=False

        Raises:
            ValueError: If validation fails
            InsufficientBalanceError: If insufficient balance
            OrderExecutionError: If order fails
        """
        # Validate parameters
        if size <= 0:
            raise ValueError("Size must be positive")

        # Get market parameters
        try:
            self.get_market_params(market)
        except Exception as e:
            raise InvalidMarketError(f"Failed to get market params: {e}") from e

        # Encode size
        encoded_size = self._encode_size(size)

        # Estimate minimum output for slippage protection
        min_amount_out = 0
        if slippage:
            # Fetch current market price from orderbook
            estimated_price = self.get_best_price(market, side)
            if estimated_price is None:
                logger.warning(
                    "Orderbook empty, using zero slippage protection",
                    market=market,
                )
                estimated_price = Decimal("0")

            if side == OrderSide.BUY:
                # For buy: min base asset received
                min_amount_out = int(size * (Decimal("1") - slippage) * Decimal(10**18))
            else:
                # For sell: min quote asset received
                min_amount_out = int(
                    size * estimated_price * (Decimal("1") - slippage) * Decimal(10**18)
                )

        # Choose correct function based on side
        if side == OrderSide.BUY:
            # For market buy: specify quote size (USDC to spend)
            order_data = self.orderbook_contract.functions.placeAndExecuteMarketBuy(
                encoded_size,  # _quoteSize (uint96)
                min_amount_out,  # _minAmountOut (uint256)
                True,  # _isMargin (use margin account)
                fill_or_kill,  # _isFillOrKill
            )._encode_transaction_data()
        else:  # SELL
            # For market sell: specify base size (asset to sell)
            order_data = self.orderbook_contract.functions.placeAndExecuteMarketSell(
                encoded_size,  # _size (uint96)
                min_amount_out,  # _minAmountOut (uint256)
                True,  # _isMargin (use margin account)
                fill_or_kill,  # _isFillOrKill
            )._encode_transaction_data()

        # Place order
        try:
            tx_hash = self.blockchain.send_transaction(
                to=market,  # Use market parameter (contract address) instead of hardcoded self.contract_address
                data=order_data,
            )

            # If async mode, return tx_hash immediately
            if async_execution:
                return tx_hash

            # Otherwise, wait for transaction receipt
            self.blockchain.wait_for_transaction_receipt(tx_hash)

            # Market orders execute immediately, return tx hash as order ID
            return tx_hash

        except TransactionFailedError as e:
            raise OrderExecutionError(f"Failed to place market order: {e}") from e
        except Exception as e:
            raise OrderExecutionError(f"Unexpected error placing market order: {e}") from e

    def cancel_order(self, order_id: str) -> str:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            str: Transaction hash

        Raises:
            ValueError: If order_id is invalid
            OrderExecutionError: If cancellation fails
        """
        if not order_id:
            raise ValueError("Order ID cannot be empty")

        # Delegate to cancel_orders for batch cancellation
        return self.cancel_orders([order_id])

    def cancel_orders(self, order_ids: list[str], market_address: str | None = None) -> str:
        """Cancel multiple orders in batch.

        Args:
            order_ids: List of order IDs to cancel
            market_address: Market contract address (optional, defaults to self.contract_address)

        Returns:
            str: Transaction hash

        Raises:
            OrderExecutionError: If batch cancellation fails
        """
        if not order_ids:
            raise ValueError("Order IDs list cannot be empty")

        # Use provided market address or fall back to default
        target_market = market_address if market_address else self.contract_address

        # DRY RUN MODE: If all order IDs are dry run transaction hashes, skip cancellation
        if all(order_id.startswith("0xdryrun") for order_id in order_ids):
            fake_tx_hash = (
                "0xdryrun_cancel_"
                + "_".join(order_id.replace("0xdryrun", "") for order_id in order_ids)[:50]
            )
            logger.info(
                "[DRY RUN] Order cancellation simulated (not sent to blockchain)",
                order_ids=order_ids,
                fake_tx_hash=fake_tx_hash,
            )
            return fake_tx_hash

        # Convert order IDs to uint40 format
        # Order IDs can be: numeric strings, hex strings, or "order_" prefixed strings
        order_ids_uint40 = []
        for order_id in order_ids:
            try:
                # Skip dry run order IDs in mixed scenarios
                if order_id.startswith("0xdryrun"):
                    logger.warning(
                        "Skipping dry run order ID in mixed cancellation",
                        order_id=order_id,
                    )
                    continue

                # Strip "order_" prefix if present
                if order_id.startswith("order_"):
                    order_id = order_id[6:]  # Remove "order_" prefix

                # Try parsing as int
                order_id_int = int(order_id, 16) if order_id.startswith("0x") else int(order_id)
                order_ids_uint40.append(order_id_int)
            except ValueError as e:
                raise ValueError(f"Invalid order ID format: {order_id}") from e

        # If all order IDs were dry run IDs, return early
        if not order_ids_uint40:
            logger.info("[DRY RUN] All order IDs were dry run IDs, skipping cancellation")
            return "0xdryrun_cancel_skipped"

        # Encode batch cancel transaction
        cancel_data = self.orderbook_contract.functions.batchCancelOrders(
            order_ids_uint40  # _orderIds (uint40[])
        )._encode_transaction_data()

        try:
            tx_hash = self.blockchain.send_transaction(
                to=target_market,  # Use market parameter instead of hardcoded self.contract_address
                data=cancel_data,
            )
            return tx_hash
        except Exception as e:
            raise OrderExecutionError(f"Failed to cancel orders: {e}") from e

    def batch_update_orders(
        self,
        market: str,
        buy_orders: list[tuple[Decimal, Decimal]],
        sell_orders: list[tuple[Decimal, Decimal]],
        cancel_order_ids: list[str],
        post_only: bool = False,
        async_execution: bool = False,
    ) -> str:
        """Atomically cancel orders and place new orders in a single transaction.

        This is useful for updating order placement strategies without intermediate
        states where orders are missing from the book.

        Args:
            market: Market identifier (contract address)
            buy_orders: List of (price, size) tuples for buy orders
            sell_orders: List of (price, size) tuples for sell orders
            cancel_order_ids: List of order IDs to cancel
            post_only: If True, orders will only be placed as maker orders
            async_execution: If True, return tx_hash without waiting for confirmation

        Returns:
            str: Transaction hash if async_execution=True, otherwise tx hash after confirmation

        Raises:
            ValueError: If order data is invalid
            OrderExecutionError: If batch update fails

        Example:
            ```python
            # Cancel old orders and place new ones atomically
            tx_hash = client.batch_update_orders(
                market="ETH-USDC",
                buy_orders=[(Decimal("2000"), Decimal("1.0"))],
                sell_orders=[(Decimal("2100"), Decimal("0.5"))],
                cancel_order_ids=["order_001", "order_002"],
                post_only=True
            )
            ```
        """
        # Get market params for encoding
        params = self.get_market_params(market)
        price_precision = params.price_precision
        size_precision = params.size_precision

        # Encode buy orders
        buy_prices = []
        buy_sizes = []
        for price, size in buy_orders:
            encoded_price = int(price * Decimal(price_precision))
            encoded_size = int(size * Decimal(size_precision))
            buy_prices.append(encoded_price)
            buy_sizes.append(encoded_size)

        # Encode sell orders
        sell_prices = []
        sell_sizes = []
        for price, size in sell_orders:
            encoded_price = int(price * Decimal(price_precision))
            encoded_size = int(size * Decimal(size_precision))
            sell_prices.append(encoded_price)
            sell_sizes.append(encoded_size)

        # Convert order IDs to uint40
        order_ids_uint40 = []
        for order_id in cancel_order_ids:
            try:
                # Strip "order_" prefix if present
                if order_id.startswith("order_"):
                    order_id = order_id[6:]

                # Parse as int
                order_id_int = int(order_id, 16) if order_id.startswith("0x") else int(order_id)
                order_ids_uint40.append(order_id_int)
            except ValueError as e:
                raise ValueError(f"Invalid order ID format: {order_id}") from e

        # Encode batch update transaction
        update_data = self.orderbook_contract.functions.batchUpdate(
            buy_prices,  # uint32[]
            buy_sizes,  # uint96[]
            sell_prices,  # uint32[]
            sell_sizes,  # uint96[]
            order_ids_uint40,  # uint40[]
            post_only,  # bool
        )._encode_transaction_data()

        try:
            tx_hash = self.blockchain.send_transaction(
                to=market,  # Use market parameter (contract address) instead of hardcoded self.contract_address
                data=update_data,
            )

            # If async mode, return tx_hash immediately
            if async_execution:
                return tx_hash

            # Otherwise, wait for confirmation
            self.blockchain.wait_for_transaction_receipt(tx_hash)
            return tx_hash

        except Exception as e:
            raise OrderExecutionError(f"Failed to batch update orders: {e}") from e

    def get_balance(self, token: str | None = None) -> Decimal:
        """Get balance from blockchain.

        Args:
            token: Token address to check (None for native token)

        Returns:
            Balance as Decimal

        Raises:
            BlockchainConnectionError: If balance check fails
        """
        try:
            if token is None:
                # Get native token balance
                return self.blockchain.get_balance(self.blockchain.wallet_address)
            else:
                # Get ERC20 token balance
                return self.blockchain.get_token_balance(
                    address=self.blockchain.wallet_address,
                    token_address=token,
                )
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to get balance: {e}") from e

    def get_market_params(self, market: str) -> MarketParams:
        """Get market parameters from contract.

        Args:
            market: Market identifier (contract address)

        Returns:
            MarketParams: Typed market parameters

        Raises:
            BlockchainConnectionError: If contract call fails
        """
        # Check cache first
        if market in self._market_cache:
            return self._market_cache[market]

        try:
            # Call contract getMarketParams() function
            # Returns: (pricePrecision, sizePrecision, baseAsset, baseAssetDecimals,
            #          quoteAsset, quoteAssetDecimals, tickSize, minSize, maxSize,
            #          takerFeeBps, makerFeeBps)
            result = self.blockchain.call_contract_function(
                contract_address=market,  # Use the market parameter, not self.contract_address
                function_name="getMarketParams",
                abi=self.orderbook_abi,
                args=[],
            )

            # Unpack 11 return values
            (
                price_precision,
                size_precision,
                base_asset,
                base_asset_decimals,
                quote_asset,
                quote_asset_decimals,
                tick_size,
                min_size,
                max_size,
                taker_fee_bps,
                maker_fee_bps,
            ) = result

            # Log raw values for debugging
            logger.debug(
                "Raw market parameters from contract",
                market=market,
                price_precision=price_precision,
                size_precision=size_precision,
                min_size_raw=min_size,
                max_size_raw=max_size,
                base_decimals=base_asset_decimals,
                quote_decimals=quote_asset_decimals,
            )

            # Convert to typed MarketParams model
            params = MarketParams(
                price_precision=price_precision,
                size_precision=size_precision,
                base_asset=base_asset,
                base_asset_decimals=base_asset_decimals,
                quote_asset=quote_asset,
                quote_asset_decimals=quote_asset_decimals,
                tick_size=Decimal(tick_size) / Decimal(price_precision),
                min_size=Decimal(min_size) / Decimal(size_precision),
                max_size=Decimal(max_size) / Decimal(size_precision),
                taker_fee_bps=taker_fee_bps,
                maker_fee_bps=maker_fee_bps,
            )

            logger.debug(
                "Converted market parameters",
                market=market,
                min_size=str(params.min_size),
                max_size=str(params.max_size),
                tick_size=str(params.tick_size),
            )

            # Cache the result
            self._market_cache[market] = params
            return params

        except Exception as e:
            raise BlockchainConnectionError(
                f"Failed to fetch market params from contract: {e}"
            ) from e

    def get_vault_params(self, market: str) -> dict[str, Any]:
        """Get AMM vault parameters from contract.

        Args:
            market: Market identifier (contract address)

        Returns:
            Dict with vault parameters including:
            - vault_address: Vault contract address
            - base_balance: Base asset balance in vault
            - vault_ask_order_size: Size of AMM ask orders
            - quote_balance: Quote asset balance in vault
            - vault_bid_order_size: Size of AMM bid orders
            - vault_ask_price: AMM ask price
            - vault_bid_price: AMM bid price
            - spread: AMM spread

        Raises:
            BlockchainConnectionError: If contract call fails
        """
        try:
            # Call contract getVaultParams() function
            # Returns: (vaultAddress, baseBalance, vaultAskOrderSize, quoteBalance,
            #          vaultBidOrderSize, vaultAskPrice, vaultBidPrice, spread)
            result = self.blockchain.call_contract_function(
                contract_address=market,  # Use the market parameter, not self.contract_address
                function_name="getVaultParams",
                abi=self.orderbook_abi,
                args=[],
            )

            # Unpack 8 return values
            (
                vault_address,
                base_balance,
                vault_ask_order_size,
                quote_balance,
                vault_bid_order_size,
                vault_ask_price,
                vault_bid_price,
                spread,
            ) = result

            # Get market params for scaling
            params = self.get_market_params(market)
            price_precision = params.price_precision
            size_precision = params.size_precision
            base_decimals = params.base_asset_decimals
            quote_decimals = params.quote_asset_decimals

            # Convert to decimal with proper scaling
            vault_params = {
                "vault_address": vault_address,
                "base_balance": Decimal(base_balance) / Decimal(10**base_decimals),
                "vault_ask_order_size": Decimal(vault_ask_order_size) / Decimal(size_precision),
                "quote_balance": Decimal(quote_balance) / Decimal(10**quote_decimals),
                "vault_bid_order_size": Decimal(vault_bid_order_size) / Decimal(size_precision),
                "vault_ask_price": Decimal(vault_ask_price) / Decimal(price_precision),
                "vault_bid_price": Decimal(vault_bid_price) / Decimal(price_precision),
                "spread": Decimal(spread) / Decimal(size_precision),
            }

            return vault_params

        except Exception as e:
            raise BlockchainConnectionError(
                f"Failed to fetch vault params from contract: {e}"
            ) from e

    def estimate_cost(
        self,
        market: str,
        side: OrderSide,
        size: Decimal,
        price: Decimal | None = None,
    ) -> Decimal:
        """Estimate trade cost including fees.

        Args:
            market: Market identifier
            side: Order side
            size: Order size
            price: Price (if None, uses estimated market price)

        Returns:
            Decimal: Estimated cost
        """
        params = self.get_market_params(market)

        # Use provided price or fetch best price from orderbook
        if price is None:
            price = self.get_best_price(market, side)
            if price is None:
                raise OrderExecutionError(
                    f"Cannot estimate cost: orderbook empty for market {market}"
                )

        # Calculate base cost
        cost = size * price

        # Add taker fee (assuming market order)
        # Convert taker_fee_bps to decimal (bps = basis points, 1 bps = 0.01%)
        taker_fee = Decimal(params.taker_fee_bps) / Decimal("10000")
        fee = cost * taker_fee

        return cost + fee

    def estimate_market_order_cost(
        self,
        market: str,
        side: OrderSide,
        size: Decimal,
        expected_price: Decimal,
        slippage: Decimal | None = None,
    ) -> Decimal:
        """Estimate market order cost with slippage.

        Args:
            market: Market identifier
            side: Order side
            size: Order size
            expected_price: Expected execution price
            slippage: Maximum slippage (e.g., 0.01 for 1%)

        Returns:
            Decimal: Estimated cost with slippage
        """
        params = self.get_market_params(market)

        # Calculate base cost
        cost = size * expected_price

        # Apply slippage if provided
        if slippage:
            cost = cost * (Decimal("1") + slippage)

        # Add taker fee
        # Convert taker_fee_bps to decimal (bps = basis points, 1 bps = 0.01%)
        taker_fee = Decimal(params.taker_fee_bps) / Decimal("10000")
        fee = cost * taker_fee

        return cost + fee

    def get_orderbook(self, market: str) -> dict[str, Any]:
        """Get current orderbook for a market from contract.

        Args:
            market: Market identifier (contract address)

        Returns:
            Dict containing orderbook data with 'bids' and 'asks' arrays
            Each entry: {"price": Decimal, "size": Decimal}
            Returns empty orderbook on error

        Note:
            This uses bestBidAsk() to get top of book. Full orderbook depth
            via getL2Book() requires parsing the bytes encoding format which
            is not documented in the public API spec.
        """
        try:
            # Call contract bestBidAsk() function to get top of book
            # Returns: (bestBid uint256, bestAsk uint256)
            result = self.blockchain.call_contract_function(
                contract_address=market,  # Use the market parameter, not self.contract_address
                function_name="bestBidAsk",
                abi=self.orderbook_abi,
                args=[],
            )

            best_bid, best_ask = result

            # Get market params for scaling
            params = self.get_market_params(market)
            price_precision = params.price_precision

            # Build orderbook with top of book only
            orderbook = {
                "bids": [],
                "asks": [],
            }

            # Add best bid if non-zero
            if best_bid > 0:
                orderbook["bids"].append(
                    {
                        "price": Decimal(best_bid) / Decimal(price_precision),
                        "size": Decimal("0"),  # Size not available from bestBidAsk()
                    }
                )

            # Add best ask if non-zero
            if best_ask > 0:
                orderbook["asks"].append(
                    {
                        "price": Decimal(best_ask) / Decimal(price_precision),
                        "size": Decimal("0"),  # Size not available from bestBidAsk()
                    }
                )

            return orderbook

        except Exception as e:
            logger.error("Failed to fetch orderbook from contract", market=market, error=str(e))
            return {"bids": [], "asks": []}

    def fetch_orderbook(self, market: str) -> L2Book:
        """Fetch orderbook as typed L2Book object.

        Args:
            market: Market identifier (contract address)

        Returns:
            L2Book: Typed orderbook with price levels

        Note:
            This uses bestBidAsk() to get top of book. Returns L2Book with
            block_num=0 (not available from this call) and size=0 for each level.
        """
        try:
            # Call contract bestBidAsk() function
            result = self.blockchain.call_contract_function(
                contract_address=market,  # Use the market parameter, not self.contract_address
                function_name="bestBidAsk",
                abi=self.orderbook_abi,
                args=[],
            )

            best_bid, best_ask = result

            # Get market params for scaling
            params = self.get_market_params(market)
            price_precision = params.price_precision

            # Build price levels
            bids = []
            asks = []

            # Add best bid if non-zero
            if best_bid > 0:
                bids.append(
                    PriceLevel(
                        price=Decimal(best_bid) / Decimal(price_precision),
                        size=Decimal("1"),  # Placeholder size since bestBidAsk() doesn't provide it
                    )
                )

            # Add best ask if non-zero
            if best_ask > 0:
                asks.append(
                    PriceLevel(
                        price=Decimal(best_ask) / Decimal(price_precision),
                        size=Decimal("1"),  # Placeholder size since bestBidAsk() doesn't provide it
                    )
                )

            return L2Book(
                block_num=0,  # Block number not available from bestBidAsk()
                bids=bids,
                asks=asks,
            )

        except Exception as e:
            logger.error("Failed to fetch orderbook from contract", market=market, error=str(e))
            # Return empty orderbook on error
            return L2Book(block_num=0, bids=[], asks=[])

    def get_best_bid(self, market: str) -> Decimal | None:
        """Get best bid price from orderbook.

        Args:
            market: Market identifier

        Returns:
            Decimal: Best bid price, or None if no bids
        """
        book = self.fetch_orderbook(market)
        return book.best_bid

    def get_best_ask(self, market: str) -> Decimal | None:
        """Get best ask price from orderbook.

        Args:
            market: Market identifier

        Returns:
            Decimal: Best ask price, or None if no asks
        """
        book = self.fetch_orderbook(market)
        return book.best_ask

    def get_best_price(self, market: str, side: OrderSide) -> Decimal | None:
        """Get best available price from orderbook.

        Args:
            market: Market identifier
            side: Order side (BUY uses asks, SELL uses bids)

        Returns:
            Best price as Decimal, or None if orderbook is empty
        """
        try:
            orderbook = self.get_orderbook(market)

            # For BUY orders, we take from asks (lowest ask price)
            # For SELL orders, we take from bids (highest bid price)
            if side == OrderSide.BUY:
                asks = orderbook.get("asks", [])
                if asks:
                    # Asks should be sorted low to high, take first
                    return asks[0]["price"]
            else:  # SELL
                bids = orderbook.get("bids", [])
                if bids:
                    # Bids should be sorted high to low, take first
                    return bids[0]["price"]

            logger.warning(
                "Empty orderbook, cannot determine best price", market=market, side=side.value
            )
            return None

        except Exception as e:
            logger.error(
                "Error fetching best price",
                market=market,
                side=side.value,
                error=str(e),
            )
            return None

    def _extract_order_id_from_receipt(self, receipt: dict[str, Any]) -> str:
        """Extract order ID from transaction receipt using Web3.py event decoding.

        Args:
            receipt: Transaction receipt

        Returns:
            str: Order ID

        Raises:
            OrderExecutionError: If order ID cannot be extracted
        """
        try:
            # Use Web3.py contract event decoding instead of manual byte parsing
            for log in receipt.get("logs", []):
                try:
                    # Try to decode as OrderCreated event
                    event = self.orderbook_contract.events.OrderCreated().process_log(log)
                    # Extract orderId from event args
                    order_id = event["args"]["orderId"]
                    return str(order_id)
                except Exception:
                    # Not an OrderCreated event, continue to next log
                    continue

            # If no OrderCreated event found, return transaction hash
            tx_hash = receipt["transactionHash"]
            if isinstance(tx_hash, bytes):
                return tx_hash.hex()
            return str(tx_hash)

        except Exception as e:
            raise OrderExecutionError(f"Failed to extract order ID from receipt: {e}") from e

    def _approve_token(self, token: str, amount: Decimal) -> str:
        """Approve ERC20 token for spending by MarginAccount contract.

        Args:
            token: Token contract address
            amount: Amount to approve

        Returns:
            str: Transaction hash
        """
        # Convert amount to wei
        amount_wei = int(amount * Decimal(10**18))

        # Create ERC20 contract instance for encoding
        token_checksum = Web3.to_checksum_address(token)
        erc20_contract = self.w3.eth.contract(address=token_checksum, abi=self.ERC20_APPROVE_ABI)

        # Encode approve function call: approve(spender, amount)
        approve_data = erc20_contract.functions.approve(
            Web3.to_checksum_address(self.margin_account_address),  # spender
            amount_wei,  # amount to approve
        )._encode_transaction_data()

        tx_hash = self.blockchain.send_transaction(
            to=token,
            data=approve_data,
        )
        return tx_hash

    def _is_valid_address(self, address: str) -> bool:
        """Validate Ethereum address format.

        Args:
            address: Address to validate

        Returns:
            bool: True if valid
        """
        if not isinstance(address, str):
            return False
        if not address.startswith("0x"):
            return False
        if len(address) != 42:
            return False
        try:
            int(address, 16)
            return True
        except ValueError:
            return False
