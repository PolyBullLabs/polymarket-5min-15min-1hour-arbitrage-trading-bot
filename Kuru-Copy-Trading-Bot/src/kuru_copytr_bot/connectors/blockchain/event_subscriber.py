"""Blockchain event subscriber using eth_subscribe for real-time contract events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import TYPE_CHECKING, Any

from web3 import Web3
from websockets import connect
from websockets.exceptions import ConnectionClosedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from websockets.asyncio.client import ClientConnection

from src.kuru_copytr_bot.models.order import OrderResponse
from src.kuru_copytr_bot.models.trade import TradeResponse
from src.kuru_copytr_bot.utils.logger import get_logger

logger = get_logger(__name__)


class BlockchainEventSubscriber:
    """Subscribes to blockchain contract events using eth_subscribe.

    Listens to OrderBook contract events directly from blockchain RPC:
    - OrderCreated
    - Trade
    - OrdersCanceled
    """

    def __init__(
        self,
        rpc_ws_url: str,
        market_address: str,
        orderbook_abi: list[dict[str, Any]],
        size_precision: int,
        price_precision: int,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
    ):
        """Initialize event subscriber.

        Args:
            rpc_ws_url: WebSocket RPC URL (e.g., wss://monad-testnet.drpc.org)
            market_address: OrderBook contract address to monitor
            orderbook_abi: OrderBook contract ABI for event parsing
            size_precision: Size precision multiplier from market params (e.g., 10^11)
            price_precision: Price precision multiplier from market params (e.g., 10^7)
            max_reconnect_attempts: Maximum number of reconnection attempts (0 = infinite)
            reconnect_delay: Initial delay between reconnection attempts in seconds
        """
        self.rpc_ws_url = rpc_ws_url
        self.market_address = market_address.lower()
        self.orderbook_abi = orderbook_abi
        self.size_precision = size_precision
        self.price_precision = price_precision
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        # WebSocket connection
        self.ws: ClientConnection | None = None
        self.subscription_id: str | None = None
        self.running = False
        self._reconnect_attempts = 0

        # Web3 instance for event parsing (no provider needed)
        self.w3 = Web3()
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(market_address), abi=orderbook_abi
        )

        # Event signatures (keccak256 of event signature)
        # Compute event signature hashes from event ABIs
        self.event_signatures = {}
        for event_name in ["OrderCreated", "Trade", "OrdersCanceled"]:
            event = getattr(self.contract.events, event_name)
            event_abi = event._get_event_abi()
            # Build event signature string: EventName(type1,type2,...)
            input_types = ",".join([inp["type"] for inp in event_abi["inputs"]])
            event_signature = f"{event_abi['name']}({input_types})"
            # Compute keccak256 hash
            signature_hash = self.w3.keccak(text=event_signature).hex()
            self.event_signatures[event_name] = signature_hash

            logger.debug(
                "Computed event signature hash",
                event_name=event_name,
                signature=event_signature,
                hash=signature_hash,
            )

        # Callbacks (async)
        self.on_order_created_callback: Callable[[OrderResponse], Awaitable[None]] | None = None
        self.on_trade_callback: Callable[[TradeResponse], Awaitable[None]] | None = None
        self.on_orders_canceled_callback: (
            Callable[[list[int], list[str], str, list[dict[str, Any]]], Awaitable[None]] | None
        ) = None

    async def connect(self) -> None:
        """Connect to blockchain RPC and subscribe to logs."""
        try:
            logger.info("blockchain_event_subscriber_connecting", url=self.rpc_ws_url)

            # Connect to WebSocket RPC
            self.ws = await connect(self.rpc_ws_url)

            # Subscribe to logs from the OrderBook contract
            subscribe_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": self.market_address,
                        # No topics filter - get all events from this contract
                    },
                ],
            }

            await self.ws.send(json.dumps(subscribe_request))
            response = await self.ws.recv()
            response_data = json.loads(response)

            if "result" in response_data:
                self.subscription_id = response_data["result"]
                logger.info(
                    "blockchain_subscription_created",
                    subscription_id=self.subscription_id,
                    market=self.market_address,
                )
            else:
                error = response_data.get("error", "Unknown error")
                raise Exception(f"Failed to subscribe: {error}")

            # Start listening loop
            self.running = True
            self._listen_task = asyncio.create_task(self._listen_loop())

        except Exception as e:
            logger.error(
                "blockchain_subscription_failed",
                error=str(e),
                url=self.rpc_ws_url,
                exc_info=True,
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from blockchain RPC."""
        self.running = False

        if self.ws and self.subscription_id:
            try:
                # Unsubscribe
                unsubscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_unsubscribe",
                    "params": [self.subscription_id],
                }
                await self.ws.send(json.dumps(unsubscribe_request))
                await self.ws.close()
                logger.info("blockchain_subscription_closed")
            except Exception as e:
                logger.warning("blockchain_unsubscribe_error", error=str(e))

    async def _reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff.

        Returns:
            True if reconnection successful, False otherwise
        """
        while self.running:
            self._reconnect_attempts += 1

            # Check if we've exceeded max attempts (0 = infinite)
            if (
                self.max_reconnect_attempts > 0
                and self._reconnect_attempts > self.max_reconnect_attempts
            ):
                logger.error(
                    "max_reconnect_attempts_reached",
                    attempts=self._reconnect_attempts,
                    market=self.market_address,
                )
                return False

            # Calculate backoff delay (exponential with max 60s)
            delay = min(self.reconnect_delay * (2 ** (self._reconnect_attempts - 1)), 60)
            logger.info(
                "attempting_reconnection",
                attempt=self._reconnect_attempts,
                delay_seconds=delay,
                market=self.market_address,
            )

            await asyncio.sleep(delay)

            try:
                # Close existing connection if any
                if self.ws:
                    with contextlib.suppress(Exception):
                        await self.ws.close()
                    self.ws = None
                    self.subscription_id = None

                # Reconnect
                self.ws = await connect(self.rpc_ws_url)

                # Re-subscribe
                subscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": [
                        "logs",
                        {
                            "address": self.market_address,
                        },
                    ],
                }

                await self.ws.send(json.dumps(subscribe_request))
                response = await self.ws.recv()
                response_data = json.loads(response)

                if "result" in response_data:
                    self.subscription_id = response_data["result"]
                    logger.info(
                        "websocket_resubscribed",
                        subscription_id=self.subscription_id,
                        market=self.market_address,
                    )
                    return True
                else:
                    error = response_data.get("error", "Unknown error")
                    logger.error(
                        "resubscription_failed",
                        error=error,
                        market=self.market_address,
                    )
                    continue

            except Exception as e:
                logger.warning(
                    "reconnection_attempt_failed",
                    attempt=self._reconnect_attempts,
                    error=str(e),
                    market=self.market_address,
                )
                continue

        return False

    async def _listen_loop(self) -> None:
        """Listen for incoming log events with automatic reconnection."""
        while self.running:
            try:
                if not self.ws:
                    break

                raw_message = await self.ws.recv()
                message = raw_message if isinstance(raw_message, str) else raw_message.decode()
                await self._process_message(message)

                # Reset reconnect attempts on successful message
                self._reconnect_attempts = 0

            except ConnectionClosedError as e:
                if self.running:
                    logger.warning(
                        "websocket_connection_closed",
                        error=str(e),
                        market=self.market_address,
                        reconnect_attempts=self._reconnect_attempts,
                    )
                    # Attempt to reconnect
                    if await self._reconnect():
                        logger.info(
                            "websocket_reconnected_successfully",
                            market=self.market_address,
                        )
                    else:
                        logger.error(
                            "websocket_reconnection_failed",
                            market=self.market_address,
                            max_attempts=self.max_reconnect_attempts,
                        )
                        break
            except Exception as e:
                if self.running:
                    logger.error(
                        "blockchain_listen_error",
                        error=str(e),
                        market=self.market_address,
                        exc_info=True,
                    )

    async def _process_message(self, message: str) -> None:
        """Process incoming log message.

        Args:
            message: JSON-RPC notification message
        """
        try:
            data = json.loads(message)

            # Check if this is a subscription notification
            if "params" not in data or "result" not in data["params"]:
                return

            log_entry = data["params"]["result"]

            # Parse the log entry
            await self._parse_log(log_entry)

        except Exception as e:
            logger.error("message_parse_error", error=str(e), message=message)

    async def _parse_log(self, log_entry: dict[str, Any]) -> None:
        """Parse log entry and call appropriate callback.

        Args:
            log_entry: Raw log entry from eth_subscribe
        """
        try:
            # Get the event signature (first topic)
            if not log_entry.get("topics") or len(log_entry["topics"]) == 0:
                return

            # Normalize event signature - remove 0x prefix if present for comparison
            event_signature = log_entry["topics"][0]
            if isinstance(event_signature, str) and event_signature.startswith("0x"):
                event_signature = event_signature[2:]

            # Identify which event this is
            if event_signature == self.event_signatures["OrderCreated"]:
                await self._handle_order_created(log_entry)
            elif event_signature == self.event_signatures["Trade"]:
                await self._handle_trade(log_entry)
            elif event_signature == self.event_signatures["OrdersCanceled"]:
                await self._handle_orders_canceled(log_entry)
            else:
                logger.debug("unknown_event_signature", signature=event_signature)

        except Exception as e:
            logger.error("log_parse_error", error=str(e), log=log_entry, exc_info=True)

    async def _handle_order_created(self, log_entry: dict[str, Any]) -> None:
        """Handle OrderCreated event.

        OrderCreated ABI fields:
        - orderId (uint40)
        - owner (address)
        - size (uint96) - 18 decimal precision
        - price (uint32) - 6 decimal precision
        - isBuy (bool)

        Note: remainingSize, isCanceled, cloid are NOT in the ABI.
        For new orders, remaining_size = size and is_canceled = False.

        Args:
            log_entry: Raw log entry
        """
        try:
            # Decode the event using Web3
            event = self.contract.events.OrderCreated().process_log(log_entry)
            args = event["args"]

            # Convert size and price using market-specific precisions
            size_decimal = args["size"] / self.size_precision
            price_decimal = args["price"] / self.price_precision

            # Create OrderResponse from event args
            order_response = OrderResponse(
                order_id=args["orderId"],
                market_address=self.market_address,
                owner=args["owner"],
                price=str(price_decimal),
                size=str(size_decimal),
                remaining_size=str(size_decimal),  # New order: remaining = full size
                is_buy=args["isBuy"],
                is_canceled=False,  # New order is not canceled
                transaction_hash=log_entry["transactionHash"],
                trigger_time=int(time.time()),  # Use current time (not in event)
                cloid=None,  # Not available in blockchain event
            )

            logger.info(
                "order_created_event",
                order_id=order_response.order_id,
                owner=order_response.owner,
                side="BUY" if order_response.is_buy else "SELL",
                price=order_response.price,
                size=order_response.size,
            )

            # Call callback
            if self.on_order_created_callback:
                await self.on_order_created_callback(order_response)

        except Exception as e:
            logger.error("order_created_parse_error", error=str(e), log=log_entry)

    async def _handle_trade(self, log_entry: dict[str, Any]) -> None:
        """Handle Trade event.

        Trade ABI fields:
        - orderId (uint40)
        - makerAddress (address)
        - isBuy (bool)
        - price (uint256) - uses SIZE precision (not price precision!)
        - updatedSize (uint96) - remaining size after fill, 18 decimals
        - takerAddress (address)
        - txOrigin (address)
        - filledSize (uint96) - size filled in this trade, 18 decimals

        Args:
            log_entry: Raw log entry
        """
        try:
            # Decode the event using Web3
            event = self.contract.events.Trade().process_log(log_entry)
            args = event["args"]

            # Create TradeResponse from event args
            # Note: Trade event price uses BOTH size_precision AND price_precision
            trade_response = TradeResponse(
                orderid=args["orderId"],
                market_address=self.market_address,
                makeraddress=args["makerAddress"],
                takeraddress=args["takerAddress"],
                isbuy=args["isBuy"],
                price=str(args["price"] / (self.size_precision * self.price_precision)),
                filledsize=str(args["filledSize"] / self.size_precision),
                transactionhash=log_entry["transactionHash"],
                triggertime=int(time.time()),  # Use current time (not in event)
                cloid=None,  # Not available in blockchain event
            )

            logger.info(
                "trade_event",
                order_id=trade_response.orderid,
                maker=trade_response.makeraddress,
                side="BUY" if trade_response.isbuy else "SELL",
                price=trade_response.price,
                filled_size=trade_response.filledsize,
            )

            # Call callback
            if self.on_trade_callback:
                await self.on_trade_callback(trade_response)

        except Exception as e:
            logger.error("trade_parse_error", error=str(e), log=log_entry)

    async def _handle_orders_canceled(self, log_entry: dict[str, Any]) -> None:
        """Handle OrdersCanceled event.

        OrdersCanceled ABI fields:
        - orderId (uint40[]) - array of canceled order IDs (note: singular name)
        - owner (address) - wallet that canceled the orders

        Note: cloids is NOT in the ABI.

        Args:
            log_entry: Raw log entry
        """
        try:
            # Decode the event using Web3
            event = self.contract.events.OrdersCanceled().process_log(log_entry)
            args = event["args"]

            # ABI uses 'orderId' (singular) for the array, and 'owner' not 'maker'
            order_ids = list(args["orderId"])  # Convert tuple to list
            owner_address = args["owner"]

            logger.info(
                "orders_canceled_event",
                order_count=len(order_ids),
                order_ids=order_ids,
                owner_address=owner_address,
            )

            # Call callback with empty cloids (not available in blockchain event)
            if self.on_orders_canceled_callback:
                await self.on_orders_canceled_callback(order_ids, [], owner_address, [])

        except Exception as e:
            logger.error("orders_canceled_parse_error", error=str(e), log=log_entry)

    def set_order_created_callback(
        self, callback: Callable[[OrderResponse], Awaitable[None]]
    ) -> None:
        """Set callback for OrderCreated events."""
        self.on_order_created_callback = callback

    def set_trade_callback(self, callback: Callable[[TradeResponse], Awaitable[None]]) -> None:
        """Set callback for Trade events."""
        self.on_trade_callback = callback

    def set_orders_canceled_callback(
        self,
        callback: Callable[[list[int], list[str], str, list[dict[str, Any]]], Awaitable[None]],
    ) -> None:
        """Set callback for OrdersCanceled events."""
        self.on_orders_canceled_callback = callback

    @property
    def is_connected(self) -> bool:
        """Check if connected to blockchain."""
        return self.ws is not None and self.running
