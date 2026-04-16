#!/usr/bin/env python3
"""
User WebSocket Client

Subscribes to Polymarket User Channel for order/trade tracking.
Used to verify order execution before retry.

Docs: https://docs.polymarket.com/developers/CLOB/websocket/user-channel
"""

import asyncio
import json
import logging
import websockets
from typing import Optional, Dict, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("btc_live.user_ws")

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"


@dataclass
class OrderStatus:
    """Tracks order status from WebSocket."""
    order_id: str
    asset_id: str
    side: str
    price: float
    original_size: int
    size_matched: int = 0
    status: str = "PENDING"  # PENDING, PLACED, MATCHED, CANCELLED
    trades: list = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class UserWebSocket:
    """
    WebSocket client for User Channel.
    
    Tracks order placements and fills in real-time.
    """
    
    def __init__(self, api_key: str, api_secret: str = "", api_passphrase: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._connected = False
        
        # Order tracking
        self._orders: Dict[str, OrderStatus] = {}
        self._pending_orders: Dict[str, asyncio.Event] = {}
        
        # Token-based fill tracking (for timeout recovery)
        self._token_fills: Dict[str, list] = {}  # asset_id -> [{"size", "price", ...}]
        self._pending_token_fills: Dict[str, asyncio.Event] = {}
        
        # Callbacks
        self._on_trade: Optional[Callable] = None
        self._on_order: Optional[Callable] = None
    
    async def connect(self):
        """Connect to User Channel WebSocket."""
        try:
            self._running = True
            
            logger.info(f"Connecting to User WebSocket at {WS_URL}...")
            print(f"  Connecting to {WS_URL}...")
            
            # Connect without extra_headers (auth via message)
            async with websockets.connect(
                WS_URL,
                ping_interval=30,
                ping_timeout=10
            ) as ws:
                self._ws = ws
                self._connected = True
                logger.info("User WebSocket connected")
                print("  WebSocket connection established")
                
                # Subscribe to user channel with auth object
                subscribe_msg = {
                    "type": "user",
                    "auth": {
                        "apiKey": self.api_key,
                        "secret": self.api_secret,
                        "passphrase": self.api_passphrase
                    }
                }
                await ws.send(json.dumps(subscribe_msg))
                logger.info("Sent subscription message")
                print("  Sent subscription message")
                
                # Wait for response
                try:
                    first_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    logger.info(f"First message: {first_msg[:200]}")
                    print(f"  First response: {first_msg[:100]}...")
                    await self._process_message(first_msg)
                except asyncio.TimeoutError:
                    logger.warning("No initial response from WebSocket")
                    print("  No initial response (timeout)")
                
                # Listen for messages
                while self._running:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=60)
                        logger.debug(f"WS message: {msg[:100]}")
                        await self._process_message(msg)
                    except asyncio.TimeoutError:
                        # Send ping to keep alive
                        await ws.ping()
                    except websockets.ConnectionClosed as e:
                        logger.warning(f"User WebSocket connection closed: {e}")
                        print(f"  WebSocket closed: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"User WebSocket error: {e}")
            print(f"  WebSocket error: {e}")
        finally:
            self._connected = False
            self._ws = None
    
    async def _process_message(self, msg: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(msg)
            event_type = data.get("event_type", "")
            
            if event_type == "order":
                await self._handle_order(data)
            elif event_type == "trade":
                await self._handle_trade(data)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_order(self, data: dict):
        """Handle order event (PLACEMENT, UPDATE, CANCELLATION)."""
        order_id = data.get("id", "")
        order_type = data.get("type", "")  # PLACEMENT, UPDATE, CANCELLATION
        
        logger.info(f"Order event: {order_type} for {order_id[:20]}...")
        
        if order_id in self._orders:
            order = self._orders[order_id]
            order.size_matched = int(float(data.get("size_matched", 0)))
            
            if order_type == "CANCELLATION":
                order.status = "CANCELLED"
            elif order.size_matched > 0:
                order.status = "MATCHED"
            else:
                order.status = "PLACED"
        else:
            # New order
            self._orders[order_id] = OrderStatus(
                order_id=order_id,
                asset_id=data.get("asset_id", ""),
                side=data.get("side", ""),
                price=float(data.get("price", 0)),
                original_size=int(float(data.get("original_size", 0))),
                size_matched=int(float(data.get("size_matched", 0))),
                status="PLACED" if order_type == "PLACEMENT" else order_type
            )
        
        # Signal waiters
        if order_id in self._pending_orders:
            self._pending_orders[order_id].set()
        
        # Callback
        if self._on_order:
            await self._on_order(data)
    
    async def _handle_trade(self, data: dict):
        """Handle trade event (MATCHED, MINED, CONFIRMED, etc)."""
        order_id = data.get("taker_order_id", "")
        asset_id = data.get("asset_id", "")
        status = data.get("status", "")
        size = int(float(data.get("size", 0)))
        price = float(data.get("price", 0))
        
        logger.info(f"Trade event: {status} - {size} @ {price} for {order_id[:20]}...")
        
        if order_id in self._orders:
            order = self._orders[order_id]
            order.trades.append({
                "size": size,
                "price": price,
                "status": status,
                "timestamp": datetime.now().isoformat()
            })
            
            if status == "MATCHED":
                order.size_matched += size
                order.status = "MATCHED"
        
        # Store trade by asset_id for token-based recovery lookups
        if asset_id and status == "MATCHED":
            if asset_id not in self._token_fills:
                self._token_fills[asset_id] = []
            self._token_fills[asset_id].append({
                "size": size,
                "price": price,
                "order_id": order_id,
                "timestamp": datetime.now().isoformat()
            })
            # Signal token waiters
            if asset_id in self._pending_token_fills:
                self._pending_token_fills[asset_id].set()
        
        # Signal waiters
        if order_id in self._pending_orders:
            self._pending_orders[order_id].set()
        
        # Callback
        if self._on_trade:
            await self._on_trade(data)
    
    async def wait_for_order(self, order_id: str, timeout: float = 2.0) -> Optional[OrderStatus]:
        """
        Wait for order confirmation via WebSocket.
        
        WebSocket responses are instant (milliseconds).
        Timeout is just safety net, normally responds < 100ms.
        
        Args:
            order_id: Order ID to wait for
            timeout: Max seconds to wait (default 2s, normally instant)
            
        Returns:
            OrderStatus if received, None if timeout
        """
        if order_id in self._orders:
            return self._orders[order_id]
        
        # Create event to wait for
        event = asyncio.Event()
        self._pending_orders[order_id] = event
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._orders.get(order_id)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for order {order_id[:20]}...")
            return None
        finally:
            self._pending_orders.pop(order_id, None)
    
    async def wait_for_fills_on_token(self, token_id: str, timeout: float = 10.0) -> Optional[Dict]:
        """
        Wait for fill events on a specific token (by asset_id).
        
        Used for timeout recovery: we don't know the order_id,
        but we know which token we tried to buy. Check buffer first,
        then wait for new events.
        
        Args:
            token_id: The asset_id (token) we tried to buy
            timeout: Max seconds to wait
            
        Returns:
            {"contracts": int, "avg_price": float, "fills": list} or None
        """
        # 1. Check buffer first — event may have arrived during HTTP timeout
        if token_id in self._token_fills and self._token_fills[token_id]:
            fills = self._token_fills[token_id]
            logger.info(f"Recovery: found {len(fills)} fills in buffer for {token_id[:20]}...")
            return self._aggregate_fills(fills)
        
        # 2. Wait for new events
        logger.info(f"Recovery: waiting up to {timeout}s for fills on {token_id[:20]}...")
        event = asyncio.Event()
        self._pending_token_fills[token_id] = event
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            
            # Event fired — check what arrived
            fills = self._token_fills.get(token_id, [])
            if fills:
                logger.info(f"Recovery: got {len(fills)} fills after waiting for {token_id[:20]}...")
                
                # Wait a bit more for additional partial fills to aggregate
                await asyncio.sleep(1.0)
                fills = self._token_fills.get(token_id, [])
                
                return self._aggregate_fills(fills)
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"Recovery: no fills after {timeout}s for {token_id[:20]}...")
            return None
        finally:
            self._pending_token_fills.pop(token_id, None)
    
    @staticmethod
    def _aggregate_fills(fills: list) -> Dict:
        """Aggregate multiple fill events into totals."""
        total_contracts = sum(f["size"] for f in fills)
        total_cost = sum(f["size"] * f["price"] for f in fills)
        avg_price = total_cost / total_contracts if total_contracts > 0 else 0
        return {
            "contracts": total_contracts,
            "avg_price": avg_price,
            "total_cost": total_cost,
            "fills": fills
        }
    
    def clear_token_fills(self):
        """Clear token fill buffer (call on market change)."""
        self._token_fills.clear()
    
    def get_order(self, order_id: str) -> Optional[OrderStatus]:
        """Get order status by ID."""
        return self._orders.get(order_id)
    
    def get_filled_contracts(self, order_id: str) -> int:
        """Get number of contracts filled for an order."""
        order = self._orders.get(order_id)
        return order.size_matched if order else 0
    
    async def disconnect(self):
        """Disconnect WebSocket."""
        self._running = False
        if self._ws:
            await self._ws.close(code=1000)
            logger.info("User WebSocket disconnected")
    
    @property
    def connected(self) -> bool:
        return self._connected
