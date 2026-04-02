"""Copy trading bot orchestrator using blockchain event subscriptions."""

import asyncio
from decimal import Decimal
from typing import Any

from src.kuru_copytr_bot.connectors.blockchain.event_subscriber import (
    BlockchainEventSubscriber,
)
from src.kuru_copytr_bot.models.order import OrderResponse
from src.kuru_copytr_bot.models.trade import TradeResponse
from src.kuru_copytr_bot.trading.copier import TradeCopier
from src.kuru_copytr_bot.utils.logger import get_logger

logger = get_logger(__name__)


class CopyTradingBot:
    """Orchestrates copy trading workflow using blockchain events for real-time updates."""

    def __init__(
        self,
        event_subscribers: list[tuple[str, BlockchainEventSubscriber]] | None = None,
        source_wallets: list[str] | None = None,
        copier: TradeCopier | None = None,
        track_all_market_orders: bool = False,
    ):
        """Initialize copy trading bot.

        Args:
            event_subscribers: List of (market_address, BlockchainEventSubscriber) tuples
            source_wallets: List of source wallet addresses to monitor
            copier: Trade copier for executing mirror trades
            track_all_market_orders: If True, track all orders on market (not just source wallets)
        """
        self.event_subscribers = event_subscribers or []
        self.source_wallets = [addr.lower() for addr in (source_wallets or [])]
        self.copier = copier
        self.track_all_market_orders = track_all_market_orders

        if not copier:
            raise ValueError("copier is required")

        if not event_subscribers:
            raise ValueError("event_subscribers is required")

        # Validate source wallets requirement
        if not self.source_wallets and not track_all_market_orders:
            raise ValueError("source_wallets is required when track_all_market_orders is False")

        self.bot_wallet_address = self.copier.kuru_client.blockchain.wallet_address.lower()

        # Running state
        self.is_running = False

        # Statistics
        self._trades_detected = 0
        self._orders_detected = 0
        self._orders_canceled_detected = 0

        # Order tracking: maps source_order_id -> our_order_id
        # This allows us to cancel our orders when source trader cancels theirs
        self._order_mapping: dict[int, str] = {}

        # Set up event subscriber callbacks
        for market_address, subscriber in self.event_subscribers:
            # Create closures to capture market_address
            subscriber.set_order_created_callback(
                self._create_order_created_callback(market_address)
            )
            subscriber.set_trade_callback(self._create_trade_callback(market_address))
            subscriber.set_orders_canceled_callback(
                self._create_orders_canceled_callback(market_address)
            )

    def _create_trade_callback(self, market_address: str):
        """Create a trade callback that captures the market address.

        Trade events are used for FILL TRACKING only, not for copying.
        Copying happens via OrderCreated events to avoid duplicates.

        Trade event semantics:
        - makerAddress = owner of resting limit order (passive)
        - takerAddress = aggressor who hit the order (active)
        - isBuy = maker's side (not taker's)

        Args:
            market_address: Market contract address

        Returns:
            Async callback function for trade events
        """

        async def on_trade(trade_response: TradeResponse):
            """Handle Trade event from blockchain.

            This handler:
            1. Tracks fills on our own orders (for fill rate calculation)
            2. Logs source wallet fills (informational only)

            NOTE: We do NOT copy trades here. Copying happens via OrderCreated.
            If we copied here too, we'd duplicate orders (source places limit order
            → OrderCreated → we copy → order gets filled → Trade → we'd copy again).

            Args:
                trade_response: Trade data from blockchain event
            """
            try:
                maker_address = trade_response.makeraddress.lower()
                taker_address = trade_response.takeraddress.lower()

                # 1. Track fills on our own orders
                if maker_address == self.bot_wallet_address:
                    logger.debug(
                        "Own order filled",
                        order_id=trade_response.orderid,
                        filled_size=trade_response.filledsize,
                    )
                    try:
                        self.copier.order_tracker.on_fill(
                            order_id=str(trade_response.orderid),
                            filled_size=Decimal(trade_response.filledsize),
                        )
                        logger.info(
                            "Own fill tracked",
                            order_id=trade_response.orderid,
                            filled_size=trade_response.filledsize,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to track own fill",
                            error=str(e),
                            order_id=trade_response.orderid,
                            exc_info=True,
                        )
                    return

                # 2. Log source wallet fills (informational - copying via OrderCreated)
                if maker_address in self.source_wallets:
                    self._trades_detected += 1
                    trade = trade_response.to_trade(market=market_address)
                    logger.info(
                        "Source wallet order filled (passive)",
                        trade_id=trade.id,
                        market=trade.market,
                        side=trade.side.value,
                        size=str(trade.size),
                        price=str(trade.price),
                        tx_hash=trade.tx_hash,
                    )
                    # NOTE: Not calling copier.process_trade() - would duplicate
                    # orders already placed via OrderCreated handler
                    return

                # 3. Log if source is taker (market order or aggressive limit)
                if taker_address in self.source_wallets:
                    self._trades_detected += 1
                    logger.info(
                        "Source wallet filled order (aggressive)",
                        order_id=trade_response.orderid,
                        taker=taker_address,
                        filled_size=trade_response.filledsize,
                        price=trade_response.price,
                    )
                    # NOTE: Not copying market orders - by the time we see the trade,
                    # the opportunity is gone and we can't match the execution price.
                    # Could be added as a feature if needed.
                    return

                # 4. Handle track_all_market_orders mode (debugging/monitoring)
                if self.track_all_market_orders:
                    logger.debug(
                        "[MARKET-WIDE TRACKING] Trade from other wallet",
                        maker=trade_response.makeraddress,
                        taker=trade_response.takeraddress,
                        order_id=trade_response.orderid,
                    )

            except Exception as e:
                logger.error(
                    "Failed to process trade event",
                    error=str(e),
                    order_id=trade_response.orderid,
                    exc_info=True,
                )

        return on_trade

    def _create_order_created_callback(self, _market_address: str):
        """Create an order created callback that captures the market address.

        Args:
            _market_address: Market contract address

        Returns:
            Async callback function for OrderCreated events
        """

        async def on_order_created(order_response: OrderResponse):
            """Handle OrderCreated event from blockchain.

            Args:
                order_response: Order data from blockchain event
            """
            try:
                owner_address = order_response.owner.lower()

                # Skip wallet filtering if tracking all market orders
                if not self.track_all_market_orders and owner_address not in self.source_wallets:
                    logger.info(
                        "[SKIPPED] order_from_non_source_wallet",
                        owner=order_response.owner,
                        order_id=order_response.order_id,
                    )
                    return

                # Log when tracking all market orders
                if self.track_all_market_orders:
                    wallet_type = "SOURCE" if owner_address in self.source_wallets else "OTHER"
                    logger.debug(
                        f"[MARKET-WIDE TRACKING] Order from {wallet_type} wallet",
                        owner=order_response.owner,
                        order_id=order_response.order_id,
                    )

                # Convert OrderResponse to Order model
                order = order_response.to_order()

                self._orders_detected += 1
                logger.info(
                    "Order created detected",
                    order_id=order.order_id,
                    market=order.market,
                    side=order.side.value,
                    size=str(order.size),
                    price=str(order.price),
                )

                # Mirror the limit order
                try:
                    # Use copier to mirror the order (it will handle validation and sizing)
                    mirrored_order_id = self.copier.process_order(order)

                    if mirrored_order_id:
                        # Track the mapping for future cancellations
                        self._order_mapping[order_response.order_id] = mirrored_order_id
                        logger.info(
                            "Order mirrored successfully",
                            source_order_id=order_response.order_id,
                            mirrored_order_id=mirrored_order_id,
                        )
                except Exception as e:
                    # Copier handles its own errors internally
                    logger.debug("Copier raised exception (expected)", error=str(e))

            except Exception as e:
                # Failed to process order event
                logger.error(
                    "Failed to process OrderCreated event",
                    error=str(e),
                    order_id=order_response.order_id,
                    exc_info=True,
                )

        return on_order_created

    def _create_orders_canceled_callback(self, market_address: str):
        """Create an orders canceled callback that captures the market address.

        Args:
            market_address: Market contract address

        Returns:
            Async callback function for OrdersCanceled events
        """

        async def on_orders_canceled(
            order_ids: list[int],
            cloids: list[str],
            maker_address: str,
            _canceled_orders_data: list[dict],
        ):
            """Handle OrdersCanceled event from blockchain.

            Args:
                order_ids: List of canceled order IDs
                cloids: List of client order IDs
                maker_address: Maker wallet address
                _canceled_orders_data: Additional cancellation data
            """
            try:
                maker_lower = maker_address.lower()

                # Skip wallet filtering if tracking all market orders
                if not self.track_all_market_orders and maker_lower not in self.source_wallets:
                    logger.info(
                        "[SKIPPED] orders_canceled_from_non_source_wallet",
                        maker_address=maker_address,
                        order_count=len(order_ids),
                    )
                    return

                # Log when tracking all market orders
                if self.track_all_market_orders:
                    wallet_type = "SOURCE" if maker_lower in self.source_wallets else "OTHER"
                    logger.debug(
                        f"[MARKET-WIDE TRACKING] Orders canceled by {wallet_type} wallet",
                        maker_address=maker_address,
                        order_count=len(order_ids),
                    )

                self._orders_canceled_detected += len(order_ids)
                logger.info(
                    "Orders canceled detected",
                    order_count=len(order_ids),
                    order_ids=order_ids,
                    cloids=cloids,
                    maker_address=maker_address,
                )

                # Find our mirrored orders
                our_order_ids = []
                for source_order_id in order_ids:
                    if source_order_id in self._order_mapping:
                        our_order_id = self._order_mapping[source_order_id]
                        our_order_ids.append(our_order_id)
                        logger.debug(
                            "Mapped source order to our order",
                            source_order_id=source_order_id,
                            our_order_id=our_order_id,
                        )

                # Cancel our mirrored orders
                if our_order_ids:
                    try:
                        self.copier.cancel_orders(our_order_ids, market_address)
                        logger.info(
                            "Mirrored orders canceled successfully",
                            canceled_count=len(our_order_ids),
                            order_ids=our_order_ids,
                            market=market_address,
                        )

                        # Remove from tracking
                        for source_order_id in order_ids:
                            self._order_mapping.pop(source_order_id, None)
                    except Exception as e:
                        logger.error(
                            "Failed to cancel mirrored orders",
                            error=str(e),
                            order_ids=our_order_ids,
                            exc_info=True,
                        )
                else:
                    logger.debug(
                        "No mirrored orders found for canceled source orders",
                        source_order_ids=order_ids,
                    )

            except Exception as e:
                # Failed to process cancellation event
                logger.error(
                    "Failed to process OrdersCanceled event",
                    error=str(e),
                    order_ids=order_ids,
                    exc_info=True,
                )

        return on_orders_canceled

    async def start(self) -> None:
        """Start the copy trading bot and connect all event subscribers."""
        logger.info(
            "Starting copy trading bot",
            markets=len(self.event_subscribers),
            source_wallets=len(self.source_wallets),
        )

        # Connect all event subscribers
        connect_tasks = []
        for market_address, subscriber in self.event_subscribers:
            logger.debug("Connecting blockchain event subscriber", market=market_address)
            connect_tasks.append(subscriber.connect())

        # Connect all in parallel
        await asyncio.gather(*connect_tasks)

        self.is_running = True
        logger.info("Copy trading bot started successfully")

    async def stop(self) -> None:
        """Stop the copy trading bot and disconnect all event subscribers."""
        logger.info("Stopping copy trading bot")

        # Disconnect all event subscribers
        disconnect_tasks = []
        for market_address, subscriber in self.event_subscribers:
            logger.debug("Disconnecting blockchain event subscriber", market=market_address)
            disconnect_tasks.append(subscriber.disconnect())

        # Disconnect all in parallel
        await asyncio.gather(*disconnect_tasks)

        self.is_running = False
        logger.info("Copy trading bot stopped")

    async def run(self) -> None:
        """Run the bot indefinitely until stopped.

        This method starts the bot and keeps it running.
        Call stop() to gracefully shutdown.
        """
        await self.start()

        try:
            # Keep running until stop() is called
            while self.is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot cancelled, shutting down")
        finally:
            await self.stop()

    def get_statistics(self) -> dict[str, Any]:
        """Get bot statistics.

        Returns:
            Dictionary with bot and copier statistics
        """
        stats: dict[str, Any] = {
            "trades_detected": self._trades_detected,
            "orders_detected": self._orders_detected,
            "orders_canceled_detected": self._orders_canceled_detected,
            "tracked_orders": len(self._order_mapping),
        }

        copier_stats = self.copier.get_statistics()
        stats.update(copier_stats)

        stats["fill_rate"] = self.copier.order_tracker.get_fill_rate()
        stats["open_orders"] = len(self.copier.order_tracker.get_open_orders())

        return stats

    def reset_statistics(self) -> None:
        """Reset bot statistics."""
        self._trades_detected = 0
        self._orders_detected = 0
        self._orders_canceled_detected = 0
        self._order_mapping.clear()
        self.copier.reset_statistics()
