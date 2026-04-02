"""Unit tests for MonadClient contract call functionality."""

from unittest.mock import MagicMock, patch

import pytest
from web3.exceptions import Web3Exception

from src.kuru_copytr_bot.connectors.blockchain.monad import MonadClient
from src.kuru_copytr_bot.core.exceptions import BlockchainConnectionError


@pytest.fixture
def mock_web3():
    """Create a mock Web3 provider."""
    with patch("src.kuru_copytr_bot.connectors.blockchain.monad.Web3") as mock:
        web3_instance = MagicMock()
        mock.return_value = web3_instance

        web3_instance.is_connected.return_value = True
        web3_instance.eth.chain_id = 41454

        mock_account = MagicMock()
        mock_account.address = "0x1234567890123456789012345678901234567890"
        web3_instance.eth.account.from_key.return_value = mock_account

        yield web3_instance


@pytest.fixture
def monad_client(mock_web3):
    """Create a MonadClient instance for testing."""
    return MonadClient(
        rpc_url="https://testnet.monad.xyz",
        private_key="0x" + "a" * 64,
    )


class TestCallContractFunction:
    """Test call_contract_function method."""

    def test_call_contract_function_view_function_success(self, monad_client, mock_web3):
        """Test successful view function call returns decoded data."""
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.return_value = (100, 200, "0x" + "1" * 40)
        mock_contract.functions.getMarketParams.return_value = mock_function
        mock_web3.eth.contract.return_value = mock_contract

        abi = [
            {
                "name": "getMarketParams",
                "type": "function",
                "inputs": [],
                "outputs": [
                    {"name": "param1", "type": "uint256"},
                    {"name": "param2", "type": "uint256"},
                    {"name": "param3", "type": "address"},
                ],
            }
        ]

        result = monad_client.call_contract_function(
            contract_address="0x" + "a" * 40,
            function_name="getMarketParams",
            abi=abi,
            args=[],
        )

        assert result == (100, 200, "0x" + "1" * 40)
        mock_contract.functions.getMarketParams.assert_called_once()
        mock_function.call.assert_called_once()

    def test_call_contract_function_with_arguments(self, monad_client, mock_web3):
        """Test contract function call with arguments."""
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.return_value = 1000000000000000000
        mock_contract.functions.balanceOf.return_value = mock_function
        mock_web3.eth.contract.return_value = mock_contract

        abi = [
            {
                "name": "balanceOf",
                "type": "function",
                "inputs": [{"name": "account", "type": "address"}],
                "outputs": [{"name": "", "type": "uint256"}],
            }
        ]

        result = monad_client.call_contract_function(
            contract_address="0x" + "b" * 40,
            function_name="balanceOf",
            abi=abi,
            args=["0x" + "c" * 40],
        )

        assert result == 1000000000000000000
        mock_contract.functions.balanceOf.assert_called_once_with("0x" + "c" * 40)
        mock_function.call.assert_called_once()

    def test_call_contract_function_connection_failure(self, monad_client, mock_web3):
        """Test connection error handling."""
        mock_web3.eth.contract.side_effect = ConnectionError("Network error")

        abi = [
            {
                "name": "getMarketParams",
                "type": "function",
                "inputs": [],
                "outputs": [],
            }
        ]

        with pytest.raises(BlockchainConnectionError) as exc_info:
            monad_client.call_contract_function(
                contract_address="0x" + "a" * 40,
                function_name="getMarketParams",
                abi=abi,
                args=[],
            )

        assert "Failed to call contract function after retries" in str(exc_info.value)

    def test_call_contract_function_invalid_abi(self, monad_client, mock_web3):
        """Test invalid ABI handling."""
        abi = []

        with pytest.raises(ValueError) as exc_info:
            monad_client.call_contract_function(
                contract_address="0x" + "a" * 40,
                function_name="nonExistentFunction",
                abi=abi,
                args=[],
            )

        assert "Function nonExistentFunction not found in ABI" in str(exc_info.value)

    def test_call_contract_function_retries_on_timeout(self, monad_client, mock_web3):
        """Test retry logic on network timeout."""
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.side_effect = [
            TimeoutError("First timeout"),
            TimeoutError("Second timeout"),
            TimeoutError("Third timeout"),
        ]
        mock_contract.functions.getMarketParams.return_value = mock_function
        mock_web3.eth.contract.return_value = mock_contract

        abi = [
            {
                "name": "getMarketParams",
                "type": "function",
                "inputs": [],
                "outputs": [],
            }
        ]

        with pytest.raises(BlockchainConnectionError) as exc_info:
            monad_client.call_contract_function(
                contract_address="0x" + "a" * 40,
                function_name="getMarketParams",
                abi=abi,
                args=[],
            )

        assert "Failed to call contract function after retries" in str(exc_info.value)
        assert mock_function.call.call_count == 3

    def test_call_contract_function_invalid_contract_address(self, monad_client):
        """Test invalid contract address handling."""
        abi = [
            {
                "name": "getMarketParams",
                "type": "function",
                "inputs": [],
                "outputs": [],
            }
        ]

        with pytest.raises(ValueError) as exc_info:
            monad_client.call_contract_function(
                contract_address="invalid_address",
                function_name="getMarketParams",
                abi=abi,
                args=[],
            )

        assert "Invalid contract address" in str(exc_info.value)

    def test_call_contract_function_with_multiple_return_values(self, monad_client, mock_web3):
        """Test function returning tuple of multiple values."""
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.return_value = (
            1000000,
            100000,
            "0x" + "a" * 40,
            18,
            "0x" + "b" * 40,
            6,
            10000,
            1000,
            1000000000,
            25,
            10,
        )
        mock_contract.functions.getMarketParams.return_value = mock_function
        mock_web3.eth.contract.return_value = mock_contract

        abi = [
            {
                "name": "getMarketParams",
                "type": "function",
                "inputs": [],
                "outputs": [
                    {"name": "pricePrecision", "type": "uint256"},
                    {"name": "sizePrecision", "type": "uint256"},
                    {"name": "baseAsset", "type": "address"},
                    {"name": "baseAssetDecimals", "type": "uint8"},
                    {"name": "quoteAsset", "type": "address"},
                    {"name": "quoteAssetDecimals", "type": "uint8"},
                    {"name": "tickSize", "type": "uint256"},
                    {"name": "minSize", "type": "uint256"},
                    {"name": "maxSize", "type": "uint256"},
                    {"name": "takerFeeBps", "type": "uint16"},
                    {"name": "makerFeeBps", "type": "uint16"},
                ],
            }
        ]

        result = monad_client.call_contract_function(
            contract_address="0x" + "c" * 40,
            function_name="getMarketParams",
            abi=abi,
            args=[],
        )

        assert len(result) == 11
        assert result[0] == 1000000
        assert result[2] == "0x" + "a" * 40
        assert result[4] == "0x" + "b" * 40

    def test_call_contract_function_with_web3_exception(self, monad_client, mock_web3):
        """Test Web3Exception handling."""
        mock_contract = MagicMock()
        mock_function = MagicMock()
        mock_function.call.side_effect = Web3Exception("Contract reverted")
        mock_contract.functions.getMarketParams.return_value = mock_function
        mock_web3.eth.contract.return_value = mock_contract

        abi = [
            {
                "name": "getMarketParams",
                "type": "function",
                "inputs": [],
                "outputs": [],
            }
        ]

        with pytest.raises(BlockchainConnectionError) as exc_info:
            monad_client.call_contract_function(
                contract_address="0x" + "a" * 40,
                function_name="getMarketParams",
                abi=abi,
                args=[],
            )

        assert "Failed to call contract function" in str(exc_info.value)
