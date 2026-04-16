#!/usr/bin/env python3
"""
BTC 5/15-min Live Trading Bot with Real-time Dashboard

Single file that combines:
- Visual terminal dashboard (rich)
- Real order execution
- Hedge management
- Auto-redemption
- Telegram notifications

Usage:
    python main.py
"""

import asyncio
import json
import time
import csv
import math
import statistics
import logging
import signal
import sys
from datetime import datetime, timezone
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path

import aiohttp
import websockets
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout

# Setup logging
Path("logs").mkdir(exist_ok=True)

# Main logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler('logs/bot.log')]
)
logger = logging.getLogger("btc_live")

# Detailed order execution logger
order_logger = logging.getLogger("btc_live.orders")
order_handler = logging.FileHandler('logs/orders.log')
order_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
order_logger.addHandler(order_handler)
order_logger.setLevel(logging.DEBUG)

# Detailed hedge logger
hedge_logger = logging.getLogger("btc_live.hedges")
hedge_handler = logging.FileHandler('logs/hedges.log')
hedge_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
hedge_logger.addHandler(hedge_handler)
hedge_logger.setLevel(logging.DEBUG)

# Signals logger
signal_logger = logging.getLogger("btc_live.signals")
signal_handler = logging.FileHandler('logs/signals.log')
signal_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
signal_logger.addHandler(signal_handler)
signal_logger.setLevel(logging.DEBUG)

# Project imports
from src.config_loader import load_config, validate_config
from src.web_dashboard import WebSnapshotHolder, start_web_dashboard
from src.order_executor import OrderExecutor, ExecutionConfig
from src.hedge_manager import HedgeManager, HedgeConfig as HedgeManagerConfig, HedgeResult
from src.auto_redeemer import AsyncAutoRedeemer
from src.telegram_notifier import TelegramNotifier
from src.user_websocket import UserWebSocket
from src.simulation_history import SimulationHistoryLogger

# Constants
GAMMA_API = "https://gamma-api.polymarket.com"
WSS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
RTDS_URL = "wss://ws-live-data.polymarket.com"

console = Console()


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Trade:
    """Single trade record"""
    timestamp: float
    price: float
    size: float
    side: str


@dataclass
class TokenData:
    """Data for a single token (Up or Down)"""
    token_id: str
    name: str
    
    best_bid: float = 0.0
    best_bid_size: float = 0.0
    best_ask: float = 0.0
    best_ask_size: float = 0.0
    
    trades: deque = field(default_factory=lambda: deque(maxlen=5000))
    
    last_price: float = 0.0
    last_trade_time: float = 0.0
    
    trade_count: int = 0
    volume_total: float = 0.0
    volume_buy: float = 0.0
    volume_sell: float = 0.0
    
    def reset(self):
        self.best_bid = 0.0
        self.best_bid_size = 0.0
        self.best_ask = 0.0
        self.best_ask_size = 0.0
        self.trades.clear()
        self.last_price = 0.0
        self.last_trade_time = 0.0
        self.trade_count = 0
        self.volume_total = 0.0
        self.volume_buy = 0.0
        self.volume_sell = 0.0


@dataclass
class MarketState:
    """Current market state"""
    market_id: str = ""
    condition_id: str = ""
    slug: str = ""
    end_time: float = 0.0
    
    up_token: Optional[TokenData] = None
    down_token: Optional[TokenData] = None
    
    connected: bool = False
    last_update: float = 0.0
    
    # Chainlink BTC/USD price tracking
    btc_anchor_price: float = 0.0    # Price at market start
    btc_current_price: float = 0.0   # Latest Chainlink price
    btc_last_update: float = 0.0     # Timestamp of last price update
    btc_connected: bool = False      # RTDS connection status


@dataclass
class Position:
    """Current open position"""
    token_name: str
    token_id: str
    opposite_token_id: str
    entry_price: float
    contracts: int
    entry_time: float
    market_slug: str
    hedged: bool = False
    hedge_contracts: int = 0
    hedge_price: float = 0.0
    min_price_seen: float = 0.0  # Lowest price after entry (for drawdown tracking)


@dataclass
class TradeRecord:
    """Completed trade record"""
    market_slug: str
    token_name: str
    entry_price: float
    exit_price: float
    contracts: int
    pnl: float
    won: bool
    timestamp: float
    max_drawdown_abs: float = 0.0   # Max absolute price drop from entry
    max_drawdown_pct: float = 0.0   # Max percentage drawdown from entry


# =============================================================================
# UTILITIES
# =============================================================================

class IndicatorCalculator:
    @staticmethod
    def get_trades_in_window(trades: deque, window_seconds: float) -> List[Trade]:
        now = time.time()
        cutoff = now - window_seconds
        return [t for t in trades if t.timestamp >= cutoff]
    
    @staticmethod
    def calc_vwap(trades: List[Trade]) -> float:
        if not trades:
            return 0.0
        total_value = sum(t.price * t.size for t in trades)
        total_volume = sum(t.size for t in trades)
        return total_value / total_volume if total_volume > 0 else 0.0
    
    @staticmethod
    def calc_deviation(current_price: float, vwap: float) -> float:
        if vwap == 0:
            return 0.0
        return ((current_price - vwap) / vwap) * 100
    
    @staticmethod
    def calc_momentum(trades: deque, current_price: float, window: float = 120, avg_band: float = 1.5) -> Optional[float]:
        """
        Price change vs average price ~window seconds ago.
        
        Takes all trades in [now-window-avg_band, now-window+avg_band] (3s band),
        computes arithmetic mean, returns % change from that to current_price.
        
        Returns None if no trades found in the band (not enough history).
        """
        now = time.time()
        band_start = now - window - avg_band
        band_end = now - window + avg_band
        
        band_prices = [t.price for t in trades if band_start <= t.timestamp <= band_end]
        
        if not band_prices:
            return None
        
        avg_price_ago = sum(band_prices) / len(band_prices)
        if avg_price_ago == 0:
            return None
        
        return ((current_price - avg_price_ago) / avg_price_ago) * 100
    
    @staticmethod
    def calc_zscore(trades: deque, current_price: float, window: float = 5) -> float:
        now = time.time()
        recent = [t for t in trades if t.timestamp >= now - window]
        if len(recent) < 2:
            return 0.0
        prices = [t.price for t in recent]
        mean_price = statistics.mean(prices)
        std_price = statistics.stdev(prices) if len(prices) > 1 else 0.001
        return (current_price - mean_price) / std_price if std_price > 0 else 0.0


class WinRateTable:
    def __init__(self, csv_path: str):
        self.data = {}
        self.price_ranges = []
        self._load(csv_path)
    
    def _load(self, csv_path):
        try:
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if not row or not row[0]:
                        continue
                    price_range = row[0]
                    self.price_ranges.append(price_range)
                    self.data[price_range] = {}
                    for i, val in enumerate(row[1:], start=0):
                        if val:
                            try:
                                self.data[price_range][i] = float(val)
                            except ValueError:
                                pass
        except Exception as e:
            logger.warning(f"Could not load win_rate.csv: {e}")
    
    def get_winrate(self, price: float, minute: int, interval_minutes: int = 15) -> Optional[float]:
        price_range = None
        for pr in self.price_ranges:
            try:
                low, high = pr.split('-')
                if float(low) <= price <= float(high):
                    price_range = pr
                    break
            except:
                continue
        if not price_range and price > 0.99 and self.price_ranges:
            price_range = self.price_ranges[-1]
        if not price_range:
            return None
        cap = max(0, interval_minutes - 1)
        minute = max(0, min(cap, minute))
        return self.data.get(price_range, {}).get(minute)


# =============================================================================
# TRADING STATS
# =============================================================================

class TradingStats:
    def __init__(self, log_file: str = "logs/trading_log.json"):
        self.log_file = Path(log_file)
        self.position: Optional[Position] = None
        self.trades: List[TradeRecord] = []
        self.markets_seen: int = 0
        self.current_market_slug: str = ""
        self.position_closed_this_market: bool = False
        self.entry_blocked: bool = False  # Блокировка повторных попыток после таймаута
        self._load()
    
    def _load(self):
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    self.trades = [TradeRecord(**t) for t in data.get('trades', [])]
                    self.markets_seen = data.get('markets_seen', 0)
        except Exception:
            pass
    
    def summary_dict(self) -> Dict[str, Any]:
        """Aggregates for dashboards and simulation summary files."""
        tc = len(self.trades)
        wins = sum(1 for t in self.trades if t.won)
        losses = tc - wins
        total = sum(t.pnl for t in self.trades)
        pnls = [t.pnl for t in self.trades]
        wr = (wins / tc * 100.0) if tc else 0.0
        return {
            "total_pnl_usd": round(total, 6),
            "trade_count": tc,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wr, 4),
            "avg_trade_pnl_usd": round(total / tc, 6) if tc else 0.0,
            "best_trade_pnl_usd": round(max(pnls), 6) if pnls else None,
            "worst_trade_pnl_usd": round(min(pnls), 6) if pnls else None,
            "last_close_unix": max((t.timestamp for t in self.trades), default=None),
        }

    def _save(self):
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'trades': [t.__dict__ for t in self.trades],
                'markets_seen': self.markets_seen,
                'summary': self.summary_dict(),
            }
            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    
    def new_market(self, slug: str):
        if slug != self.current_market_slug:
            self.current_market_slug = slug
            self.markets_seen += 1
            self.position = None
            self.position_closed_this_market = False
            self.entry_blocked = False  # Сброс блокировки для нового рынка
            self._save()
    
    def can_enter(self) -> bool:
        return self.position is None and not self.position_closed_this_market and not self.entry_blocked
    
    def block_entry(self, reason: str = ""):
        """Блокирует повторные попытки входа на текущем рынке."""
        self.entry_blocked = True
        if reason:
            logger.warning(f"Entry blocked: {reason}")
    
    def record_entry(self, token_name: str, token_id: str, opposite_token_id: str,
                     price: float, contracts: int, market_slug: str):
        self.position = Position(
            token_name=token_name,
            token_id=token_id,
            opposite_token_id=opposite_token_id,
            entry_price=price,
            contracts=contracts,
            entry_time=time.time(),
            market_slug=market_slug,
            min_price_seen=price  # Start tracking from entry price
        )
    
    def record_hedge(self, contracts: int, price: float):
        if self.position:
            self.position.hedged = True
            self.position.hedge_contracts = contracts
            self.position.hedge_price = price
    
    def update_drawdown(self, current_price: float):
        """Track minimum price seen since entry for drawdown calculation."""
        if self.position and current_price > 0:
            if current_price < self.position.min_price_seen:
                self.position.min_price_seen = current_price
    
    def close_position(self, final_price: float) -> Optional[TradeRecord]:
        if not self.position:
            return None
        
        won = final_price >= 0.70  # Win threshold
        entry_cost = self.position.contracts * self.position.entry_price
        
        if won:
            pnl = self.position.contracts - entry_cost
        else:
            pnl = -entry_cost
        
        # Calculate max drawdown from entry
        dd_abs = max(0, self.position.entry_price - self.position.min_price_seen)
        dd_pct = (dd_abs / self.position.entry_price * 100) if self.position.entry_price > 0 else 0
        
        record = TradeRecord(
            market_slug=self.position.market_slug,
            token_name=self.position.token_name,
            entry_price=self.position.entry_price,
            exit_price=final_price,
            contracts=self.position.contracts,
            pnl=pnl,
            won=won,
            timestamp=time.time(),
            max_drawdown_abs=dd_abs,
            max_drawdown_pct=dd_pct,
        )
        
        self.trades.append(record)
        self.position = None
        self.position_closed_this_market = True
        self._save()
        return record
    
    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)
    
    @property
    def win_count(self) -> int:
        return sum(1 for t in self.trades if t.won)
    
    @property
    def trade_count(self) -> int:
        return len(self.trades)
    
    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return (self.win_count / self.trade_count) * 100


# =============================================================================
# WEBSOCKET CLIENT
# =============================================================================

class WebSocketClient:
    def __init__(self, state: MarketState):
        self.state = state
        self.running = False
        self._tokens_validated = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
    
    def _validate_tokens(self):
        """Log token prices after first WebSocket data received.
        
        NOTE: Token swap logic was REMOVED because it was buggy.
        The API token assignment should be trusted.
        """
        if self._tokens_validated:
            return
        
        up = self.state.up_token
        down = self.state.down_token
        
        if not up or not down:
            return
        
        up_price = up.best_bid or up.best_ask or up.last_price
        down_price = down.best_bid or down.best_ask or down.last_price
        
        # Only log once we have valid prices
        if up_price > 0.05 and down_price > 0.05:
            price_sum = up_price + down_price
            logger.info(f"Tokens validated: UP={up_price:.2f}, DOWN={down_price:.2f}, sum={price_sum:.2f}")
            self._tokens_validated = True
    
    async def connect(self):
        self.running = True
        
        while self.running:
            try:
                async with websockets.connect(WSS_URL) as ws:
                    self._ws = ws
                    self.state.connected = True
                    
                    token_ids = []
                    if self.state.up_token:
                        token_ids.append(self.state.up_token.token_id)
                    if self.state.down_token:
                        token_ids.append(self.state.down_token.token_id)
                    
                    # Log exact token_ids being subscribed
                    logger.info(f"WebSocket subscribing to tokens:")
                    logger.info(f"  UP: {self.state.up_token.token_id[:40]}..." if self.state.up_token else "  UP: None")
                    logger.info(f"  DOWN: {self.state.down_token.token_id[:40]}..." if self.state.down_token else "  DOWN: None")
                    
                    await ws.send(json.dumps({"assets_ids": token_ids, "type": "market"}))
                    
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)
                    
                    self._ws = None
                        
            except websockets.ConnectionClosed:
                self._ws = None
                self.state.connected = False
                if self.running:
                    await asyncio.sleep(1)
            except Exception:
                self._ws = None
                self.state.connected = False
                if self.running:
                    await asyncio.sleep(2)
    
    async def disconnect(self):
        """Gracefully close WebSocket connection with code 1000 (normal closure)."""
        self.running = False
        if self._ws:
            try:
                await self._ws.close(code=1000, reason="Normal shutdown")
                logger.info("WebSocket closed gracefully (code 1000)")
            except Exception as e:
                logger.warning(f"Error during WebSocket close: {e}")
            finally:
                self._ws = None
        self.state.connected = False
    
    async def _handle_message(self, message: str):
        try:
            data = json.loads(message)
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        await self._process_item(item)
            elif isinstance(data, dict):
                await self._process_item(data)
            
            self.state.last_update = time.time()
            
            # Validate tokens after receiving price data
            if not self._tokens_validated:
                self._validate_tokens()
        except Exception:
            pass
    
    async def _process_item(self, data: dict):
        event_type = data.get("event_type", "")
        
        if event_type == "last_trade_price":
            asset_id = data.get("asset_id")
            token = self._get_token(asset_id)
            
            if not token and asset_id:
                # Asset ID doesn't match our tokens - might indicate subscription issue
                logger.warning(f"Received price for unknown asset: {asset_id[:30]}...")
                logger.warning(f"  Our UP token: {self.state.up_token.token_id[:30] if self.state.up_token else 'None'}...")
                logger.warning(f"  Our DOWN token: {self.state.down_token.token_id[:30] if self.state.down_token else 'None'}...")
            
            if token:
                price = float(data.get("price", 0))
                size = float(data.get("size", 0))
                side = data.get("side", "BUY")
                
                if price > 0 and size > 0:
                    token.last_price = price
                    token.last_trade_time = time.time()
                    token.trades.append(Trade(time.time(), price, size, side))
                    token.trade_count += 1
                    token.volume_total += size
                    if side == "BUY":
                        token.volume_buy += size
                    else:
                        token.volume_sell += size
        
        elif event_type == "price_change":
            for change in data.get("price_changes", []):
                token = self._get_token(change.get("asset_id"))
                if token:
                    if change.get("best_bid"):
                        token.best_bid = float(change["best_bid"])
                    if change.get("best_ask"):
                        token.best_ask = float(change["best_ask"])
        
        elif event_type == "book":
            token = self._get_token(data.get("asset_id"))
            if token:
                bids = data.get("bids", [])
                if bids:
                    bids.sort(key=lambda x: float(x["price"]), reverse=True)
                    token.best_bid = float(bids[0]["price"])
                    token.best_bid_size = float(bids[0]["size"])
                asks = data.get("asks", [])
                if asks:
                    asks.sort(key=lambda x: float(x["price"]))
                    token.best_ask = float(asks[0]["price"])
                    token.best_ask_size = float(asks[0]["size"])
    
    def _get_token(self, asset_id: str) -> Optional[TokenData]:
        if self.state.up_token and asset_id == self.state.up_token.token_id:
            return self.state.up_token
        elif self.state.down_token and asset_id == self.state.down_token.token_id:
            return self.state.down_token
        return None
    
    def stop(self):
        """Stop WebSocket (sync version - just sets flag)."""
        self.running = False
    
    async def stop_graceful(self):
        """Stop WebSocket gracefully with proper close."""
        await self.disconnect()


# =============================================================================
# CHAINLINK BTC PRICE CLIENT
# =============================================================================

class ChainlinkPriceClient:
    """
    Always-on BTC/USD price stream from Polymarket RTDS (Chainlink source).
    
    Connects to wss://ws-live-data.polymarket.com and subscribes to
    crypto_prices_chainlink for btc/usd.
    
    Autonomously tracks market boundaries (epoch-aligned to interval length)
    and snapshots the anchor price at the exact boundary crossing, independent
    of the bot's market finding flow. This ensures the anchor is captured
    within ~1 second of the real boundary, not 5-15s later.
    """
    
    def __init__(self, state: 'MarketState', market_duration_sec: int):
        self.state = state
        self._market_duration = int(market_duration_sec)
        if self._market_duration <= 0:
            self._market_duration = 900
        self.running = False
        self._ws = None
        self._ping_task: Optional[asyncio.Task] = None
        # Track which window the current anchor belongs to
        self._current_window: int = 0
        # Buffer: last price before boundary (for most accurate anchor)
        self._last_price_before_boundary: float = 0.0
        self._last_price_ts: float = 0.0
    
    def _get_window(self, ts: float) -> int:
        """Window start timestamp (epoch) for the configured interval."""
        d = self._market_duration
        return int(ts) // d * d
    
    DATA_TIMEOUT = 30  # seconds without any message → force reconnect
    
    async def connect(self):
        """Connect to RTDS and subscribe to Chainlink BTC/USD prices. Always on."""
        self.running = True
        self._last_msg_time = time.time()
        
        while self.running:
            try:
                async with websockets.connect(RTDS_URL) as ws:
                    self._ws = ws
                    self.state.btc_connected = True
                    self._last_msg_time = time.time()
                    logger.info("RTDS Chainlink connected")
                    
                    # Subscribe to chainlink prices (all symbols, filter in code)
                    subscribe_msg = json.dumps({
                        "action": "subscribe",
                        "subscriptions": [{
                            "topic": "crypto_prices_chainlink",
                            "type": "*",
                            "filters": ""
                        }]
                    })
                    await ws.send(subscribe_msg)
                    
                    # Start ping task and watchdog
                    self._ping_task = asyncio.create_task(self._ping_loop(ws))
                    watchdog_task = asyncio.create_task(self._watchdog(ws))
                    
                    try:
                        async for message in ws:
                            if not self.running:
                                break
                            self._last_msg_time = time.time()
                            self._handle_message(message)
                    finally:
                        watchdog_task.cancel()
                        try:
                            await watchdog_task
                        except asyncio.CancelledError:
                            pass
                    
                    self._ws = None
                    
            except websockets.ConnectionClosed:
                self._ws = None
                self.state.btc_connected = False
                if self.running:
                    logger.warning("RTDS Chainlink disconnected, reconnecting in 2s...")
                    await asyncio.sleep(2)
            except Exception as e:
                self._ws = None
                self.state.btc_connected = False
                if self.running:
                    logger.warning(f"RTDS Chainlink error: {e}, reconnecting in 5s...")
                    await asyncio.sleep(5)
            finally:
                if self._ping_task and not self._ping_task.done():
                    self._ping_task.cancel()
                    try:
                        await self._ping_task
                    except:
                        pass
                    self._ping_task = None
    
    async def _watchdog(self, ws):
        """Force-close WebSocket if no messages received for DATA_TIMEOUT seconds."""
        try:
            while self.running:
                await asyncio.sleep(5)
                silence = time.time() - self._last_msg_time
                if silence > self.DATA_TIMEOUT:
                    logger.warning(
                        f"RTDS Chainlink watchdog: no data for {silence:.0f}s, forcing reconnect"
                    )
                    self.state.btc_connected = False
                    await ws.close()
                    break
        except asyncio.CancelledError:
            pass
    
    def _handle_message(self, message: str):
        """Parse incoming Chainlink price message and auto-detect market boundaries."""
        try:
            if not isinstance(message, str) or not message.strip():
                return
            
            data = json.loads(message)
            topic = data.get("topic", "")
            
            if topic != "crypto_prices_chainlink":
                return
            
            payload = data.get("payload", {})
            symbol = payload.get("symbol", "")
            
            if symbol != "btc/usd":
                return
            
            price = float(payload.get("value", 0))
            if price <= 0:
                return
            
            # Use Chainlink's own timestamp (ms) for precise boundary detection
            chainlink_ts_ms = payload.get("timestamp", 0)
            if chainlink_ts_ms:
                price_ts = chainlink_ts_ms / 1000.0
            else:
                price_ts = time.time()
            
            now = time.time()
            
            # Update current price (always)
            self.state.btc_current_price = price
            self.state.btc_last_update = now
            
            # === CALIBRATION LOG: every tick within [-15s..+5s] of any boundary ===
            price_window = self._get_window(price_ts)
            next_boundary = price_window + self._market_duration
            secs_to_next = next_boundary - price_ts
            secs_from_prev = price_ts - price_window
            
            # Log if within 15s before next boundary OR 5s after current boundary start
            if secs_to_next <= 15.0 or secs_from_prev <= 5.0:
                cl_time = datetime.fromtimestamp(price_ts, tz=timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                local_time = datetime.fromtimestamp(now, tz=timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                if secs_from_prev <= 5.0:
                    offset_str = f"+{secs_from_prev:.3f}s after {datetime.fromtimestamp(price_window, tz=timezone.utc).strftime('%H:%M:%S')}"
                else:
                    offset_str = f"-{secs_to_next:.3f}s before {datetime.fromtimestamp(next_boundary, tz=timezone.utc).strftime('%H:%M:%S')}"
                logger.info(
                    f"BTC_TICK {cl_time} (local {local_time}) ${price:,.2f} [{offset_str}]"
                )
            
            # Detect window boundary crossing
            
            if self._current_window == 0:
                # First price ever — initialize
                self._current_window = price_window
                self.state.btc_anchor_price = price
                logger.info(
                    f"BTC Chainlink init: ${price:,.2f} "
                    f"(window {self._current_window}, "
                    f"ts={datetime.fromtimestamp(price_ts, tz=timezone.utc).strftime('%H:%M:%S.%f')[:-3]})"
                )
            elif price_window != self._current_window:
                # === NEW WINDOW === use FIRST tick of new window as anchor
                # Calibrated: reference program uses the first tick AT or AFTER boundary
                old_anchor = self.state.btc_anchor_price
                old_window = self._current_window
                
                self.state.btc_anchor_price = price  # First tick of new window
                self._current_window = price_window
                
                boundary_time = datetime.fromtimestamp(price_window, tz=timezone.utc).strftime('%H:%M:%S')
                price_time = datetime.fromtimestamp(price_ts, tz=timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                delay_ms = (price_ts - price_window) * 1000
                
                logger.info(
                    f"BTC anchor reset: ${self.state.btc_anchor_price:,.2f} "
                    f"(boundary {boundary_time}, first tick at {price_time}, "
                    f"delay {delay_ms:.0f}ms, prev anchor ${old_anchor:,.2f})"
                )
            
            # Always buffer the latest price for next boundary crossing
            self._last_price_before_boundary = price
            self._last_price_ts = price_ts
            
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    
    async def _ping_loop(self, ws):
        """Send ping every 5 seconds to keep connection alive."""
        try:
            while self.running:
                await asyncio.sleep(5)
                try:
                    await ws.ping()
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
    
    async def disconnect(self):
        """Gracefully close RTDS WebSocket connection."""
        self.running = False
        
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except:
                pass
            self._ping_task = None
        
        if self._ws:
            try:
                # Unsubscribe before closing
                unsub_msg = json.dumps({
                    "action": "unsubscribe",
                    "subscriptions": [{
                        "topic": "crypto_prices_chainlink",
                        "type": "*",
                        "filters": ""
                    }]
                })
                await self._ws.send(unsub_msg)
                await self._ws.close(code=1000, reason="Normal shutdown")
                logger.info("RTDS Chainlink closed gracefully")
            except Exception as e:
                logger.warning(f"RTDS close error: {e}")
            finally:
                self._ws = None
        
        self.state.btc_connected = False


# =============================================================================
# DASHBOARD
# =============================================================================

class Dashboard:
    def __init__(self, state: MarketState, stats: TradingStats, config: Any):
        self.state = state
        self.stats = stats
        self.config = config
        self.calc = IndicatorCalculator()
        
        win_rate_path = Path(__file__).parent / config.strategy.win_rate_csv
        self.winrate_table = WinRateTable(str(win_rate_path))
        
        self.last_signal = ""
        self.entry_flash = False
        self.hedge_flash = False
    
    def _fmt_price(self, price: float) -> str:
        if price >= 0.6:
            return f"[green]{price:.3f}[/green]"
        elif price <= 0.4:
            return f"[red]{price:.3f}[/red]"
        return f"[yellow]{price:.3f}[/yellow]"
    
    def _fmt_dev(self, dev: float) -> str:
        if dev > 5:
            return f"[bold green]+{dev:.1f}%[/bold green]"
        elif dev > 0:
            return f"[green]+{dev:.1f}%[/green]"
        elif dev < -5:
            return f"[bold red]{dev:.1f}%[/bold red]"
        elif dev < 0:
            return f"[red]{dev:.1f}%[/red]"
        return f"{dev:+.1f}%"
    
    def _fmt_zscore(self, z: float) -> str:
        if z > 2:
            return f"[bold magenta]+{z:.2f}[/bold magenta] ⚡"
        elif z > 1:
            return f"[magenta]+{z:.2f}[/magenta]"
        elif z < -2:
            return f"[bold cyan]{z:.2f}[/bold cyan] ⚡"
        elif z < -1:
            return f"[cyan]{z:.2f}[/cyan]"
        return f"{z:+.2f}"
    
    def create_header(self) -> Panel:
        now = time.time()
        time_left = max(0, self.state.end_time - now)
        minutes = int(time_left // 60)
        seconds = int(time_left % 60)
        
        if time_left < 60:
            timer = f"[bold red]⏱️ {seconds}s[/bold red]"
        elif time_left < 180:
            timer = f"[yellow]⏱️ {minutes}:{seconds:02d}[/yellow]"
        else:
            timer = f"[green]⏱️ {minutes}:{seconds:02d}[/green]"
        
        status = "[green]● LIVE[/green]" if self.state.connected else "[red]○ DISCONNECTED[/red]"
        if getattr(self.config, "simulation", None) and self.config.simulation.enabled:
            mode = "[bold yellow]SIMULATION (no real orders)[/bold yellow]"
        else:
            mode = "[bold cyan]REAL TRADING[/bold cyan]"
        
        header = f"{timer}  |  {self.state.slug}  |  {status}  |  {mode}"
        im = self.config.market.interval_minutes
        return Panel(header, title=f"[bold]BTC {im}-Min Live Bot[/bold]")
    
    def create_token_panel(self, token: TokenData, label: str) -> Panel:
        if not token:
            return Panel("No data", title=label)
        
        lines = []
        if token.best_ask > 0:
            lines.append(f"[red]ASK  {token.best_ask:.3f}[/red] | {token.best_ask_size:.0f}")
        else:
            lines.append(f"[red]ASK  ---[/red]")
        
        lines.append("─" * 20)
        lines.append(f"[bold white]LAST {token.last_price:.3f}[/bold white]")
        
        if token.best_ask > 0 and token.best_bid > 0:
            spread = token.best_ask - token.best_bid
            lines.append(f"[dim]Spread: {spread:.3f}[/dim]")
        
        lines.append("─" * 20)
        
        if token.best_bid > 0:
            lines.append(f"[green]BID  {token.best_bid:.3f}[/green] | {token.best_bid_size:.0f}")
        else:
            lines.append(f"[green]BID  ---[/green]")
        
        return Panel(
            "\n".join(lines),
            title=f"[bold]{label}[/bold] - {self._fmt_price(token.last_price)}",
            border_style="green" if "Up" in label else "red"
        )
    
    def _fmt_momentum(self, m: Optional[float]) -> str:
        if m is None:
            return "[dim]N/A[/dim]"
        if m > 0:
            return f"[green]+{m:.2f}%[/green]"
        elif m < 0:
            return f"[red]{m:.2f}%[/red]"
        return f"[cyan]0.00%[/cyan]"
    
    def create_indicators_panel(self, token: TokenData, label: str) -> Panel:
        if not token or not token.trades:
            return Panel("Waiting for data...", title=f"{label} Indicators")
        
        mom_window = self.config.strategy.momentum_window_sec
        
        vwap_window = self.config.strategy.vwap_window_sec
        vwap = self.calc.calc_vwap(self.calc.get_trades_in_window(token.trades, vwap_window))
        deviation = self.calc.calc_deviation(token.last_price, vwap)
        zscore = self.calc.calc_zscore(token.trades, token.last_price, window=5)
        momentum = self.calc.calc_momentum(token.trades, token.last_price, window=mom_window)
        
        def fmt_vol(v):
            if v >= 1_000_000:
                return f"{v/1_000_000:.1f}M"
            elif v >= 1_000:
                return f"{v/1_000:.1f}K"
            return f"{v:.0f}"
        
        lines = [
            f"VWAP {vwap_window}s:   {vwap:.4f}",
            f"Deviation:   {self._fmt_dev(deviation)}",
            f"Z-Score 5s:  {self._fmt_zscore(zscore)}",
            f"Mom {mom_window}s:   {self._fmt_momentum(momentum)}",
            "",
            f"Trades:      {token.trade_count}",
            f"Volume:      {fmt_vol(token.volume_total)}",
            f"  Buy:  [green]{fmt_vol(token.volume_buy)}[/green]",
            f"  Sell: [red]{fmt_vol(token.volume_sell)}[/red]",
        ]
        
        return Panel("\n".join(lines), title=f"{label} Indicators", border_style="blue")
    
    def create_strategy_panel(self) -> Panel:
        if not self.state.up_token or not self.state.down_token:
            return Panel("Waiting for data...", title="Strategy Signal")
        
        up = self.state.up_token
        down = self.state.down_token
        
        vwap_window = self.config.strategy.vwap_window_sec
        up_vwap = self.calc.calc_vwap(self.calc.get_trades_in_window(up.trades, vwap_window))
        down_vwap = self.calc.calc_vwap(self.calc.get_trades_in_window(down.trades, vwap_window))
        
        up_dev = self.calc.calc_deviation(up.last_price, up_vwap)
        down_dev = self.calc.calc_deviation(down.last_price, down_vwap)
        
        mom_window = self.config.strategy.momentum_window_sec
        up_mom = self.calc.calc_momentum(up.trades, up.last_price, window=mom_window)
        down_mom = self.calc.calc_momentum(down.trades, down.last_price, window=mom_window)
        
        time_left = max(0, self.state.end_time - time.time())
        time_minutes = time_left / 60
        span = self.config.market.interval_minutes
        time_bin = int((span - 1) - time_minutes)
        time_bin = max(0, min(time_bin, span - 1))
        
        if up.last_price > down.last_price:
            fav_name = "UP"
            fav_price = up.last_price
            fav_dev = up_dev
            fav_mom = up_mom
        else:
            fav_name = "DOWN"
            fav_price = down.last_price
            fav_dev = down_dev
            fav_mom = down_mom
        
        base_wr = self.winrate_table.get_winrate(fav_price, time_bin, span)
        wr_str = f"{base_wr:.1f}%" if base_wr else "N/A"
        
        min_price = self.config.strategy.min_price
        max_price = self.config.strategy.max_price
        min_elapsed = self.config.strategy.min_elapsed_sec
        min_dev = self.config.strategy.min_deviation_pct
        max_dev = self.config.strategy.max_deviation_pct
        
        no_entry_cutoff = self.config.strategy.no_entry_before_end_sec
        
        elapsed_sec = self.config.market.duration_sec - time_left
        
        price_ok = min_price <= fav_price <= max_price
        time_ok = elapsed_sec >= min_elapsed
        dev_ok = fav_dev > min_dev and fav_dev < max_dev
        mom_ok = fav_mom is not None and fav_mom > 5
        time_cutoff_ok = time_left > no_entry_cutoff
        
        signal = "⏳ WAIT"
        signal_color = "yellow"
        
        if not time_cutoff_ok:
            signal = f"🚫 NO ENTRY (< {no_entry_cutoff}s left)"
            signal_color = "red"
            self.last_signal = ""
        elif price_ok and time_ok and dev_ok and mom_ok:
            signal = f"✅ BUY {fav_name}"
            signal_color = "bold green"
            self.last_signal = f"BUY_{fav_name}"
        elif fav_price >= 0.70 and time_ok:
            if not mom_ok:
                signal = "🟡 ALMOST (need Mom>0%)"
            elif fav_dev >= max_dev:
                signal = f"🟡 ALMOST (Dev≥{max_dev}%)"
            else:
                signal = "🟡 ALMOST (need dev)"
            self.last_signal = ""
        else:
            self.last_signal = ""
            if not time_ok:
                signal = f"⏳ WAIT (elapsed<{min_elapsed}s)"
            elif not price_ok:
                signal = f"⏳ WAIT (P not in range)"
            elif not dev_ok:
                if fav_dev >= max_dev:
                    signal = f"⏳ WAIT (Dev≥{max_dev}%)"
                else:
                    signal = f"⏳ WAIT (Dev<{min_dev}%)"
            elif not mom_ok:
                signal = f"⏳ WAIT (Mom≤0%)"
        
        lines = [
            f"Favorite:    [{signal_color}]{fav_name} ({fav_price:.3f})[/{signal_color}] — WR: [cyan]{wr_str}[/cyan]",
            f"Signal:      [{signal_color}][bold]{signal}[/bold][/{signal_color}]",
            "",
            f"Price:       {self._fmt_price(fav_price)} (range: {min_price}-{max_price})",
            f"Deviation:   {self._fmt_dev(fav_dev)} (need {min_dev}%–{max_dev}%)",
            f"Momentum:    {self._fmt_momentum(fav_mom)}",
            f"Elapsed:     {int(elapsed_sec)}s (need ≥{min_elapsed}s)  [bin {time_bin}]",
            "",
            f"Up:          {self._fmt_price(up.last_price)} | Dev: {self._fmt_dev(up_dev)} | Mom: {self._fmt_momentum(up_mom)}",
            f"Down:        {self._fmt_price(down.last_price)} | Dev: {self._fmt_dev(down_dev)} | Mom: {self._fmt_momentum(down_mom)}",
        ]
        
        title = f"[bold]Strategy: P {min_price}-{max_price}, T≥{min_elapsed}s, Dev {min_dev}%-{max_dev}%[/bold]"
        border = "green" if signal_color == "bold green" else "magenta"
        return Panel("\n".join(lines), title=title, border_style=border)
    
    def create_trading_panel(self) -> Panel:
        s = self.stats
        bet = self.config.entry.bet_amount_usd
        
        wr_str = f"{s.win_rate:.1f}%" if s.trade_count > 0 else "N/A"
        stats_line = f"📊 Markets: {s.markets_seen} | Trades: {s.trade_count} | WR: {wr_str}"
        
        pnl_color = "green" if s.total_pnl >= 0 else "red"
        pnl_line = f"💰 PnL: [{pnl_color}]${s.total_pnl:+.2f}[/{pnl_color}]"
        
        if s.position:
            pos = s.position
            if pos.token_name == "UP" and self.state.up_token:
                current_price = self.state.up_token.best_bid or self.state.up_token.last_price
            elif pos.token_name == "DOWN" and self.state.down_token:
                current_price = self.state.down_token.best_bid or self.state.down_token.last_price
            else:
                current_price = pos.entry_price
            
            unrealized = (pos.contracts * current_price) - (pos.contracts * pos.entry_price)
            ur_color = "green" if unrealized >= 0 else "red"
            
            hedge_str = " [cyan]🛡️ HEDGED[/cyan]" if pos.hedged else ""
            flash = "🔔 " if self.entry_flash else ""
            self.entry_flash = False
            
            pos_line = f"{flash}🟢 LONG {pos.token_name} @ {pos.entry_price:.3f} ({pos.contracts} contracts){hedge_str}"
            ur_line = f"   Unrealized: [{ur_color}]${unrealized:+.2f}[/{ur_color}] (price: {current_price:.3f})"
            
            # Live drawdown
            dd_price = max(0, pos.entry_price - pos.min_price_seen)
            dd_pct = (dd_price / pos.entry_price * 100) if pos.entry_price > 0 else 0
            dd_usd = dd_price * pos.contracts
            if dd_price > 0:
                ur_line += f"\n   Max DD: [red]-${dd_usd:.2f} (-{dd_pct:.1f}%)[/red] (low: {pos.min_price_seen:.3f})"
        else:
            pos_line = "⏳ No position (waiting for signal)"
            ur_line = ""
        
        last_trades_lines = []
        for trade in s.trades[-3:][::-1]:
            icon = "✅" if trade.won else "❌"
            last_trades_lines.append(f"  {icon} {trade.token_name} @ {trade.entry_price:.2f} → ${trade.pnl:+.2f}")
        
        lines = [stats_line, pnl_line, "", pos_line]
        if ur_line:
            lines.append(ur_line)
        if last_trades_lines:
            lines.append("")
            lines.append("Last trades:")
            lines.extend(last_trades_lines)
        
        border = "bold yellow" if self.entry_flash or self.hedge_flash else "cyan"
        self.hedge_flash = False
        return Panel("\n".join(lines), title=f"[bold]💰 REAL Trading (${bet:.0f}/trade)[/bold]", border_style=border)
    
    def create_btc_price_panel(self) -> Panel:
        """Panel showing Chainlink BTC/USD price and deviation from market start."""
        s = self.state
        
        if s.btc_current_price <= 0:
            status = "[green]● LIVE[/green]" if s.btc_connected else "[red]○ OFF[/red]"
            return Panel(
                f"Chainlink {status}\nWaiting for price...",
                title="[bold]₿ BTC/USD (Chainlink)[/bold]",
                border_style="dim"
            )
        
        # Connection status
        status = "[green]●[/green]" if s.btc_connected else "[red]○[/red]"
        
        # Freshness indicator
        age = time.time() - s.btc_last_update if s.btc_last_update > 0 else 999
        if age < 5:
            fresh = "[green]LIVE[/green]"
        elif age < 30:
            fresh = f"[yellow]{int(age)}s ago[/yellow]"
        else:
            fresh = f"[red]{int(age)}s ago[/red]"
        
        lines = [
            f"Price:       [bold white]${s.btc_current_price:,.2f}[/bold white]  {status} {fresh}",
        ]
        
        if s.btc_anchor_price > 0:
            dev_abs = s.btc_current_price - s.btc_anchor_price
            dev_pct = (dev_abs / s.btc_anchor_price) * 100 if s.btc_anchor_price else 0
            
            # Color based on direction
            if dev_abs > 0:
                dev_abs_str = f"[green]+${dev_abs:,.2f}[/green]"
                dev_pct_str = f"[green]+{dev_pct:.3f}%[/green]"
            elif dev_abs < 0:
                dev_abs_str = f"[red]-${abs(dev_abs):,.2f}[/red]"
                dev_pct_str = f"[red]{dev_pct:.3f}%[/red]"
            else:
                dev_abs_str = "$0.00"
                dev_pct_str = "0.000%"
            
            lines.append(f"Anchor:      [dim]${s.btc_anchor_price:,.2f}[/dim]")
            lines.append(f"Deviation:   {dev_abs_str}  ({dev_pct_str})")
        else:
            lines.append("[dim]Anchor: waiting for market start...[/dim]")
        
        return Panel(
            "\n".join(lines),
            title="[bold]₿ BTC/USD (Chainlink)[/bold]",
            border_style="yellow"
        )
    
    def render(self) -> Layout:
        layout = Layout()
        
        layout.split_column(
            Layout(self.create_header(), name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=16),
            Layout(self.create_btc_price_panel(), name="btc_price", size=6)
        )
        
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        layout["left"].split_column(
            Layout(self.create_token_panel(self.state.up_token, "⬆️ UP"), name="up_book"),
            Layout(self.create_indicators_panel(self.state.up_token, "UP"), name="up_ind")
        )
        
        layout["right"].split_column(
            Layout(self.create_token_panel(self.state.down_token, "⬇️ DOWN"), name="down_book"),
            Layout(self.create_indicators_panel(self.state.down_token, "DOWN"), name="down_ind")
        )
        
        layout["footer"].split_row(
            Layout(name="strategy"),
            Layout(name="trading")
        )
        layout["strategy"].update(self.create_strategy_panel())
        layout["trading"].update(self.create_trading_panel())
        
        return layout

    def build_web_snapshot(self) -> dict:
        """Plain dict for the HTTP dashboard (same numbers as terminal panels; no Rich markup)."""
        now = time.time()
        time_left = max(0.0, self.state.end_time - now)
        sim = bool(getattr(self.config, "simulation", None) and self.config.simulation.enabled)
        header = {
            "slug": self.state.slug or "—",
            "time_left_sec": time_left,
            "elapsed_sec": max(0.0, self.config.market.duration_sec - time_left),
            "ws_connected": bool(self.state.connected),
            "simulation": sim,
            "interval_minutes": self.config.market.interval_minutes,
        }

        def token_block(token: Optional[TokenData]) -> Optional[dict]:
            if not token:
                return None
            book = {
                "best_bid": token.best_bid,
                "best_bid_size": token.best_bid_size,
                "best_ask": token.best_ask,
                "best_ask_size": token.best_ask_size,
                "last_price": token.last_price,
                "trade_count": token.trade_count,
                "volume_total": token.volume_total,
                "volume_buy": token.volume_buy,
                "volume_sell": token.volume_sell,
            }
            ind = None
            if token.trades:
                vw = self.config.strategy.vwap_window_sec
                mw = self.config.strategy.momentum_window_sec
                vwap = self.calc.calc_vwap(self.calc.get_trades_in_window(token.trades, vw))
                ind = {
                    "vwap_window_sec": vw,
                    "vwap": vwap,
                    "deviation_pct": self.calc.calc_deviation(token.last_price, vwap),
                    "zscore": self.calc.calc_zscore(token.trades, token.last_price, window=5),
                    "momentum_window_sec": mw,
                    "momentum_pct": self.calc.calc_momentum(token.trades, token.last_price, window=mw),
                }
            return {"book": book, "indicators": ind}

        strategy: dict = {
            "signal_text": "Waiting for data...",
            "favorite": None,
            "win_rate_str": None,
            "checks": {},
            "up_line": "",
            "down_line": "",
        }

        if self.state.up_token and self.state.down_token:
            up = self.state.up_token
            down = self.state.down_token
            vwap_window = self.config.strategy.vwap_window_sec
            up_vwap = self.calc.calc_vwap(self.calc.get_trades_in_window(up.trades, vwap_window))
            down_vwap = self.calc.calc_vwap(self.calc.get_trades_in_window(down.trades, vwap_window))
            up_dev = self.calc.calc_deviation(up.last_price, up_vwap)
            down_dev = self.calc.calc_deviation(down.last_price, down_vwap)
            mom_window = self.config.strategy.momentum_window_sec
            up_mom = self.calc.calc_momentum(up.trades, up.last_price, window=mom_window)
            down_mom = self.calc.calc_momentum(down.trades, down.last_price, window=mom_window)

            time_minutes = time_left / 60.0
            span = self.config.market.interval_minutes
            time_bin = int((span - 1) - time_minutes)
            time_bin = max(0, min(time_bin, span - 1))

            if up.last_price > down.last_price:
                fav_name = "UP"
                fav_price = up.last_price
                fav_dev = up_dev
                fav_mom = up_mom
            else:
                fav_name = "DOWN"
                fav_price = down.last_price
                fav_dev = down_dev
                fav_mom = down_mom

            base_wr = self.winrate_table.get_winrate(fav_price, time_bin, span)
            wr_str = f"{base_wr:.1f}%" if base_wr else None

            min_price = self.config.strategy.min_price
            max_price = self.config.strategy.max_price
            min_elapsed = self.config.strategy.min_elapsed_sec
            min_dev = self.config.strategy.min_deviation_pct
            max_dev = self.config.strategy.max_deviation_pct
            no_entry_cutoff = self.config.strategy.no_entry_before_end_sec
            elapsed_sec = self.config.market.duration_sec - time_left

            price_ok = min_price <= fav_price <= max_price
            time_ok = elapsed_sec >= min_elapsed
            dev_ok = fav_dev > min_dev and fav_dev < max_dev
            mom_ok = fav_mom is not None and fav_mom > 5
            time_cutoff_ok = time_left > no_entry_cutoff

            if not time_cutoff_ok:
                signal = f"🚫 NO ENTRY (< {no_entry_cutoff}s left)"
            elif price_ok and time_ok and dev_ok and mom_ok:
                signal = f"✅ BUY {fav_name}"
            elif fav_price >= 0.70 and time_ok:
                if not mom_ok:
                    signal = "🟡 ALMOST (need Mom>0%)"
                elif fav_dev >= max_dev:
                    signal = f"🟡 ALMOST (Dev≥{max_dev}%)"
                else:
                    signal = "🟡 ALMOST (need dev)"
            elif not time_ok:
                signal = f"⏳ WAIT (elapsed<{min_elapsed}s)"
            elif not price_ok:
                signal = "⏳ WAIT (P not in range)"
            elif not dev_ok:
                signal = (
                    f"⏳ WAIT (Dev≥{max_dev}%)"
                    if fav_dev >= max_dev
                    else f"⏳ WAIT (Dev<{min_dev}%)"
                )
            elif not mom_ok:
                signal = "⏳ WAIT (Mom≤0%)"
            else:
                signal = "⏳ WAIT"

            strategy = {
                "signal_text": signal,
                "favorite": f"{fav_name} ({fav_price:.3f})",
                "win_rate_str": wr_str,
                "time_bin": time_bin,
                "checks": {
                    "price": price_ok,
                    "time": time_ok,
                    "dev": dev_ok,
                    "mom": mom_ok,
                    "time_cutoff": time_cutoff_ok,
                },
                "up_line": f"{up.last_price:.3f} | Dev {up_dev:+.1f}% | Mom {up_mom if up_mom is not None else 0:.2f}%",
                "down_line": f"{down.last_price:.3f} | Dev {down_dev:+.1f}% | Mom {down_mom if down_mom is not None else 0:.2f}%",
            }

        s = self.state
        btc_age = time.time() - s.btc_last_update if s.btc_last_update > 0 else None
        btc_block: dict = {
            "btc_current_price": s.btc_current_price,
            "btc_anchor_price": s.btc_anchor_price,
            "btc_connected": s.btc_connected,
            "fresh_sec": btc_age,
            "deviation_line": "",
        }
        if s.btc_current_price > 0 and s.btc_anchor_price > 0:
            dev_abs = s.btc_current_price - s.btc_anchor_price
            dev_pct = (dev_abs / s.btc_anchor_price) * 100 if s.btc_anchor_price else 0.0
            btc_block["deviation_line"] = f"${dev_abs:+,.2f} ({dev_pct:+.3f}%)"

        st = self.stats
        bet = self.config.entry.bet_amount_usd
        wr_str = f"{st.win_rate:.1f}%" if st.trade_count > 0 else None
        trading: dict = {
            "bet_usd": bet,
            "markets_seen": st.markets_seen,
            "trade_count": st.trade_count,
            "win_rate_str": wr_str,
            "total_pnl": st.total_pnl,
            "position": None,
            "recent_trades": [],
        }
        if st.position:
            pos = st.position
            if pos.token_name == "UP" and self.state.up_token:
                current_price = self.state.up_token.best_bid or self.state.up_token.last_price
            elif pos.token_name == "DOWN" and self.state.down_token:
                current_price = self.state.down_token.best_bid or self.state.down_token.last_price
            else:
                current_price = pos.entry_price
            unrealized = (pos.contracts * current_price) - (pos.contracts * pos.entry_price)
            dd_price = max(0.0, pos.entry_price - pos.min_price_seen)
            dd_pct = (dd_price / pos.entry_price * 100) if pos.entry_price > 0 else 0.0
            dd_usd = dd_price * pos.contracts
            trading["position"] = {
                "token_name": pos.token_name,
                "entry_price": pos.entry_price,
                "contracts": pos.contracts,
                "hedged": pos.hedged,
                "current_price": current_price,
                "unrealized_pnl": unrealized,
                "max_dd_usd": dd_usd,
                "max_dd_pct": dd_pct,
                "min_price_seen": pos.min_price_seen,
            }
        for trade in st.trades[-5:][::-1]:
            icon = "✅" if trade.won else "❌"
            trading["recent_trades"].append({
                "line": f"{icon} {trade.token_name} @ {trade.entry_price:.2f} → ${trade.pnl:+.2f}",
            })

        return {
            "ts": now,
            "header": header,
            "strategy": strategy,
            "up": token_block(self.state.up_token),
            "down": token_block(self.state.down_token),
            "btc": btc_block,
            "trading": trading,
            "last_signal": self.last_signal,
        }


# =============================================================================
# MAIN BOT
# =============================================================================

class LiveTradingBot:
    def __init__(self):
        self.config = None
        self.state = MarketState()
        self.stats = TradingStats()
        self.dashboard: Dashboard = None
        
        # Trading components
        self.executor: OrderExecutor = None
        self.hedge_mgr: HedgeManager = None
        self.redeemer: Optional[AsyncAutoRedeemer] = None
        self.telegram: TelegramNotifier = None
        self.user_ws = None
        self._user_ws_task: Optional[asyncio.Task] = None

        # WebSocket
        self.ws_client: WebSocketClient = None
        
        # Chainlink BTC price
        self.chainlink_client: ChainlinkPriceClient = None
        self._chainlink_task: Optional[asyncio.Task] = None
        
        # Control
        self.running = False
        self.tasks = []
        self._sim_history: Optional[SimulationHistoryLogger] = None
        self._web_snapshot_holder: Optional[WebSnapshotHolder] = None
    
    async def initialize(self) -> bool:
        # Load config
        self.config = load_config()
        errors = validate_config(self.config)
        if errors:
            for err in errors:
                console.print(f"[red]Config error: {err}[/red]")
            return False

        im = self.config.market.interval_minutes
        console.print(f"[bold cyan]🚀 BTC {im}-Min Live Trading Bot[/bold cyan]")
        if self.config.simulation.enabled:
            console.print("[bold yellow]   SIMULATION MODE — no CLOB orders, no redeemer[/bold yellow]\n")
        else:
            console.print("[bold cyan]   Real Trading + Dashboard[/bold cyan]\n")

        console.print(f"[green]✓ Market: BTC up/down {im}m (slug btc-updown-{im}m-*)[/green]")
        console.print(f"[green]✓ Config: P {self.config.strategy.min_price}-{self.config.strategy.max_price}, "
                      f"T≥{self.config.strategy.min_elapsed_sec}s, "
                      f"Dev {self.config.strategy.min_deviation_pct}%-{self.config.strategy.max_deviation_pct}%[/green]")
        console.print(f"[green]✓ Bet: ${self.config.entry.bet_amount_usd}, "
                      f"Hedge: {'ON' if self.config.hedge.enabled else 'OFF'}[/green]")
        if self.config.simulation.enabled:
            if self.config.simulation.separate_trading_log:
                self.stats = TradingStats(self.config.simulation.trading_log_path)
                console.print(
                    f"[yellow]✓ Simulation stats: {self.config.simulation.trading_log_path}[/yellow]"
                )
            else:
                console.print("[yellow]✓ Simulation stats: same file as live (trading_log.json)[/yellow]")

        # Initialize trading components
        console.print("[yellow]Initializing trading components...[/yellow]")
        
        # Telegram
        self.telegram = TelegramNotifier(
            bot_token=self.config.telegram.bot_token,
            chat_id=self.config.telegram.chat_id,
            enabled=self.config.telegram.enabled
        )

        sim = self.config.simulation.enabled

        if sim:
            self.user_ws = None
            self._user_ws_task = None
            # Dummy credentials — CLOB is never initialized in simulation
            pk = self.config.polymarket.private_key or "0x0000000000000000000000000000000000000000000000000000000000000001"
            ak = self.config.polymarket.api_key or "sim"
            sec = self.config.polymarket.api_secret or "sim"
            ph = self.config.polymarket.api_passphrase or "sim"
            self.executor = OrderExecutor(
                private_key=pk,
                api_key=ak,
                api_secret=sec,
                api_passphrase=ph,
                clob_host=self.config.polymarket.clob_host,
                chain_id=self.config.polymarket.chain_id,
                signature_type=self.config.polymarket.signature_type,
                funder_address=self.config.polymarket.funder_address or None,
                user_ws=None,
                simulation_mode=True,
            )
            console.print("[green]✓ Order executor: simulation (no CLOB)[/green]")
        else:
            # User WebSocket for order tracking (CRITICAL for fill confirmation!)
            self.user_ws = UserWebSocket(
                api_key=self.config.polymarket.api_key,
                api_secret=self.config.polymarket.api_secret,
                api_passphrase=self.config.polymarket.api_passphrase
            )
            self._user_ws_task = None

            self.executor = OrderExecutor(
                private_key=self.config.polymarket.private_key,
                api_key=self.config.polymarket.api_key,
                api_secret=self.config.polymarket.api_secret,
                api_passphrase=self.config.polymarket.api_passphrase,
                clob_host=self.config.polymarket.clob_host,
                chain_id=self.config.polymarket.chain_id,
                signature_type=self.config.polymarket.signature_type,
                funder_address=self.config.polymarket.funder_address or None,
                user_ws=self.user_ws,
                simulation_mode=False,
            )

            if not await self.executor.initialize():
                console.print("[red]Failed to initialize order executor[/red]")
                return False

            console.print("[yellow]Starting User WebSocket for order tracking...[/yellow]")
            self._user_ws_task = asyncio.create_task(self.user_ws.connect())
            await asyncio.sleep(1)
            if self.user_ws.connected:
                console.print("[green]User WebSocket connected - order tracking active[/green]")
                logger.info("User WebSocket connected for order fill tracking")
            else:
                console.print("[yellow]User WebSocket connecting... (will retry)[/yellow]")
                logger.warning("User WebSocket not yet connected")
        
        # Hedge manager
        hedge_config = HedgeManagerConfig(
            enabled=self.config.hedge.enabled,
            hedge_price=self.config.hedge.hedge_price,
            order_type=self.config.hedge.order_type,
            max_retries=self.config.hedge.max_retries,
            retry_delay_ms=self.config.hedge.retry_delay_ms,
            simulation_mode=sim,
        )
        self.hedge_mgr = HedgeManager(self.executor, hedge_config)
        
        # Auto redeemer (live only)
        if sim:
            self.redeemer = None
            console.print("[yellow]✓ Auto-redeemer: disabled in simulation[/yellow]")
        else:
            self.redeemer = AsyncAutoRedeemer(
                private_key=self.config.polymarket.private_key,
                rpc_url=self.config.polymarket.rpc_url,
                funder_address=self.config.polymarket.funder_address or None,
                signature_type=self.config.polymarket.signature_type,
                interval_seconds=self.config.redeem.interval_seconds,
                telegram_notifier=self.telegram
            )

        if sim:
            jl = (self.config.simulation.history_jsonl_path or "").strip()
            self._sim_history = SimulationHistoryLogger(
                csv_path=self.config.simulation.history_csv_path,
                jsonl_path=jl if jl else None,
                summary_path=self.config.simulation.history_summary_path,
            )
            if self.stats.trades:
                self._sim_history.write_summary(
                    [t.__dict__ for t in self.stats.trades],
                    self.stats.summary_dict(),
                )
            csv_p = self.config.simulation.history_csv_path or "(disabled)"
            sum_p = self.config.simulation.history_summary_path or "(disabled)"
            jl_p = jl or "(disabled)"
            console.print(
                f"[green]✓ Simulation analytics: CSV={csv_p} | JSONL={jl_p} | summary={sum_p}[/green]"
            )
        else:
            self._sim_history = None
        
        # Chainlink BTC price client
        self.chainlink_client = ChainlinkPriceClient(
            self.state, self.config.market.duration_sec
        )
        self._chainlink_task = asyncio.create_task(self.chainlink_client.connect())
        console.print("[green]✓ Chainlink BTC/USD price feed starting...[/green]")
        
        # Dashboard
        self.dashboard = Dashboard(self.state, self.stats, self.config)

        wd = self.config.web_dashboard
        if wd.enabled:
            self._web_snapshot_holder = WebSnapshotHolder()
            ok = start_web_dashboard(wd.host, wd.port, self._web_snapshot_holder)
            # 0.0.0.0 is not a valid host in a browser URL; use loopback for display.
            if wd.host in ("0.0.0.0", ""):
                open_url = f"http://127.0.0.1:{wd.port}/"
            elif wd.host in ("::", "[::]"):
                open_url = f"http://[::1]:{wd.port}/"
            else:
                open_url = f"http://{wd.host}:{wd.port}/"
            if ok:
                console.print(f"[green]✓ Web dashboard:[/green] [bold]{open_url}[/bold]")
                console.print(
                    "[dim]  Use http:// not https://. On Windows, if the page fails in your browser, "
                    "open this exact URL (avoid typing only “localhost”, which may use IPv6).[/dim]"
                )
            else:
                console.print(
                    f"[yellow]⚠ Web dashboard did not start on port {wd.port} "
                    f"(in use by another app, or bind failed). Check logs.[/yellow]"
                )
        
        console.print("[green]✓ All components initialized[/green]\n")
        return True
    
    async def find_market(self) -> bool:
        d = self.config.market.duration_sec
        sfx = self.config.market.slug_infix
        console.print(f"[yellow]Searching for active BTC {self.config.market.interval_minutes}-min market...[/yellow]")
        
        async with aiohttp.ClientSession() as session:
            now = int(time.time())
            current_window = (now // d) * d
            
            for offset in [0, d, -d, 2 * d]:
                target_ts = current_window + offset
                expected_slug = f"btc-updown-{sfx}-{target_ts}"
                
                try:
                    async with session.get(f"{GAMMA_API}/markets?slug={expected_slug}") as resp:
                        if resp.status == 200:
                            markets = await resp.json()
                            if markets:
                                market = markets[0]
                                returned_slug = market.get("slug", "")
                                
                                # CRITICAL: Verify API returned the market we asked for
                                if returned_slug != expected_slug:
                                    logger.warning(f"API slug mismatch! Asked for {expected_slug}, got {returned_slug}")
                                    continue
                                
                                if not market.get("closed", True):
                                    return await self._setup_market(market)
                except Exception as e:
                    logger.debug(f"Error finding market {expected_slug}: {e}")
                    continue
        
        return False
    
    async def _setup_market(self, market: dict) -> bool:
        console.print(f"[green]Found: {market.get('slug')}[/green]")
        
        outcomes = market.get("outcomes", [])
        tokens = market.get("clobTokenIds", [])
        
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(tokens, str):
            tokens = json.loads(tokens)
        
        up_token_id = None
        down_token_id = None
        
        # Use exact index lookup like reference implementation
        try:
            up_index = outcomes.index("Up") if "Up" in outcomes else None
            down_index = outcomes.index("Down") if "Down" in outcomes else None
            
            if up_index is not None and up_index < len(tokens):
                up_token_id = tokens[up_index]
            if down_index is not None and down_index < len(tokens):
                down_token_id = tokens[down_index]
        except (ValueError, IndexError):
            pass
        
        # Fallback to contains-based matching
        if not up_token_id or not down_token_id:
            for i, outcome in enumerate(outcomes):
                if i < len(tokens):
                    outcome_lower = str(outcome).lower()
                    if not up_token_id and "up" in outcome_lower:
                        up_token_id = tokens[i]
                    elif not down_token_id and "down" in outcome_lower:
                        down_token_id = tokens[i]
        
        # Last resort fallback
        if not up_token_id and len(tokens) >= 1:
            up_token_id = tokens[0]
        if not down_token_id and len(tokens) >= 2:
            down_token_id = tokens[1]
        
        if not up_token_id or not down_token_id:
            return False
        
        end_str = market.get("end_date_iso") or market.get("endDate", "")
        try:
            end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            end_timestamp = end_time.timestamp()
        except:
            end_timestamp = time.time() + self.config.market.duration_sec
        
        slug = market.get("slug", "")
        
        self.state.market_id = market.get("id", "")
        self.state.condition_id = market.get("conditionId", "")
        self.state.slug = slug
        self.state.end_time = end_timestamp
        self.state.up_token = TokenData(token_id=up_token_id, name="Up")
        self.state.down_token = TokenData(token_id=down_token_id, name="Down")
        self.state.connected = False
        
        # Log token assignments for debugging
        logger.info(f"Market tokens assigned:")
        logger.info(f"  Slug: {slug}")
        logger.info(f"  End Time: {end_str} (timestamp: {end_timestamp})")
        logger.info(f"  UP token: {up_token_id[:40]}...")
        logger.info(f"  DOWN token: {down_token_id[:40]}...")
        
        self.stats.new_market(self.state.slug)
        self.hedge_mgr.clear()  # Reset hedge state for new market
        if self.user_ws:
            self.user_ws.clear_token_fills()  # Reset WS fill buffer for new market
        
        # BTC anchor is now auto-managed by ChainlinkPriceClient
        # It detects interval boundaries from Chainlink timestamps independently
        
        return True

    def _simulation_log_entry(
        self,
        token_name: str,
        avg_price: float,
        contracts: int,
        total_cost: float,
    ) -> None:
        if not self._sim_history or not self.config.simulation.enabled:
            return
        pos = self.stats.position
        hedged = bool(pos and pos.hedged)
        self._sim_history.log_open(
            market_slug=self.state.slug,
            token_name=token_name,
            contracts=contracts,
            avg_price=avg_price,
            total_cost=total_cost,
            cumulative_realized_pnl=self.stats.total_pnl,
            hedged=hedged,
            trade_number=len(self.stats.trades) + 1,
        )
        signal_logger.info(
            f"  [SIM] History OPEN logged | realized PnL before exit: ${self.stats.total_pnl:+.4f}"
        )

    def _simulation_log_close(self, record: TradeRecord, hedged_was: bool) -> None:
        if not self._sim_history or not self.config.simulation.enabled:
            return
        n = len(self.stats.trades)
        self._sim_history.log_close(
            record,
            cumulative_pnl=self.stats.total_pnl,
            total_closed=n,
            win_rate_pct=self.stats.win_rate,
            hedged=hedged_was,
        )
        self._sim_history.write_summary(
            [t.__dict__ for t in self.stats.trades],
            self.stats.summary_dict(),
        )
        s = self.stats.summary_dict()
        signal_logger.info(
            f"  [SIM] History CLOSE logged | trade PnL ${record.pnl:+.4f} | "
            f"cumulative ${s['total_pnl_usd']:+.4f} | WR {s['win_rate_pct']:.2f}% ({n} closed)"
        )
    
    async def execute_entry(self, side: str):
        """Execute entry order (live CLOB or simulation)."""
        if not self.stats.can_enter():
            signal_logger.info(f"SIGNAL IGNORED: {side} - cannot enter (already in position)")
            return
        
        # Defensive time cutoff check (race condition guard)
        time_left = max(0, self.state.end_time - time.time())
        no_entry_cutoff = self.config.strategy.no_entry_before_end_sec
        if time_left < no_entry_cutoff:
            signal_logger.info(
                f"SIGNAL BLOCKED: {side} - too close to market end "
                f"({time_left:.0f}s left < {no_entry_cutoff}s cutoff)"
            )
            logger.warning(f"Entry blocked: {time_left:.0f}s left < {no_entry_cutoff}s cutoff")
            return
        
        if side == "BUY_UP":
            token = self.state.up_token
            token_name = "UP"
            opposite_token = self.state.down_token
        else:
            token = self.state.down_token
            token_name = "DOWN"
            opposite_token = self.state.up_token
        
        if not token or not opposite_token:
            signal_logger.warning(f"SIGNAL IGNORED: {side} - token data missing")
            return
        
        # Log full signal snapshot
        signal_logger.info("=" * 60)
        signal_logger.info(
            "TRADE SIGNAL TRIGGERED (SIMULATION)" if self.config.simulation.enabled else "TRADE SIGNAL TRIGGERED"
        )
        signal_logger.info(f"  Time: {datetime.now().isoformat()}")
        signal_logger.info(f"  Market: {self.state.slug}")
        signal_logger.info(f"  Signal: {side}")
        signal_logger.info(f"  Token: {token_name}")
        
        time_left = max(0, self.state.end_time - time.time())
        dur = self.config.market.duration_sec
        span = self.config.market.interval_minutes
        elapsed_sec = dur - time_left
        time_bin = int((span - 1) - time_left / 60)
        time_bin = max(0, min(time_bin, span - 1))
        signal_logger.info(f"  Elapsed: {elapsed_sec:.0f}s | Remaining: {time_left:.0f}s | Bin: {time_bin}")
        
        # Calculate all indicators for both tokens
        calc = self.dashboard.calc
        vwap_window = self.config.strategy.vwap_window_sec
        mom_window = self.config.strategy.momentum_window_sec
        
        for label, tk in [("UP", self.state.up_token), ("DOWN", self.state.down_token)]:
            if not tk:
                signal_logger.info(f"  {label}: no data")
                continue
            
            vwap = calc.calc_vwap(calc.get_trades_in_window(tk.trades, vwap_window))
            dev = calc.calc_deviation(tk.last_price, vwap)
            zscore = calc.calc_zscore(tk.trades, tk.last_price, window=5)
            mom = calc.calc_momentum(tk.trades, tk.last_price, window=mom_window)
            mom_str = f"{mom:+.2f}%" if mom is not None else "N/A"
            
            signal_logger.info(f"  --- {label} ---")
            signal_logger.info(f"    Price:   LAST={tk.last_price:.4f}  BID={tk.best_bid:.4f}  ASK={tk.best_ask:.4f}")
            signal_logger.info(f"    VWAP {vwap_window}s: {vwap:.4f}  |  Deviation: {dev:+.2f}%")
            signal_logger.info(f"    Z-Score 5s: {zscore:+.2f}  |  Momentum {mom_window}s: {mom_str}")
            signal_logger.info(f"    Trades: {tk.trade_count}  |  Volume: {tk.volume_total:.0f}")
            signal_logger.info(f"    Buy Vol: {tk.volume_buy:.0f}  |  Sell Vol: {tk.volume_sell:.0f}")
        
        # Win rate
        up = self.state.up_token
        down = self.state.down_token
        if up and down:
            fav_price = up.last_price if up.last_price > down.last_price else down.last_price
            wr = self.dashboard.winrate_table.get_winrate(
                fav_price, time_bin, self.config.market.interval_minutes
            )
            signal_logger.info(f"  Win Rate: {wr:.1f}%" if wr else "  Win Rate: N/A")
        
        # Strategy conditions snapshot
        signal_logger.info(f"  Config: min_price={self.config.strategy.min_price}, "
                          f"max_price={self.config.strategy.max_price}, "
                          f"min_elapsed={self.config.strategy.min_elapsed_sec}s, "
                          f"dev_range={self.config.strategy.min_deviation_pct}%-{self.config.strategy.max_deviation_pct}%, "
                          f"no_entry_cutoff={self.config.strategy.no_entry_before_end_sec}s")
        
        # Chainlink BTC/USD
        s = self.state
        if s.btc_current_price > 0 and s.btc_anchor_price > 0:
            btc_dev_abs = s.btc_current_price - s.btc_anchor_price
            btc_dev_pct = (btc_dev_abs / s.btc_anchor_price) * 100
            signal_logger.info(f"  BTC Chainlink: ${s.btc_current_price:,.2f} (anchor: ${s.btc_anchor_price:,.2f})")
            signal_logger.info(f"  BTC Deviation: ${btc_dev_abs:+,.2f} ({btc_dev_pct:+.4f}%)")
        else:
            signal_logger.info(f"  BTC Chainlink: N/A")
        
        signal_logger.info("=" * 60)
        
        logger.info(f"Executing entry: {token_name}")
        
        exec_config = ExecutionConfig(
            bet_amount_usd=self.config.entry.bet_amount_usd,
            price_offset=self.config.entry.price_offset,
            max_retries=self.config.entry.max_retries,
            retry_delay_ms=self.config.entry.retry_delay_ms,
            fill_timeout_ms=self.config.entry.fill_timeout_ms,
            min_contracts=self.config.entry.min_contracts,
            min_order_usd=self.config.entry.min_order_usd,
            max_entry_price=self.config.entry.max_entry_price
        )
        
        result = await self.executor.execute_entry(
            token_id=token.token_id,
            config=exec_config,
            websocket_price=token.best_ask  # Для ПОКУПКИ нужен ASK! Мы платим продавцам.
        )
        
        if result.success:
            self.stats.record_entry(
                token_name=token_name,
                token_id=token.token_id,
                opposite_token_id=opposite_token.token_id,
                price=result.avg_price,
                contracts=result.contracts_filled,
                market_slug=self.state.slug
            )
            self._simulation_log_entry(
                token_name, result.avg_price, result.contracts_filled, result.total_cost
            )
            
            self.dashboard.entry_flash = True
            
            # Log successful entry
            signal_logger.info(
                "ENTRY EXECUTED SUCCESSFULLY (SIMULATED)"
                if self.config.simulation.enabled
                else "ENTRY EXECUTED SUCCESSFULLY"
            )
            signal_logger.info(f"  Token: {token_name}")
            signal_logger.info(f"  Contracts: {result.contracts_filled}")
            signal_logger.info(f"  Avg Price: {result.avg_price:.4f}")
            signal_logger.info(f"  Total Cost: ${result.total_cost:.2f}")
            signal_logger.info(f"  Attempts: {result.attempts}")
            signal_logger.info("-" * 40)
            
            await self.telegram.notify_entry(
                side=token_name,
                price=result.avg_price,
                contracts=result.contracts_filled,
                cost=result.total_cost,
                retries=result.attempts,
                interval_minutes=self.config.market.interval_minutes,
                simulation=self.config.simulation.enabled,
            )
            
            logger.info(f"Entry complete: {result.contracts_filled} @ {result.avg_price:.3f}")
            
            # === PLACE GTD HEDGE ORDER ===
            if self.config.hedge.enabled:
                self.hedge_mgr.set_position(
                    opposite_token_id=opposite_token.token_id,
                    contracts=result.contracts_filled
                )
                
                hedge_result = await self.hedge_mgr.place_gtd_hedge()
                
                if hedge_result.success:
                    self.dashboard.hedge_flash = True
                    hedge_cost = hedge_result.contracts * hedge_result.price
                    
                    hsim = "🎮 <b>[SIMULATION]</b>\n" if self.config.simulation.enabled else ""
                    await self.telegram.send_message(
                        f"{hsim}"
                        f"🛡️ <b>Hedge Order Placed (GTD)</b>\n"
                        f"📦 {hedge_result.contracts} contracts @ ${hedge_result.price}\n"
                        f"💰 Cost: ${hedge_cost:.2f}\n"
                        f"🔖 Order ID: {hedge_result.order_id[:20]}...\n"
                        f"📋 Status: LIVE (passive)\n"
                        f"🔄 Attempts: {hedge_result.attempts}"
                    )
                    
                    # Register WebSocket handler for hedge fills
                    self._register_hedge_ws_handler()
                    
                    logger.info(f"GTD hedge placed: {hedge_result.contracts} @ ${hedge_result.price}")
                else:
                    await self.telegram.send_message(
                        f"⚠️ <b>Hedge Failed</b>\n"
                        f"❌ {hedge_result.error}\n"
                        f"🔄 Attempts: {hedge_result.attempts}"
                    )
                    logger.error(f"Hedge failed: {hedge_result.error}")
        else:
            signal_logger.error(f"ENTRY FAILED: {result.error}")
            signal_logger.info(f"  Attempts: {result.attempts}")
            signal_logger.info("-" * 40)
            logger.error(f"Entry failed: {result.error}")
            
            # ============================================================
            # КРИТИЧНО: Если был таймаут - НЕ делаем retry (двойная покупка!)
            # Вместо этого проверяем через WebSocket - может ордер исполнился
            # ============================================================
            if result.was_timeout:
                signal_logger.error("🛑 TIMEOUT: Checking WebSocket for fills...")
                logger.warning("Timeout detected — starting WS recovery")
                
                recovered = False
                
                if self.user_ws and self.user_ws.connected:
                    recovery_timeout = self.config.entry.ws_recovery_timeout_sec
                    
                    signal_logger.info(f"  Checking WS for fills on {token.token_id[:30]}...")
                    signal_logger.info(f"  Recovery timeout: {recovery_timeout}s")
                    
                    fill_data = await self.user_ws.wait_for_fills_on_token(
                        token_id=token.token_id,
                        timeout=recovery_timeout
                    )
                    
                    if fill_data and fill_data["contracts"] > 0:
                        # ==============================
                        # RECOVERY: Order DID execute!
                        # ==============================
                        recovered = True
                        rec_contracts = fill_data["contracts"]
                        rec_price = fill_data["avg_price"]
                        rec_cost = fill_data["total_cost"]
                        
                        signal_logger.info("=" * 60)
                        signal_logger.info("✅ TIMEOUT RECOVERY: Position found via WebSocket!")
                        signal_logger.info(f"  Contracts: {rec_contracts}")
                        signal_logger.info(f"  Avg Price: {rec_price:.4f}")
                        signal_logger.info(f"  Total Cost: ${rec_cost:.2f}")
                        signal_logger.info(f"  Fills: {len(fill_data['fills'])}")
                        signal_logger.info("=" * 60)
                        
                        logger.info(f"Timeout recovery: {rec_contracts} @ {rec_price:.4f}")
                        
                        # Record position as if entry succeeded
                        self.stats.record_entry(
                            token_name=token_name,
                            token_id=token.token_id,
                            opposite_token_id=opposite_token.token_id,
                            price=rec_price,
                            contracts=rec_contracts,
                            market_slug=self.state.slug
                        )
                        self._simulation_log_entry(
                            token_name, rec_price, rec_contracts, rec_cost
                        )
                        
                        self.dashboard.entry_flash = True
                        
                        await self.telegram.send_message(
                            f"🔄 <b>Timeout Recovery!</b>\n"
                            f"Order filled despite HTTP timeout.\n"
                            f"📊 {token_name} {rec_contracts} @ ${rec_price:.4f}\n"
                            f"💰 Cost: ${rec_cost:.2f}\n"
                            f"Market: {self.state.slug}"
                        )
                        
                        await self.telegram.notify_entry(
                            side=token_name,
                            price=rec_price,
                            contracts=rec_contracts,
                            cost=rec_cost,
                            retries=result.attempts,
                            interval_minutes=self.config.market.interval_minutes,
                            simulation=self.config.simulation.enabled,
                        )
                        
                        # Place hedge (normal flow)
                        if self.config.hedge.enabled:
                            self.hedge_mgr.set_position(
                                opposite_token_id=opposite_token.token_id,
                                contracts=rec_contracts
                            )
                            
                            hedge_result = await self.hedge_mgr.place_gtd_hedge()
                            
                            if hedge_result.success:
                                self.dashboard.hedge_flash = True
                                hedge_cost = hedge_result.contracts * hedge_result.price
                                hsim2 = "🎮 <b>[SIMULATION]</b>\n" if self.config.simulation.enabled else ""
                                await self.telegram.send_message(
                                    f"{hsim2}"
                                    f"🛡️ <b>Hedge Order Placed (GTD)</b>\n"
                                    f"📦 {hedge_result.contracts} contracts @ ${hedge_result.price}\n"
                                    f"💰 Cost: ${hedge_cost:.2f}\n"
                                    f"🔖 Order ID: {hedge_result.order_id[:20]}...\n"
                                    f"📋 Status: LIVE (passive)\n"
                                    f"🔄 Attempts: {hedge_result.attempts}"
                                )
                                
                                self._register_hedge_ws_handler()
                                logger.info(f"GTD hedge placed after recovery: {hedge_result.contracts} @ ${hedge_result.price}")
                            else:
                                await self.telegram.send_message(
                                    f"⚠️ <b>Hedge Failed (after recovery)</b>\n"
                                    f"❌ {hedge_result.error}"
                                )
                    else:
                        signal_logger.info("  WS recovery: no fills found")
                else:
                    signal_logger.warning("  WS not connected — cannot recover")
                
                if not recovered:
                    # No fill found — block entry (original behavior)
                    self.stats.block_entry("Network timeout - no fill detected via WS. Blocking re-entry.")
                    signal_logger.error("🛑 ENTRY BLOCKED: Timeout + no WS fill detected")
                    await self.telegram.send_message(
                        f"⚠️ <b>TIMEOUT — No Fill Detected</b>\n"
                        f"Order status unknown after timeout.\n"
                        f"WebSocket recovery found nothing.\n"
                        f"Re-entry blocked.\n"
                        f"Market: {self.state.slug}"
                    )
    
    def _register_hedge_ws_handler(self):
        """Register WebSocket handler to track hedge order fills."""
        if not self.user_ws:
            logger.warning("User WebSocket not available for hedge tracking")
            return
        
        hedge_order_id = self.hedge_mgr.hedge_order_id
        if not hedge_order_id:
            return
        
        original_on_trade = self.user_ws._on_trade
        
        async def _hedge_trade_handler(data: dict):
            """Handle trade events and check for hedge fills."""
            # Call original handler first
            if original_on_trade:
                await original_on_trade(data)
            
            # Check if this trade is for our hedge order
            # GTD orders are maker orders, so check maker_order_id
            trade_order_id = data.get("maker_order_id", "") or data.get("taker_order_id", "")
            status = data.get("status", "")
            
            if trade_order_id == hedge_order_id and status == "MATCHED":
                size = int(float(data.get("size", 0)))
                price = float(data.get("price", 0))
                
                self.hedge_mgr.on_hedge_fill(size, price)
                
                pos = self._position if hasattr(self, '_position') else None
                filled = self.hedge_mgr._position.hedge_contracts_filled if self.hedge_mgr._position else 0
                total = self.hedge_mgr._position.contracts if self.hedge_mgr._position else 0
                
                if self.hedge_mgr.is_hedged:
                    # Fully filled
                    self.stats.record_hedge(filled, price)
                    self.dashboard.hedge_flash = True
                    
                    await self.telegram.send_message(
                        f"✅ <b>Hedge FULLY Filled!</b>\n"
                        f"📦 {filled} contracts @ ${price}\n"
                        f"🛡️ Position fully protected"
                    )
                    logger.info(f"Hedge fully filled: {filled} contracts")
                else:
                    # Partial fill
                    await self.telegram.send_message(
                        f"🛡️ <b>Hedge Partial Fill</b>\n"
                        f"📦 +{size} contracts @ ${price}\n"
                        f"📊 Progress: {filled}/{total}"
                    )
                    logger.info(f"Hedge partial fill: +{size}, total {filled}/{total}")
        
        self.user_ws._on_trade = _hedge_trade_handler
        logger.info(f"Registered hedge fill handler for order {hedge_order_id[:20]}...")
    
    async def check_market_end(self):
        """Close position at market end."""
        pos = self.stats.position
        if not pos:
            return
        
        time_left = self.state.end_time - time.time()
        if time_left <= 10:  # 10 seconds before end
            hedged_was = pos.hedged
            if pos.token_name == "UP" and self.state.up_token:
                final_price = self.state.up_token.last_price
            elif pos.token_name == "DOWN" and self.state.down_token:
                final_price = self.state.down_token.last_price
            else:
                final_price = 0.5
            
            # Log market end details
            signal_logger.info("=" * 60)
            signal_logger.info("MARKET END - POSITION CLOSING")
            signal_logger.info(f"  Time: {datetime.now().isoformat()}")
            signal_logger.info(f"  Market: {self.state.slug}")
            signal_logger.info(f"  Position: {pos.token_name}")
            signal_logger.info(f"  Entry Price: {pos.entry_price:.4f}")
            signal_logger.info(f"  Final Price: {final_price:.4f}")
            signal_logger.info(f"  Contracts: {pos.contracts}")
            signal_logger.info(f"  Hedged: {pos.hedged}")
            
            record = self.stats.close_position(final_price)
            if record:
                self._simulation_log_close(record, hedged_was)
                status = "✅ WIN" if record.won else "❌ LOSS"
                
                signal_logger.info(f"  Result: {'WIN' if record.won else 'LOSS'}")
                signal_logger.info(f"  P&L: ${record.pnl:+.2f}")
                signal_logger.info(f"  Max Drawdown: -{record.max_drawdown_abs:.4f} (-{record.max_drawdown_pct:.2f}%)")
                dd_usd = record.max_drawdown_abs * record.contracts
                signal_logger.info(f"  Max DD ($): -${dd_usd:.2f} (min price: {record.entry_price - record.max_drawdown_abs:.4f})")
                signal_logger.info(f"  Total Trades: {len(self.stats.trades)}")
                signal_logger.info(f"  Session Stats: W={sum(1 for r in self.stats.trades if r.won)} / L={sum(1 for r in self.stats.trades if not r.won)}")
                signal_logger.info(f"  Total P&L: ${sum(r.pnl for r in self.stats.trades):+.2f}")
                signal_logger.info("=" * 60)
                
                logger.info(f"Position closed: {status}, PnL: ${record.pnl:+.2f}")
    
    async def run_session(self):
        """Run single market session with dashboard."""
        # Start WebSocket
        self.ws_client = WebSocketClient(self.state)
        ws_task = asyncio.create_task(self.ws_client.connect())
        
        await asyncio.sleep(1)
        
        # Track running order task (для non-blocking execution)
        order_task: Optional[asyncio.Task] = None
        
        try:
            with Live(self.dashboard.render(), refresh_per_second=4, console=console) as live:
                while self.running:
                    # Update dashboard (никогда не блокируется)
                    live.update(self.dashboard.render())
                    if self._web_snapshot_holder:
                        self._web_snapshot_holder.set(self.dashboard.build_web_snapshot())
                    
                    # Check for entry signal - запускаем в отдельном task
                    if self.stats.can_enter() and self.dashboard.last_signal:
                        if order_task is None or order_task.done():
                            signal = self.dashboard.last_signal
                            self.dashboard.last_signal = ""
                            order_task = asyncio.create_task(self._safe_execute_entry(signal))
                    
                    # Check if order completed
                    if order_task and order_task.done():
                        try:
                            order_task.result()  # Получаем исключения если были
                        except Exception as e:
                            logger.error(f"Order task error: {e}")
                        order_task = None
                    
                    # Track drawdown while in position
                    if self.stats.position:
                        pos = self.stats.position
                        if pos.token_name == "UP" and self.state.up_token:
                            self.stats.update_drawdown(self.state.up_token.last_price)
                        elif pos.token_name == "DOWN" and self.state.down_token:
                            self.stats.update_drawdown(self.state.down_token.last_price)
                    
                    # Check market end (быстрая операция - не выносим в task)
                    await self.check_market_end()
                    
                    # Market ended?
                    if time.time() > self.state.end_time:
                        console.print("\n[yellow]Market ended![/yellow]")
                        break
                    
                    await asyncio.sleep(0.25)
        finally:
            # Cancel any running order tasks
            for task in [order_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except:
                        pass
            
            # Graceful WebSocket shutdown
            await self.ws_client.stop_graceful()
            try:
                ws_task.cancel()
                await ws_task
            except:
                pass
            
            # Stop User WebSocket for order tracking
            if self.user_ws:
                await self.user_ws.disconnect()
            if self._user_ws_task:
                try:
                    self._user_ws_task.cancel()
                    await self._user_ws_task
                except:
                    pass
    
    async def _safe_execute_entry(self, signal: str):
        """Execute entry in separate task with error handling."""
        try:
            await self.execute_entry(signal)
        except Exception as e:
            logger.error(f"Entry execution error: {e}")
            signal_logger.error(f"ENTRY ERROR: {e}")
    
    # GTD hedge is placed immediately after entry (no polling needed)
    # Fills are tracked via WebSocket _register_hedge_ws_handler()
    
    async def run(self):
        """Main run loop."""
        if not await self.initialize():
            return
        
        self.running = True

        redeemer_task = None
        if self.redeemer is not None:
            redeemer_task = asyncio.create_task(self.redeemer.run_loop())

        sim_note = ""
        if self.config.simulation.enabled:
            sim_note = "🎮 <b>SIMULATION MODE</b> — no real orders\n"
        await self.telegram.send_message(
            f"{sim_note}"
            f"🤖 <b>Bot Started</b>\n"
            f"Strategy: ${self.config.entry.bet_amount_usd} per trade\n"
            f"Hedge: {'enabled' if self.config.hedge.enabled else 'disabled'}"
        )
        
        try:
            while self.running:
                # Find market
                if not await self.find_market():
                    console.print("[red]No market found. Waiting 30s...[/red]")
                    await asyncio.sleep(30)
                    continue
                
                console.print("\n[bold green]Starting session...[/bold green]\n")
                await self.run_session()
                
                console.print("[yellow]Waiting 5s for next market...[/yellow]")
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping...[/yellow]")
        finally:
            self.running = False
            if self.redeemer is not None:
                self.redeemer.stop()
            if redeemer_task is not None:
                try:
                    redeemer_task.cancel()
                    await redeemer_task
                except Exception:
                    pass
            
            # Gracefully close Chainlink RTDS WebSocket
            if self.chainlink_client:
                await self.chainlink_client.disconnect()
            if self._chainlink_task:
                try:
                    self._chainlink_task.cancel()
                    await self._chainlink_task
                except:
                    pass
            
            await self.telegram.send_message("🛑 Bot stopped")
            await self.telegram.close()
            
            console.print("[green]Bot stopped.[/green]")


async def main():
    bot = LiveTradingBot()
    
    loop = asyncio.get_event_loop()
    
    def shutdown():
        bot.running = False
    
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, shutdown)
    
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
