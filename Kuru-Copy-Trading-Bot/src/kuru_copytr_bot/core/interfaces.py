"""Core interfaces for the Kuru copy trading bot."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class BlockchainConnector(ABC):
    """Interface for blockchain interactions."""

    # Wallet address associated with this connector (implementations must set this)
    wallet_address: str

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to blockchain.

        Returns:
            bool: True if connected, False otherwise
        """
        pass

    @abstractmethod
    def get_balance(self, address: str) -> Decimal:
        """Get native token balance for an address.

        Args:
            address: Ethereum address

        Returns:
            Decimal: Balance in native tokens

        Raises:
            BlockchainConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_token_balance(self, address: str, token_address: str) -> Decimal:
        """Get ERC20 token balance for an address.

        Args:
            address: Ethereum address
            token_address: ERC20 token contract address

        Returns:
            Decimal: Token balance

        Raises:
            BlockchainConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def send_transaction(
        self,
        to: str,
        data: str = "0x",
        value: int = 0,
        gas: int | None = None,
    ) -> str:
        """Build, sign, and send a transaction.

        Args:
            to: Recipient address
            data: Transaction data (hex string)
            value: Amount to send in wei
            gas: Gas limit (estimated if not provided)

        Returns:
            str: Transaction hash

        Raises:
            TransactionFailedError: If transaction fails
            InsufficientGasError: If gas estimation fails
            BlockchainConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any]:
        """Get transaction receipt.

        Args:
            tx_hash: Transaction hash

        Returns:
            Dict[str, Any]: Transaction receipt

        Raises:
            BlockchainConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """Wait for transaction to be confirmed.

        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds

        Returns:
            Dict[str, Any]: Transaction receipt

        Raises:
            TransactionFailedError: If transaction fails
            BlockchainConnectionError: If connection fails
            TimeoutError: If timeout is reached
        """
        pass

    @abstractmethod
    def parse_event_logs(
        self,
        logs: list[dict[str, Any]],
        event_abi: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Parse event logs from transaction receipt.

        Args:
            logs: Raw event logs from receipt
            event_abi: Event ABI specification

        Returns:
            List[Dict[str, Any]]: Parsed events

        Raises:
            ValueError: If log parsing fails
        """
        pass

    @abstractmethod
    def get_nonce(self, address: str) -> int:
        """Get current nonce for address.

        Args:
            address: Ethereum address

        Returns:
            int: Current nonce

        Raises:
            BlockchainConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def estimate_gas(
        self,
        to: str,
        data: str = "0x",
        value: int = 0,
    ) -> int:
        """Estimate gas for a transaction.

        Args:
            to: Recipient address
            data: Transaction data
            value: Amount to send in wei

        Returns:
            int: Estimated gas

        Raises:
            InsufficientGasError: If estimation fails
            BlockchainConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def get_latest_transactions(
        self, addresses: list[str], from_block: int
    ) -> list[dict[str, Any]]:
        """Get latest transactions for given addresses.

        Args:
            addresses: List of addresses to filter transactions
            from_block: Starting block number

        Returns:
            List[Dict[str, Any]]: List of transaction dictionaries with keys:
                - hash: Transaction hash
                - from: Sender address
                - to: Recipient address
                - value: Transaction value in wei
                - blockNumber: Block number
                - timestamp: Block timestamp
                - input: Transaction input data

        Raises:
            BlockchainConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def call_contract_function(
        self,
        contract_address: str,
        function_name: str,
        abi: list[dict[str, Any]],
        args: list[Any] | None = None,
    ) -> Any:
        """Call a contract view or pure function.

        Args:
            contract_address: Contract address to call
            function_name: Name of the function to call
            abi: Contract ABI definition
            args: Function arguments (optional)

        Returns:
            Any: Function return value (single value or tuple)

        Raises:
            BlockchainConnectionError: If connection fails
            ValueError: If function not found in ABI or invalid address
        """
        pass


class PlatformConnector(ABC):
    """Interface for platform-specific connectors (e.g., Kuru Exchange)."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to platform."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to platform."""
        pass

    @abstractmethod
    async def deposit_margin(self, amount: Decimal) -> str:
        """Deposit margin to trading account.

        Args:
            amount: Amount to deposit

        Returns:
            str: Transaction hash
        """
        pass

    @abstractmethod
    async def place_order(
        self,
        market: str,
        side: str,
        order_type: str,
        size: Decimal,
        price: Decimal | None = None,
    ) -> str:
        """Place an order on the platform.

        Args:
            market: Market identifier (e.g., "ETH-USDC")
            side: Order side ("BUY" or "SELL")
            order_type: Order type ("LIMIT", "MARKET", etc.)
            size: Order size
            price: Limit price (required for limit orders)

        Returns:
            str: Order ID
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancelled successfully
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get order status.

        Args:
            order_id: Order ID

        Returns:
            Dict[str, Any]: Order details
        """
        pass

    @abstractmethod
    async def get_open_orders(self, market: str | None = None) -> list[dict[str, Any]]:
        """Get all open orders.

        Args:
            market: Filter by market (optional)

        Returns:
            List[Dict[str, Any]]: List of open orders
        """
        pass
