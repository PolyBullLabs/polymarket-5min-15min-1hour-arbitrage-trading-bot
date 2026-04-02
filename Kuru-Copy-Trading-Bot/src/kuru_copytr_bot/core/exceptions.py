"""Core exceptions for the Kuru copy trading bot."""


class KuruCopyTradingBotError(Exception):
    """Base exception for all bot errors."""

    pass


class InvalidStateTransitionError(KuruCopyTradingBotError):
    """Raised when an invalid state transition is attempted."""

    pass


class BlockchainConnectionError(KuruCopyTradingBotError):
    """Raised when blockchain connection fails."""

    pass


class TransactionFailedError(KuruCopyTradingBotError):
    """Raised when a transaction fails."""

    pass


class InsufficientGasError(KuruCopyTradingBotError):
    """Raised when there's insufficient gas for a transaction."""

    pass


class InsufficientBalanceError(KuruCopyTradingBotError):
    """Raised when there's insufficient balance for an operation."""

    pass


class OrderExecutionError(KuruCopyTradingBotError):
    """Raised when order execution fails."""

    pass


class TradeValidationError(KuruCopyTradingBotError):
    """Raised when trade validation fails."""

    pass


class InvalidMarketError(KuruCopyTradingBotError):
    """Raised when an invalid or unknown market is specified."""

    pass


class ConfigurationError(KuruCopyTradingBotError):
    """Raised when configuration is invalid."""

    pass


class InvalidOrderError(KuruCopyTradingBotError):
    """Raised when order parameters are invalid."""

    pass


class OrderPlacementError(KuruCopyTradingBotError):
    """Raised when order placement fails."""

    pass
