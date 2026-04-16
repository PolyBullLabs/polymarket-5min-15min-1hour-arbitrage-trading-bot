#!/usr/bin/env python3
"""WebSocket Client for Market + User channels."""
import asyncio, json, logging, time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Callable, Set
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger("btc_live.websocket")
MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
USER_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSED = "closed"

@dataclass
class TradeEvent:
    token_id: str; price: float; size: float; side: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PriceUpdate:
    token_id: str; best_bid: float; best_ask: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class OrderUpdate:
    order_id: str
    asset_id: str
    side: str
    price: float
    original_size: float
    size_matched: float
    event_type: str
    status: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TradeUpdate:
    trade_id: str
    asset_id: str
    price: float
    size: float
    side: str
    status: str
    taker_order_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class MarketWebSocket:
    """WebSocket client for Market channel."""
    
    def __init__(self, on_trade=None, on_price=None, reconnect_delay=1.0, max_reconnect_delay=60.0):
        self.on_trade = on_trade
        self.on_price = on_price
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self._ws = None
        self._state = ConnectionState.DISCONNECTED
        self._subscribed_tokens: Set[str] = set()
        self._running = False
        self._reconnect_count = 0
        self.messages_received = 0
        self.trades_received = 0
    
    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED
    
    async def connect(self, token_ids: List[str]) -> bool:
        if not token_ids:
            return False
        self._subscribed_tokens = set(token_ids)
        self._state = ConnectionState.CONNECTING
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(MARKET_WS_URL, ping_interval=20, ping_timeout=10),
                timeout=30
            )
            await self._ws.send(json.dumps({"type": "market", "assets_ids": list(token_ids)}))
            self._state = ConnectionState.CONNECTED
            self._reconnect_count = 0
            logger.info(f"Market WS connected, subscribed to {len(token_ids)} tokens")
            return True
        except Exception as e:
            logger.error(f"Market WS connect error: {e}")
            self._state = ConnectionState.DISCONNECTED
            return False
    
    async def _process_message(self, data):
        try:
            items = data if isinstance(data, list) else [data]
            for item in items:
                event_type = item.get("event_type", "")
                if event_type == "last_trade_price":
                    trade = TradeEvent(
                        token_id=item.get("asset_id", ""),
                        price=float(item.get("price", 0)),
                        size=float(item.get("size", 0)),
                        side=item.get("side", ""),
                    )
                    self.trades_received += 1
                    if self.on_trade:
                        if asyncio.iscoroutinefunction(self.on_trade):
                            await self.on_trade(trade)
                        else:
                            self.on_trade(trade)
                elif event_type == "best_bid_ask":
                    update = PriceUpdate(
                        token_id=item.get("asset_id", ""),
                        best_bid=float(item.get("best_bid", 0) or 0),
                        best_ask=float(item.get("best_ask", 0) or 0),
                    )
                    if self.on_price:
                        if asyncio.iscoroutinefunction(self.on_price):
                            await self.on_price(update)
                        else:
                            self.on_price(update)
        except Exception as e:
            logger.error(f"Process error: {e}")
    
    async def _receive_loop(self):
        while self._running and self._ws:
            try:
                msg = await asyncio.wait_for(self._ws.recv(), timeout=30)
                self.messages_received += 1
                await self._process_message(json.loads(msg))
            except asyncio.TimeoutError:
                if self._ws and self._ws.open:
                    try:
                        await asyncio.wait_for(self._ws.ping(), timeout=5)
                    except:
                        break
                else:
                    break
            except ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break
    
    async def run_loop(self, token_ids: List[str]):
        self._running = True
        self._subscribed_tokens = set(token_ids)
        while self._running:
            try:
                if not await self.connect(list(self._subscribed_tokens)):
                    delay = min(self.reconnect_delay * (2 ** self._reconnect_count), self.max_reconnect_delay)
                    await asyncio.sleep(delay)
                    self._reconnect_count += 1
                    continue
                await self._receive_loop()
                if self._running:
                    delay = min(self.reconnect_delay * (2 ** self._reconnect_count), self.max_reconnect_delay)
                    await asyncio.sleep(delay)
                    self._reconnect_count += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(self.reconnect_delay)
        await self.close()
    
    async def close(self):
        self._running = False
        self._state = ConnectionState.CLOSED
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except:
                pass
        self._ws = None
    
    def stop(self):
        self._running = False


class UserWebSocket:
    """WebSocket client for User channel with auth."""
    
    def __init__(self, api_key, api_secret, api_passphrase, on_order=None, on_trade=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.on_order = on_order
        self.on_trade = on_trade
        self._ws = None
        self._state = ConnectionState.DISCONNECTED
        self._running = False
        self._reconnect_count = 0
        self._pending_orders: Dict[str, OrderUpdate] = {}
        self.messages_received = 0
    
    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED
    
    async def connect(self) -> bool:
        self._state = ConnectionState.CONNECTING
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(USER_WS_URL, ping_interval=20, ping_timeout=10),
                timeout=30
            )
            msg = {
                "type": "user",
                "markets": [],
                "auth": {"apikey": self.api_key, "secret": self.api_secret, "passphrase": self.api_passphrase}
            }
            await self._ws.send(json.dumps(msg))
            self._state = ConnectionState.CONNECTED
            self._reconnect_count = 0
            logger.info("User WS connected")
            return True
        except Exception as e:
            logger.error(f"User WS connect error: {e}")
            self._state = ConnectionState.DISCONNECTED
            return False
    
    async def _process_message(self, data: Dict):
        try:
            event_type = data.get("event_type", "")
            msg_type = data.get("type", "")
            if event_type == "order" or msg_type in ("PLACEMENT", "UPDATE", "CANCELLATION"):
                order = OrderUpdate(
                    order_id=data.get("id", ""),
                    asset_id=data.get("asset_id", ""),
                    side=data.get("side", ""),
                    price=float(data.get("price", 0)),
                    original_size=float(data.get("original_size", 0)),
                    size_matched=float(data.get("size_matched", 0)),
                    event_type=data.get("type", msg_type),
                    status=data.get("status", ""),
                )
                self._pending_orders[order.order_id] = order
                if self.on_order:
                    if asyncio.iscoroutinefunction(self.on_order):
                        await self.on_order(order)
                    else:
                        self.on_order(order)
            elif event_type == "trade" or msg_type == "TRADE":
                trade = TradeUpdate(
                    trade_id=data.get("id", ""),
                    asset_id=data.get("asset_id", ""),
                    price=float(data.get("price", 0)),
                    size=float(data.get("size", 0)),
                    side=data.get("side", ""),
                    status=data.get("status", ""),
                    taker_order_id=data.get("taker_order_id", ""),
                )
                if self.on_trade:
                    if asyncio.iscoroutinefunction(self.on_trade):
                        await self.on_trade(trade)
                    else:
                        self.on_trade(trade)
        except Exception as e:
            logger.error(f"User msg error: {e}")
    
    async def _receive_loop(self):
        while self._running and self._ws:
            try:
                msg = await asyncio.wait_for(self._ws.recv(), timeout=30)
                self.messages_received += 1
                await self._process_message(json.loads(msg))
            except asyncio.TimeoutError:
                if self._ws and self._ws.open:
                    try:
                        await asyncio.wait_for(self._ws.ping(), timeout=5)
                    except:
                        break
                else:
                    break
            except ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"User recv error: {e}")
                break
    
    async def run_loop(self):
        self._running = True
        while self._running:
            try:
                if not await self.connect():
                    await asyncio.sleep(min(1 * (2 ** self._reconnect_count), 60))
                    self._reconnect_count += 1
                    continue
                await self._receive_loop()
                if self._running:
                    await asyncio.sleep(min(1 * (2 ** self._reconnect_count), 60))
                    self._reconnect_count += 1
            except asyncio.CancelledError:
                break
        await self.close()
    
    async def close(self):
        self._running = False
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except:
                pass
        self._ws = None
    
    def stop(self):
        self._running = False
    
    def get_order(self, order_id: str) -> Optional[OrderUpdate]:
        return self._pending_orders.get(order_id)
    
    async def wait_for_fill(self, order_id: str, timeout: float = 5.0) -> Optional[OrderUpdate]:
        start = time.time()
        while time.time() - start < timeout:
            order = self._pending_orders.get(order_id)
            if order and (order.size_matched > 0 or order.event_type == "CANCELLATION"):
                return order
            await asyncio.sleep(0.1)
        return self._pending_orders.get(order_id)
