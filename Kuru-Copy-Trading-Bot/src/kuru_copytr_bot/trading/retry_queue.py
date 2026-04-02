"""Retry queue for failed order management."""

import time
from dataclasses import dataclass, field
from typing import Any

from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientBalanceError,
    InvalidOrderError,
    OrderPlacementError,
)
from src.kuru_copytr_bot.models.trade import Trade
from src.kuru_copytr_bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetryItem:
    """Item in retry queue."""

    trade: Trade
    error: str
    error_type: str
    retry_count: int
    next_retry_time: float
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "trade": self.trade,
            "error": self.error,
            "error_type": self.error_type,
            "retry_count": self.retry_count,
            "next_retry_time": self.next_retry_time,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class RetryQueue:
    """Queue for managing failed orders with exponential backoff and circuit breaker."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        circuit_breaker_threshold: int = 10,
        circuit_breaker_window: int = 60,
        circuit_breaker_cooldown: float = 300.0,
    ):
        """Initialize retry queue.

        Args:
            max_retries: Maximum retry attempts per order
            base_delay: Base delay in seconds for first retry
            backoff_multiplier: Multiplier for exponential backoff
            circuit_breaker_threshold: Failures to trigger circuit breaker
            circuit_breaker_window: Time window for counting failures (seconds)
            circuit_breaker_cooldown: Time before circuit breaker auto-resets (seconds)
        """
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._backoff_multiplier = backoff_multiplier
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_window = circuit_breaker_window
        self._circuit_breaker_cooldown = circuit_breaker_cooldown

        self._queue: list[RetryItem] = []
        self._dead_letter_queue: list[RetryItem] = []

        self._failure_timestamps: list[float] = []
        self._circuit_open_time: float | None = None

    def enqueue(
        self,
        trade: Trade,
        error: Exception,
        retry_count: int = 0,
        next_retry_time: float | None = None,
    ) -> None:
        """Add failed order to retry queue.

        Args:
            trade: Trade that failed
            error: Exception that caused the failure
            retry_count: Current retry count
            next_retry_time: Optional override for next retry time
        """
        if next_retry_time is None:
            delay = self.calculate_backoff(retry_count)
            next_retry_time = time.time() + delay

        retry_item = RetryItem(
            trade=trade,
            error=str(error),
            error_type=type(error).__name__,
            retry_count=retry_count,
            next_retry_time=next_retry_time,
        )

        self._queue.append(retry_item)

        logger.debug(
            "Enqueued order for retry",
            trade_id=trade.id,
            retry_count=retry_count,
            next_retry_time=next_retry_time,
            error_type=retry_item.error_type,
        )

    def dequeue(self) -> dict[str, Any] | None:
        """Remove and return next item from queue.

        Returns:
            Dictionary representation of RetryItem, or None if queue empty
        """
        if not self._queue:
            return None

        retry_item = self._queue.pop(0)
        return retry_item.to_dict()

    def peek(self) -> dict[str, Any] | None:
        """View first item without removing.

        Returns:
            Dictionary representation of RetryItem, or None if queue empty
        """
        if not self._queue:
            return None

        return self._queue[0].to_dict()

    def calculate_backoff(self, retry_count: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            retry_count: Current retry attempt number

        Returns:
            Delay in seconds
        """
        return self._base_delay * (self._backoff_multiplier**retry_count)

    def should_retry(self, retry_count: int) -> bool:
        """Check if retry should be attempted.

        Args:
            retry_count: Current retry count

        Returns:
            True if retry should be attempted
        """
        if retry_count >= self._max_retries:
            return False

        if self.is_circuit_open():
            logger.warning("Circuit breaker open, rejecting retry")
            return False

        return True

    def is_retriable(self, error: Exception) -> bool:
        """Check if error type is retriable.

        Args:
            error: Exception to check

        Returns:
            True if error is retriable
        """
        retriable_errors = (
            BlockchainConnectionError,
            OrderPlacementError,
            TimeoutError,
        )

        non_retriable_errors = (
            InsufficientBalanceError,
            InvalidOrderError,
        )

        if isinstance(error, retriable_errors):
            return True

        if isinstance(error, non_retriable_errors):
            return False

        return False

    def mark_failed(self, item: dict[str, Any]) -> None:
        """Mark retry as failed and update retry count.

        Args:
            item: Retry item that failed
        """
        retry_count = item["retry_count"] + 1

        if retry_count >= self._max_retries:
            retry_item = RetryItem(
                trade=item["trade"],
                error=item["error"],
                error_type=item["error_type"],
                retry_count=retry_count,
                next_retry_time=item["next_retry_time"],
                created_at=item["created_at"],
                updated_at=time.time(),
            )
            self._dead_letter_queue.append(retry_item)
            logger.warning(
                "Order moved to dead letter queue after max retries",
                trade_id=item["trade"].id,
                retry_count=retry_count,
            )
        else:
            self.enqueue(
                trade=item["trade"],
                error=Exception(item["error"]),
                retry_count=retry_count,
            )

        self.record_failure()

    def get_due_retries(self) -> list[dict[str, Any]]:
        """Get orders ready for retry.

        Returns:
            List of retry items past their retry time
        """
        current_time = time.time()
        due_items = []

        remaining_items = []
        for retry_item in self._queue:
            if retry_item.next_retry_time <= current_time:
                due_items.append(retry_item.to_dict())
            else:
                remaining_items.append(retry_item)

        self._queue = remaining_items

        return due_items

    def record_failure(self) -> None:
        """Record a failure for circuit breaker tracking."""
        current_time = time.time()
        cutoff_time = current_time - self._circuit_breaker_window

        self._failure_timestamps = [ts for ts in self._failure_timestamps if ts > cutoff_time]
        self._failure_timestamps.append(current_time)

        if len(self._failure_timestamps) >= self._circuit_breaker_threshold:
            self._circuit_open_time = current_time
            logger.warning(
                "Circuit breaker opened",
                failures=len(self._failure_timestamps),
                threshold=self._circuit_breaker_threshold,
            )

    def record_success(self) -> None:
        """Record a success, resetting circuit breaker."""
        self._failure_timestamps.clear()
        self._circuit_open_time = None
        logger.debug("Circuit breaker reset after success")

    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open.

        Returns:
            True if circuit breaker is open
        """
        if self._circuit_open_time is None:
            return False

        elapsed = time.time() - self._circuit_open_time

        if elapsed >= self._circuit_breaker_cooldown:
            self._circuit_open_time = None
            self._failure_timestamps.clear()
            logger.info("Circuit breaker auto-reset after cooldown")
            return False

        return True

    def size(self) -> int:
        """Get current queue size.

        Returns:
            Number of items in retry queue
        """
        return len(self._queue)

    def dead_letter_size(self) -> int:
        """Get dead letter queue size.

        Returns:
            Number of items in dead letter queue
        """
        return len(self._dead_letter_queue)

    def get_statistics(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary with queue metrics
        """
        return {
            "queue_size": self.size(),
            "dead_letter_size": self.dead_letter_size(),
            "circuit_open": self.is_circuit_open(),
            "failure_count": len(self._failure_timestamps),
        }
