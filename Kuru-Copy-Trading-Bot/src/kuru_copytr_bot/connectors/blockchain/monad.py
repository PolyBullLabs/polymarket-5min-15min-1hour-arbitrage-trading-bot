"""Monad blockchain connector using Web3.py."""

import threading
import time
from decimal import Decimal
from typing import Any, ClassVar

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from web3 import Web3
from web3.exceptions import Web3Exception

from src.kuru_copytr_bot.config.constants import (
    MAX_RETRIES,
    RETRY_BACKOFF_SECONDS,
)
from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientBalanceError,
    InsufficientGasError,
    TransactionFailedError,
)
from src.kuru_copytr_bot.core.interfaces import BlockchainConnector
from src.kuru_copytr_bot.utils.logger import get_logger

logger = get_logger(__name__)


class MonadClient(BlockchainConnector):
    """Monad blockchain connector implementing BlockchainConnector interface."""

    # Standard ERC20 ABI for balanceOf
    ERC20_ABI: ClassVar[list[dict[str, Any]]] = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function",
        },
    ]

    def __init__(self, rpc_url: str, private_key: str, dry_run: bool = False):
        """Initialize Monad client.

        Args:
            rpc_url: Monad RPC endpoint URL
            private_key: Private key for signing transactions
            dry_run: If True, transactions are logged but not sent to blockchain

        Raises:
            BlockchainConnectionError: If connection fails
        """
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.dry_run = dry_run

        # Initialize Web3
        try:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to initialize Web3: {e}") from e

        # Verify connection
        if not self.w3.is_connected():
            raise BlockchainConnectionError(f"Failed to connect to {rpc_url}")

        # Set up account from private key
        try:
            self.account = self.w3.eth.account.from_key(private_key)
            self.wallet_address = self.account.address
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}") from e

        # Lock for serializing nonce fetching and transaction submission
        # Prevents race conditions when multiple transactions are submitted rapidly
        self._nonce_lock = threading.Lock()

        # Counter for dry run transaction hashes
        self._dry_run_tx_counter = 0

    def is_connected(self) -> bool:
        """Check if connected to blockchain.

        Returns:
            bool: True if connected, False otherwise
        """
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def get_balance(self, address: str) -> Decimal:
        """Get native token balance for an address.

        Args:
            address: Ethereum address

        Returns:
            Decimal: Balance in native tokens (MON)

        Raises:
            BlockchainConnectionError: If connection fails
            ValueError: If address is invalid
        """
        # Validate address
        if not self._is_valid_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")

        @retry(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=RETRY_BACKOFF_SECONDS, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        )
        def _get_balance_with_retry():
            return self.w3.eth.get_balance(address)

        try:
            balance_wei = _get_balance_with_retry()
            # Convert wei to ETH/MON (18 decimals)
            return Decimal(balance_wei) / Decimal(10**18)
        except (ConnectionError, TimeoutError) as e:
            raise BlockchainConnectionError(f"Failed to get balance after retries: {e}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to get balance: {e}") from e

    def get_token_balance(self, address: str, token_address: str) -> Decimal:
        """Get ERC20 token balance for an address.

        Args:
            address: Ethereum address
            token_address: ERC20 token contract address

        Returns:
            Decimal: Token balance

        Raises:
            BlockchainConnectionError: If connection fails
            ValueError: If address is invalid
        """
        # Validate addresses
        if not self._is_valid_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")
        if not self._is_valid_address(token_address):
            raise ValueError(f"Invalid token address: {token_address}")

        @retry(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=RETRY_BACKOFF_SECONDS, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        )
        def _get_token_balance_with_retry():
            contract = self.w3.eth.contract(address=token_address, abi=self.ERC20_ABI)
            balance_raw = contract.functions.balanceOf(address).call()
            try:
                decimals = contract.functions.decimals().call()
            except Exception:
                decimals = 18
            return balance_raw, decimals

        try:
            balance_raw, decimals = _get_token_balance_with_retry()
            # Convert to decimal
            return Decimal(balance_raw) / Decimal(10**decimals)
        except (ConnectionError, TimeoutError) as e:
            raise BlockchainConnectionError(
                f"Failed to get token balance after retries: {e}"
            ) from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to get token balance: {e}") from e

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
            str: Transaction hash (hex string with 0x prefix)

        Raises:
            TransactionFailedError: If transaction fails
            InsufficientGasError: If gas estimation fails
            BlockchainConnectionError: If connection fails
            ValueError: If validation fails
        """
        # Validate address
        if not self._is_valid_address(to):
            raise ValueError(f"Invalid recipient address: {to}")

        # Convert to checksum address (required by Web3.py for transactions)
        to = Web3.to_checksum_address(to)

        @retry(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=RETRY_BACKOFF_SECONDS, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        )
        def _send_with_retry(tx):
            signed_tx = self.account.sign_transaction(tx)
            return self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        try:
            # Use lock to serialize nonce fetching and transaction submission
            # This prevents race conditions when multiple transactions are submitted rapidly
            with self._nonce_lock:
                # Get nonce (using 'pending' to include pending transactions)
                nonce = self.w3.eth.get_transaction_count(self.wallet_address, "pending")

                # Build transaction
                tx = {
                    "from": self.wallet_address,
                    "to": to,
                    "value": value,
                    "data": data,
                    "nonce": nonce,
                    "chainId": self.w3.eth.chain_id,
                    "gasPrice": self.w3.eth.gas_price,
                }

                # Estimate gas if not provided
                if gas is None:
                    try:
                        estimated_gas = self.w3.eth.estimate_gas(tx)
                        tx["gas"] = estimated_gas
                    except Web3Exception as e:
                        error_msg = str(e).lower()
                        # Check for common insufficient balance / contract rejection errors
                        # Include known Kuru contract error codes
                        if any(
                            keyword in error_msg
                            for keyword in [
                                "out of gas",
                                "insufficient",
                                "balance",
                                "funds",
                                "0x0a5c4f1f",  # Kuru: insufficient balance
                                "0xf4d678b8",  # Kuru: another balance/margin error
                            ]
                        ):
                            raise InsufficientBalanceError(
                                f"Insufficient balance or margin: {e}"
                            ) from e

                        # If it's any other contract custom error (hex code), treat as insufficient balance
                        # Most contract rejections during gas estimation are due to balance/margin issues
                        if (
                            "0x" in error_msg and len(error_msg) < 50
                        ):  # Likely a contract error code
                            raise InsufficientBalanceError(
                                f"Contract rejected order (likely insufficient balance): {e}"
                            ) from e

                        raise InsufficientGasError(f"Failed to estimate gas: {e}") from e
                else:
                    tx["gas"] = gas

                # DRY RUN MODE: Log transaction instead of sending it
                if self.dry_run:
                    self._dry_run_tx_counter += 1
                    fake_tx_hash = f"0xdryrun{self._dry_run_tx_counter:056x}"
                    logger.info(
                        "[DRY RUN] Transaction simulated (not sent to blockchain)",
                        to=to,
                        value=value,
                        data=data[:66] + "..." if len(data) > 66 else data,
                        gas=tx["gas"],
                        fake_tx_hash=fake_tx_hash,
                    )
                    return fake_tx_hash

                # Send transaction with retry (inside lock to ensure nonce is used immediately)
                tx_hash = _send_with_retry(tx)

            # Return hex string (outside lock since we already sent the transaction)
            if isinstance(tx_hash, bytes):
                # Convert bytes to hex string
                result = tx_hash.hex() if not tx_hash.startswith(b"0x") else tx_hash.decode("utf-8")
                return result if result.startswith("0x") else "0x" + result
            return tx_hash

        except (ConnectionError, TimeoutError) as e:
            raise BlockchainConnectionError(f"Failed to send transaction after retries: {e}") from e
        except InsufficientBalanceError:
            # Don't wrap balance errors - let them propagate up
            raise
        except InsufficientGasError:
            # Don't wrap gas errors
            raise
        except (ValueError, Web3Exception) as e:
            # Wrap transaction validation/execution errors
            raise TransactionFailedError(f"Transaction failed: {e}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to send transaction: {e}") from e

    def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any]:
        """Get transaction receipt.

        Args:
            tx_hash: Transaction hash

        Returns:
            Dict[str, Any]: Transaction receipt

        Raises:
            BlockchainConnectionError: If connection fails
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return None
            # Convert to dict if needed
            return dict(receipt) if not isinstance(receipt, dict) else receipt
        except Exception as e:
            # If transaction not found, return None so polling can continue
            if "not found" in str(e).lower():
                return None
            raise BlockchainConnectionError(f"Failed to get transaction receipt: {e}") from e

    def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: int = 10,
    ) -> dict[str, Any]:
        """Wait for transaction to be confirmed.

        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds (default: 10)

        Returns:
            Dict[str, Any]: Transaction receipt

        Raises:
            TransactionFailedError: If transaction fails
            BlockchainConnectionError: If connection fails
            TimeoutError: If timeout is reached
        """
        # DRY RUN MODE: Return fake receipt immediately
        if self.dry_run and tx_hash.startswith("0xdryrun"):
            logger.debug("[DRY RUN] Returning fake transaction receipt", tx_hash=tx_hash)
            return {
                "transactionHash": tx_hash,
                "status": 1,
                "blockNumber": 0,
                "logs": [],
                "gasUsed": 0,
            }

        start_time = time.time()
        poll_interval = 1  # seconds

        while time.time() - start_time < timeout:
            receipt = self.get_transaction_receipt(tx_hash)

            if receipt is not None:
                # Check if transaction succeeded
                if receipt.get("status") == 0:
                    raise TransactionFailedError(f"Transaction {tx_hash} failed (status=0)")
                return receipt

            # Wait before polling again
            time.sleep(poll_interval)

        raise TimeoutError(f"Transaction {tx_hash} not confirmed within {timeout}s")

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
        if not logs:
            return []

        try:
            # Create a contract interface for parsing
            # We need a minimal contract ABI with just the event
            contract_abi = [event_abi]
            # Use a dummy address since we're only parsing logs
            dummy_address = "0x" + "0" * 40
            contract = self.w3.eth.contract(address=dummy_address, abi=contract_abi)

            parsed_events = []
            for log in logs:
                try:
                    # Try to parse this log with the event ABI
                    event_name = event_abi.get("name", "Unknown")
                    # Get the event from contract
                    event = getattr(contract.events, event_name, None)
                    if event:
                        parsed = event.process_log(log)
                        parsed_events.append(dict(parsed))
                except Exception:
                    # Skip logs that don't match this event
                    continue

            return parsed_events

        except Exception as e:
            raise ValueError(f"Failed to parse event logs: {e}") from e

    def get_nonce(self, address: str) -> int:
        """Get current nonce for address.

        Args:
            address: Ethereum address

        Returns:
            int: Current nonce

        Raises:
            BlockchainConnectionError: If connection fails
            ValueError: If address is invalid
        """
        # Validate address
        if not self._is_valid_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")

        @retry(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=RETRY_BACKOFF_SECONDS, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        )
        def _get_nonce_with_retry():
            return self.w3.eth.get_transaction_count(address, "pending")

        try:
            return _get_nonce_with_retry()
        except (ConnectionError, TimeoutError) as e:
            raise BlockchainConnectionError(f"Failed to get nonce after retries: {e}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to get nonce: {e}") from e

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
            ValueError: If validation fails
        """
        # Validate address
        if not self._is_valid_address(to):
            raise ValueError(f"Invalid recipient address: {to}")

        try:
            tx = {
                "from": self.wallet_address,
                "to": to,
                "value": value,
                "data": data,
            }
            return self.w3.eth.estimate_gas(tx)
        except Web3Exception as e:
            if "out of gas" in str(e).lower():
                raise InsufficientGasError(f"Gas estimation failed: {e}") from e
            raise InsufficientGasError(f"Failed to estimate gas: {e}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to estimate gas: {e}") from e

    def get_latest_transactions(
        self,
        addresses: list[str],
        from_block: int,
    ) -> list[dict[str, Any]]:
        """Get latest transactions for addresses.

        Scans blocks from from_block to current block and returns transactions
        where any of the given addresses appear as sender or recipient.

        Args:
            addresses: List of Ethereum addresses to filter by
            from_block: Starting block number

        Returns:
            List[Dict[str, Any]]: List of transactions with keys:
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
        try:
            # Normalize addresses to lowercase for comparison
            normalized_addresses = {addr.lower() for addr in addresses}

            # Get current block number
            current_block = self.w3.eth.block_number

            # Limit block range to prevent excessive scanning
            max_blocks_to_scan = 1000
            to_block = min(current_block, from_block + max_blocks_to_scan)

            if current_block - from_block > max_blocks_to_scan:
                logger.warning(
                    "Block range exceeds maximum, limiting scan",
                    from_block=from_block,
                    current_block=current_block,
                    max_blocks=max_blocks_to_scan,
                    to_block=to_block,
                )

            logger.debug(
                "Scanning blocks for transactions",
                from_block=from_block,
                to_block=to_block,
                addresses=list(normalized_addresses),
            )

            matching_transactions = []

            # Scan blocks in the range
            for block_number in range(from_block, to_block + 1):
                try:
                    block = self.w3.eth.get_block(block_number, full_transactions=True)

                    # Process each transaction in the block
                    transactions_in_block = (
                        block.get("transactions", [])
                        if isinstance(block, dict)
                        else block.transactions
                    )
                    for tx in transactions_in_block:
                        tx_from = tx.get("from", "").lower() if tx.get("from") else ""
                        tx_to = tx.get("to", "").lower() if tx.get("to") else ""

                        # Check if transaction involves any of our target addresses
                        if tx_from in normalized_addresses or tx_to in normalized_addresses:
                            # Get timestamp from block (handle both dict and AttributeDict)
                            timestamp = (
                                block.get("timestamp", 0)
                                if isinstance(block, dict)
                                else block.timestamp
                            )

                            matching_transactions.append(
                                {
                                    "hash": tx["hash"].hex()
                                    if isinstance(tx["hash"], bytes)
                                    else tx["hash"],
                                    "from": tx.get("from", ""),
                                    "to": tx.get("to", ""),
                                    "value": int(tx.get("value", 0)),
                                    "blockNumber": block_number,
                                    "timestamp": int(timestamp),
                                    "input": tx.get("input", "0x"),
                                }
                            )

                except Exception as e:
                    logger.warning(
                        "Error fetching block",
                        block_number=block_number,
                        error=str(e),
                    )
                    # Continue scanning other blocks
                    continue

            logger.info(
                "Transaction scan complete",
                from_block=from_block,
                to_block=to_block,
                transactions_found=len(matching_transactions),
            )

            return matching_transactions

        except Web3Exception as e:
            raise BlockchainConnectionError(f"Failed to fetch transactions: {e}") from e
        except Exception as e:
            raise BlockchainConnectionError(f"Unexpected error fetching transactions: {e}") from e

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
        if not self._is_valid_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        if args is None:
            args = []

        function_abi = None
        for item in abi:
            if item.get("type") == "function" and item.get("name") == function_name:
                function_abi = item
                break

        if function_abi is None:
            raise ValueError(f"Function {function_name} not found in ABI")

        @retry(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=RETRY_BACKOFF_SECONDS, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        )
        def _call_with_retry():
            checksum_address = Web3.to_checksum_address(contract_address)
            contract = self.w3.eth.contract(address=checksum_address, abi=abi)
            function = getattr(contract.functions, function_name)
            return function(*args).call()

        try:
            return _call_with_retry()
        except RetryError as e:
            raise BlockchainConnectionError(
                f"Failed to call contract function after retries: {e.last_attempt.exception()}"
            ) from e
        except (ConnectionError, TimeoutError) as e:
            raise BlockchainConnectionError(
                f"Failed to call contract function after retries: {e}"
            ) from e
        except Exception as e:
            raise BlockchainConnectionError(f"Failed to call contract function: {e}") from e

    def _is_valid_address(self, address: str) -> bool:
        """Validate Ethereum address format.

        Args:
            address: Address to validate

        Returns:
            bool: True if valid, False otherwise
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
