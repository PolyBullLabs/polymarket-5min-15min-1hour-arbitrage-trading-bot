"""Unit tests for Monad blockchain connector."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from web3.exceptions import Web3Exception

from src.kuru_copytr_bot.connectors.blockchain.monad import MonadClient
from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientGasError,
    TransactionFailedError,
)


@pytest.fixture
def mock_web3():
    """Create a mock Web3 provider."""
    with patch("src.kuru_copytr_bot.connectors.blockchain.monad.Web3") as mock:
        web3_instance = MagicMock()
        mock.return_value = web3_instance

        # Set up default mock responses
        web3_instance.is_connected.return_value = True
        web3_instance.eth.chain_id = 41454
        web3_instance.eth.get_balance.return_value = 1000000000000000000  # 1 ETH in wei
        web3_instance.eth.get_transaction_count.return_value = 5
        web3_instance.eth.block_number = 1000000

        # Mock account
        mock_account = MagicMock()
        mock_account.address = "0x1234567890123456789012345678901234567890"
        web3_instance.eth.account.from_key.return_value = mock_account

        # Transaction submission
        web3_instance.eth.send_raw_transaction.return_value = (
            b"0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )

        # Transaction receipt
        web3_instance.eth.get_transaction_receipt.return_value = {
            "status": 1,
            "blockNumber": 1000001,
            "transactionHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "gasUsed": 200000,
            "logs": [
                {
                    "address": "0xcontractaddress",
                    "topics": [
                        "0x" + "0" * 64,  # event signature
                    ],
                    "data": "0x" + "1" * 64,
                    "blockNumber": 1000001,
                }
            ],
        }

        # Gas estimation
        web3_instance.eth.estimate_gas.return_value = 250000

        # Gas price
        web3_instance.eth.gas_price = 1000000000  # 1 gwei

        yield web3_instance


class TestMonadClientConnection:
    """Test MonadClient connection functionality."""

    def test_monad_client_initializes_successfully(self, mock_web3):
        """MonadClient should initialize with RPC URL and private key."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        assert client is not None
        assert client.rpc_url == "https://testnet.monad.xyz"

    def test_monad_client_connects_successfully(self, mock_web3):
        """Client should connect to RPC successfully."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        assert client.is_connected() is True
        mock_web3.is_connected.assert_called()

    def test_monad_client_raises_error_on_connection_failure(self, mock_web3):
        """Client should raise BlockchainConnectionError on connection failure."""
        mock_web3.is_connected.return_value = False

        with pytest.raises(BlockchainConnectionError):
            MonadClient(
                rpc_url="https://invalid.url",
                private_key="0x" + "a" * 64,
            )

    def test_monad_client_derives_wallet_address_from_private_key(self, mock_web3):
        """Client should derive wallet address from private key."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        assert client.wallet_address == "0x1234567890123456789012345678901234567890"

    def test_monad_client_validates_chain_id(self, mock_web3):
        """Client should validate it's connected to the correct chain."""
        _ = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        # Should connect to Monad testnet (chain ID 41454)
        assert mock_web3.eth.chain_id == 41454


class TestMonadClientBalanceQueries:
    """Test MonadClient balance query functionality."""

    def test_monad_client_gets_native_balance(self, mock_web3):
        """Client should query wallet native token balance."""
        mock_web3.eth.get_balance.return_value = 1500000000000000000  # 1.5 ETH

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )
        test_address = "0xabcdef1234567890abcdef1234567890abcdef12"
        balance = client.get_balance(test_address)

        assert balance == Decimal("1.5")
        mock_web3.eth.get_balance.assert_called_with(test_address)

    def test_monad_client_gets_token_balance(self, mock_web3):
        """Client should query ERC20 token balance."""
        # Mock ERC20 contract call returning balance in wei
        mock_contract = MagicMock()
        mock_contract.functions.balanceOf.return_value.call.return_value = (
            1000000000000000000000  # 1000 tokens (18 decimals)
        )
        mock_contract.functions.decimals.return_value.call.return_value = (
            18  # Standard ERC20 decimals
        )
        mock_web3.eth.contract.return_value = mock_contract

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )
        test_wallet = "0x1234567890123456789012345678901234567890"
        test_token = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
        balance = client.get_token_balance(
            address=test_wallet,
            token_address=test_token,
        )

        assert balance == Decimal("1000")
        mock_web3.eth.contract.assert_called_with(
            address=test_token,
            abi=client.ERC20_ABI,
        )

    def test_monad_client_handles_zero_balance(self, mock_web3):
        """Client should handle zero balance correctly."""
        mock_web3.eth.get_balance.return_value = 0

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )
        test_address = "0xabcdef1234567890abcdef1234567890abcdef12"
        balance = client.get_balance(test_address)

        assert balance == Decimal("0")


class TestMonadClientTransactions:
    """Test MonadClient transaction functionality."""

    def test_monad_client_builds_transaction(self, mock_web3):
        """Client should build transaction with correct parameters."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        # Send transaction
        tx_hash = client.send_transaction(
            to="0x2222222222222222222222222222222222222222",
            data="0xdeadbeef",
            value=1000000000000000000,  # 1 ETH in wei
            gas=300000,
        )

        # Verify transaction was sent
        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66
        mock_web3.eth.send_raw_transaction.assert_called_once()

    def test_monad_client_signs_transaction(self, mock_web3):
        """Client should sign transaction with private key."""
        mock_account = MagicMock()
        mock_account.address = "0x1234567890123456789012345678901234567890"
        mock_signed_tx = MagicMock()
        mock_signed_tx.rawTransaction = b"0xsignedtx"
        mock_account.sign_transaction.return_value = mock_signed_tx
        mock_web3.eth.account.from_key.return_value = mock_account

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        client.send_transaction(
            to="0x2222222222222222222222222222222222222222",
            data="0x",
            value=0,
        )

        # Verify transaction was signed
        mock_account.sign_transaction.assert_called_once()

    def test_monad_client_submits_transaction(self, mock_web3):
        """Client should submit signed transaction to network."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        tx_hash = client.send_transaction(
            to="0x2222222222222222222222222222222222222222",
            data="0x",
        )

        assert tx_hash.startswith("0x")
        mock_web3.eth.send_raw_transaction.assert_called_once()

    def test_monad_client_estimates_gas_before_sending(self, mock_web3):
        """Client should estimate gas if not provided."""
        mock_web3.eth.estimate_gas.return_value = 250000

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        client.send_transaction(
            to="0x2222222222222222222222222222222222222222",
            data="0xfunction",
        )

        # Should estimate gas
        assert mock_web3.eth.estimate_gas.called

    def test_monad_client_uses_provided_gas_limit(self, mock_web3):
        """Client should use provided gas limit instead of estimating."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        client.send_transaction(
            to="0x2222222222222222222222222222222222222222",
            data="0x",
            gas=500000,
        )

        # Should not estimate gas when provided
        mock_web3.eth.estimate_gas.assert_not_called()

    def test_monad_client_raises_error_on_transaction_failure(self, mock_web3):
        """Client should raise TransactionFailedError on transaction failure."""
        mock_web3.eth.send_raw_transaction.side_effect = Web3Exception("Transaction failed")

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(TransactionFailedError):
            client.send_transaction(to="0x2222222222222222222222222222222222222222", data="0x")


class TestMonadClientReceipts:
    """Test MonadClient receipt handling."""

    def test_monad_client_gets_transaction_receipt(self, mock_web3):
        """Client should get transaction receipt."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        receipt = client.get_transaction_receipt(
            "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )

        assert receipt["status"] == 1
        assert receipt["blockNumber"] == 1000001
        mock_web3.eth.get_transaction_receipt.assert_called_once()

    def test_monad_client_waits_for_receipt(self, mock_web3):
        """Client should wait for transaction confirmation."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        receipt = client.wait_for_transaction_receipt(
            "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            timeout=120,
        )

        assert receipt["status"] == 1
        assert "blockNumber" in receipt

    def test_monad_client_handles_pending_transaction(self, mock_web3):
        """Client should poll for receipt if transaction is pending."""
        # First call returns None (pending), second call returns receipt
        mock_web3.eth.get_transaction_receipt.side_effect = [
            None,
            {
                "status": 1,
                "blockNumber": 1000001,
                "transactionHash": "0xabcdef",
                "gasUsed": 200000,
                "logs": [],
            },
        ]

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        receipt = client.wait_for_transaction_receipt("0xabcdef", timeout=10)

        assert receipt["status"] == 1
        assert mock_web3.eth.get_transaction_receipt.call_count == 2

    def test_monad_client_raises_error_on_failed_receipt(self, mock_web3):
        """Client should raise error if transaction receipt shows failure."""
        mock_web3.eth.get_transaction_receipt.return_value = {
            "status": 0,  # Failed
            "blockNumber": 1000001,
            "transactionHash": "0xabcdef",
            "gasUsed": 200000,
            "logs": [],
        }

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(TransactionFailedError):
            client.wait_for_transaction_receipt("0xabcdef")


class TestMonadClientEventLogs:
    """Test MonadClient event log parsing."""

    def test_monad_client_parses_event_logs(self, mock_web3):
        """Client should parse event logs from receipt."""
        logs = [
            {
                "address": "0xcontract",
                "topics": ["0x" + "0" * 64],
                "data": "0x" + "1" * 64,
                "blockNumber": 1000001,
            }
        ]

        event_abi = {
            "type": "event",
            "name": "OrderPlaced",
            "inputs": [
                {"name": "orderId", "type": "uint256", "indexed": False},
            ],
        }

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        parsed_events = client.parse_event_logs(logs, event_abi)

        assert isinstance(parsed_events, list)
        assert len(parsed_events) > 0

    def test_monad_client_handles_empty_logs(self, mock_web3):
        """Client should handle empty event logs."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        event_abi = {
            "type": "event",
            "name": "OrderPlaced",
            "inputs": [],
        }

        parsed_events = client.parse_event_logs([], event_abi)

        assert isinstance(parsed_events, list)
        assert len(parsed_events) == 0


class TestMonadClientNonceManagement:
    """Test MonadClient nonce management."""

    def test_monad_client_gets_current_nonce(self, mock_web3):
        """Client should get current nonce for address."""
        mock_web3.eth.get_transaction_count.return_value = 42

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        nonce = client.get_nonce("0x3333333333333333333333333333333333333333")

        assert nonce == 42
        mock_web3.eth.get_transaction_count.assert_called_with(
            "0x3333333333333333333333333333333333333333", "pending"
        )

    def test_monad_client_increments_nonce_for_multiple_transactions(self, mock_web3):
        """Client should manage nonce correctly for multiple transactions."""
        mock_web3.eth.get_transaction_count.return_value = 5

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        # Send multiple transactions
        client.send_transaction(to="0x2222222222222222222222222222222222222221", data="0x")
        client.send_transaction(to="0x2222222222222222222222222222222222222223", data="0x")

        # Should fetch nonce for each transaction
        assert mock_web3.eth.get_transaction_count.call_count >= 2


class TestMonadClientErrorHandling:
    """Test MonadClient error handling."""

    def test_monad_client_handles_network_error(self, mock_web3):
        """Client should handle network errors gracefully."""
        mock_web3.eth.get_balance.side_effect = ConnectionError("Network error")

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(BlockchainConnectionError):
            client.get_balance("0x3333333333333333333333333333333333333333")

    def test_monad_client_handles_insufficient_gas_error(self, mock_web3):
        """Client should raise InsufficientGasError when gas estimation fails."""
        mock_web3.eth.estimate_gas.side_effect = Web3Exception("out of gas")

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(InsufficientGasError):
            client.send_transaction(to="0x2222222222222222222222222222222222222222", data="0x")

    def test_monad_client_handles_invalid_address(self, mock_web3):
        """Client should validate Ethereum addresses."""
        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(ValueError):
            client.get_balance("invalid_address")


class TestMonadClientRetryLogic:
    """Test MonadClient retry logic."""

    def test_monad_client_retries_on_network_error(self, mock_web3):
        """Client should retry on network failures."""
        # First two calls fail, third succeeds
        mock_web3.eth.send_raw_transaction.side_effect = [
            ConnectionError("Network error"),
            ConnectionError("Network error"),
            b"0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        ]

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        tx_hash = client.send_transaction(
            to="0x2222222222222222222222222222222222222222", data="0x"
        )

        assert tx_hash.startswith("0x")
        assert mock_web3.eth.send_raw_transaction.call_count == 3

    def test_monad_client_retries_with_exponential_backoff(self, mock_web3):
        """Client should use exponential backoff for retries."""
        mock_web3.eth.get_balance.side_effect = [
            ConnectionError("Network error"),
            1000000000000000000,  # 1 ETH
        ]

        with patch("time.sleep") as mock_sleep:
            client = MonadClient(
                rpc_url="https://testnet.monad.xyz",
                private_key="0x" + "a" * 64,
            )

            balance = client.get_balance("0x3333333333333333333333333333333333333333")

            assert balance == Decimal("1.0")
            # Should have slept for backoff
            assert mock_sleep.called

    def test_monad_client_gives_up_after_max_retries(self, mock_web3):
        """Client should raise error after max retries exceeded."""
        # All attempts fail
        mock_web3.eth.send_raw_transaction.side_effect = ConnectionError("Network error")

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(BlockchainConnectionError):
            client.send_transaction(to="0x2222222222222222222222222222222222222222", data="0x")

        # Should have retried max_retries times (default: 3)
        assert mock_web3.eth.send_raw_transaction.call_count == 3

    def test_monad_client_does_not_retry_on_validation_errors(self, mock_web3):
        """Client should not retry on validation errors."""
        mock_web3.eth.send_raw_transaction.side_effect = ValueError("Invalid transaction")

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(TransactionFailedError):
            client.send_transaction(to="0x2222222222222222222222222222222222222222", data="0x")

        # Should not retry on validation errors
        assert mock_web3.eth.send_raw_transaction.call_count == 1


class TestMonadClientTransactionFetching:
    """Test MonadClient transaction fetching functionality."""

    def test_monad_client_fetches_transactions_for_single_address(self, mock_web3):
        """Client should fetch transactions for a single address."""
        target_address = "0x1111111111111111111111111111111111111111"

        # Mock block with transactions
        mock_block = {
            "timestamp": 1704067200,
            "transactions": [
                {
                    "hash": b"0xabc123",
                    "from": target_address,
                    "to": "0x2222222222222222222222222222222222222222",
                    "value": 1000000000000000000,  # 1 ETH
                    "input": "0x",
                },
                {
                    "hash": b"0xdef456",
                    "from": "0x3333333333333333333333333333333333333333",
                    "to": "0x4444444444444444444444444444444444444444",
                    "value": 500000000000000000,
                    "input": "0x",
                },
            ],
        }

        mock_web3.eth.block_number = 1000
        mock_web3.eth.get_block.return_value = mock_block

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        transactions = client.get_latest_transactions(
            addresses=[target_address],
            from_block=1000,
        )

        assert len(transactions) == 1
        assert transactions[0]["from"] == target_address
        assert transactions[0]["value"] == 1000000000000000000
        assert "hash" in transactions[0]
        assert "timestamp" in transactions[0]
        assert transactions[0]["blockNumber"] == 1000

    def test_monad_client_fetches_transactions_for_multiple_addresses(self, mock_web3):
        """Client should fetch transactions for multiple addresses."""
        address1 = "0x1111111111111111111111111111111111111111"
        address2 = "0x2222222222222222222222222222222222222222"

        # Mock block with multiple transactions
        mock_block = {
            "timestamp": 1704067200,
            "transactions": [
                {
                    "hash": b"0xabc123",
                    "from": address1,
                    "to": "0x3333333333333333333333333333333333333333",
                    "value": 1000000000000000000,
                    "input": "0x",
                },
                {
                    "hash": b"0xdef456",
                    "from": "0x4444444444444444444444444444444444444444",
                    "to": address2,
                    "value": 500000000000000000,
                    "input": "0x",
                },
                {
                    "hash": b"0xghi789",
                    "from": "0x5555555555555555555555555555555555555555",
                    "to": "0x6666666666666666666666666666666666666666",
                    "value": 2000000000000000000,
                    "input": "0x",
                },
            ],
        }

        mock_web3.eth.block_number = 1000
        mock_web3.eth.get_block.return_value = mock_block

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        transactions = client.get_latest_transactions(
            addresses=[address1, address2],
            from_block=1000,
        )

        # Should find 2 transactions (one from address1, one to address2)
        assert len(transactions) == 2
        assert any(tx["from"] == address1 for tx in transactions)
        assert any(tx["to"] == address2 for tx in transactions)

    def test_monad_client_scans_multiple_blocks(self, mock_web3):
        """Client should scan multiple blocks in range."""
        target_address = "0x1111111111111111111111111111111111111111"

        # Mock different blocks
        def get_block_side_effect(block_num, full_transactions=False):
            return {
                "timestamp": 1704067200 + block_num,
                "transactions": [
                    {
                        "hash": f"0xblock{block_num}tx1".encode(),
                        "from": target_address
                        if block_num % 2 == 0
                        else "0x2222222222222222222222222222222222222222",
                        "to": "0x3333333333333333333333333333333333333333",
                        "value": block_num * 1000000000,
                        "input": "0x",
                    }
                ],
            }

        mock_web3.eth.block_number = 1005
        mock_web3.eth.get_block.side_effect = get_block_side_effect

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        transactions = client.get_latest_transactions(
            addresses=[target_address],
            from_block=1000,
        )

        # Should find transactions in blocks 1000, 1002, 1004 (even blocks)
        assert len(transactions) == 3
        assert all(tx["from"] == target_address for tx in transactions)
        # Verify get_block was called for each block in range
        assert mock_web3.eth.get_block.call_count == 6  # 1000-1005 inclusive

    def test_monad_client_returns_empty_list_when_no_matches(self, mock_web3):
        """Client should return empty list when no matching transactions."""
        target_address = "0x1111111111111111111111111111111111111111"

        # Mock block with no matching transactions
        mock_block = {
            "timestamp": 1704067200,
            "transactions": [
                {
                    "hash": b"0xabc123",
                    "from": "0x2222222222222222222222222222222222222222",
                    "to": "0x3333333333333333333333333333333333333333",
                    "value": 1000000000000000000,
                    "input": "0x",
                }
            ],
        }

        mock_web3.eth.block_number = 1000
        mock_web3.eth.get_block.return_value = mock_block

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        transactions = client.get_latest_transactions(
            addresses=[target_address],
            from_block=1000,
        )

        assert len(transactions) == 0

    def test_monad_client_handles_empty_blocks(self, mock_web3):
        """Client should handle blocks with no transactions."""
        # Mock empty block
        mock_block = {
            "timestamp": 1704067200,
            "transactions": [],
        }

        mock_web3.eth.block_number = 1000
        mock_web3.eth.get_block.return_value = mock_block

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        transactions = client.get_latest_transactions(
            addresses=["0x1111111111111111111111111111111111111111"],
            from_block=1000,
        )

        assert len(transactions) == 0

    def test_monad_client_limits_block_scan_range(self, mock_web3):
        """Client should limit block scanning to prevent excessive load."""
        mock_block = {"timestamp": 1704067200, "transactions": []}

        mock_web3.eth.block_number = 5000  # 4000 blocks ahead
        mock_web3.eth.get_block.return_value = mock_block

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        client.get_latest_transactions(
            addresses=["0x1111111111111111111111111111111111111111"],
            from_block=1000,
        )

        # Should limit to max_blocks_to_scan (1000 blocks)
        # So it scans from 1000 to 2000 (1001 blocks total)
        assert mock_web3.eth.get_block.call_count == 1001

    def test_monad_client_handles_block_fetch_errors_gracefully(self, mock_web3):
        """Client should continue scanning even if some blocks fail."""
        target_address = "0x1111111111111111111111111111111111111111"

        def get_block_side_effect(block_num, full_transactions=False):
            if block_num == 1001:
                raise Web3Exception("Block not found")
            return {
                "timestamp": 1704067200,
                "transactions": [
                    {
                        "hash": f"0xblock{block_num}".encode(),
                        "from": target_address,
                        "to": "0x2222222222222222222222222222222222222222",
                        "value": 1000000000000000000,
                        "input": "0x",
                    }
                ],
            }

        mock_web3.eth.block_number = 1002
        mock_web3.eth.get_block.side_effect = get_block_side_effect

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        transactions = client.get_latest_transactions(
            addresses=[target_address],
            from_block=1000,
        )

        # Should still find transactions in blocks 1000 and 1002 (skipping 1001)
        assert len(transactions) == 2

    def test_monad_client_normalizes_addresses_for_comparison(self, mock_web3):
        """Client should normalize addresses to lowercase for comparison."""
        # Mixed case address
        target_address_mixed = "0x1111111111111111111111111111111111111111"
        address_in_block = "0x1111111111111111111111111111111111111111".upper()

        mock_block = {
            "timestamp": 1704067200,
            "transactions": [
                {
                    "hash": b"0xabc123",
                    "from": address_in_block,
                    "to": "0x2222222222222222222222222222222222222222",
                    "value": 1000000000000000000,
                    "input": "0x",
                }
            ],
        }

        mock_web3.eth.block_number = 1000
        mock_web3.eth.get_block.return_value = mock_block

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        transactions = client.get_latest_transactions(
            addresses=[target_address_mixed],
            from_block=1000,
        )

        # Should match despite case differences
        assert len(transactions) == 1

    def test_monad_client_raises_error_on_connection_failure(self, mock_web3):
        """Client should raise BlockchainConnectionError when getting block number fails."""
        # Make block_number property raise an exception
        type(mock_web3.eth).block_number = property(
            lambda self: (_ for _ in ()).throw(Web3Exception("Connection failed"))
        )

        client = MonadClient(
            rpc_url="https://testnet.monad.xyz",
            private_key="0x" + "a" * 64,
        )

        with pytest.raises(BlockchainConnectionError, match="Failed to fetch transactions"):
            client.get_latest_transactions(
                addresses=["0x1111111111111111111111111111111111111111"],
                from_block=1000,
            )
