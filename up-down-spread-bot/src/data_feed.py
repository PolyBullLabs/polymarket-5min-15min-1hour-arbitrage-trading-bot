"""
Multi-Market data feed: Polymarket orderbook for 4 coins
"""
import json
import time
import threading
import websocket
import subprocess
import requests
import os
import hmac
import hashlib
import base64
from typing import Optional, Dict
import trader as trader_module
from position_tracker import PositionTracker


class DataFeed:
    """Polymarket orderbooks for BTC, ETH, SOL, XRP (configurable 5m or 15m windows)."""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # ✅ POSITION TRACKER - single source of truth for positions!
        self.position_tracker = PositionTracker()
        
        # API credentials for authenticated WebSocket
        self.api_key = os.getenv('POLYMARKET_API_KEY')
        self.api_secret = os.getenv('POLYMARKET_API_SECRET')
        self.api_passphrase = os.getenv('POLYMARKET_API_PASSPHRASE')
        
        pm = config.get("data_sources", {}).get("polymarket", {})
        self.market_interval_sec = int(pm.get("market_interval_sec", 900))
        if self.market_interval_sec <= 0:
            self.market_interval_sec = 900
        # Slug: {coin}-updown-5m-{slot} or {coin}-updown-15m-{slot}
        if self.market_interval_sec == 300:
            self.market_slug_suffix = "5m"
        elif self.market_interval_sec == 900:
            self.market_slug_suffix = "15m"
        else:
            self.market_slug_suffix = (
                f"{self.market_interval_sec // 60}m"
                if self.market_interval_sec % 60 == 0
                else "15m"
            )
            print(
                f"[DATA] Warning: market_interval_sec={self.market_interval_sec} "
                f"(standard Polymarket crypto up/down uses 300 or 900). Slug suffix={self.market_slug_suffix}"
            )
        
        iv = self.market_interval_sec
        tnow = int(time.time())
        self.markets = {}
        for coin in ["btc", "eth", "sol", "xrp"]:
            self.markets[coin] = {
                "slug": "",
                "up_ask": 0.5,
                "down_ask": 0.5,
                "up_bid": 0.5,
                "down_bid": 0.5,
                "up_ask_timestamp": 0.0,
                "down_ask_timestamp": 0.0,
                "up_bid_timestamp": 0.0,
                "down_bid_timestamp": 0.0,
                "up_bids_full": [],
                "down_bids_full": [],
                "up_asks_full": [],
                "down_asks_full": [],
                "tokens": {},
                "seconds_till_end": iv,
                "market_end_time": tnow + iv,
                "market_start_price": 0.0,
            }
        
        # Current prices (only BTC and ETH have price feeds)
        self.btc_price = 0.0
        self.eth_price = 0.0
        
        # Thread safety - per-coin locks for full parallelism
        self.locks = {
            'btc': threading.Lock(),
            'eth': threading.Lock(),
            'sol': threading.Lock(),
            'xrp': threading.Lock()
        }
        self.stop_event = threading.Event()
        
        # Threads
        self.threads = []
        
        # Event-driven callbacks for price updates
        self.price_callbacks = []
    
    def start(self):
        """Start data streams for BTC, ETH, SOL, XRP + User Channel"""
        # Polymarket WebSocket for all 4 coins
        for coin in ['btc', 'eth', 'sol', 'xrp']:
            pm_thread = threading.Thread(target=self._polymarket_worker, args=(coin,), daemon=True)
            pm_thread.start()
            self.threads.append(pm_thread)
            print(f"[DATA] Started Polymarket feed for {coin.upper()}")
        
        # ❌ USER CHANNEL DISABLED - WebSocket auth doesn't work
        # Using REST API takingAmount/makingAmount instead!
        print(f"[DATA] ℹ️  Position tracking via REST API responses")
        
        # Start local timer update (fixes timer freeze)
        timer_thread = threading.Thread(target=self._timer_worker, daemon=True)
        timer_thread.start()
        self.threads.append(timer_thread)
        
        print(
            f"[DATA] All feeds started: 4 Polymarket orderbooks "
            f"({self.market_slug_suffix} / {self.market_interval_sec}s windows)"
        )
    
    def stop(self):
        """Stop all data streams"""
        print("[DATA] Stopping feeds...")
        self.stop_event.set()
        
        # Give threads time to cleanup
        for t in self.threads:
            if t.is_alive():
                t.join(timeout=1)
        
        print("[DATA] Feeds stopped")
    
    def get_state(self, coin: str = 'btc') -> Dict:
        """Get current market state for specified coin (thread-safe)"""
        with self.locks[coin]:
            market = self.markets.get(coin)
            if not market:
                return None
            
            # Price only for BTC and ETH (SOL/XRP don't have price feeds)
            if coin == 'btc':
                price = self.btc_price
            elif coin == 'eth':
                price = self.eth_price
            else:
                price = 0.0  # SOL and XRP don't need price
            
            # Safe handling of None values
            up_ask = market.get('up_ask') or 0.0
            down_ask = market.get('down_ask') or 0.0
            confidence = abs(down_ask - up_ask) if (up_ask > 0 and down_ask > 0) else 0.0
            
            return {
                'up_ask': up_ask,
                'down_ask': down_ask,
                'price': price,
                'market_start_price': market['market_start_price'],
                'seconds_till_end': market['seconds_till_end'],
                'market_slug': market['slug'],
                'confidence': confidence,
                'coin': coin,
                'market_interval_sec': self.market_interval_sec,
                'market_slug_suffix': self.market_slug_suffix,
            }
    
    def register_price_callback(self, callback):
        """Register callback function for price updates (event-driven)"""
        self.price_callbacks.append(callback)
    
    def _current_slug(self, coin: str) -> str:
        """Calculate current market slug (5m or 15m per config)."""
        iv = self.market_interval_sec
        current_slot = int(time.time()) // iv * iv
        return f"{coin}-updown-{self.market_slug_suffix}-{current_slot}"
    
    def _fetch_tokens(self, coin: str) -> Optional[Dict]:
        """Fetch current market tokens from Polymarket for specified coin"""
        try:
            gamma_api = self.config['data_sources']['polymarket']['gamma_api']
            slug = self._current_slug(coin)
            
            # Use events API with specific slug
            url = f"{gamma_api}/events?slug={slug}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            
            events = resp.json()
            if not events:
                # Market not found - may not be open yet
                current_time = int(time.time())
                iv = self.market_interval_sec
                next_market = ((current_time // iv) + 1) * iv
                wait_time = next_market - current_time
                print(f"[PM-{coin.upper()}] Market {slug} not found (may not be open yet, next in {wait_time}s)")
                return None
            
            # Get first market
            market = events[0]["markets"][0]
            clob_token_ids = market.get("clobTokenIds", [])
            outcomes = market.get("outcomes", [])
            condition_id = market.get("conditionId", "")
            neg_risk = market.get("negRisk", True)
            
            # Parse if string format
            if isinstance(clob_token_ids, str):
                clob_token_ids = json.loads(clob_token_ids)
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            
            # Find Up and Down indices
            up_idx = outcomes.index("Up") if "Up" in outcomes else 0
            down_idx = outcomes.index("Down") if "Down" in outcomes else 1
            
            return {
                'up': clob_token_ids[up_idx],
                'down': clob_token_ids[down_idx],
                'condition_id': condition_id,
                'neg_risk': neg_risk
            }
            
        except Exception as e:
            print(f"[PM-{coin.upper()}] Error fetching tokens: {e}")
        return None
    
    def _polymarket_worker(self, coin: str):
        """Polymarket WebSocket worker for specified coin"""
        while not self.stop_event.is_set():
            # Fetch tokens
            tokens = self._fetch_tokens(coin)
            if not tokens:
                time.sleep(5)
                continue
            
            with self.locks[coin]:
                self.markets[coin]['tokens'] = tokens
            
            # Save token IDs to trader module for real trading
            market_slug = self._current_slug(coin)
            trader_module.set_token_ids(
                market_slug=market_slug,
                up_token_id=tokens['up'],
                down_token_id=tokens['down'],
                condition_id=tokens.get('condition_id', ''),
                neg_risk=tokens.get('neg_risk', True)
            )
            
            # Calculate reconnect time
            current_time = int(time.time())
            iv = self.market_interval_sec
            market_end = ((current_time // iv) * iv) + iv
            reconnect_in = market_end - current_time + 2
            
            # Get market slug
            market_slug = self._current_slug(coin)
            
            with self.locks[coin]:
                self.markets[coin]['slug'] = market_slug
                self.markets[coin]['market_end_time'] = market_end
                self.markets[coin]['tokens'] = tokens
                
                # ✅ Register market in PositionTracker for tracking via WebSocket
                self.position_tracker.register_market(
                    market_slug=market_slug,
                    up_token_id=tokens['up'],
                    down_token_id=tokens['down']
                )
                
                # Set market start price only for BTC/ETH (not needed for SOL/XRP)
                if self.markets[coin]['market_start_price'] == 0.0:
                    if coin == 'btc':
                        self.markets[coin]['market_start_price'] = self.btc_price
                    elif coin == 'eth':
                        self.markets[coin]['market_start_price'] = self.eth_price
                    # SOL/XRP: leave at 0.0 (no price feed needed)
            
            print(f"[PM-{coin.upper()}] Connected to {market_slug}, reconnect in {reconnect_in}s")
            
            # Connect WebSocket
            try:
                ws_url = self.config['data_sources']['polymarket']['ws_url']
                ws_ref = [None]  # Store ws reference for closing
                
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=lambda ws, msg: self._on_pm_message(msg, tokens, coin),
                    on_error=lambda ws, err: None,
                    on_close=lambda ws, code, reason: None
                )
                
                ws_ref[0] = ws
                
                def on_open(ws):
                    sub_msg = {
                        "auth": {},
                        "type": "MARKET",
                        "assets_ids": [tokens["up"], tokens["down"]]
                    }
                    ws.send(json.dumps(sub_msg))
                
                ws.on_open = on_open
                
                # Auto-reconnect timer
                timer = threading.Timer(reconnect_in, lambda: ws.close())
                timer.start()
                
                # Stop checker thread
                def check_stop():
                    while not self.stop_event.is_set():
                        time.sleep(0.5)
                    if ws_ref[0]:
                        ws_ref[0].close()
                
                stop_checker = threading.Thread(target=check_stop, daemon=True)
                stop_checker.start()
                
                ws.run_forever(ping_interval=20, ping_timeout=10, skip_utf8_validation=True)
                timer.cancel()
                
                # Stop immediately if stop_event is set
                if self.stop_event.is_set():
                    break
                
            except Exception as e:
                print(f"[PM-{coin.upper()}] Error: {e}")
                time.sleep(5)
    
    def _on_pm_message(self, message: str, tokens: Dict, coin: str):
        """Parse Polymarket orderbook message for specified coin"""
        try:
            data = json.loads(message)
            
            if not isinstance(data, dict):
                return
            
            # Only process "book" events (full orderbook snapshots)
            event_type = data.get("event_type", "unknown")
            if event_type != "book":
                return
            
            # Parse orderbook
            asks_raw = data.get("asks", [])
            bids_raw = data.get("bids", [])
            
            # Parse asks (price, size) tuples
            asks = []
            for ask in asks_raw or []:
                if isinstance(ask, dict):
                    price = float(ask.get("price", 0))
                    size = float(ask.get("size", 0))
                else:
                    price = float(ask[0]) if len(ask) > 0 else 0
                    size = float(ask[1]) if len(ask) > 1 else 0
                if price > 0 and size > 0:
                    asks.append((price, size))
            
            # Parse bids (price, size) tuples
            bids = []
            for bid in bids_raw or []:
                if isinstance(bid, dict):
                    price = float(bid.get("price", 0))
                    size = float(bid.get("size", 0))
                else:
                    price = float(bid[0]) if len(bid) > 0 else 0
                    size = float(bid[1]) if len(bid) > 1 else 0
                if price > 0 and size > 0:
                    bids.append((price, size))
            
            # Sort asks ascending (lowest first)
            asks.sort(key=lambda x: x[0])
            
            # Sort bids descending (highest first)
            bids.sort(key=lambda x: x[0], reverse=True)
            
            # Get best ask (lowest price) and best bid (highest price)
            best_ask = asks[0] if asks else None
            best_bid = bids[0] if bids else None
            
            asset = data.get("asset_id", "")
            
            # Update state and trigger callbacks (per-coin lock - fully parallel!)
            with self.locks[coin]:
                price_changed = False
                old_up_ask = self.markets[coin]['up_ask']
                old_down_ask = self.markets[coin]['down_ask']
                old_up_bid = self.markets[coin]['up_bid']
                old_down_bid = self.markets[coin]['down_bid']
                
                if best_ask:
                    price, size = best_ask
                    
                    if asset == tokens.get("up"):
                        self.markets[coin]['up_ask'] = price
                        self.markets[coin]['up_ask_timestamp'] = time.time()  # Track update time
                        # Save full orderbook (1 ask level + 5 bid levels)
                        self.markets[coin]['up_asks_full'] = asks[:1]  # Top 1 ask
                        self.markets[coin]['up_bids_full'] = bids[:5]  # Top 5 bids
                        if price != old_up_ask:
                            price_changed = True
                    elif asset == tokens.get("down"):
                        self.markets[coin]['down_ask'] = price
                        self.markets[coin]['down_ask_timestamp'] = time.time()  # Track update time
                        # Save full orderbook (1 ask level + 5 bid levels)
                        self.markets[coin]['down_asks_full'] = asks[:1]  # Top 1 ask
                        self.markets[coin]['down_bids_full'] = bids[:5]  # Top 5 bids
                        if price != old_down_ask:
                            price_changed = True
                
                if best_bid:
                    price, size = best_bid
                    
                    if asset == tokens.get("up"):
                        self.markets[coin]['up_bid'] = price
                        self.markets[coin]['up_bid_timestamp'] = time.time()  # Track update time
                        # Update full orderbook if not set by ask
                        if not self.markets[coin]['up_bids_full']:
                            self.markets[coin]['up_bids_full'] = bids[:5]
                        if price != old_up_bid:
                            price_changed = True
                    elif asset == tokens.get("down"):
                        self.markets[coin]['down_bid'] = price
                        self.markets[coin]['down_bid_timestamp'] = time.time()  # Track update time
                        # Update full orderbook if not set by ask
                        if not self.markets[coin]['down_bids_full']:
                            self.markets[coin]['down_bids_full'] = bids[:5]
                        if price != old_down_bid:
                            price_changed = True
                
                # Trigger callbacks if price changed
                if price_changed:
                    up_ask = self.markets[coin]['up_ask']
                    down_ask = self.markets[coin]['down_ask']
                    up_bid = self.markets[coin]['up_bid']
                    down_bid = self.markets[coin]['down_bid']
                    
                    # Skip if prices not ready yet
                    if up_ask is None or down_ask is None:
                        price_changed = False
                    else:
                        market_slug = self.markets[coin]['slug']
                        seconds_till_end = self.markets[coin]['seconds_till_end']
                        
                        # Get price only for BTC/ETH
                        if coin == 'btc':
                            market_price = self.btc_price
                        elif coin == 'eth':
                            market_price = self.eth_price
                        else:
                            market_price = 0.0  # SOL/XRP don't have price
                        
                        market_start_price = self.markets[coin]['market_start_price']
                        
                        # Build market_state for callback
                        market_state = {
                            'up_ask': up_ask,
                            'down_ask': down_ask,
                            'up_bid': up_bid,
                            'down_bid': down_bid,
                            'up_ask_timestamp': self.markets[coin]['up_ask_timestamp'],
                            'down_ask_timestamp': self.markets[coin]['down_ask_timestamp'],
                            'up_bid_timestamp': self.markets[coin]['up_bid_timestamp'],
                            'down_bid_timestamp': self.markets[coin]['down_bid_timestamp'],
                            'price': market_price,
                            'market_start_price': market_start_price,
                            'seconds_till_end': seconds_till_end,
                            'market_slug': market_slug,
                            'confidence': abs(down_ask - up_ask),
                            'coin': coin
                        }
                    
                    # Call all registered callbacks (outside lock to avoid deadlock)
                    callbacks_to_call = list(self.price_callbacks)
            
            # Call callbacks outside the lock
            # 🔥 ASYNC: each coin is processed in parallel
            if price_changed and callbacks_to_call:
                for callback in callbacks_to_call:
                    try:
                        # Wrapper for safe call
                        def safe_callback_wrapper():
                            try:
                                callback(coin, market_state)
                            except Exception as e:
                                # Log but don't crash
                                print(f"[CALLBACK ERROR] {coin}: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # 🛡️ Start in separate thread (doesn't block other coins)
                        threading.Thread(
                            target=safe_callback_wrapper,
                            daemon=True,
                            name=f"cb_{coin}_{int(time.time()*1000)}"
                        ).start()
                    except Exception as e:
                        print(f"[CALLBACK ERROR] Failed to start callback for {coin}: {e}")
                
        except Exception as e:
            pass  # Ignore parsing errors
    
    def _timer_worker(self):
        """Update timer every second locally for all markets (per-coin locks)"""
        while not self.stop_event.is_set():
            current_time = int(time.time())
            # Update each coin's timer independently (fully parallel)
            for coin in ['btc', 'eth', 'sol', 'xrp']:
                with self.locks[coin]:
                    market_end_time = self.markets[coin]['market_end_time']
                    self.markets[coin]['seconds_till_end'] = max(0, market_end_time - current_time)
            time.sleep(1)
    
    def _user_channel_worker(self):
        """
        WebSocket User Channel - source of ALL position data!
        
        Connects to authenticated channel and receives:
        - ORDER events (with size_matched - real amount!)
        - TRADE events (transaction confirmations)
        
        THIS IS THE SINGLE SOURCE OF TRUTH!
        """
        reconnect_delay = 5
        
        while not self.stop_event.is_set():
            try:
                ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
                
                print("[USER-WS] 🔌 Connecting to User Channel...")
                
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=lambda ws, msg: self._on_user_message(msg),
                    on_error=lambda ws, err: print(f"[USER-WS] ❌ Error: {err}") if err else None,
                    on_close=lambda ws, code, reason: print(f"[USER-WS] 🔌 Disconnected (code={code})")
                )
                
                def on_open(ws):
                    """Send authenticated subscription request"""
                    try:
                        # Create signature for authentication
                        timestamp = str(int(time.time()))
                        message = timestamp
                        signature = hmac.new(
                            self.api_secret.encode('utf-8'),
                            message.encode('utf-8'),
                            hashlib.sha256
                        ).digest()
                        signature_b64 = base64.b64encode(signature).decode('utf-8')
                        
                        sub_msg = {
                            "auth": {
                                "apikey": self.api_key,
                                "secret": signature_b64,
                                "passphrase": self.api_passphrase,
                                "timestamp": timestamp
                            },
                            "type": "user"
                        }
                        ws.send(json.dumps(sub_msg))
                        print("[USER-WS] ✅ Authenticated & subscribed to user channel")
                    except Exception as e:
                        print(f"[USER-WS] ⚠️  Auth failed: {e}")
                
                ws.on_open = on_open
                
                # Run forever (blocking call)
                ws.run_forever()
                
            except Exception as e:
                print(f"[USER-WS] ⚠️  Exception: {e}")
            
            # Reconnect delay
            if not self.stop_event.is_set():
                print(f"[USER-WS] ⏳ Reconnecting in {reconnect_delay}s...")
                time.sleep(reconnect_delay)
    
    def _on_user_message(self, message: str):
        """
        Process all USER events - SINGLE source of truth!
        
        Event types:
        - order: ORDER events (PLACEMENT/UPDATE/CANCELLATION)
        - trade: TRADE events (MATCHED/MINED/CONFIRMED)
        
        All events are passed to PositionTracker!
        """
        try:
            data = json.loads(message)
            event_type = data.get("event_type")
            
            if event_type == "order":
                # ✅ ORDER EVENT - update position via tracker
                self.position_tracker.on_order_event(data)
            
            elif event_type == "trade":
                # ✅ TRADE EVENT - confirm trade
                self.position_tracker.on_trade_event(data)
            
            else:
                # Other event types (e.g., heartbeat)
                pass
        
        except json.JSONDecodeError:
            # Not JSON message (e.g., connection established)
            pass
        except Exception as e:
            print(f"[USER-WS] ⚠️  Parse error: {e}")
