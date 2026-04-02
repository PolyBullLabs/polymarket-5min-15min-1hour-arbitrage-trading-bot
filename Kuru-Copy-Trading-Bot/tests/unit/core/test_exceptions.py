"""Tests for custom exceptions."""

import pytest

from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    ConfigurationError,
    InsufficientBalanceError,
    InsufficientGasError,
    InvalidMarketError,
    InvalidOrderError,
    InvalidStateTransitionError,
    KuruCopyTradingBotError,
    OrderExecutionError,
    OrderPlacementError,
    TradeValidationError,
    TransactionFailedError,
)


class TestBaseException:
    """Test base exception class."""

    def test_base_exception_can_be_raised(self):
        """Should be able to raise base exception."""
        with pytest.raises(KuruCopyTradingBotError):
            raise KuruCopyTradingBotError("Base error")

    def test_base_exception_message(self):
        """Should preserve error message."""
        message = "Custom error message"
        with pytest.raises(KuruCopyTradingBotError, match=message):
            raise KuruCopyTradingBotError(message)

    def test_base_exception_is_exception_subclass(self):
        """Should be a subclass of Exception."""
        assert issubclass(KuruCopyTradingBotError, Exception)

    def test_base_exception_with_no_message(self):
        """Should work with no message."""
        with pytest.raises(KuruCopyTradingBotError):
            raise KuruCopyTradingBotError()


class TestInvalidStateTransitionError:
    """Test invalid state transition exception."""

    def test_invalid_state_transition_can_be_raised(self):
        """Should be able to raise InvalidStateTransitionError."""
        with pytest.raises(InvalidStateTransitionError):
            raise InvalidStateTransitionError("Invalid state")

    def test_invalid_state_transition_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(InvalidStateTransitionError, KuruCopyTradingBotError)

    def test_invalid_state_transition_message(self):
        """Should preserve error message."""
        message = "Cannot transition from IDLE to TRADING"
        with pytest.raises(InvalidStateTransitionError, match=message):
            raise InvalidStateTransitionError(message)


class TestBlockchainConnectionError:
    """Test blockchain connection error."""

    def test_blockchain_connection_error_can_be_raised(self):
        """Should be able to raise BlockchainConnectionError."""
        with pytest.raises(BlockchainConnectionError):
            raise BlockchainConnectionError("Connection failed")

    def test_blockchain_connection_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(BlockchainConnectionError, KuruCopyTradingBotError)

    def test_blockchain_connection_error_message(self):
        """Should preserve error message."""
        message = "Failed to connect to RPC endpoint"
        with pytest.raises(BlockchainConnectionError, match=message):
            raise BlockchainConnectionError(message)

    def test_blockchain_connection_error_with_url(self):
        """Should include URL in error message."""
        url = "https://rpc.monad.example.com"
        message = f"Failed to connect to {url}"
        with pytest.raises(BlockchainConnectionError, match=message):
            raise BlockchainConnectionError(message)


class TestTransactionFailedError:
    """Test transaction failed error."""

    def test_transaction_failed_error_can_be_raised(self):
        """Should be able to raise TransactionFailedError."""
        with pytest.raises(TransactionFailedError):
            raise TransactionFailedError("Transaction failed")

    def test_transaction_failed_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(TransactionFailedError, KuruCopyTradingBotError)

    def test_transaction_failed_error_message(self):
        """Should preserve error message."""
        message = "Transaction reverted with reason: Insufficient balance"
        with pytest.raises(TransactionFailedError, match=message):
            raise TransactionFailedError(message)


class TestInsufficientGasError:
    """Test insufficient gas error."""

    def test_insufficient_gas_error_can_be_raised(self):
        """Should be able to raise InsufficientGasError."""
        with pytest.raises(InsufficientGasError):
            raise InsufficientGasError("Insufficient gas")

    def test_insufficient_gas_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(InsufficientGasError, KuruCopyTradingBotError)

    def test_insufficient_gas_error_message(self):
        """Should preserve error message."""
        message = "Insufficient gas: required 50000, available 30000"
        with pytest.raises(InsufficientGasError, match=message):
            raise InsufficientGasError(message)


class TestInsufficientBalanceError:
    """Test insufficient balance error."""

    def test_insufficient_balance_error_can_be_raised(self):
        """Should be able to raise InsufficientBalanceError."""
        with pytest.raises(InsufficientBalanceError):
            raise InsufficientBalanceError("Insufficient balance")

    def test_insufficient_balance_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(InsufficientBalanceError, KuruCopyTradingBotError)

    def test_insufficient_balance_error_message(self):
        """Should preserve error message."""
        message = "Insufficient balance: required 1000 USDC, available 500 USDC"
        with pytest.raises(InsufficientBalanceError, match=message):
            raise InsufficientBalanceError(message)


class TestOrderExecutionError:
    """Test order execution error."""

    def test_order_execution_error_can_be_raised(self):
        """Should be able to raise OrderExecutionError."""
        with pytest.raises(OrderExecutionError):
            raise OrderExecutionError("Order execution failed")

    def test_order_execution_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(OrderExecutionError, KuruCopyTradingBotError)

    def test_order_execution_error_message(self):
        """Should preserve error message."""
        message = "Failed to execute order: Market closed"
        with pytest.raises(OrderExecutionError, match=message):
            raise OrderExecutionError(message)


class TestTradeValidationError:
    """Test trade validation error."""

    def test_trade_validation_error_can_be_raised(self):
        """Should be able to raise TradeValidationError."""
        with pytest.raises(TradeValidationError):
            raise TradeValidationError("Validation failed")

    def test_trade_validation_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(TradeValidationError, KuruCopyTradingBotError)

    def test_trade_validation_error_message(self):
        """Should preserve error message."""
        message = "Trade validation failed: Size below minimum"
        with pytest.raises(TradeValidationError, match=message):
            raise TradeValidationError(message)


class TestInvalidMarketError:
    """Test invalid market error."""

    def test_invalid_market_error_can_be_raised(self):
        """Should be able to raise InvalidMarketError."""
        with pytest.raises(InvalidMarketError):
            raise InvalidMarketError("Invalid market")

    def test_invalid_market_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(InvalidMarketError, KuruCopyTradingBotError)

    def test_invalid_market_error_message(self):
        """Should preserve error message."""
        message = "Invalid market: INVALID-PAIR does not exist"
        with pytest.raises(InvalidMarketError, match=message):
            raise InvalidMarketError(message)


class TestConfigurationError:
    """Test configuration error."""

    def test_configuration_error_can_be_raised(self):
        """Should be able to raise ConfigurationError."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Configuration invalid")

    def test_configuration_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(ConfigurationError, KuruCopyTradingBotError)

    def test_configuration_error_message(self):
        """Should preserve error message."""
        message = "Configuration error: PRIVATE_KEY not set"
        with pytest.raises(ConfigurationError, match=message):
            raise ConfigurationError(message)


class TestInvalidOrderError:
    """Test invalid order error."""

    def test_invalid_order_error_can_be_raised(self):
        """Should be able to raise InvalidOrderError."""
        with pytest.raises(InvalidOrderError):
            raise InvalidOrderError("Invalid order")

    def test_invalid_order_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(InvalidOrderError, KuruCopyTradingBotError)

    def test_invalid_order_error_message(self):
        """Should preserve error message."""
        message = "Invalid order: Price must be positive"
        with pytest.raises(InvalidOrderError, match=message):
            raise InvalidOrderError(message)


class TestOrderPlacementError:
    """Test order placement error."""

    def test_order_placement_error_can_be_raised(self):
        """Should be able to raise OrderPlacementError."""
        with pytest.raises(OrderPlacementError):
            raise OrderPlacementError("Order placement failed")

    def test_order_placement_error_is_bot_exception(self):
        """Should be a subclass of KuruCopyTradingBotError."""
        assert issubclass(OrderPlacementError, KuruCopyTradingBotError)

    def test_order_placement_error_message(self):
        """Should preserve error message."""
        message = "Failed to place order: API rate limit exceeded"
        with pytest.raises(OrderPlacementError, match=message):
            raise OrderPlacementError(message)


class TestExceptionHierarchy:
    """Test exception hierarchy and inheritance."""

    def test_all_exceptions_inherit_from_base(self):
        """All custom exceptions should inherit from base exception."""
        exceptions = [
            InvalidStateTransitionError,
            BlockchainConnectionError,
            TransactionFailedError,
            InsufficientGasError,
            InsufficientBalanceError,
            OrderExecutionError,
            TradeValidationError,
            InvalidMarketError,
            ConfigurationError,
            InvalidOrderError,
            OrderPlacementError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, KuruCopyTradingBotError)
            assert issubclass(exc_class, Exception)

    def test_exceptions_can_be_caught_as_base_exception(self):
        """All custom exceptions can be caught as base exception."""
        exceptions_to_test = [
            InvalidStateTransitionError("test"),
            BlockchainConnectionError("test"),
            TransactionFailedError("test"),
            InsufficientGasError("test"),
            InsufficientBalanceError("test"),
            OrderExecutionError("test"),
            TradeValidationError("test"),
            InvalidMarketError("test"),
            ConfigurationError("test"),
            InvalidOrderError("test"),
            OrderPlacementError("test"),
        ]

        for exc in exceptions_to_test:
            with pytest.raises(KuruCopyTradingBotError):
                raise exc

    def test_exceptions_have_different_types(self):
        """Each exception should have a unique type."""
        exceptions = [
            InvalidStateTransitionError,
            BlockchainConnectionError,
            TransactionFailedError,
            InsufficientGasError,
            InsufficientBalanceError,
            OrderExecutionError,
            TradeValidationError,
            InvalidMarketError,
            ConfigurationError,
            InvalidOrderError,
            OrderPlacementError,
        ]

        # Each exception type should be unique
        assert len(exceptions) == len(set(exceptions))


class TestExceptionAttributes:
    """Test exception attributes and behavior."""

    def test_exception_str_representation(self):
        """Exceptions should have string representation."""
        exc = BlockchainConnectionError("Connection failed")
        assert str(exc) == "Connection failed"

    def test_exception_args_attribute(self):
        """Exceptions should store args."""
        message = "Test error"
        exc = InsufficientBalanceError(message)
        assert exc.args == (message,)

    def test_exception_with_multiple_args(self):
        """Exceptions should handle multiple arguments."""
        exc = OrderExecutionError("Failed", "Reason: Market closed")
        assert len(exc.args) == 2
        assert exc.args[0] == "Failed"
        assert exc.args[1] == "Reason: Market closed"

    def test_exception_repr(self):
        """Exceptions should have repr."""
        exc = TradeValidationError("Validation failed")
        repr_str = repr(exc)
        assert "TradeValidationError" in repr_str
        assert "Validation failed" in repr_str
