"""Trade copier for executing mirror trades."""

from decimal import Decimal

from src.kuru_copytr_bot.connectors.platforms.kuru import KuruClient
from src.kuru_copytr_bot.core.enums import OrderType
from src.kuru_copytr_bot.core.exceptions import (
    BlockchainConnectionError,
    InsufficientBalanceError,
    InvalidOrderError,
    OrderExecutionError,
    OrderPlacementError,
    TransactionFailedError,
)
from src.kuru_copytr_bot.models.order import Order
from src.kuru_copytr_bot.models.trade import Trade
from src.kuru_copytr_bot.risk.calculator import PositionSizeCalculator
from src.kuru_copytr_bot.risk.validator import TradeValidator
from src.kuru_copytr_bot.trading.order_tracker import OrderTracker
from src.kuru_copytr_bot.trading.retry_queue import RetryQueue
from src.kuru_copytr_bot.utils.logger import get_logger

logger = get_logger(__name__)


class TradeCopier:
    """Copies trades from source wallets with risk management."""

    def __init__(
        self,
        kuru_client: KuruClient,
        calculator: PositionSizeCalculator,
        validator: TradeValidator,
        order_tracker: OrderTracker | None = None,
        retry_queue: RetryQueue | None = None,
        default_order_type: OrderType = OrderType.LIMIT,
    ):
        """Initialize trade copier.

        Args:
            kuru_client: Kuru Exchange client for order execution
            calculator: Position size calculator
            validator: Trade validator
            order_tracker: Optional order tracker for fill tracking
            retry_queue: Optional retry queue for failed order management
            default_order_type: Default order type (LIMIT or MARKET)
        """
        self.kuru_client = kuru_client
        self.calculator = calculator
        self.validator = validator
        self.order_tracker = order_tracker or OrderTracker()
        self.retry_queue = retry_queue or RetryQueue()
        self.default_order_type = default_order_type

        # Statistics tracking
        self._successful_trades = 0
        self._failed_trades = 0
        self._rejected_trades = 0
        self._successful_orders = 0
        self._failed_orders = 0
        self._rejected_orders = 0
        self._orders_canceled = 0
        self._retried_orders = 0

    def process_trade(self, trade: Trade) -> str | None:
        """Process a single trade from source wallet.

        Args:
            trade: Trade detected from source wallet

        Returns:
            Order ID if successful, None otherwise
        """
        logger.info(
            "Processing trade for copying",
            trade_id=trade.id,
            market=trade.market,
            side=trade.side.value,
            size=str(trade.size),
            price=str(trade.price),
        )

        try:
            # Step 1: Get market params to determine quote asset
            market_params = self.kuru_client.get_market_params(trade.market)

            # Step 2: Get current margin balance for the quote asset
            balance = self.kuru_client.get_margin_balance(
                market_params.quote_asset, market_params.quote_asset_decimals
            )
            logger.debug(
                "Retrieved margin balance",
                balance=str(balance),
                quote_asset=market_params.quote_asset,
            )

            # Step 3: Calculate position size
            calculated_size = self.calculator.calculate(
                source_size=trade.size,
                available_balance=balance,
                price=trade.price,
            )

            # Log calculation details
            if calculated_size == 0:
                # Calculate what the trade would have been at each step
                raw_calculated = trade.size * self.calculator.copy_ratio
                raw_usd = raw_calculated * trade.price

                # Check if it would have been capped by max_position_size
                capped_usd = raw_usd
                if (
                    self.calculator.max_position_size
                    and raw_usd > self.calculator.max_position_size
                ):
                    capped_usd = self.calculator.max_position_size

                min_required = (
                    self.calculator.min_order_size
                    if self.calculator.min_order_size
                    else Decimal("0")
                )

                if balance < min_required:
                    logger.info(
                        "Insufficient balance for minimum order size, skipping trade",
                        trade_id=trade.id,
                        source_size=str(trade.size),
                        price=str(trade.price),
                        calculated_usd=f"{raw_usd:.2f}",
                        min_required_usd=f"{min_required:.2f}",
                        balance_usd=f"{balance:.2f}",
                    )
                else:
                    # Show capping in the message
                    if capped_usd < raw_usd:
                        logger.info(
                            "Order capped to max size, but still exceeds balance, skipping trade",
                            trade_id=trade.id,
                            source_size=str(trade.size),
                            price=str(trade.price),
                            raw_calculated_usd=f"{raw_usd:.2f}",
                            capped_to_max_usd=f"{capped_usd:.2f}",
                            balance_usd=f"{balance:.2f}",
                            copy_ratio=f"{float(self.calculator.copy_ratio * 100):.1f}%",
                        )
                    else:
                        logger.info(
                            "Insufficient balance for calculated order size, skipping trade",
                            trade_id=trade.id,
                            source_size=str(trade.size),
                            price=str(trade.price),
                            calculated_usd=f"{raw_usd:.2f}",
                            required_usd=f"{raw_usd:.2f}",
                            balance_usd=f"{balance:.2f}",
                            copy_ratio=f"{float(self.calculator.copy_ratio * 100):.1f}%",
                        )
                return None
            else:
                calculated_usd = calculated_size * trade.price
                logger.debug(
                    "Calculated position size",
                    source_size=str(trade.size),
                    calculated_size=str(calculated_size),
                    calculated_usd=str(calculated_usd),
                )

            # Step 3: Create mirror trade with calculated size
            mirror_trade = Trade(
                id=f"mirror_{trade.id}",
                trader_address=trade.trader_address,
                market=trade.market,
                side=trade.side,
                price=trade.price,
                size=calculated_size,
                timestamp=trade.timestamp,
                tx_hash=trade.tx_hash,
            )

            # Step 4: Validate trade
            validation_result = self.validator.validate(
                trade=mirror_trade,
                current_balance=balance,
            )

            if not validation_result.is_valid:
                self._rejected_trades += 1
                logger.warning(
                    "Trade validation failed, rejecting",
                    trade_id=trade.id,
                    reason=validation_result.reason,
                )
                return None

            logger.info(
                "Executing mirror trade",
                market=mirror_trade.market,
                side=mirror_trade.side.value,
                size=str(mirror_trade.size),
                price=str(mirror_trade.price),
                order_type=self.default_order_type.value,
            )

            # Step 6: Execute order
            if self.default_order_type == OrderType.LIMIT:
                order_id = self.kuru_client.place_limit_order(
                    market=trade.market,
                    side=trade.side,
                    size=calculated_size,
                    price=trade.price,
                )
            else:  # MARKET
                order_id = self.kuru_client.place_market_order(
                    market=trade.market,
                    side=trade.side,
                    size=calculated_size,
                )

            self.order_tracker.register_order(order_id=order_id, size=calculated_size)

            self._successful_trades += 1
            logger.debug(
                "Trade order placed and tracked",
                trade_id=trade.id,
                order_id=order_id,
                size=str(calculated_size),
            )
            return order_id

        except InsufficientBalanceError as e:
            self._failed_trades += 1
            logger.error(
                "Insufficient balance for trade",
                trade_id=trade.id,
                error=str(e),
            )
            return None
        except InvalidOrderError as e:
            self._failed_trades += 1
            logger.error(
                "Invalid order parameters",
                trade_id=trade.id,
                error=str(e),
            )
            return None
        except (BlockchainConnectionError, OrderPlacementError, TimeoutError) as e:
            if self.retry_queue.is_retriable(e):
                self.retry_queue.enqueue(mirror_trade, e)
                self.retry_queue.record_failure()
                logger.warning(
                    "Trade enqueued for retry",
                    trade_id=trade.id,
                    error_type=type(e).__name__,
                    error=str(e),
                )
            else:
                self._failed_trades += 1
                logger.error(
                    "Non-retriable error processing trade",
                    trade_id=trade.id,
                    error=str(e),
                )
            return None
        except Exception as e:
            self._failed_trades += 1
            logger.error(
                "Unexpected error processing trade",
                trade_id=trade.id,
                error=str(e),
                exc_info=True,
            )
            return None

    def process_trades(self, trades: list[Trade]) -> list[str]:
        """Process multiple trades in batch.

        Args:
            trades: List of trades to process

        Returns:
            List of order IDs for successful trades
        """
        order_ids = []

        for trade in trades:
            order_id = self.process_trade(trade)
            if order_id is not None:
                order_ids.append(order_id)

        return order_ids

    def process_order(self, order: Order) -> str | None:
        """Process a limit order from source wallet.

        Args:
            order: Order detected from source wallet

        Returns:
            Order ID if successful, None otherwise
        """
        logger.info(
            "Processing order for copying",
            order_id=order.order_id,
            market=order.market,
            side=order.side.value,
            size=str(order.size),
            price=str(order.price),
        )

        try:
            # Step 1: Get market params to determine quote asset
            market_params = self.kuru_client.get_market_params(order.market)

            # Step 2: Get current margin balance for the quote asset
            balance = self.kuru_client.get_margin_balance(
                market_params.quote_asset, market_params.quote_asset_decimals
            )
            logger.debug(
                "Retrieved margin balance",
                balance=str(balance),
                quote_asset=market_params.quote_asset,
            )

            # Step 3: Calculate position size
            calculated_size = self.calculator.calculate(
                source_size=order.size,
                available_balance=balance,
                price=order.price,
            )

            # Log calculation details
            if calculated_size == 0:
                # Calculate what the order would have been at each step
                raw_calculated = order.size * self.calculator.copy_ratio
                raw_usd = raw_calculated * order.price

                # Check if it would have been capped by max_position_size
                capped_usd = raw_usd
                if (
                    self.calculator.max_position_size
                    and raw_usd > self.calculator.max_position_size
                ):
                    capped_usd = self.calculator.max_position_size

                min_required = (
                    self.calculator.min_order_size
                    if self.calculator.min_order_size
                    else Decimal("0")
                )

                if balance < min_required:
                    logger.info(
                        "Insufficient balance for minimum order size, skipping order",
                        order_id=order.order_id,
                        source_size=str(order.size),
                        price=str(order.price),
                        calculated_usd=f"{raw_usd:.2f}",
                        min_required_usd=f"{min_required:.2f}",
                        balance_usd=f"{balance:.2f}",
                    )
                else:
                    # Show capping in the message
                    if capped_usd < raw_usd:
                        logger.info(
                            "Order capped to max size, but still exceeds balance, skipping order",
                            order_id=order.order_id,
                            source_size=str(order.size),
                            price=str(order.price),
                            raw_calculated_usd=f"{raw_usd:.2f}",
                            capped_to_max_usd=f"{capped_usd:.2f}",
                            balance_usd=f"{balance:.2f}",
                            copy_ratio=f"{float(self.calculator.copy_ratio * 100):.1f}%",
                        )
                    else:
                        logger.info(
                            "Insufficient balance for calculated order size, skipping order",
                            order_id=order.order_id,
                            source_size=str(order.size),
                            price=str(order.price),
                            calculated_usd=f"{raw_usd:.2f}",
                            required_usd=f"{raw_usd:.2f}",
                            balance_usd=f"{balance:.2f}",
                            copy_ratio=f"{float(self.calculator.copy_ratio * 100):.1f}%",
                        )
                return None
            else:
                calculated_usd = calculated_size * order.price
                logger.debug(
                    "Calculated position size",
                    source_size=str(order.size),
                    calculated_size=str(calculated_size),
                    calculated_usd=str(calculated_usd),
                )

            # Step 3: Create mirror order for validation
            # Create a temporary Order object with calculated size
            from src.kuru_copytr_bot.core.enums import OrderStatus, OrderType

            mirror_order = Order(
                order_id=f"mirror_{order.order_id}",
                order_type=OrderType.LIMIT,
                status=OrderStatus.PENDING,
                side=order.side,
                price=order.price,
                size=calculated_size,
                filled_size=Decimal("0"),
                market=order.market,
                created_at=order.created_at,
                updated_at=order.created_at,
            )

            # Step 4: Validate order
            validation_result = self.validator.validate_order(
                order=mirror_order,
                current_balance=balance,
            )

            if not validation_result.is_valid:
                self._rejected_orders += 1
                logger.warning(
                    "Order validation failed, rejecting",
                    order_id=order.order_id,
                    reason=validation_result.reason,
                )
                return None

            logger.info(
                "Executing mirror order",
                market=order.market,
                side=order.side.value,
                size=str(calculated_size),
                price=str(order.price),
            )

            # Step 5: Place limit order
            order_id = self.kuru_client.place_limit_order(
                market=order.market,
                side=order.side,
                size=calculated_size,
                price=order.price,
                post_only=True,  # Post-only (maker-only) orders
            )

            self.order_tracker.register_order(order_id=order_id, size=calculated_size)

            self._successful_orders += 1
            logger.debug(
                "Order placed and tracked",
                source_order_id=order.order_id,
                order_id=order_id,
                size=str(calculated_size),
            )
            return order_id

        except InsufficientBalanceError:
            self._rejected_orders += 1
            logger.warning(
                "Insufficient balance, skipping order",
                order_id=order.order_id,
                market=order.market,
                side=order.side.value,
                size=str(calculated_size),
                price=str(order.price),
            )
            return None
        except TransactionFailedError as e:
            # Transaction failures like nonce conflicts, gas issues - expected in high-speed trading
            self._failed_orders += 1
            error_msg = str(e)
            # Extract just the relevant message
            if "An existing transaction had higher priority" in error_msg:
                logger.warning("Nonce conflict, skipping order", order_id=order.order_id)
            elif "replacement transaction underpriced" in error_msg:
                logger.warning("Gas price too low, skipping order", order_id=order.order_id)
            else:
                logger.warning(
                    "Transaction failed, skipping order",
                    order_id=order.order_id,
                    reason=error_msg[:100],
                )
            return None
        except (OrderExecutionError, OrderPlacementError) as e:
            # Order execution issues - expected failures
            self._failed_orders += 1
            logger.warning(
                "Order execution failed, skipping",
                order_id=order.order_id,
                reason=str(e)[:100],
            )
            return None
        except InvalidOrderError as e:
            # Invalid parameters - should not happen, log as error
            self._failed_orders += 1
            logger.error(
                "Invalid order parameters",
                order_id=order.order_id,
                error=str(e),
            )
            return None
        except Exception as e:
            # Truly unexpected errors - log with full traceback
            self._failed_orders += 1
            logger.error(
                "Unexpected error processing order",
                order_id=order.order_id,
                error=str(e),
                exc_info=True,
            )
            return None

    def cancel_orders(self, order_ids: list[str], market_address: str) -> bool:
        """Cancel multiple orders.

        Args:
            order_ids: List of order IDs to cancel
            market_address: Market contract address where orders were placed

        Returns:
            True if successful, False otherwise
        """
        if not order_ids:
            logger.debug("No orders to cancel")
            return True

        logger.info(
            "Canceling orders",
            order_count=len(order_ids),
            order_ids=order_ids,
            market=market_address,
        )

        try:
            # Use batch cancel for efficiency
            tx_hash = self.kuru_client.cancel_orders(order_ids, market_address)

            self._orders_canceled += len(order_ids)

            # Remove canceled orders from tracker
            for order_id in order_ids:
                self.order_tracker.remove_order(order_id)

            logger.info(
                "Successfully canceled orders",
                order_count=len(order_ids),
                tx_hash=tx_hash,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to cancel orders",
                error=str(e),
                order_ids=order_ids,
                exc_info=True,
            )
            return False

    def process_retry_queue(self) -> None:
        """Process retry queue and attempt failed orders."""
        if self.retry_queue.is_circuit_open():
            logger.warning("Circuit breaker open, skipping retry processing")
            return

        due_retries = self.retry_queue.get_due_retries()

        if not due_retries:
            return

        logger.info("Processing retry queue", count=len(due_retries))

        for item in due_retries:
            trade = item["trade"]
            retry_count = item["retry_count"]

            if not self.retry_queue.should_retry(retry_count):
                logger.warning(
                    "Skipping retry, max attempts reached",
                    trade_id=trade.id,
                    retry_count=retry_count,
                )
                continue

            logger.info(
                "Retrying trade",
                trade_id=trade.id,
                retry_count=retry_count + 1,
            )

            try:
                # Get market params to determine quote asset
                market_params = self.kuru_client.get_market_params(trade.market)

                # Get margin balance for the quote asset
                balance = self.kuru_client.get_margin_balance(
                    market_params.quote_asset, market_params.quote_asset_decimals
                )

                calculated_size = self.calculator.calculate(
                    source_size=trade.size,
                    available_balance=balance,
                    price=trade.price,
                )

                if calculated_size == 0:
                    raw_calculated = trade.size * self.calculator.copy_ratio
                    raw_usd = raw_calculated * trade.price

                    # Check if it would have been capped by max_position_size
                    capped_usd = raw_usd
                    if (
                        self.calculator.max_position_size
                        and raw_usd > self.calculator.max_position_size
                    ):
                        capped_usd = self.calculator.max_position_size

                    min_required = (
                        self.calculator.min_order_size
                        if self.calculator.min_order_size
                        else Decimal("0")
                    )

                    if balance < min_required:
                        logger.info(
                            "Insufficient balance for minimum order size, skipping retry",
                            trade_id=trade.id,
                            calculated_usd=f"{raw_usd:.2f}",
                            min_required_usd=f"{min_required:.2f}",
                            balance_usd=f"{balance:.2f}",
                        )
                    else:
                        # Show capping in the message
                        if capped_usd < raw_usd:
                            logger.info(
                                "Order capped to max size, but still exceeds balance, skipping retry",
                                trade_id=trade.id,
                                raw_calculated_usd=f"{raw_usd:.2f}",
                                capped_to_max_usd=f"{capped_usd:.2f}",
                                balance_usd=f"{balance:.2f}",
                                copy_ratio=f"{float(self.calculator.copy_ratio * 100):.1f}%",
                            )
                        else:
                            logger.info(
                                "Insufficient balance for calculated order size, skipping retry",
                                trade_id=trade.id,
                                calculated_usd=f"{raw_usd:.2f}",
                                required_usd=f"{raw_usd:.2f}",
                                balance_usd=f"{balance:.2f}",
                                copy_ratio=f"{float(self.calculator.copy_ratio * 100):.1f}%",
                            )
                    continue

                validation_result = self.validator.validate(
                    trade=trade,
                    current_balance=balance,
                )

                if not validation_result.is_valid:
                    logger.warning(
                        "Trade validation failed on retry, skipping",
                        trade_id=trade.id,
                        reason=validation_result.reason,
                    )
                    continue

                if self.default_order_type == OrderType.LIMIT:
                    order_id = self.kuru_client.place_limit_order(
                        market=trade.market,
                        side=trade.side,
                        size=calculated_size,
                        price=trade.price,
                    )
                else:
                    order_id = self.kuru_client.place_market_order(
                        market=trade.market,
                        side=trade.side,
                        size=calculated_size,
                    )

                self.order_tracker.register_order(order_id=order_id, size=calculated_size)
                self.retry_queue.record_success()
                self._successful_trades += 1
                self._retried_orders += 1

                logger.info(
                    "Successfully retried trade",
                    trade_id=trade.id,
                    order_id=order_id,
                    retry_count=retry_count + 1,
                )

            except (BlockchainConnectionError, OrderPlacementError, TimeoutError) as e:
                if self.retry_queue.is_retriable(e):
                    self.retry_queue.mark_failed(item)
                    logger.warning(
                        "Retry failed, re-enqueueing",
                        trade_id=trade.id,
                        retry_count=retry_count + 1,
                        error=str(e),
                    )
                else:
                    self._failed_trades += 1
                    logger.error(
                        "Retry failed with non-retriable error",
                        trade_id=trade.id,
                        error=str(e),
                    )

            except Exception as e:
                self._failed_trades += 1
                logger.error(
                    "Unexpected error during retry",
                    trade_id=trade.id,
                    error=str(e),
                    exc_info=True,
                )

    def get_statistics(self) -> dict[str, int]:
        """Get trade and order statistics.

        Returns:
            Dictionary with successful, failed, and rejected counts
        """
        retry_stats = self.retry_queue.get_statistics()

        return {
            "successful_trades": self._successful_trades,
            "failed_trades": self._failed_trades,
            "rejected_trades": self._rejected_trades,
            "successful_orders": self._successful_orders,
            "failed_orders": self._failed_orders,
            "rejected_orders": self._rejected_orders,
            "orders_canceled": self._orders_canceled,
            "retried_orders": self._retried_orders,
            "retry_queue_size": retry_stats["queue_size"],
            "dead_letter_size": retry_stats["dead_letter_size"],
            "circuit_open": retry_stats["circuit_open"],
        }

    def reset_statistics(self) -> None:
        """Reset trade and order statistics."""
        self._successful_trades = 0
        self._failed_trades = 0
        self._rejected_trades = 0
        self._successful_orders = 0
        self._failed_orders = 0
        self._rejected_orders = 0
        self._orders_canceled = 0
        self._retried_orders = 0
