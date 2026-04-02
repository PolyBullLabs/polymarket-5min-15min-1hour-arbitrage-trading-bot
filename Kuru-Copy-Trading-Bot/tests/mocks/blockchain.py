"""Mock blockchain client for testing."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock


class MockWeb3Provider:
    """Mock Web3 provider for testing blockchain interactions."""

    def __init__(self) -> None:
        """Initialize mock Web3 provider."""
        self.eth = MagicMock()
        self.net = MagicMock()

        # Set default mock responses
        self.eth.get_balance.return_value = 1000000000000000000  # 1 ETH in wei
        self.eth.get_transaction_count.return_value = 0
        self.eth.block_number = 1000000
        self.eth.chain_id = 41454  # Monad testnet chain ID (placeholder)
        self.net.version = "41454"

        # Transaction submission mock
        self.eth.send_raw_transaction.return_value = b"0xmocktxhash"

        # Transaction receipt mock
        self.eth.get_transaction_receipt.return_value = {
            "status": 1,
            "blockNumber": 1000000,
            "transactionHash": "0xmocktxhash",
            "gasUsed": 200000,
            "logs": [],
        }

    def is_connected(self) -> bool:
        """Mock connection check."""
        return True


class MockBlockchainClient:
    """Mock blockchain client implementing BlockchainConnector interface."""

    def __init__(
        self,
        rpc_url: str = "http://mock-rpc",
        private_key: str = "0xmockprivatekey",
    ) -> None:
        """Initialize mock blockchain client."""
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.wallet_address = "0x1234567890123456789012345678901234567890"
        self.connected = True

        # Track calls for testing
        self.transactions_sent: list[dict[str, Any]] = []
        self.receipts_requested: list[str] = []
        self.events_parsed: list[dict[str, Any]] = []

    def is_connected(self) -> bool:
        """Check if connected to blockchain."""
        return self.connected

    def get_balance(self, address: str) -> Decimal:
        """Get wallet balance in native token."""
        # Return mock balance
        return Decimal("10.0")

    def get_token_balance(self, address: str, token_address: str) -> Decimal:
        """Get ERC20 token balance."""
        # Return mock token balance
        return Decimal("1000.0")

    def send_transaction(
        self,
        to: str,
        data: str = "0x",
        value: int = 0,
        gas: int | None = None,
    ) -> str:
        """Send a transaction to the blockchain."""
        tx = {
            "to": to,
            "data": data,
            "value": value,
            "gas": gas or 300000,
            "from": self.wallet_address,
        }
        self.transactions_sent.append(tx)

        # Return mock transaction hash
        return f"0xmocktx{len(self.transactions_sent):064x}"

    def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any]:
        """Get transaction receipt."""
        self.receipts_requested.append(tx_hash)

        # Return mock receipt
        return {
            "transactionHash": tx_hash,
            "status": 1,
            "blockNumber": 1000000,
            "gasUsed": 200000,
            "logs": [],
        }

    def parse_event_logs(
        self,
        logs: list[dict[str, Any]],
        event_abi: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Parse event logs from transaction receipt."""
        self.events_parsed.extend(logs)

        # Return mock parsed events
        return [{"event": "MockEvent", "args": {"data": "mock"}} for _ in logs]

    def get_nonce(self, address: str) -> int:
        """Get current nonce for address."""
        return 0

    def estimate_gas(
        self,
        to: str,
        data: str = "0x",
        value: int = 0,
    ) -> int:
        """Estimate gas for transaction."""
        return 250000

    def get_latest_transactions(
        self,
        addresses: list[str],
        from_block: int,
    ) -> list[dict[str, Any]]:
        """Get latest transactions for addresses (legacy - bot uses events)."""
        return []

    def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """Wait for transaction receipt with timeout."""
        return self.get_transaction_receipt(tx_hash)
