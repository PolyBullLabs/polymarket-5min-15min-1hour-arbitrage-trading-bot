#!/usr/bin/env python3
"""
Polymarket BTC 5m / 15m up-down auto-trading (WebSocket)
Monitors markets, checks rules, places orders, manages stops.
Uses WebSockets for lower-latency prices.
"""
import os
import sys
import time
import json
import threading
import requests
from datetime import datetime, timezone
from urllib.parse import urlencode
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Load environment
load_dotenv(os.path.join(BASE_DIR, "config.env"))

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL
    HAS_CLOB = True
except:
    HAS_CLOB = False
    print("Please install: pip install py-clob-client")
    sys.exit(1)

try:
    import websocket
    HAS_WS = True
except:
    HAS_WS = False
    print("Please install: pip install websocket-client")
    sys.exit(1)

try:
    from web3 import Web3
    HAS_WEB3 = True
except:
    HAS_WEB3 = False

# ============== Settings ==============
GAMMA_API = "https://gamma-api.polymarket.com"
CRYPTO_PRICE_API = "https://polymarket.com/api/crypto/crypto-price"
# PTB must match Polymarket UI: use "fifteen" for both 5m and 15m BTC up/down when passing
# the event's eventStartTime + endDate from Gamma. variant "five" returns a different anchor.
CRYPTO_PRICE_PTB_VARIANT = "fifteen"
BINANCE_WSS = "wss://stream.binance.com:9443/ws/btcusdt@trade"
POLYMARKET_WSS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
CLOB_API = "https://clob.polymarket.com"
RTDS_WS = "wss://ws-live-data.polymarket.com"  # Chainlink price WebSocket
DATA_API = "https://data-api.polymarket.com"
CTF_CONTRACT = "0x4d97dcd97ec945f40cf65f87097ace5ea0476045"
USDC_E_CONTRACT = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"

# Proxy (optional)
HTTP_PROXY = os.getenv("HTTP_PROXY", "")  # e.g. http://127.0.0.1:7890
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")

# Build proxy dict
PROXIES = {}
if HTTP_PROXY:
    PROXIES["http"] = HTTP_PROXY
    # log(f"Using HTTP proxy: {HTTP_PROXY}", "INFO") # log function not yet defined here
if HTTPS_PROXY:
    PROXIES["https"] = HTTPS_PROXY
    # log(f"Using HTTPS proxy: {HTTPS_PROXY}", "INFO") # log function not yet defined here

# Trading
AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT", "5"))
# Paper trading: run strategy with instant fills; no CLOB orders. Implies no on-chain redeem in main().
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "false").lower() == "true"
# One JSON object per line: fills, PnL, BTC/PTB context for offline analysis
# Relative paths are resolved against BASE_DIR (script folder), not the shell cwd.
_tal_raw = (os.getenv("TRADING_ANALYSIS_LOG", "") or "").strip()
if not _tal_raw:
    TRADING_ANALYSIS_LOG = os.path.join(BASE_DIR, "trading_analysis.jsonl")
elif os.path.isabs(_tal_raw):
    TRADING_ANALYSIS_LOG = os.path.normpath(_tal_raw)
else:
    TRADING_ANALYSIS_LOG = os.path.normpath(os.path.join(BASE_DIR, _tal_raw))
TRADING_ANALYSIS_LOG = os.path.abspath(TRADING_ANALYSIS_LOG)

# Trigger rules (examples in comments)
# C1: within 120s left, diff ≥ 30, UP prob ~80–92%
C1_TIME = int(os.getenv("CONDITION_1_TIME", "120"))
C1_DIFF = float(os.getenv("CONDITION_1_DIFF", "30"))
C1_MIN_PROB = float(os.getenv("CONDITION_1_MIN_PROB", "0.80"))
C1_MAX_PROB = float(os.getenv("CONDITION_1_MAX_PROB", "0.92"))

# C2: within 120s, diff ≥ 30, DOWN prob ~80–92%
C2_TIME = int(os.getenv("CONDITION_2_TIME", "120"))
C2_DIFF = float(os.getenv("CONDITION_2_DIFF", "30"))
C2_MIN_PROB = float(os.getenv("CONDITION_2_MIN_PROB", "0.80"))
C2_MAX_PROB = float(os.getenv("CONDITION_2_MAX_PROB", "0.92"))

# C3: within 60s, diff ≥ 50, UP prob ~80–92%
C3_TIME = int(os.getenv("CONDITION_3_TIME", "60"))
C3_DIFF = float(os.getenv("CONDITION_3_DIFF", "50"))
C3_MIN_PROB = float(os.getenv("CONDITION_3_MIN_PROB", "0.80"))
C3_MAX_PROB = float(os.getenv("CONDITION_3_MAX_PROB", "0.92"))

# C4: within 60s, diff ≥ 50, DOWN prob ~80–92%
C4_TIME = int(os.getenv("CONDITION_4_TIME", "60"))
C4_DIFF = float(os.getenv("CONDITION_4_DIFF", "50"))
C4_MIN_PROB = float(os.getenv("CONDITION_4_MIN_PROB", "0.80"))
C4_MAX_PROB = float(os.getenv("CONDITION_4_MAX_PROB", "0.92"))

ORDER_TIMEOUT_SEC = int(os.getenv("ORDER_TIMEOUT_SEC", "8"))  # cancel if unfilled after N seconds
SLIPPAGE_THRESHOLD = float(os.getenv("SLIPPAGE_THRESHOLD", "0.05"))  # 5% slippage cap
MAX_RETRY_PER_MARKET = int(os.getenv("MAX_RETRY_PER_MARKET", "2"))  # max retries per market
BUY_RETRY_STEP = max(0.001, float(os.getenv("BUY_RETRY_STEP", "0.01")))
STOP_LOSS_PROB_PCT = float(os.getenv("STOP_LOSS_PROB_PCT", "0.15"))
TAKE_PROFIT_RR = max(0.2, float(os.getenv("TAKE_PROFIT_RR", "1.0")))
TAKE_PROFIT_CAP = min(0.995, max(0.55, float(os.getenv("TAKE_PROFIT_CAP", "0.99"))))
TAKE_PROFIT_RETRY_STEP = max(0.001, float(os.getenv("TAKE_PROFIT_RETRY_STEP", "0.005")))
TAKE_PROFIT_RETRY_MAX = max(1, int(os.getenv("TAKE_PROFIT_RETRY_MAX", "3")))
MARKET_DATA_MAX_LAG_SEC = max(0.2, float(os.getenv("MARKET_DATA_MAX_LAG_SEC", "1.2")))
LOOP_INTERVAL_SEC = max(0.1, float(os.getenv("LOOP_INTERVAL_SEC", "0.25")))

# Risk / ops
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "2"))

AUTO_REDEEM = os.getenv("AUTO_REDEEM", "true").lower() == "true"
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "")
REDEEM_SCAN_INTERVAL = max(3, int(os.getenv("REDEEM_SCAN_INTERVAL", "15")))
REDEEM_RETRY_INTERVAL = max(10, int(os.getenv("REDEEM_RETRY_INTERVAL", "120")))
REDEEM_MAX_PER_SCAN = max(1, int(os.getenv("REDEEM_MAX_PER_SCAN", "2")))
REDEEM_PENDING_LOG_INTERVAL = max(10, int(os.getenv("REDEEM_PENDING_LOG_INTERVAL", "30")))
POLY_BUILDER_API_KEY = os.getenv("POLY_BUILDER_API_KEY", "")
POLY_BUILDER_SECRET = os.getenv("POLY_BUILDER_SECRET", "")
POLY_BUILDER_PASSPHRASE = os.getenv("POLY_BUILDER_PASSPHRASE", "")
RELAYER_URL = os.getenv("RELAYER_URL", "https://relayer-v2.polymarket.com")
RELAYER_TX_TYPE = os.getenv("RELAYER_TX_TYPE", "SAFE").upper()
DASHBOARD_ACCOUNT_SYNC_SEC = max(10, int(os.getenv("DASHBOARD_ACCOUNT_SYNC_SEC", "20")))
MARKET_FOUND_LOG_INTERVAL = max(10, int(os.getenv("MARKET_FOUND_LOG_INTERVAL", "30")))
MARKET_META_REFRESH_SEC = max(2, int(os.getenv("MARKET_META_REFRESH_SEC", "5")))

WEB_ENABLED = os.getenv("WEB_ENABLED", "true").lower() == "true"
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "5080"))


def _normalize_btc_market_minutes(m):
    """Polymarket supports 5m and 15m BTC up/down events."""
    try:
        n = int(float(str(m).strip()))
    except (TypeError, ValueError):
        return 15
    return 5 if n == 5 else 15


_btc_market_minutes = _normalize_btc_market_minutes(os.getenv("BTC_MARKET_MINUTES", "15"))
_market_interval_sec = _btc_market_minutes * 60

# Persisted state file
STATE_FILE = os.path.join(BASE_DIR, "state.json")

# Global price snapshot
price_data = {
    "btc": None,           # Chainlink BTC (trading reference)
    "binance": None,       # Binance BTC (secondary)
    "ptb": None,           # Price to Beat
    "up_price": None,      # UP token mid
    "down_price": None,    # DOWN token mid
    "up_bid": None,
    "up_ask": None,
    "down_bid": None,
    "down_ask": None,
    "btc_update_ts": 0.0,
    "up_update_ts": 0.0,
    "down_update_ts": 0.0,
    "last_update": None,
}

dashboard_lock = threading.Lock()
dashboard_cond = threading.Condition(dashboard_lock)
dashboard_version = 0
dashboard_state = {
    "updated_at": None,
    "market": {},
    "wallet_balance": None,
    "prices": {},
    "position": {},
    "pending_order": {},
    "last_order": {},
    "trade_history": [],
    "wallet_positions": [],
    "wallet_history": [],
    "live_trades": [],
    "live_positions_count": 0,
    "live_realized_pnl": 0.0,
    "live_unrealized_pnl": 0.0,
    "live_total_pnl": 0.0,
    "auto_redeem": {},
    "activity": [],
    "btc_market_minutes": _btc_market_minutes,
    "cumulative_realized_pnl": 0.0,
    "simulation_mode": SIMULATION_MODE,
}

app = Flask(__name__, static_folder=STATIC_DIR)

_market_found_log_state = {"slug": "", "kind": "", "last_ts": 0.0}
_price_refresh_lock = threading.Lock()
_price_refresh_running = False
_market_cache_lock = threading.Lock()
_market_cache = None
_market_refresh_running = False
_account_sync_lock = threading.Lock()
_account_sync_running = False
_trading_analysis_log_lock = threading.Lock()


def _log_market_found_throttled(kind, slug, remaining):
    same_market = (_market_found_log_state.get("slug") == slug and _market_found_log_state.get("kind") == kind)
    if same_market:
        return
    _market_found_log_state["slug"] = slug
    _market_found_log_state["kind"] = kind
    _market_found_log_state["last_ts"] = time.time()
    log(f"Found {kind} market: {slug[:40]}... ({remaining//60}m {remaining%60}s left)", "OK")


def _trigger_price_refresh():
    global _price_refresh_running
    with _price_refresh_lock:
        if _price_refresh_running:
            return
        _price_refresh_running = True

    def worker():
        global _price_refresh_running
        try:
            chainlink_price = get_chainlink_btc_price()
            if chainlink_price:
                price_data["btc"] = chainlink_price
                ts = time.time()
                price_data["btc_update_ts"] = ts
                price_data["last_update"] = ts

            binance_price = get_binance_btc_price()
            if binance_price:
                price_data["binance"] = binance_price
        finally:
            with _price_refresh_lock:
                _price_refresh_running = False

    threading.Thread(target=worker, daemon=True).start()


def _trigger_market_refresh():
    global _market_refresh_running, _market_cache
    with _market_cache_lock:
        if _market_refresh_running:
            return
        _market_refresh_running = True

    def worker():
        global _market_refresh_running, _market_cache
        try:
            market = get_active_market()
            with _market_cache_lock:
                _market_cache = dict(market) if isinstance(market, dict) else None
        finally:
            with _market_cache_lock:
                _market_refresh_running = False

    threading.Thread(target=worker, daemon=True).start()


def _get_market_cache():
    with _market_cache_lock:
        return dict(_market_cache) if isinstance(_market_cache, dict) else None


def _clear_market_cache():
    global _market_cache
    with _market_cache_lock:
        _market_cache = None


def _trigger_account_sync(user):
    global _account_sync_running
    u = str(user or "").strip().lower()
    if not u:
        return
    with _account_sync_lock:
        if _account_sync_running:
            return
        _account_sync_running = True

    def worker():
        global _account_sync_running
        try:
            _sync_dashboard_account_snapshot(u)
        except Exception:
            pass
        finally:
            with _account_sync_lock:
                _account_sync_running = False

    threading.Thread(target=worker, daemon=True).start()


def _dashboard_set(**kwargs):
    global dashboard_version
    with dashboard_cond:
        for k, v in kwargs.items():
            dashboard_state[k] = v
        dashboard_state["updated_at"] = datetime.now().isoformat()
        dashboard_version += 1
        dashboard_cond.notify_all()


@app.route("/")
def dashboard_index():
    return send_from_directory(STATIC_DIR, "dashboard.html")


@app.route("/api/status")
def dashboard_status():
    with dashboard_lock:
        return jsonify(dict(dashboard_state))


@app.route("/api/logs")
def dashboard_logs():
    with dashboard_lock:
        return jsonify({"items": list(dashboard_state.get("activity") or [])[-300:]})


@app.route("/api/stream")
def dashboard_stream():
    def _event(name, payload):
        return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def generate():
        last_seen = -1
        last_log_sig = ""
        while True:
            with dashboard_cond:
                if dashboard_version == last_seen:
                    dashboard_cond.wait(timeout=15)
                version_now = dashboard_version
                state_now = dict(dashboard_state)

            if version_now != last_seen:
                logs = list(state_now.get("activity") or [])[-300:]
                state_now.pop("activity", None)
                yield _event("status", {"data": state_now})

                if logs:
                    tail = logs[-1]
                    sig = f"{len(logs)}|{tail.get('time','')}|{tail.get('message','')}"
                else:
                    sig = "0"
                if sig != last_log_sig:
                    yield _event("logs", {"items": logs})
                    last_log_sig = sig

                last_seen = version_now
            else:
                yield ": ping\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/history")
def dashboard_history():
    with dashboard_lock:
        live_items = list(dashboard_state.get("live_trades") or [])
        if live_items:
            return jsonify({"items": live_items[-300:]})
        local_items = list(dashboard_state.get("trade_history") or [])
        wallet_items = list(dashboard_state.get("wallet_history") or [])
        return jsonify({"items": (local_items + wallet_items)[-300:]})


@app.route("/api/btc-market-minutes", methods=["POST"])
def api_btc_market_minutes():
    """Switch between 5m and 15m BTC markets (clears cached market metadata)."""
    if not WEB_ENABLED:
        return jsonify({"ok": False, "error": "web disabled"}), 404
    try:
        body = request.get_json(silent=True) or {}
        m = body.get("minutes", body.get("interval", 15))
        m = int(m)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid body"}), 400
    if m not in (5, 15):
        return jsonify({"ok": False, "error": "minutes must be 5 or 15"}), 400
    set_btc_market_minutes(m)
    return jsonify({"ok": True, "minutes": get_btc_market_minutes()})


def start_web_server():
    if not WEB_ENABLED:
        return

    def run():
        app.run(host=WEB_HOST, port=WEB_PORT, threaded=True, use_reloader=False)

    t = threading.Thread(target=run, daemon=True)
    t.start()

# ============== Utilities ==============
def log(msg, level="INFO", force=False):
    """Console + dashboard log."""
    if force or level in ["OK", "ERR", "WARN", "TRADE"]:
        icons = {"INFO": "ℹ️", "OK": "✅", "ERR": "❌", "WARN": "⚠️", "TRADE": "💰"}
        icon = icons.get(level, "ℹ️")
        ts = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{ts}] {icon} {msg}"
        print(log_msg)

        global dashboard_version
        with dashboard_cond:
            arr = dashboard_state.get("activity") or []
            arr.append({
                "time": ts,
                "level": level,
                "message": str(msg),
            })
            if len(arr) > 400:
                arr = arr[-400:]
            dashboard_state["activity"] = arr
            dashboard_state["updated_at"] = datetime.now().isoformat()
            dashboard_version += 1
            dashboard_cond.notify_all()
        
        # Persist TRADE and ERR to trade.log
        if level in ["TRADE", "ERR"]:
            try:
                with open("trade.log", "a", encoding="utf-8") as f:
                    f.write(log_msg + "\n")
            except:
                pass


def get_btc_market_minutes():
    return _btc_market_minutes


def set_btc_market_minutes(m):
    global _btc_market_minutes, _market_interval_sec
    _btc_market_minutes = _normalize_btc_market_minutes(m)
    _market_interval_sec = _btc_market_minutes * 60
    price_data["ptb"] = None
    _clear_market_cache()
    _trigger_market_refresh()
    _dashboard_set(btc_market_minutes=_btc_market_minutes)
    log(
        f"BTC market interval set to {_btc_market_minutes}m "
        f"(slug btc-updown-{_btc_market_minutes}m-*, PTB via {CRYPTO_PRICE_PTB_VARIANT!r} + event window)",
        "OK",
        force=True,
    )


def get_binance_btc_price():
    """Fetch BTC/USDT from Binance REST."""
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", 
                        params={"symbol": "BTCUSDT"}, 
                        proxies=PROXIES if PROXIES else None,
                        timeout=5)
        if r.status_code == 200:
            return float(r.json().get("price"))
    except:
        pass
    return None

def get_chainlink_btc_price():
    """Chainlink BTC via Polymarket RTDS WebSocket (fallback)."""
    result = {"price": None}
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            if data.get("topic") == "crypto_prices" and data.get("payload"):
                payload = data["payload"]
                if "data" in payload and payload.get("symbol") == "btc/usd":
                    prices = payload["data"]
                    if prices:
                        result["price"] = prices[-1]["value"]
                elif "value" in payload:
                    result["price"] = payload["value"]
            ws.close()
        except:
            pass
    
    def on_open(ws):
        sub_msg = {
            "action": "subscribe",
            "subscriptions": [{
                "topic": "crypto_prices_chainlink",
                "type": "*",
                "filters": "{\"symbol\":\"btc/usd\"}"
            }]
        }
        ws.send(json.dumps(sub_msg))
    
    def on_error(ws, error):
        pass
    
    try:
        ws = websocket.WebSocketApp(RTDS_WS,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error)
        
        def close_after():
            time.sleep(3)
            try:
                ws.close()
            except:
                pass
        threading.Thread(target=close_after, daemon=True).start()
        
        ws.run_forever()
        return result["price"]
    except:
        return None

def get_crypto_price_api(start_time, end_time):
    """
    PTB from Polymarket crypto-price API.
    Returns: {"openPrice": PTB, "closePrice": current or None, "completed": bool}
    """
    try:
        # Accept str or datetime for window bounds
        if isinstance(start_time, str):
            start_str = start_time.replace("Z", "+00:00")
            if "+" in start_str:
                start_str = start_str.split("+")[0] + "Z"
            else:
                start_str = start_time
        else:
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        if isinstance(end_time, str):
            end_str = end_time.replace("Z", "+00:00")
            if "+" in end_str:
                end_str = end_str.split("+")[0] + "Z"
            else:
                end_str = end_time
        else:
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        params = {
            "symbol": "BTC",
            "eventStartTime": start_str,
            "variant": CRYPTO_PRICE_PTB_VARIANT,
            "endDate": end_str
        }
        
        # Browser-like headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://polymarket.com/"
        }
        
        log(f"PTB request: {CRYPTO_PRICE_API}?{urlencode(params)}", "INFO")
        r = requests.get(CRYPTO_PRICE_API, params=params, headers=headers, 
                        proxies=PROXIES if PROXIES else None, timeout=10)
        
        log(f"PTB HTTP status: {r.status_code}", "INFO")
        
        if r.status_code == 200:
            data = r.json()
            log(f"PTB payload: {data}", "INFO")
            return data
        else:
            log(f"PTB request failed: HTTP {r.status_code} - {r.text[:200]}", "ERR")
    except Exception as e:
        log(f"crypto-price error: {type(e).__name__}: {str(e)}", "ERR")
    return {}

def get_current_slug():
    """Current window slug for configured interval (5m or 15m)."""
    ts = int(time.time())
    step = _market_interval_sec
    window_start = (ts // step) * step
    return f"btc-updown-{_btc_market_minutes}m-{window_start}"

def get_next_slug():
    """Next window slug for configured interval."""
    ts = int(time.time())
    step = _market_interval_sec
    window_start = ((ts // step) + 1) * step
    return f"btc-updown-{_btc_market_minutes}m-{window_start}"

def get_active_market():
    """Active BTC up/down market for the configured interval."""
    try:
        # Try current window first
        current_slug = get_current_slug()
        market = fetch_market_by_slug(current_slug)
        if market and market["remaining"] > 0:
            _log_market_found_throttled("current", current_slug, market["remaining"])
            return market
        
        # Then next window
        next_slug = get_next_slug()
        market = fetch_market_by_slug(next_slug)
        if market and market["remaining"] > 0:
            _log_market_found_throttled("next", next_slug, market["remaining"])
            return market
        
        log("No active market in current or next window", "WARN")
        
    except Exception as e:
        log(f"Market fetch failed: {e}", "ERR")
        import traceback
        traceback.print_exc()
    return None

def fetch_market_by_slug(slug):
    """Gamma API market row for slug."""
    try:
        r = requests.get(f"{GAMMA_API}/events", params={"slug": slug}, 
                        proxies=PROXIES if PROXIES else None, timeout=10)
        data = r.json()
        
        if not data:
            return None
        
        event = data[0]
        
        # Skip closed events
        if event.get("closed", False):
            return None
        
        end_str = event.get("endDate", "")
        start_str = event.get("startTime", "")
        if not end_str or not start_str:
            return None
        
        # Seconds until end
        now = datetime.now(timezone.utc).timestamp()
        end_ts = datetime.fromisoformat(end_str.replace("Z", "+00:00")).timestamp()
        remaining_time = int(end_ts - now)
        
        if remaining_time <= 0:
            return None
        
        # Parse first market
        markets = event.get("markets", [])
        if not markets:
            return None
        
        m = markets[0]
        outcomes = json.loads(m.get("outcomes", "[]")) if isinstance(m.get("outcomes"), str) else m.get("outcomes", [])
        prices = json.loads(m.get("outcomePrices", "[]")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices", [])
        tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
        
        # Assume outcomes[0]=UP, [1]=DOWN
        up_price = float(prices[0]) if len(prices) > 0 else None
        down_price = float(prices[1]) if len(prices) > 1 else None
        up_token = tokens[0] if len(tokens) > 0 else None
        down_token = tokens[1] if len(tokens) > 1 else None
        
        return {
            "slug": slug,
            "start": start_str,
            "end": end_str,
            "remaining": remaining_time,
            "up_price": up_price,
            "down_price": down_price,
            "up_token": up_token,
            "down_token": down_token
        }
    except Exception as e:
        # Missing market is normal
        return None

def get_ptb(start_time, end_time):
    """Fetch Price to Beat (open) for window."""
    try:
        params = {
            "symbol": "BTC",
            "eventStartTime": start_time,
            "variant": CRYPTO_PRICE_PTB_VARIANT,
            "endDate": end_time
        }
        r = requests.get(CRYPTO_PRICE_API, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return float(data.get("openPrice")) if data.get("openPrice") else None
    except:
        pass
    return None


def _normalize_state(state):
    if not isinstance(state, dict):
        state = {}
    if not isinstance(state.get("position"), dict):
        state["position"] = {}
    if not isinstance(state.get("pending_order"), dict):
        state["pending_order"] = {}
    if not isinstance(state.get("last_order"), dict):
        state["last_order"] = {}
    if not isinstance(state.get("take_profit_order"), dict):
        state["take_profit_order"] = {}
    if not isinstance(state.get("trade_history"), list):
        state["trade_history"] = []
    if state.get("cumulative_realized_pnl") is None or not isinstance(
        state.get("cumulative_realized_pnl"), (int, float)
    ):
        try:
            state["cumulative_realized_pnl"] = float(state.get("cumulative_realized_pnl") or 0.0)
        except (TypeError, ValueError):
            state["cumulative_realized_pnl"] = 0.0
    return state


def _dashboard_pending_order_from_state(state):
    state = _normalize_state(state)
    pending = dict(state.get("pending_order") or {})
    if pending:
        return pending
    tp = dict(state.get("take_profit_order") or {})
    if tp:
        tp.setdefault("action", "SELL")
        tp.setdefault("reason", "take_profit")
    return tp


def _append_trade_history(state, item):
    state = _normalize_state(state)
    hist = list(state.get("trade_history") or [])
    hist.append(item)
    if len(hist) > 300:
        hist = hist[-300:]
    state["trade_history"] = hist
    _dashboard_set(trade_history=list(hist))
    return state


def _planned_take_profit_stop_loss(entry_prob):
    """
    Same TP/SL probability levels as the main loop (for logging planned targets after a buy).
    Returns (take_profit_prob, stop_loss_prob) or (None, None).
    """
    if entry_prob is None or entry_prob <= 0:
        return None, None
    try:
        ep = float(entry_prob)
    except (TypeError, ValueError):
        return None, None
    stop_prob = max(0.0, ep * (1.0 - STOP_LOSS_PROB_PCT))
    risk_abs = max(0.0, ep - stop_prob)
    tp_trigger = min(TAKE_PROFIT_CAP, ep + risk_abs * TAKE_PROFIT_RR)
    if tp_trigger <= ep:
        return None, stop_prob
    balanced_risk = (tp_trigger - ep) / TAKE_PROFIT_RR
    balanced_stop = max(0.0, ep - balanced_risk)
    if balanced_stop > stop_prob:
        stop_prob = balanced_stop
    return tp_trigger, stop_prob


def _emit_trading_analysis(event, **fields):
    """Append one JSON line with a stable schema for analysis (see schema_version)."""
    ts = fields.get("time") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    btc = fields.get("btc_price")
    if btc is None:
        btc = fields.get("chainlink_btc")
    ptb = fields.get("ptb")

    diff = fields.get("difference")
    if diff is None:
        diff = fields.get("diff_rule", fields.get("diff"))
    if diff is None and btc is not None and ptb is not None:
        try:
            diff = float(btc) - float(ptb)
        except (TypeError, ValueError):
            diff = None

    st = fields.get("status")
    if not st:
        act = str(fields.get("action") or "").upper()
        if act == "BUY":
            st = "buy"
        elif act == "SELL":
            st = "sell"

    shares_type = fields.get("shares_type") or fields.get("side")

    share_price = fields.get("share_price")
    if share_price is None:
        share_price = fields.get("price")
    if share_price is None:
        share_price = fields.get("exit_share_price")

    share_amount = fields.get("share_amount")
    if share_amount is None:
        share_amount = fields.get("shares")

    pnl_trade = fields.get("pnl_trade_usd")
    if pnl_trade is None:
        pnl_trade = fields.get("realized_pnl_usd")

    pnl_total = fields.get("pnl_total_usd")
    if pnl_total is None:
        pnl_total = fields.get("cumulative_realized_pnl_usd")

    tp = fields.get("take_profit")
    sl = fields.get("stop_loss")
    if tp is None and sl is None:
        entry_plan = fields.get("entry_share_price")
        if entry_plan is None:
            entry_plan = share_price
        _no_auto_plan = (
            "SELL_CLOSE",
            "SELL_SUBMIT",
            "SELL_FAILED",
            "SELL_ALERT",
            "BUY_CANCEL_TIMEOUT",
        )
        if entry_plan is not None and event not in _no_auto_plan:
            tp, sl = _planned_take_profit_stop_loss(entry_plan)

    def _nf(x):
        if x is None:
            return None
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    row = {
        "schema_version": 2,
        "event": event,
        "slug": fields.get("slug"),
        "shares_type": shares_type,
        "share_price": _nf(share_price),
        "share_amount": _nf(share_amount),
        "ptb": _nf(ptb),
        "btc_price": _nf(btc),
        "difference": _nf(diff),
        "difference_note": "Chainlink BTC minus PTB (USD); same as diff in bot logic.",
        "status": st,
        "take_profit": _nf(tp),
        "stop_loss": _nf(sl),
        "time": ts,
        "pnl_trade_usd": _nf(pnl_trade),
        "pnl_total_usd": _nf(pnl_total),
        "simulation": SIMULATION_MODE,
        "btc_market_minutes": _btc_market_minutes,
    }

    passthrough = (
        "reason",
        "order_id",
        "order_size_usdc",
        "remaining_sec",
        "entry_share_price",
        "exit_share_price",
        "notional_exit_usd",
        "action",
        "chainlink_btc",
        "btc_minus_ptb",
        "diff_rule",
    )
    for k in passthrough:
        if k in fields and fields[k] is not None:
            row[k] = fields[k]

    try:
        log_dir = os.path.dirname(TRADING_ANALYSIS_LOG)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with _trading_analysis_log_lock:
            with open(TRADING_ANALYSIS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
    except Exception as e:
        try:
            log(f"Trading analysis log write failed ({TRADING_ANALYSIS_LOG}): {e}", "ERR", force=True)
        except Exception:
            print(f"Trading analysis log write failed ({TRADING_ANALYSIS_LOG}): {e}", file=sys.stderr)


def _init_trading_analysis_session():
    """Create log file and write SESSION_START so path is visible even before any trade."""
    row = {
        "schema_version": 2,
        "event": "SESSION_START",
        "log_path": TRADING_ANALYSIS_LOG,
        "slug": None,
        "shares_type": None,
        "share_price": None,
        "share_amount": None,
        "ptb": None,
        "btc_price": None,
        "difference": None,
        "difference_note": "Chainlink BTC minus PTB (USD).",
        "status": None,
        "take_profit": None,
        "stop_loss": None,
        "time": None,
        "pnl_trade_usd": None,
        "pnl_total_usd": None,
        "simulation": SIMULATION_MODE,
        "auto_trade": AUTO_TRADE,
        "btc_market_minutes": _btc_market_minutes,
        "trade_amount_usdc": TRADE_AMOUNT,
        "note": "Trade rows use the same keys as SESSION_START; pnl_total_usd is cumulative realized.",
    }
    row["logged_at"] = row["time"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    try:
        log_dir = os.path.dirname(TRADING_ANALYSIS_LOG)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with _trading_analysis_log_lock:
            with open(TRADING_ANALYSIS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"FATAL: cannot write trading log at {TRADING_ANALYSIS_LOG}: {e}", file=sys.stderr)
        try:
            log(f"Cannot init trading analysis log: {e}", "ERR", force=True)
        except Exception:
            pass


def _shares_from_usdc_buy(usdc, share_price):
    if share_price and share_price > 0 and usdc and usdc > 0:
        return float(usdc) / float(share_price)
    return 0.0


def _btc_ptb_snapshot(btc, ptb):
    if btc is None or ptb is None:
        return None
    try:
        return float(btc) - float(ptb)
    except (TypeError, ValueError):
        return None


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _maybe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _data_api_get(path, params=None):
    try:
        r = requests.get(
            f"{DATA_API}{path}",
            params=params or {},
            proxies=PROXIES if PROXIES else None,
            timeout=12,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def _text_scalar(v):
    if isinstance(v, (str, int, float, bool)):
        return str(v).strip()
    return ""


def _normalize_outcome_label(v):
    s = str(v or "").upper()
    if "UP" in s or s == "YES":
        return "UP"
    if "DOWN" in s or s == "NO":
        return "DOWN"
    return s or "-"


def _trade_pick_field(tr, *keys):
    if not isinstance(tr, dict):
        return ""
    sources = [tr]
    market = tr.get("market")
    if isinstance(market, dict):
        sources.append(market)
    event = tr.get("event")
    if isinstance(event, dict):
        sources.append(event)
    for src in sources:
        for k in keys:
            if k not in src:
                continue
            s = _text_scalar(src.get(k))
            if s:
                return s
    return ""


def _trade_event_kind(tr):
    typ = str((tr or {}).get("type") or "").upper().strip()
    side = str((tr or {}).get("side") or "").upper().strip()
    if typ == "REDEEM":
        return "REDEEM"
    if typ in ["DEPOSIT", "WITHDRAW", "WITHDRAWAL", "TRANSFER"]:
        return "IGNORE"
    if side in ["BUY", "SELL"]:
        return side
    return "IGNORE"


def _trade_ts_ms(tr):
    v = (tr or {}).get("matchtime") or (tr or {}).get("match_time") or (tr or {}).get("timestamp") or (tr or {}).get("created_at") or (tr or {}).get("time")
    if isinstance(v, (int, float)):
        n = float(v)
        return int(n if n > 1e12 else n * 1000)
    s = str(v or "").strip()
    if not s:
        return 0
    if s.isdigit():
        n = int(s)
        return n if n > 1e12 else n * 1000
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _trade_usdc_size(tr):
    usdc = _maybe_float((tr or {}).get("usdcSize") or (tr or {}).get("usdc_size"))
    if usdc is not None:
        return abs(usdc)
    price = _maybe_float((tr or {}).get("price"))
    size = _maybe_float((tr or {}).get("size_matched") or (tr or {}).get("size") or (tr or {}).get("original_size"))
    if price is not None and size is not None:
        return abs(price * size)
    return 0.0


def _trade_market_key(tr):
    cond = _trade_pick_field(tr, "conditionId", "condition_id", "market", "market_id")
    slug = _trade_pick_field(tr, "eventSlug", "slug")
    if cond:
        return cond
    if slug:
        return slug
    asset = _trade_pick_field(tr, "asset_id", "asset", "token_id")
    return asset or "market"


def _resolve_trade_reason(tr):
    title = _trade_pick_field(tr, "title", "eventTitle", "name", "question")
    if title:
        return title
    slug = _trade_pick_field(tr, "eventSlug", "slug")
    if slug:
        return slug
    return "market"


def _fetch_trade_activity(user, limit=500):
    if not user:
        return []
    lim = min(max(int(limit), 50), 1000)
    param_sets = [
        {"user": user, "limit": lim, "offset": 0},
        {"user": user},
        {"address": user, "limit": lim, "offset": 0},
        {"wallet": user, "limit": lim, "offset": 0},
    ]

    rows = []
    seen = set()
    for params in param_sets:
        data = _data_api_get("/activity", params)
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            kind = _trade_event_kind(item)
            if kind == "IGNORE":
                continue
            tid = _text_scalar(item.get("id") or item.get("tradeID") or item.get("transaction_hash") or item.get("transactionHash"))
            if not tid:
                tid = f"act-{kind}-{_trade_ts_ms(item)}-{_trade_usdc_size(item):.6f}-{_trade_market_key(item)}"
            if tid in seen:
                continue
            seen.add(tid)
            norm = dict(item)
            if norm.get("type") is not None:
                norm["type"] = str(norm.get("type")).upper()
            if norm.get("side") is not None:
                norm["side"] = str(norm.get("side")).upper()
            norm["id"] = tid
            rows.append(norm)
        if rows:
            break

    rows.sort(key=_trade_ts_ms)
    return rows


def _build_market_aggregated_trades(raw_trades):
    groups = {}
    for tr in sorted((raw_trades or []), key=_trade_ts_ms):
        if not isinstance(tr, dict):
            continue
        kind = _trade_event_kind(tr)
        if kind == "IGNORE":
            continue

        price = _maybe_float(tr.get("price"))
        size = _maybe_float(tr.get("size_matched") or tr.get("size") or tr.get("original_size"))
        usdc_size = _trade_usdc_size(tr)
        if kind in ["BUY", "SELL"] and (price is None or size is None or size <= 0):
            continue
        if kind == "REDEEM" and usdc_size <= 0:
            continue

        key = _trade_market_key(tr)
        ts = tr.get("matchtime") or tr.get("match_time") or tr.get("timestamp") or tr.get("created_at") or tr.get("time")
        ts_ms = _trade_ts_ms(tr)
        g = groups.get(key)
        if g is None:
            g = {
                "id": f"agg-{key}",
                "direction": _normalize_outcome_label(tr.get("outcome") or tr.get("direction")),
                "outcomes": set(),
                "reason": _resolve_trade_reason(tr),
                "buy_count": 0,
                "sell_count": 0,
                "redeem_count": 0,
                "buy_size": 0.0,
                "sell_size": 0.0,
                "buy_notional": 0.0,
                "sell_notional": 0.0,
                "redeem_notional": 0.0,
                "first_ts": ts,
                "last_ts": ts,
                "first_ts_ms": ts_ms,
                "last_ts_ms": ts_ms,
            }
            groups[key] = g

        if ts_ms and ts_ms < g["first_ts_ms"]:
            g["first_ts_ms"] = ts_ms
            g["first_ts"] = ts
        if ts_ms and ts_ms >= g["last_ts_ms"]:
            g["last_ts_ms"] = ts_ms
            g["last_ts"] = ts

        outcome = _normalize_outcome_label(tr.get("outcome") or tr.get("direction"))
        if outcome and outcome != "-":
            g["outcomes"].add(outcome)

        if kind == "BUY":
            g["buy_count"] += 1
            g["buy_size"] += float(size)
            g["buy_notional"] += float(usdc_size)
        elif kind == "SELL":
            g["sell_count"] += 1
            g["sell_size"] += float(size)
            g["sell_notional"] += float(usdc_size)
        elif kind == "REDEEM":
            g["redeem_count"] += 1
            g["redeem_notional"] += float(usdc_size)

    rows = []
    for g in groups.values():
        if (g["buy_count"] + g["sell_count"] + g["redeem_count"]) <= 0:
            continue
        buy_avg = (g["buy_notional"] / g["buy_size"]) if g["buy_size"] > 1e-9 else None
        sell_avg = (g["sell_notional"] / g["sell_size"]) if g["sell_size"] > 1e-9 else None
        matched_size = min(g["buy_size"], g["sell_size"])
        pnl = g["sell_notional"] + g["redeem_notional"] - g["buy_notional"]

        if len(g["outcomes"]) == 1:
            g["direction"] = list(g["outcomes"])[0]
        elif len(g["outcomes"]) > 1:
            g["direction"] = "MIX"

        result = "CLOSED" if (g["sell_count"] > 0 or g["redeem_count"] > 0) else "OPEN"
        rows.append({
            "id": g["id"],
            "pair_id": g["id"],
            "direction": g["direction"],
            "reason": g["reason"],
            "buy_count": g["buy_count"],
            "sell_count": g["sell_count"],
            "redeem_count": g["redeem_count"],
            "buy_usdc": g["buy_notional"],
            "sell_usdc": g["sell_notional"],
            "redeem_usdc": g["redeem_notional"],
            "size": matched_size if matched_size > 1e-9 else max(g["buy_size"], g["sell_size"]),
            "entry_price_quote": buy_avg,
            "exit_price_quote": sell_avg,
            "order_time": g["first_ts"],
            "settle_time": g["last_ts"],
            "profit": pnl,
            "result": result,
            "status": "AGG",
        })

    rows.sort(key=lambda x: _trade_ts_ms({"timestamp": x.get("settle_time")}) if isinstance(x, dict) else 0)
    return rows


def _compute_wallet_realized_pnl(rows):
    realized = 0.0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        rp = _maybe_float(row.get("realizedPnl") if row.get("realizedPnl") is not None else row.get("realized_pnl"))
        if rp is not None:
            realized += rp
    return float(realized)


def _compute_wallet_unrealized_pnl(rows):
    unrealized = 0.0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        mark = _maybe_float(row.get("curPrice") if row.get("curPrice") is not None else row.get("cur_price"))
        avg = _maybe_float(row.get("avgPrice") if row.get("avgPrice") is not None else row.get("avg_price"))
        size = _maybe_float(row.get("size"))
        if mark is None or avg is None or size is None:
            continue
        unrealized += (mark - avg) * size
    return float(unrealized)


def _fetch_wallet_usdc_balance(user):
    if not HAS_WEB3:
        return None
    rpc_url = (POLYGON_RPC_URL or "").strip()
    if not rpc_url or not user:
        return None
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 8}))
        if not w3.is_connected():
            return None
        usdc_addr = Web3.to_checksum_address(USDC_E_CONTRACT)
        user_addr = Web3.to_checksum_address(user)
        contract = w3.eth.contract(
            address=usdc_addr,
            abi=[
                {
                    "name": "balanceOf",
                    "type": "function",
                    "stateMutability": "view",
                    "inputs": [{"name": "account", "type": "address"}],
                    "outputs": [{"name": "", "type": "uint256"}],
                },
                {
                    "name": "decimals",
                    "type": "function",
                    "stateMutability": "view",
                    "inputs": [],
                    "outputs": [{"name": "", "type": "uint8"}],
                },
            ],
        )
        raw = contract.functions.balanceOf(user_addr).call()
        decimals = contract.functions.decimals().call()
        return float(raw) / (10 ** int(decimals))
    except Exception:
        return None


def _sync_dashboard_account_snapshot(user):
    u = str(user or "").strip().lower()
    if not u:
        return False
    wallet_positions = _fetch_wallet_positions(u)
    wallet_closed = _fetch_wallet_closed_positions(u)
    wallet_history = _build_wallet_history_items(wallet_closed)
    raw_activity = _fetch_trade_activity(u, limit=500)
    agg_trades = _build_market_aggregated_trades(raw_activity)
    realized_pnl = _compute_wallet_realized_pnl(wallet_closed)
    unrealized_pnl = _compute_wallet_unrealized_pnl(wallet_positions)
    wallet_balance = _fetch_wallet_usdc_balance(u)
    _dashboard_set(
        wallet_balance=wallet_balance,
        wallet_positions=list(wallet_positions)[:120],
        wallet_history=list(wallet_history)[:200],
        live_trades=list(agg_trades)[-300:],
        live_positions_count=len(wallet_positions),
        live_realized_pnl=float(realized_pnl),
        live_unrealized_pnl=float(unrealized_pnl),
        live_total_pnl=float(realized_pnl + unrealized_pnl),
    )
    return True


def _fetch_wallet_positions(user):
    if not user:
        return []
    try:
        r = requests.get(
            f"{DATA_API}/positions",
            params={"user": user, "sizeThreshold": 0},
            proxies=PROXIES if PROXIES else None,
            timeout=12,
        )
        if r.status_code == 200:
            rows = r.json()
            if isinstance(rows, list):
                out = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    size = _to_float(row.get("size"), 0)
                    if size <= 0:
                        continue
                    if _to_bool(row.get("redeemable")) or _to_bool(row.get("mergeable")):
                        continue
                    out.append(row)
                return out
    except Exception:
        pass
    return []


def _fetch_wallet_closed_positions(user):
    if not user:
        return []
    try:
        r = requests.get(
            f"{DATA_API}/closed-positions",
            params={
                "user": user,
                "limit": 200,
                "offset": 0,
                "sortBy": "TIMESTAMP",
                "sortDirection": "DESC",
            },
            proxies=PROXIES if PROXIES else None,
            timeout=12,
        )
        if r.status_code == 200:
            rows = r.json()
            if isinstance(rows, list):
                return rows
    except Exception:
        pass
    return []


def _build_wallet_history_items(rows):
    items = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        side = row.get("outcome") or row.get("side") or row.get("positionSide") or "-"
        item = {
            "time": row.get("endDate") or row.get("timestamp") or row.get("updatedAt") or "-",
            "slug": row.get("slug") or row.get("marketSlug") or row.get("question") or "-",
            "action": "CLOSE",
            "side": side,
            "price": row.get("avgPrice") if row.get("avgPrice") is not None else row.get("avg_price"),
            "amount": row.get("size"),
            "order_id": row.get("transactionHash") or row.get("id") or "",
            "status": "closed",
            "reason": "wallet_sync",
            "pnl": row.get("realizedPnl") if row.get("realizedPnl") is not None else row.get("realized_pnl"),
        }
        items.append(item)
    return items[:200]

def load_state():
    """Load persisted bot state."""
    if not os.path.exists(STATE_FILE):
        return _normalize_state({})
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return _normalize_state(json.load(f))
    except:
        return _normalize_state({})

def save_state(state):
    """Persist bot state + latest prices."""
    try:
        state = _normalize_state(state)
        # Snapshot prices into state file
        state["ptb"] = price_data.get("ptb")
        state["chainlink"] = price_data.get("btc")
        state["binance"] = price_data.get("binance")
        state["up_price"] = price_data.get("up_price")
        state["down_price"] = price_data.get("down_price")
        state["last_update"] = datetime.now().isoformat()
        
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"save_state failed: {e}", "ERR")

# ============== WebSocket feeds ==============
class BTCPriceListener:
    """Binance BTC trades WebSocket."""
    def __init__(self):
        self.ws = None
        self.running = False
    
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if "p" in data:  # trade price field
                price_data["btc"] = float(data["p"])
                ts = time.time()
                price_data["btc_update_ts"] = ts
                price_data["last_update"] = ts
        except:
            pass
    
    def on_error(self, ws, error):
        pass
    
    def on_close(self, ws, *args):
        if self.running:
            log("BTC feed disconnected, reconnecting in 5s...", "WARN")
            time.sleep(5)
            self.start()
    
    def on_open(self, ws):
        log("BTC WebSocket connected", "OK")
    
    def start(self):
        self.running = True
        self.ws = websocket.WebSocketApp(
            BINANCE_WSS,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()

class MarketPriceListener:
    """CLOB market book / price_change for UP/DOWN."""
    def __init__(self, up_token, down_token):
        self.up_token = up_token
        self.down_token = down_token
        self.ws = None
        self.running = False
    
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            
            # Message may be list or dict
            items = data if isinstance(data, list) else [data]
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                event_type = item.get("event_type")
                asset_id = item.get("asset_id")
                
                # Order book snapshot
                if event_type == "book":
                    bids = item.get("bids") or []
                    asks = item.get("asks") or []
                    
                    if bids and asks:
                        best_bid = max([float(b["price"]) for b in bids], default=0)
                        best_ask = min([float(a["price"]) for a in asks], default=0)
                        mid_price = (best_bid + best_ask) / 2
                        ts = time.time()
                        
                        if asset_id == self.up_token:
                            price_data["up_bid"] = best_bid
                            price_data["up_ask"] = best_ask
                            price_data["up_price"] = mid_price
                            price_data["up_update_ts"] = ts
                            price_data["last_update"] = ts
                        elif asset_id == self.down_token:
                            price_data["down_bid"] = best_bid
                            price_data["down_ask"] = best_ask
                            price_data["down_price"] = mid_price
                            price_data["down_update_ts"] = ts
                            price_data["last_update"] = ts
                
                # Incremental price_change
                elif event_type == "price_change":
                    price_changes = item.get("price_changes", [])
                    if price_changes:
                        pc = price_changes[0]
                        best_bid = float(pc.get("best_bid", 0))
                        best_ask = float(pc.get("best_ask", 0))
                        
                        if best_bid > 0 and best_ask > 0:
                            mid_price = (best_bid + best_ask) / 2
                            ts = time.time()
                            
                            if asset_id == self.up_token:
                                price_data["up_bid"] = best_bid
                                price_data["up_ask"] = best_ask
                                price_data["up_price"] = mid_price
                                price_data["up_update_ts"] = ts
                                price_data["last_update"] = ts
                            elif asset_id == self.down_token:
                                price_data["down_bid"] = best_bid
                                price_data["down_ask"] = best_ask
                                price_data["down_price"] = mid_price
                                price_data["down_update_ts"] = ts
                                price_data["last_update"] = ts
        except:
            pass
    
    def on_error(self, ws, error):
        pass
    
    def on_close(self, ws, *args):
        if self.running:
            log("Market feed disconnected, reconnecting in 5s...", "WARN")
            time.sleep(5)
            self.start()
    
    def on_open(self, ws):
        # Subscribe both outcome tokens
        ws.send(json.dumps({
            "assets_ids": [self.up_token, self.down_token],
            "type": "market"
        }))
        log("Market WebSocket connected", "OK")
    
    def start(self):
        self.running = True
        self.ws = websocket.WebSocketApp(
            POLYMARKET_WSS,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
    
    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()

# ============== CLOB client ==============
class Trader:
    def __init__(self):
        self.client = None
        self.connected = False
        self.address = None
    
    def connect(self):
        """Connect py-clob client."""
        pk = os.getenv("PRIVATE_KEY")
        if not pk:
            log("PRIVATE_KEY not set", "ERR")
            return False
        
        try:
            if not pk.startswith("0x"):
                pk = "0x" + pk
            
            log("Connecting CLOB client...")
            temp = ClobClient(host="https://clob.polymarket.com", chain_id=137, key=pk)
            self.address = temp.get_address()
            log(f"Wallet: {self.address}")
            
            creds = temp.create_or_derive_api_creds()
            funder = os.getenv("FUNDER_ADDRESS") or self.address
            sig_type = int(os.getenv("SIGNATURE_TYPE", "2"))
            
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=137,
                key=pk,
                creds=creds,
                signature_type=sig_type,
                funder=funder
            )
            self.connected = True
            log("CLOB client connected", "OK")
            return True
        except Exception as e:
            log(f"Connect failed: {e}", "ERR")
            return False
    
    def place_order(self, token_id, side, price, size):
        """Place limit order."""
        if not self.connected:
            log("CLOB client not connected", "ERR")
            return None
        
        try:
            log(f"Order: {side} ${size} @ {price:.3f}", "TRADE")
            
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=BUY if side == "BUY" else SELL
            )
            
            signed_order = self.client.create_order(order_args)
            resp = self.client.post_order(signed_order)
            
            if resp and resp.get("orderID"):
                order_id = resp.get("orderID")
                log(f"Order placed, id: {order_id}", "OK")
                return order_id
            else:
                log("Order rejected", "ERR")
                return None
        except Exception as e:
            log(f"Order error: {e}", "ERR")
            return None
    
    def get_order_status(self, order_id):
        """Poll order status."""
        if not self.connected or not order_id:
            return None
        
        try:
            order = self.client.get_order(order_id)
            if order:
                status = order.get("status", "").upper()
                original_size = float(order.get("original_size", 0) or 0)
                size_matched = float(order.get("size_matched", 0) or 0)
                
                return {
                    "status": status,
                    "original_size": original_size,
                    "size_matched": size_matched,
                    "filled": size_matched >= original_size if original_size > 0 else False
                }
        except Exception as e:
            log(f"get_order failed: {e}", "WARN")
        return None
    
    def cancel_order(self, order_id):
        """Cancel open order."""
        if not self.connected or not order_id:
            return False
        
        try:
            log(f"Cancel order: {order_id}", "WARN")
            resp = self.client.cancel(order_id)
            if resp:
                log("Order canceled", "OK")
                return True
            else:
                log("Cancel failed", "ERR")
                return False
        except Exception as e:
            log(f"Cancel error: {e}", "ERR")
            return False

class AutoRedeemer:
    def __init__(self, private_key, funder_address):
        self.enabled = bool(AUTO_REDEEM)
        self.private_key = (private_key or "").strip()
        if self.private_key and not self.private_key.startswith("0x"):
            self.private_key = "0x" + self.private_key
        self.funder_address = (funder_address or "").strip()
        self.scan_addresses = []
        self.last_try_by_condition = {}
        self.last_pending_signature = ""
        self.last_pending_log_ts = 0.0
        self.running = False
        self.thread = None
        self.relayer_client = None
        self.relayer_error = ""
        self.last_pending_count = 0
        self.last_claimable_count = 0
        self.last_result = {}
        self.last_error = ""

        if not self.enabled:
            _dashboard_set(auto_redeem={"enabled": False, "pending_count": 0, "claimable_count": 0, "last_result": {}, "last_error": ""})
            return
        if not HAS_WEB3:
            log("Auto-redeem disabled: web3 not installed", "WARN", force=True)
            self.enabled = False
            _dashboard_set(auto_redeem={"enabled": False, "pending_count": 0, "claimable_count": 0, "last_result": {}, "last_error": "web3 missing"})
            return
        if not self.private_key:
            log("Auto-redeem disabled: PRIVATE_KEY missing", "WARN", force=True)
            self.enabled = False
            _dashboard_set(auto_redeem={"enabled": False, "pending_count": 0, "claimable_count": 0, "last_result": {}, "last_error": "PRIVATE_KEY missing"})
            return
        if not self.funder_address:
            log("Auto-redeem disabled: FUNDER_ADDRESS missing (proxy wallet)", "WARN", force=True)
            self.enabled = False
            _dashboard_set(auto_redeem={"enabled": False, "pending_count": 0, "claimable_count": 0, "last_result": {}, "last_error": "FUNDER_ADDRESS missing"})
            return
        if not (POLY_BUILDER_API_KEY and POLY_BUILDER_SECRET and POLY_BUILDER_PASSPHRASE):
            log("Auto-redeem disabled: POLY_BUILDER_API_KEY/SECRET/PASSPHRASE missing", "WARN", force=True)
            self.enabled = False
            _dashboard_set(auto_redeem={"enabled": False, "pending_count": 0, "claimable_count": 0, "last_result": {}, "last_error": "Builder API creds missing"})
            return

        self.scan_addresses = [self.funder_address]

        client, err = self._create_relayer_client()
        if client is None:
            log(f"Auto-redeem disabled: relayer init failed {err}", "ERR", force=True)
            self.enabled = False
            _dashboard_set(auto_redeem={"enabled": False, "pending_count": 0, "claimable_count": 0, "last_result": {}, "last_error": str(err)})
            return
        self.relayer_client = client

    def _normalize_condition_id(self, value):
        s = str(value or "").strip().lower()
        if not s:
            return ""
        if s.startswith("0x"):
            s = s[2:]
        if len(s) != 64:
            return ""
        try:
            int(s, 16)
        except Exception:
            return ""
        return "0x" + s

    def _fetch_positions(self, user):
        try:
            r = requests.get(
                f"{DATA_API}/positions",
                params={"user": user, "sizeThreshold": 0},
                proxies=PROXIES if PROXIES else None,
                timeout=12,
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _create_relayer_client(self):
        try:
            import inspect
            import py_builder_relayer_client.client as rel_mod
            from py_builder_relayer_client.client import RelayClient
            try:
                from py_builder_signing_sdk import BuilderConfig, BuilderApiKeyCreds
            except Exception:
                from py_builder_signing_sdk.config import BuilderConfig, BuilderApiKeyCreds

            cfg = BuilderConfig(
                local_builder_creds=BuilderApiKeyCreds(
                    key=POLY_BUILDER_API_KEY,
                    secret=POLY_BUILDER_SECRET,
                    passphrase=POLY_BUILDER_PASSPHRASE,
                )
            )

            args = [RELAYER_URL, 137, self.private_key, cfg]
            init_params = inspect.signature(RelayClient.__init__).parameters
            if len(init_params) >= 6:
                tx_enum = getattr(rel_mod, "RelayerTxType", None) or getattr(rel_mod, "TransactionType", None)
                tx_value = None
                if tx_enum is not None:
                    if RELAYER_TX_TYPE == "PROXY" and hasattr(tx_enum, "PROXY"):
                        tx_value = getattr(tx_enum, "PROXY")
                    elif hasattr(tx_enum, "SAFE"):
                        tx_value = getattr(tx_enum, "SAFE")
                    elif hasattr(tx_enum, "SAFE_CREATE"):
                        tx_value = getattr(tx_enum, "SAFE_CREATE")
                if tx_value is not None:
                    args.append(tx_value)

            return RelayClient(*args), ""
        except Exception as e:
            return None, str(e)

    def _collect_redeemable(self):
        pending = []
        seen = set()
        claimable = []

        for owner in self.scan_addresses:
            rows = self._fetch_positions(owner)
            owner_l = owner.lower()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                size = row.get("size")
                try:
                    size_f = float(size or 0)
                except Exception:
                    size_f = 0.0
                if size_f <= 0:
                    continue

                redeemable = bool(row.get("redeemable") or row.get("mergeable"))
                if not redeemable:
                    continue

                cid = self._normalize_condition_id(
                    row.get("conditionId") or row.get("condition_id")
                )
                if not cid:
                    continue

                key = owner_l + "|" + cid
                if key in seen:
                    continue
                seen.add(key)
                pending.append({"owner": owner, "condition_id": cid})

                if owner_l == self.funder_address.lower() and cid not in claimable:
                    claimable.append(cid)

        return pending, claimable

    def _redeem_condition(self, condition_id):
        try:
            from py_builder_relayer_client.models import SafeTransaction, OperationType

            ctf_addr = Web3.to_checksum_address(CTF_CONTRACT)
            usdc_addr = Web3.to_checksum_address(USDC_E_CONTRACT)
            contract = Web3().eth.contract(
                address=ctf_addr,
                abi=[{
                    "name": "redeemPositions",
                    "type": "function",
                    "stateMutability": "nonpayable",
                    "inputs": [
                        {"name": "collateralToken", "type": "address"},
                        {"name": "parentCollectionId", "type": "bytes32"},
                        {"name": "conditionId", "type": "bytes32"},
                        {"name": "indexSets", "type": "uint256[]"},
                    ],
                    "outputs": [],
                }],
            )
            cond_bytes = bytes.fromhex(condition_id[2:])
            data = contract.encode_abi(
                abi_element_identifier="redeemPositions",
                args=[usdc_addr, b"\x00" * 32, cond_bytes, [1, 2]],
            )
            op_call = getattr(OperationType, "Call", None)
            if op_call is None:
                op_call = list(OperationType)[0]
            tx = SafeTransaction(to=str(ctf_addr), operation=op_call, data=str(data), value="0")

            def execute_once():
                resp = self.relayer_client.execute([tx], f"Redeem {condition_id}")
                result = resp.wait()
                txh = str(getattr(resp, "transaction_hash", "") or "")
                state = ""
                if isinstance(result, dict):
                    txh = str(result.get("transaction_hash") or result.get("transactionHash") or txh)
                    state = str(result.get("state") or "")
                else:
                    txh = str(getattr(result, "transaction_hash", "") or getattr(result, "transactionHash", "") or txh)
                    state = str(getattr(result, "state", "") or "")
                if result is None:
                    return False, txh, "relayer_not_confirmed"
                if state and state not in ["STATE_CONFIRMED", "STATE_MINED", "STATE_EXECUTED"]:
                    return False, txh, f"state={state}"
                return True, txh, ""

            try:
                return execute_once()
            except Exception as e:
                msg = str(e)
                low = msg.lower()
                if "expected safe" in low and "not deployed" in low:
                    dep = self.relayer_client.deploy()
                    dep.wait()
                    return execute_once()
                return False, "", msg
        except Exception as e:
            return False, "", str(e)

    def scan_once(self):
        if not self.enabled:
            return

        pending, claimable = self._collect_redeemable()
        now = time.time()
        self.last_pending_count = len(pending)
        self.last_claimable_count = len(claimable)
        _dashboard_set(auto_redeem={
            "enabled": self.enabled,
            "pending_count": self.last_pending_count,
            "claimable_count": self.last_claimable_count,
            "last_result": dict(self.last_result or {}),
            "last_error": self.last_error,
            "scan_interval": REDEEM_SCAN_INTERVAL,
        })

        if pending:
            signature = "|".join([f"{x['owner']}:{x['condition_id']}" for x in pending])
            if signature != self.last_pending_signature or (now - self.last_pending_log_ts) >= REDEEM_PENDING_LOG_INTERVAL:
                self.last_pending_signature = signature
                self.last_pending_log_ts = now
                owners = sorted(list({x["owner"] for x in pending}))
                owner_text = ", ".join(owners[:3])
                if len(owners) > 3:
                    owner_text += f" +{len(owners) - 3} more"
                log(f"Redeemable pending: {len(pending)}, relayer-claimable: {len(claimable)}, owners: {owner_text}", "WARN", force=True)

        if not claimable:
            return

        processed = 0
        for cid in claimable:
            t0 = self.last_try_by_condition.get(cid, 0)
            if now - t0 < REDEEM_RETRY_INTERVAL:
                continue
            self.last_try_by_condition[cid] = now

            ok, tx_hash, err = self._redeem_condition(cid)
            if ok:
                log(f"Relayer redeem ok: {cid} | tx {tx_hash}", "TRADE", force=True)
                self.last_error = ""
                self.last_result = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ok": True,
                    "condition_id": cid,
                    "tx": tx_hash,
                    "message": "ok",
                }
            else:
                log(f"Relayer redeem failed: {cid} | {err}", "ERR", force=True)
                self.last_error = str(err)
                self.last_result = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ok": False,
                    "condition_id": cid,
                    "tx": tx_hash,
                    "message": str(err),
                }

            _dashboard_set(auto_redeem={
                "enabled": self.enabled,
                "pending_count": self.last_pending_count,
                "claimable_count": self.last_claimable_count,
                "last_result": dict(self.last_result or {}),
                "last_error": self.last_error,
                "scan_interval": REDEEM_SCAN_INTERVAL,
            })
            _sync_dashboard_account_snapshot(self.funder_address)

            processed += 1
            if processed >= REDEEM_MAX_PER_SCAN:
                break

    def _loop(self):
        while self.running:
            try:
                self.scan_once()
            except Exception as e:
                log(f"Auto-redeem scan error: {e}", "ERR", force=True)
            for _ in range(REDEEM_SCAN_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

    def start(self):
        if not self.enabled:
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        log(f"Auto-redeem on: scan every {REDEEM_SCAN_INTERVAL}s", "OK", force=True)
        _dashboard_set(auto_redeem={
            "enabled": self.enabled,
            "pending_count": self.last_pending_count,
            "claimable_count": self.last_claimable_count,
            "last_result": dict(self.last_result or {}),
            "last_error": self.last_error,
            "scan_interval": REDEEM_SCAN_INTERVAL,
        })

    def stop(self):
        self.running = False

# ============== Main loop ==============
def main():
    start_web_server()
    if WEB_ENABLED:
        log(f"Dashboard: http://{WEB_HOST}:{WEB_PORT}", "OK", force=True)

    print("\n" + "="*60)
    print(f"  Polymarket BTC {_btc_market_minutes}m auto-trader")
    print("="*60)
    print(f"  Simulation mode: {'on (paper, no CLOB)' if SIMULATION_MODE else 'off'}")
    print(f"  Auto trade: {'on' if AUTO_TRADE else 'off'}")
    print(f"  BTC market window: {_btc_market_minutes}m (config BTC_MARKET_MINUTES or dashboard)")
    print(f"  Trading analysis log: {TRADING_ANALYSIS_LOG}")
    print(f"  Auto redeem: {'on' if AUTO_REDEEM and not SIMULATION_MODE else 'off'}")
    _init_trading_analysis_session()
    log(f"Trading analysis log ready (append-only): {TRADING_ANALYSIS_LOG}", "OK", force=True)
    print(f"  Order size: ${TRADE_AMOUNT}")
    print(f"  Rule 1: time≤{C1_TIME}s and diff≥${C1_DIFF} (UP prob {C1_MIN_PROB*100:.0f}-{C1_MAX_PROB*100:.0f}%)")
    print(f"  Rule 2: time≤{C2_TIME}s and diff≥${C2_DIFF} (DOWN prob {C2_MIN_PROB*100:.0f}-{C2_MAX_PROB*100:.0f}%)")
    print(f"  Rule 3: time≤{C3_TIME}s and diff≥${C3_DIFF} (UP prob {C3_MIN_PROB*100:.0f}-{C3_MAX_PROB*100:.0f}%)")
    print(f"  Rule 4: time≤{C4_TIME}s and diff≥${C4_DIFF} (DOWN prob {C4_MIN_PROB*100:.0f}-{C4_MAX_PROB*100:.0f}%)")
    print(f"  TP/SL: prob-based (SL {STOP_LOSS_PROB_PCT*100:.0f}%, RR≈{TAKE_PROFIT_RR:.2f}, TP cap {TAKE_PROFIT_CAP*100:.1f}%)")
    print(f"  Cancel after: {ORDER_TIMEOUT_SEC}s unfilled")
    print(f"  Slippage cap: {SLIPPAGE_THRESHOLD*100:.0f}%")
    print(f"  Max retries / market: {MAX_RETRY_PER_MARKET}")
    print(f"  Chase step: +{BUY_RETRY_STEP*100:.1f}% per retry")
    print(f"  TP retries: up to {TAKE_PROFIT_RETRY_MAX}, step +{TAKE_PROFIT_RETRY_STEP*100:.1f}%")
    print(f"  Stop: entry prob down {STOP_LOSS_PROB_PCT*100:.0f}%")
    print(f"  Stale data skip: >{MARKET_DATA_MAX_LAG_SEC:.1f}s")
    print(f"  Loop interval: {LOOP_INTERVAL_SEC:.2f}s")
    print("="*60 + "\n")
    
    trader = Trader()
    redeemer = AutoRedeemer(os.getenv("PRIVATE_KEY"), os.getenv("FUNDER_ADDRESS"))
    if SIMULATION_MODE:
        log("SIMULATION_MODE: paper trading — instant fills, no CLOB orders, no redeem", "OK", force=True)
    elif AUTO_TRADE:
        if not trader.connect():
            log("Cannot connect CLOB client, exiting", "ERR", force=True)
            return
    if not SIMULATION_MODE:
        redeemer.start()
    else:
        _dashboard_set(auto_redeem={"enabled": False, "pending_count": 0, "claimable_count": 0, "last_result": {}, "last_error": "simulation mode"})

    init_state = load_state()
    _dashboard_set(
        position=dict(init_state.get("position") or {}),
        pending_order=_dashboard_pending_order_from_state(init_state),
        last_order=dict(init_state.get("last_order") or {}),
        trade_history=list(init_state.get("trade_history") or []),
        wallet_balance=None,
        wallet_positions=[],
        wallet_history=[],
        live_trades=[],
        live_positions_count=0,
        live_realized_pnl=0.0,
        live_unrealized_pnl=0.0,
        live_total_pnl=0.0,
        cumulative_realized_pnl=float(init_state.get("cumulative_realized_pnl") or 0.0),
        simulation_mode=SIMULATION_MODE,
    )
    
    log("Starting price feeds...", "INFO", force=True)
    
    last_slug = None
    market_listener = None
    first_display = True
    last_chainlink_update = 0
    last_account_sync = 0.0
    last_market_fetch = 0.0
    last_stale_log_ts = 0.0
    dashboard_user = (os.getenv("FUNDER_ADDRESS", "") or "").strip().lower()
    if not dashboard_user:
        dashboard_user = (os.getenv("PRIVATE_KEY_ADDRESS", "") or "").strip().lower()
    if not SIMULATION_MODE and AUTO_TRADE and trader.address:
        dashboard_user = ((os.getenv("FUNDER_ADDRESS", "") or trader.address) or "").strip().lower()
    _trigger_market_refresh()
    _trigger_account_sync(dashboard_user)
    
    try:
        while True:
            now = time.time()

            # Refresh reference prices async so the loop stays responsive
            if now - last_chainlink_update > 5:
                _trigger_price_refresh()
                last_chainlink_update = now

            # Market metadata refresh async
            if now - last_market_fetch >= MARKET_META_REFRESH_SEC:
                _trigger_market_refresh()
                last_market_fetch = now

            market = None
            market_data_cache = _get_market_cache()
            if market_data_cache:
                try:
                    end_ts = datetime.fromisoformat(str(market_data_cache.get("end", "")).replace("Z", "+00:00")).timestamp()
                    remaining_live = int(end_ts - now)
                except Exception:
                    remaining_live = 0
                if remaining_live <= 0:
                    _clear_market_cache()
                    last_market_fetch = 0.0
                else:
                    market = dict(market_data_cache)
                    market["remaining"] = remaining_live

            if now - last_account_sync >= DASHBOARD_ACCOUNT_SYNC_SEC:
                _trigger_account_sync(dashboard_user)
                last_account_sync = now

            if not market:
                state_snapshot = load_state()
                _dashboard_set(
                    market={"slug": "", "remaining": 0, "status": "waiting"},
                    prices={
                        "ptb": price_data.get("ptb"),
                        "chainlink_btc": price_data.get("btc"),
                        "binance_btc": price_data.get("binance"),
                        "up_price": price_data.get("up_price"),
                        "down_price": price_data.get("down_price"),
                        "diff": None,
                        "diff_abs": None,
                    },
                    position=dict(state_snapshot.get("position") or {}),
                    pending_order=_dashboard_pending_order_from_state(state_snapshot),
                    last_order=dict(state_snapshot.get("last_order") or {}),
                    trade_history=list(state_snapshot.get("trade_history") or []),
                    btc_market_minutes=_btc_market_minutes,
                    cumulative_realized_pnl=float(state_snapshot.get("cumulative_realized_pnl") or 0.0),
                    simulation_mode=SIMULATION_MODE,
                )
                if first_display:
                    print("\nWaiting for active market...")
                    if price_data["btc"]:
                        print(f"BTC (Chainlink): ${price_data['btc']:,.2f}")
                time.sleep(LOOP_INTERVAL_SEC)
                continue
            
            slug = market["slug"]
            remaining = market["remaining"]
            
            # Market rollover
            if last_slug and slug != last_slug:
                if market_listener:
                    market_listener.stop()
                
                state = load_state()
                state.pop("position", None)
                state.pop("last_order", None)
                state.pop("take_profit_order", None)
                save_state(state)
                
                market_listener = MarketPriceListener(market["up_token"], market["down_token"])
                market_listener.start()
                
                price_data["ptb"] = None
                
                first_display = True
                
                time.sleep(2)
            
            elif not last_slug:
                market_listener = MarketPriceListener(market["up_token"], market["down_token"])
                market_listener.start()
                time.sleep(2)
            
            last_slug = slug
            
            # PTB from crypto-price API
            if not price_data["ptb"]:
                crypto_data = get_crypto_price_api(market["start"], market["end"])
                if crypto_data.get("openPrice"):
                    price_data["ptb"] = crypto_data["openPrice"]
                elif crypto_data.get("closePrice"):
                    price_data["ptb"] = crypto_data["closePrice"]
                    log(f"Using prior window closePrice as PTB: {price_data['ptb']}", "INFO")
            
            # Live book mid from WebSocket
            btc = _to_float(price_data.get("btc"), 0.0)
            ptb = _to_float(price_data.get("ptb"), 0.0)
            up_price = _to_float(price_data.get("up_price") if price_data.get("up_price") is not None else market.get("up_price"), 0.0)
            down_price = _to_float(price_data.get("down_price") if price_data.get("down_price") is not None else market.get("down_price"), 0.0)
            up_bid = _maybe_float(price_data.get("up_bid"))
            up_ask = _maybe_float(price_data.get("up_ask"))
            down_bid = _maybe_float(price_data.get("down_bid"))
            down_ask = _maybe_float(price_data.get("down_ask"))

            # Use ask side for buys (executable)
            up_entry_price = up_ask if (up_ask is not None and up_ask > 0) else up_price
            down_entry_price = down_ask if (down_ask is not None and down_ask > 0) else down_price
            
            # Diff vs PTB
            diff = btc - ptb if (btc > 0 and ptb > 0) else 0
            diff_abs = abs(diff)
            _dashboard_set(
                market={
                    "slug": slug,
                    "remaining": remaining,
                    "remaining_text": f"{remaining//60}m {remaining%60}s",
                    "start": market.get("start"),
                    "end": market.get("end"),
                    "status": "active",
                },
                prices={
                    "ptb": ptb if ptb > 0 else None,
                    "chainlink_btc": btc if btc > 0 else None,
                    "binance_btc": (price_data.get("binance") or None),
                    "up_price": up_price,
                    "down_price": down_price,
                    "up_bid": up_bid,
                    "up_ask": up_ask,
                    "down_bid": down_bid,
                    "down_ask": down_ask,
                    "diff": diff if (btc > 0 and ptb > 0) else None,
                    "diff_abs": diff_abs if (btc > 0 and ptb > 0) else None,
                    "updated_ts": time.time(),
                },
                btc_market_minutes=_btc_market_minutes,
            )

            state_snapshot = load_state()
            _dashboard_set(
                position=dict(state_snapshot.get("position") or {}),
                pending_order=_dashboard_pending_order_from_state(state_snapshot),
                last_order=dict(state_snapshot.get("last_order") or {}),
                trade_history=list(state_snapshot.get("trade_history") or []),
                cumulative_realized_pnl=float(state_snapshot.get("cumulative_realized_pnl") or 0.0),
                simulation_mode=SIMULATION_MODE,
            )
            
            if first_display:
                print("\n" + "="*90)
                print(f"Market: {slug}")
                print(f"Time left: {remaining//60}m {remaining%60}s")
                print()
                print("┌────────────────────────┬────────────────────────┬────────────────────────┐")
                print("│ PTB                    │ Chainlink (ref)        │ Binance (ref)          │")
                ptb_display = f"${ptb:,.2f}" if ptb > 0 else "fetching..."
                btc_display = f"${btc:,.2f}" if btc > 0 else "fetching..."
                binance = price_data.get("binance") or 0
                binance_display = f"${binance:,.2f}" if binance > 0 else "fetching..."
                print(f"│ {ptb_display:22s} │ {btc_display:22s} │ {binance_display:22s} │")
                print("├────────────────────────┴────────────────────────┴────────────────────────┤")
                print("│ Market mid                                                               │")
                print(f"│ UP: {up_price*100:.2f}%  DOWN: {down_price*100:.2f}%                                                │")
                print("├──────────────────────────────────────────────────────────────────────────┤")
                print("│ Live diff (Chainlink - PTB)                                              │")
                if btc > 0 and ptb > 0:
                    diff_display = f"{diff:+.0f} USD"
                else:
                    diff_display = "waiting for prices..."
                print(f"│ {diff_display:72s} │")
                print("└──────────────────────────────────────────────────────────────────────────┘")
                print()
                print("="*90)
                print("Live log:")
                print("="*90)
                first_display = False
            
            ptb_str = f"${ptb:,.0f}" if ptb > 0 else "..."
            btc_str = f"${btc:,.0f}" if btc > 0 else "..."
            binance = price_data.get("binance") or 0
            binance_str = f"${binance:,.0f}" if binance > 0 else "N/A"
            diff_str = f"{diff:+.0f}" if (btc > 0 and ptb > 0) else "N/A"
            status = f"[{datetime.now().strftime('%H:%M:%S')}] left {remaining//60:02d}m{remaining%60:02d}s | CL:{btc_str} | BN:{binance_str} | PTB:{ptb_str} | diff:{diff_str} | UP:{up_price*100:.1f}% DOWN:{down_price*100:.1f}%"
            print(f"\r{status}" + " "*10, end="", flush=True)
            
            # Evaluate trigger rules
            triggered = False
            condition = None
            side = None
            desired_side = None
            price = None
            token = None
            
            if remaining <= C1_TIME and diff >= C1_DIFF:
                prob = up_entry_price
                if C1_MIN_PROB <= prob <= C1_MAX_PROB:
                    triggered = True
                    desired_side = "UP"
                    condition = f"R1: time≤{C1_TIME}s & diff≥${C1_DIFF} (UP {prob*100:.0f}%)"
                else:
                    log(f"R1 skip: UP prob {prob*100:.1f}% not in {C1_MIN_PROB*100:.0f}–{C1_MAX_PROB*100:.0f}%", "INFO")
            
            elif remaining <= C2_TIME and diff <= -C2_DIFF:
                prob = down_entry_price
                if C2_MIN_PROB <= prob <= C2_MAX_PROB:
                    triggered = True
                    desired_side = "DOWN"
                    condition = f"R2: time≤{C2_TIME}s & diff≤-${C2_DIFF} (DOWN {prob*100:.0f}%)"
                else:
                    log(f"R2 skip: DOWN prob {prob*100:.1f}% not in {C2_MIN_PROB*100:.0f}–{C2_MAX_PROB*100:.0f}%", "INFO")
            
            elif remaining <= C3_TIME and diff >= C3_DIFF:
                prob = up_entry_price
                if C3_MIN_PROB <= prob <= C3_MAX_PROB:
                    triggered = True
                    desired_side = "UP"
                    condition = f"R3: time≤{C3_TIME}s & diff≥${C3_DIFF} (UP {prob*100:.0f}%)"
                else:
                    log(f"R3 skip: UP prob {prob*100:.1f}% not in {C3_MIN_PROB*100:.0f}–{C3_MAX_PROB*100:.0f}%", "INFO")
            
            elif remaining <= C4_TIME and diff <= -C4_DIFF:
                prob = down_entry_price
                if C4_MIN_PROB <= prob <= C4_MAX_PROB:
                    triggered = True
                    desired_side = "DOWN"
                    condition = f"R4: time≤{C4_TIME}s & diff≤-${C4_DIFF} (DOWN {prob*100:.0f}%)"
                else:
                    log(f"R4 skip: DOWN prob {prob*100:.1f}% not in {C4_MIN_PROB*100:.0f}–{C4_MAX_PROB*100:.0f}%", "INFO")
            
            if triggered:
                side = desired_side or ("UP" if diff > 0 else "DOWN")
                price = up_entry_price if side == "UP" else down_entry_price
                token = market["up_token"] if side == "UP" else market["down_token"]

                # Skip stale book / BTC to avoid chasing on lag
                side_ts = _to_float(price_data.get("up_update_ts" if side == "UP" else "down_update_ts"), 0.0)
                btc_ts = _to_float(price_data.get("btc_update_ts"), 0.0)
                side_age = now - side_ts if side_ts > 0 else 999.0
                btc_age = now - btc_ts if btc_ts > 0 else 999.0
                if price <= 0:
                    triggered = False
                    condition = None
                elif side_age > MARKET_DATA_MAX_LAG_SEC or btc_age > MARKET_DATA_MAX_LAG_SEC:
                    if now - last_stale_log_ts >= 2:
                        log(
                            f"Stale data skip: {side} book age {side_age:.2f}s, BTC age {btc_age:.2f}s (max {MARKET_DATA_MAX_LAG_SEC:.1f}s)",
                            "WARN",
                        )
                        last_stale_log_ts = now
                    triggered = False
                    condition = None
                
                # Order / position state
                state = load_state()
                last_order = state.get("last_order", {})
                order_key = f"{slug}|{side}"
                
                # Track working orders
                pending_order = state.get("pending_order")
                _dashboard_set(
                    position=dict(state.get("position") or {}),
                    pending_order=_dashboard_pending_order_from_state(state),
                    last_order=dict(last_order or {}),
                )
                if pending_order and (not SIMULATION_MODE) and AUTO_TRADE and trader.connected:
                    order_id = pending_order.get("order_id")
                    order_time = pending_order.get("time")
                    
                    if order_time:
                        elapsed = (datetime.now() - datetime.fromisoformat(order_time)).total_seconds()
                        if elapsed > ORDER_TIMEOUT_SEC:
                            order_status = trader.get_order_status(order_id)
                            if order_status and not order_status.get("filled"):
                                log(f"Order timeout, cancel & retry (id {order_id})", "TRADE")
                                trader.cancel_order(order_id)
                                state.pop("pending_order", None)
                                save_state(state)
                                _emit_trading_analysis(
                                    "BUY_CANCEL_TIMEOUT",
                                    slug=slug,
                                    order_id=order_id,
                                    status="buy",
                                    shares_type=pending_order.get("side"),
                                    share_price=float(pending_order.get("price") or 0) or None,
                                    btc_price=btc if btc > 0 else None,
                                    chainlink_btc=btc if btc > 0 else None,
                                    ptb=ptb if ptb > 0 else None,
                                    btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                    remaining_sec=remaining,
                                    pnl_trade_usd=None,
                                    pnl_total_usd=_to_float(state.get("cumulative_realized_pnl"), 0.0),
                                )
                                _dashboard_set(
                                    position=dict(state.get("position") or {}),
                                    pending_order=_dashboard_pending_order_from_state(state),
                                    last_order=dict(state.get("last_order") or {}),
                                )
                            elif order_status and order_status.get("filled"):
                                filled_side = pending_order.get("side") or side
                                filled_price = float(pending_order.get("price") or price or 0)
                                filled_slug = pending_order.get("slug") or slug
                                log(f"Filled {filled_side} @ {filled_price*100:.2f}% ({filled_slug})", "TRADE")
                                state.pop("pending_order", None)
                                filled_size = float(order_status.get("size_matched") or order_status.get("original_size") or TRADE_AMOUNT)
                                state["position"] = {
                                    "slug": filled_slug,
                                    "side": filled_side,
                                    "entry_price": filled_price,
                                    "entry_diff": diff_abs,
                                    "size": filled_size,
                                }
                                cum = _to_float(state.get("cumulative_realized_pnl"), 0.0)
                                state = _append_trade_history(state, {
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "slug": filled_slug,
                                    "action": "BUY",
                                    "side": filled_side,
                                    "price": filled_price,
                                    "amount": TRADE_AMOUNT,
                                    "shares": filled_size,
                                    "order_size_usdc": TRADE_AMOUNT,
                                    "order_id": order_id,
                                    "status": "filled",
                                    "reason": "pending_filled",
                                    "diff": diff,
                                    "btc": btc if btc > 0 else None,
                                    "ptb": ptb if ptb > 0 else None,
                                    "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                    "remaining_sec": remaining,
                                    "cumulative_realized_pnl_usd": cum,
                                })
                                _emit_trading_analysis(
                                    "BUY_FILL",
                                    action="BUY",
                                    slug=filled_slug,
                                    status="buy",
                                    shares_type=filled_side,
                                    share_price=filled_price,
                                    share_amount=filled_size,
                                    order_size_usdc=TRADE_AMOUNT,
                                    order_id=order_id,
                                    reason="pending_filled",
                                    btc_price=btc if btc > 0 else None,
                                    chainlink_btc=btc if btc > 0 else None,
                                    ptb=ptb if ptb > 0 else None,
                                    btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                    diff_rule=diff,
                                    remaining_sec=remaining,
                                    pnl_trade_usd=0.0,
                                    pnl_total_usd=cum,
                                )
                                save_state(state)
                                _dashboard_set(
                                    position=dict(state.get("position") or {}),
                                    pending_order=_dashboard_pending_order_from_state(state),
                                    last_order=dict(state.get("last_order") or {}),
                                    trade_history=list(state.get("trade_history") or []),
                                    cumulative_realized_pnl=cum,
                                )
                                _sync_dashboard_account_snapshot(dashboard_user)
                
                # New entry if flat and no working order
                has_position = bool(state.get("position"))
                retry_count = int(last_order.get("retry_count", 0) or 0)
                same_key_retry = (last_order.get("key") == order_key)
                can_place = (not pending_order) and (not has_position) and ((not same_key_retry) or (retry_count < MAX_RETRY_PER_MARKET))
                if can_place:
                    if same_key_retry and retry_count > 0:
                        last_price = _to_float(last_order.get("last_price"), price)
                        retry_cap_price = min(0.995, last_price + BUY_RETRY_STEP)
                        if price > retry_cap_price:
                            log(
                                f"Chase cap: {price*100:.2f}% > last {last_price*100:.2f}%+{BUY_RETRY_STEP*100:.2f}%, use {retry_cap_price*100:.2f}%",
                                "INFO",
                            )
                        price = min(price, retry_cap_price)

                    current_price = up_entry_price if side == "UP" else down_entry_price
                    if price > 0:
                        slippage = abs(current_price - price) / price
                        if slippage > SLIPPAGE_THRESHOLD:
                            log(f"Slippage too high: {slippage*100:.1f}% > {SLIPPAGE_THRESHOLD*100:.0f}%, skip", "WARN")
                            triggered = False
                            condition = None
                    
                    if triggered:
                        if same_key_retry and retry_count >= MAX_RETRY_PER_MARKET:
                            log(f"Max retries ({MAX_RETRY_PER_MARKET}) for {order_key}", "WARN")
                            triggered = False
                            condition = None
                    
                    if triggered:
                        log(f"Trigger: {condition} -> {side} @ {price*100:.1f}%", "TRADE")
                    
                    if SIMULATION_MODE:
                        sim_shares = _shares_from_usdc_buy(TRADE_AMOUNT, price)
                        if sim_shares <= 0:
                            log(f"[SIM] Buy skipped: invalid price {price}", "WARN")
                        else:
                            sim_oid = f"SIM-{int(time.time() * 1000)}"
                            state.pop("pending_order", None)
                            current_retry = retry_count if same_key_retry else 0
                            state["last_order"] = {
                                "key": order_key,
                                "time": datetime.now().isoformat(),
                                "retry_count": current_retry + 1,
                                "last_price": price,
                            }
                            state["position"] = {
                                "slug": slug,
                                "side": side,
                                "entry_price": price,
                                "entry_diff": diff_abs,
                                "size": sim_shares,
                            }
                            cum = _to_float(state.get("cumulative_realized_pnl"), 0.0)
                            state = _append_trade_history(state, {
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "slug": slug,
                                "action": "BUY",
                                "side": side,
                                "price": price,
                                "amount": TRADE_AMOUNT,
                                "shares": sim_shares,
                                "order_size_usdc": TRADE_AMOUNT,
                                "order_id": sim_oid,
                                "status": "filled",
                                "reason": condition,
                                "diff": diff,
                                "btc": btc if btc > 0 else None,
                                "ptb": ptb if ptb > 0 else None,
                                "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                "remaining_sec": remaining,
                                "cumulative_realized_pnl_usd": cum,
                            })
                            _emit_trading_analysis(
                                "BUY_FILL",
                                action="BUY",
                                slug=slug,
                                status="buy",
                                shares_type=side,
                                share_price=price,
                                share_amount=sim_shares,
                                order_size_usdc=TRADE_AMOUNT,
                                order_id=sim_oid,
                                reason=condition,
                                btc_price=btc if btc > 0 else None,
                                chainlink_btc=btc if btc > 0 else None,
                                ptb=ptb if ptb > 0 else None,
                                btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                diff_rule=diff,
                                remaining_sec=remaining,
                                pnl_trade_usd=0.0,
                                pnl_total_usd=cum,
                            )
                            save_state(state)
                            _dashboard_set(
                                position=dict(state.get("position") or {}),
                                pending_order=_dashboard_pending_order_from_state(state),
                                last_order=dict(state.get("last_order") or {}),
                                trade_history=list(state.get("trade_history") or []),
                                cumulative_realized_pnl=cum,
                            )
                            log(
                                f"[SIM] BUY {side} @ {price*100:.2f}% | USDC {TRADE_AMOUNT} | shares≈{sim_shares:.4f} | id {sim_oid}",
                                "TRADE",
                            )
                    elif AUTO_TRADE and trader.connected:
                        order_id = trader.place_order(token, "BUY", price, TRADE_AMOUNT)
                        
                        if order_id:
                            state["pending_order"] = {
                                "order_id": order_id,
                                "time": datetime.now().isoformat(),
                                "slug": slug,
                                "side": side,
                                "price": price
                            }
                            current_retry = retry_count if same_key_retry else 0
                            state["last_order"] = {
                                "key": order_key, 
                                "time": datetime.now().isoformat(),
                                "retry_count": current_retry + 1,
                                "last_price": price,
                            }
                            cum = _to_float(state.get("cumulative_realized_pnl"), 0.0)
                            state = _append_trade_history(state, {
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "slug": slug,
                                "action": "BUY",
                                "side": side,
                                "price": price,
                                "amount": TRADE_AMOUNT,
                                "order_size_usdc": TRADE_AMOUNT,
                                "order_id": order_id,
                                "status": "submitted",
                                "reason": condition,
                                "diff": diff,
                                "btc": btc if btc > 0 else None,
                                "ptb": ptb if ptb > 0 else None,
                                "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                "remaining_sec": remaining,
                                "cumulative_realized_pnl_usd": cum,
                            })
                            _emit_trading_analysis(
                                "BUY_SUBMIT",
                                action="BUY",
                                slug=slug,
                                status="buy",
                                shares_type=side,
                                share_price=price,
                                order_size_usdc=TRADE_AMOUNT,
                                order_id=order_id,
                                reason=condition,
                                btc_price=btc if btc > 0 else None,
                                chainlink_btc=btc if btc > 0 else None,
                                ptb=ptb if ptb > 0 else None,
                                btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                diff_rule=diff,
                                remaining_sec=remaining,
                                pnl_trade_usd=0.0,
                                pnl_total_usd=cum,
                            )
                            save_state(state)
                            _dashboard_set(
                                pending_order=_dashboard_pending_order_from_state(state),
                                last_order=dict(state.get("last_order") or {}),
                                trade_history=list(state.get("trade_history") or []),
                                cumulative_realized_pnl=cum,
                            )
                            _sync_dashboard_account_snapshot(dashboard_user)
                            log(f"Order submitted, watching id {order_id}", "TRADE")
                        else:
                            log(f"Order failed: {side} @ {price*100:.1f}%", "ERR")
                            current_retry = retry_count if same_key_retry else 0
                            state["last_order"] = {
                                "key": order_key,
                                "time": datetime.now().isoformat(),
                                "retry_count": current_retry + 1,
                                "last_price": price,
                            }
                            cum = _to_float(state.get("cumulative_realized_pnl"), 0.0)
                            state = _append_trade_history(state, {
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "slug": slug,
                                "action": "BUY",
                                "side": side,
                                "price": price,
                                "amount": TRADE_AMOUNT,
                                "order_id": "",
                                "status": "failed",
                                "reason": condition,
                                "diff": diff,
                                "btc": btc if btc > 0 else None,
                                "ptb": ptb if ptb > 0 else None,
                                "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                "remaining_sec": remaining,
                                "cumulative_realized_pnl_usd": cum,
                            })
                            _emit_trading_analysis(
                                "BUY_FAILED",
                                action="BUY",
                                slug=slug,
                                status="buy",
                                shares_type=side,
                                share_price=price,
                                order_size_usdc=TRADE_AMOUNT,
                                reason=condition,
                                btc_price=btc if btc > 0 else None,
                                chainlink_btc=btc if btc > 0 else None,
                                ptb=ptb if ptb > 0 else None,
                                btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                diff_rule=diff,
                                remaining_sec=remaining,
                                pnl_trade_usd=None,
                                pnl_total_usd=cum,
                            )
                            save_state(state)
                            _dashboard_set(
                                last_order=dict(state.get("last_order") or {}),
                                trade_history=list(state.get("trade_history") or []),
                                cumulative_realized_pnl=cum,
                            )
                            _sync_dashboard_account_snapshot(dashboard_user)
                    elif not SIMULATION_MODE:
                        log(f"Alert: consider BUY {side} @ {price*100:.1f}%", "TRADE")
                        current_retry = retry_count if same_key_retry else 0
                        state["last_order"] = {
                            "key": order_key,
                            "time": datetime.now().isoformat(),
                            "retry_count": current_retry + 1,
                            "last_price": price,
                        }
                        _emit_trading_analysis(
                            "BUY_ALERT",
                            action="BUY",
                            slug=slug,
                            status="buy",
                            shares_type=side,
                            share_price=price,
                            order_size_usdc=TRADE_AMOUNT,
                            reason=condition,
                            btc_price=btc if btc > 0 else None,
                            chainlink_btc=btc if btc > 0 else None,
                            ptb=ptb if ptb > 0 else None,
                            btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            diff_rule=diff,
                            remaining_sec=remaining,
                            pnl_trade_usd=None,
                            pnl_total_usd=_to_float(state.get("cumulative_realized_pnl"), 0.0),
                        )
                        save_state(state)
                        _dashboard_set(last_order=dict(state.get("last_order") or {}))
            
            # Position TP / SL
            state = load_state()
            pos = state.get("position")
            tp_order = state.get("take_profit_order") or {}
            if pos and pos.get("slug") == slug:
                pos_side = pos.get("side")
                current_prob = up_price if pos_side == "UP" else down_price
                position_size = max(0.001, _to_float(pos.get("size"), TRADE_AMOUNT))
                entry_prob = _maybe_float(pos.get("entry_price"))
                stop_loss_triggered = False
                stop_prob = None
                tp_trigger_prob = None
                tp_sell_price = None
                if entry_prob is not None and entry_prob > 0:
                    stop_prob = max(0.0, entry_prob * (1.0 - STOP_LOSS_PROB_PCT))
                    risk_abs = max(0.0, entry_prob - stop_prob)
                    tp_trigger_prob = min(TAKE_PROFIT_CAP, entry_prob + risk_abs * TAKE_PROFIT_RR)
                    if tp_trigger_prob <= entry_prob:
                        tp_trigger_prob = None
                    else:
                        # If TP capped, tighten stop to preserve RR
                        balanced_risk = (tp_trigger_prob - entry_prob) / TAKE_PROFIT_RR
                        balanced_stop_prob = max(0.0, entry_prob - balanced_risk)
                        if balanced_stop_prob > stop_prob:
                            stop_prob = balanced_stop_prob
                        tp_sell_price = tp_trigger_prob
                    stop_loss_triggered = (current_prob > 0) and (current_prob <= stop_prob)

                if SIMULATION_MODE and pos and pos.get("slug") == slug and entry_prob is not None and entry_prob > 0:
                    sim_exit = False
                    if stop_loss_triggered:
                        sell_x = (up_bid if pos_side == "UP" else down_bid) or (up_price if pos_side == "UP" else down_price)
                        ep = float(entry_prob)
                        xp = float(sell_x)
                        realized = position_size * (xp - ep)
                        cum = _to_float(state.get("cumulative_realized_pnl"), 0.0) + realized
                        state["cumulative_realized_pnl"] = cum
                        state = _append_trade_history(state, {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "slug": slug,
                            "action": "SELL",
                            "side": pos_side,
                            "price": xp,
                            "entry_price": ep,
                            "shares": position_size,
                            "amount": position_size * xp,
                            "order_id": f"SIM-SL-{int(time.time() * 1000)}",
                            "status": "filled",
                            "reason": "stop_loss",
                            "diff": diff,
                            "btc": btc if btc > 0 else None,
                            "ptb": ptb if ptb > 0 else None,
                            "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            "remaining_sec": remaining,
                            "realized_pnl_usd": realized,
                            "cumulative_realized_pnl_usd": cum,
                        })
                        _emit_trading_analysis(
                            "SELL_CLOSE",
                            reason="stop_loss",
                            slug=slug,
                            action="SELL",
                            status="sell",
                            shares_type=pos_side,
                            share_price=xp,
                            share_amount=position_size,
                            entry_share_price=ep,
                            exit_share_price=xp,
                            notional_exit_usd=position_size * xp,
                            take_profit=tp_trigger_prob,
                            stop_loss=stop_prob,
                            btc_price=btc if btc > 0 else None,
                            chainlink_btc=btc if btc > 0 else None,
                            ptb=ptb if ptb > 0 else None,
                            btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            diff_rule=diff,
                            remaining_sec=remaining,
                            order_id=f"SIM-SL-{int(time.time() * 1000)}",
                            pnl_trade_usd=realized,
                            pnl_total_usd=cum,
                        )
                        state.pop("position", None)
                        state.pop("take_profit_order", None)
                        save_state(state)
                        _dashboard_set(
                            position={},
                            pending_order=_dashboard_pending_order_from_state(state),
                            trade_history=list(state.get("trade_history") or []),
                            cumulative_realized_pnl=cum,
                        )
                        log(
                            f"[SIM] Stop-loss {pos_side} @ {xp*100:.2f}% | PnL ${realized:+.4f} | cumulative ${cum:+.4f}",
                            "TRADE",
                        )
                        sim_exit = True
                    elif (
                        tp_trigger_prob is not None
                        and tp_sell_price
                        and current_prob > 0
                        and current_prob >= tp_trigger_prob
                    ):
                        ep = float(entry_prob)
                        xp = float(tp_sell_price)
                        realized = position_size * (xp - ep)
                        cum = _to_float(state.get("cumulative_realized_pnl"), 0.0) + realized
                        state["cumulative_realized_pnl"] = cum
                        state = _append_trade_history(state, {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "slug": slug,
                            "action": "SELL",
                            "side": pos_side,
                            "price": xp,
                            "entry_price": ep,
                            "shares": position_size,
                            "amount": position_size * xp,
                            "order_id": f"SIM-TP-{int(time.time() * 1000)}",
                            "status": "filled",
                            "reason": "take_profit",
                            "diff": diff,
                            "btc": btc if btc > 0 else None,
                            "ptb": ptb if ptb > 0 else None,
                            "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            "remaining_sec": remaining,
                            "realized_pnl_usd": realized,
                            "cumulative_realized_pnl_usd": cum,
                        })
                        _emit_trading_analysis(
                            "SELL_CLOSE",
                            reason="take_profit",
                            slug=slug,
                            action="SELL",
                            status="sell",
                            shares_type=pos_side,
                            share_price=xp,
                            share_amount=position_size,
                            entry_share_price=ep,
                            exit_share_price=xp,
                            notional_exit_usd=position_size * xp,
                            take_profit=tp_trigger_prob,
                            stop_loss=stop_prob,
                            btc_price=btc if btc > 0 else None,
                            chainlink_btc=btc if btc > 0 else None,
                            ptb=ptb if ptb > 0 else None,
                            btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            diff_rule=diff,
                            remaining_sec=remaining,
                            order_id=f"SIM-TP-{int(time.time() * 1000)}",
                            pnl_trade_usd=realized,
                            pnl_total_usd=cum,
                        )
                        state.pop("position", None)
                        state.pop("take_profit_order", None)
                        save_state(state)
                        _dashboard_set(
                            position={},
                            pending_order=_dashboard_pending_order_from_state(state),
                            trade_history=list(state.get("trade_history") or []),
                            cumulative_realized_pnl=cum,
                        )
                        log(
                            f"[SIM] Take-profit {pos_side} @ {xp*100:.2f}% | PnL ${realized:+.4f} | cumulative ${cum:+.4f}",
                            "TRADE",
                        )
                        sim_exit = True
                    if sim_exit:
                        state = load_state()
                        pos = state.get("position")
                        tp_order = state.get("take_profit_order") or {}

                # Working TP order lifecycle (live only)
                if (
                    (not SIMULATION_MODE)
                    and tp_order
                    and tp_order.get("slug") == slug
                    and tp_order.get("side") == pos_side
                    and AUTO_TRADE
                    and trader.connected
                ):
                    tp_order_id = tp_order.get("order_id")
                    tp_status = trader.get_order_status(tp_order_id)
                    if tp_status and tp_status.get("filled"):
                        tp_price = float(tp_order.get("price") or tp_sell_price or 0.0)
                        tp_amount = max(0.001, _to_float(tp_order.get("amount"), position_size))
                        ep = _maybe_float(pos.get("entry_price")) or 0.0
                        realized = tp_amount * (tp_price - ep) if ep else 0.0
                        cum = _to_float(state.get("cumulative_realized_pnl"), 0.0) + realized
                        state["cumulative_realized_pnl"] = cum
                        state = _append_trade_history(state, {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "slug": slug,
                            "action": "SELL",
                            "side": pos_side,
                            "price": tp_price,
                            "entry_price": ep,
                            "shares": tp_amount,
                            "amount": tp_amount * tp_price,
                            "order_id": tp_order_id or "",
                            "status": "filled",
                            "reason": "take_profit",
                            "diff": diff,
                            "btc": btc if btc > 0 else None,
                            "ptb": ptb if ptb > 0 else None,
                            "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            "remaining_sec": remaining,
                            "realized_pnl_usd": realized,
                            "cumulative_realized_pnl_usd": cum,
                        })
                        _emit_trading_analysis(
                            "SELL_CLOSE",
                            reason="take_profit",
                            slug=slug,
                            action="SELL",
                            status="sell",
                            shares_type=pos_side,
                            share_price=tp_price,
                            share_amount=tp_amount,
                            entry_share_price=ep,
                            exit_share_price=tp_price,
                            notional_exit_usd=tp_amount * tp_price,
                            take_profit=tp_trigger_prob,
                            stop_loss=stop_prob,
                            btc_price=btc if btc > 0 else None,
                            chainlink_btc=btc if btc > 0 else None,
                            ptb=ptb if ptb > 0 else None,
                            btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            diff_rule=diff,
                            remaining_sec=remaining,
                            order_id=tp_order_id or "",
                            pnl_trade_usd=realized,
                            pnl_total_usd=cum,
                        )
                        state.pop("take_profit_order", None)
                        state.pop("position", None)
                        save_state(state)
                        _dashboard_set(
                            position={},
                            pending_order=_dashboard_pending_order_from_state(state),
                            trade_history=list(state.get("trade_history") or []),
                            cumulative_realized_pnl=cum,
                        )
                        _sync_dashboard_account_snapshot(dashboard_user)
                        log(f"TP order filled: {pos_side} @ {tp_price*100:.2f}%", "TRADE")
                        pos = None
                        tp_order = {}
                    elif tp_status and tp_status.get("status") in ["CANCELED", "CANCELLED", "REJECTED", "EXPIRED"]:
                        log("TP order dead; will re-arm if price moves", "WARN")
                        state.pop("take_profit_order", None)
                        save_state(state)
                        _dashboard_set(pending_order=_dashboard_pending_order_from_state(state))
                        tp_order = {}

                if (
                    (not SIMULATION_MODE)
                    and pos
                    and (not tp_order)
                    and tp_trigger_prob is not None
                    and current_prob > 0
                    and current_prob >= tp_trigger_prob
                ):
                    log(
                        f"TP arm: entry {entry_prob*100:.1f}%, now {current_prob*100:.1f}%, target {tp_trigger_prob*100:.1f}% (RR≈{TAKE_PROFIT_RR:.2f})",
                        "TRADE",
                    )
                    if AUTO_TRADE and trader.connected:
                        sell_token = market["up_token"] if pos_side == "UP" else market["down_token"]
                        tp_order_id = None
                        tp_submit_price = tp_sell_price
                        attempt_price = tp_sell_price
                        for attempt_idx in range(TAKE_PROFIT_RETRY_MAX):
                            tp_order_id = trader.place_order(sell_token, "SELL", attempt_price, position_size)
                            if tp_order_id:
                                tp_submit_price = attempt_price
                                break
                            if attempt_idx + 1 >= TAKE_PROFIT_RETRY_MAX:
                                break
                            next_price = min(TAKE_PROFIT_CAP, attempt_price + TAKE_PROFIT_RETRY_STEP)
                            if next_price <= attempt_price + 1e-9:
                                break
                            log(
                                f"TP retry {attempt_idx+2}/{TAKE_PROFIT_RETRY_MAX}: bump to {next_price*100:.1f}%",
                                "WARN",
                            )
                            attempt_price = next_price
                        if tp_order_id:
                            state["take_profit_order"] = {
                                "order_id": tp_order_id,
                                "time": datetime.now().isoformat(),
                                "slug": slug,
                                "side": pos_side,
                                "price": tp_submit_price,
                                "amount": position_size,
                                "action": "SELL",
                                "reason": "take_profit",
                            }
                            cum = _to_float(state.get("cumulative_realized_pnl"), 0.0)
                            state = _append_trade_history(state, {
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "slug": slug,
                                "action": "SELL",
                                "side": pos_side,
                                "price": tp_submit_price,
                                "amount": position_size,
                                "order_id": tp_order_id,
                                "status": "submitted",
                                "reason": "take_profit",
                                "diff": diff,
                                "btc": btc if btc > 0 else None,
                                "ptb": ptb if ptb > 0 else None,
                                "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                "remaining_sec": remaining,
                                "cumulative_realized_pnl_usd": cum,
                            })
                            _emit_trading_analysis(
                                "SELL_SUBMIT",
                                reason="take_profit",
                                slug=slug,
                                action="SELL",
                                status="sell",
                                shares_type=pos_side,
                                share_price=tp_submit_price,
                                share_amount=position_size,
                                take_profit=tp_trigger_prob,
                                stop_loss=stop_prob,
                                order_id=tp_order_id,
                                btc_price=btc if btc > 0 else None,
                                chainlink_btc=btc if btc > 0 else None,
                                ptb=ptb if ptb > 0 else None,
                                btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                                diff_rule=diff,
                                remaining_sec=remaining,
                                pnl_trade_usd=None,
                                pnl_total_usd=cum,
                            )
                            save_state(state)
                            _dashboard_set(
                                pending_order=_dashboard_pending_order_from_state(state),
                                trade_history=list(state.get("trade_history") or []),
                                cumulative_realized_pnl=cum,
                            )
                            _sync_dashboard_account_snapshot(dashboard_user)
                            tp_order = dict(state.get("take_profit_order") or {})
                            log(f"TP order live id {tp_order_id}", "TRADE")
                        else:
                            log(f"TP order failed: {pos_side} @ {attempt_price*100:.1f}%", "ERR")
                    elif not SIMULATION_MODE:
                        log(f"Alert: consider SELL {pos_side} @ {tp_sell_price*100:.1f}% (size {position_size:.4f})", "TRADE")
                        _emit_trading_analysis(
                            "SELL_ALERT",
                            reason="take_profit",
                            slug=slug,
                            action="SELL",
                            status="sell",
                            shares_type=pos_side,
                            share_price=tp_sell_price,
                            share_amount=position_size,
                            take_profit=tp_trigger_prob,
                            stop_loss=stop_prob,
                            btc_price=btc if btc > 0 else None,
                            chainlink_btc=btc if btc > 0 else None,
                            ptb=ptb if ptb > 0 else None,
                            btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            remaining_sec=remaining,
                            pnl_trade_usd=None,
                            pnl_total_usd=_to_float(state.get("cumulative_realized_pnl"), 0.0),
                        )

                if (not SIMULATION_MODE) and pos and stop_loss_triggered:
                    log(
                        f"Stop hit: {pos_side} prob {current_prob*100:.1f}% <= stop {stop_prob*100:.1f}% (entry {entry_prob*100:.1f}%)",
                        "TRADE",
                    )

                    if AUTO_TRADE and trader.connected:
                        if tp_order and tp_order.get("order_id"):
                            trader.cancel_order(tp_order.get("order_id"))
                            state.pop("take_profit_order", None)

                        sell_price = (up_bid if pos_side == "UP" else down_bid) or (up_price if pos_side == "UP" else down_price)
                        sell_token = market["up_token"] if pos_side == "UP" else market["down_token"]
                        sell_order_id = trader.place_order(sell_token, "SELL", sell_price, position_size)
                        ep = _maybe_float(pos.get("entry_price")) or 0.0
                        xp = float(sell_price)
                        realized = position_size * (xp - ep) if sell_order_id and ep else 0.0
                        cum = _to_float(state.get("cumulative_realized_pnl"), 0.0) + (realized if sell_order_id else 0.0)
                        if sell_order_id:
                            state["cumulative_realized_pnl"] = cum
                        state = _append_trade_history(state, {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "slug": slug,
                            "action": "SELL",
                            "side": pos_side,
                            "price": sell_price,
                            "entry_price": ep,
                            "shares": position_size,
                            "amount": position_size * xp,
                            "order_id": sell_order_id or "",
                            "status": "submitted" if sell_order_id else "failed",
                            "reason": "stop_loss",
                            "diff": diff,
                            "btc": btc if btc > 0 else None,
                            "ptb": ptb if ptb > 0 else None,
                            "btc_minus_ptb": _btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            "remaining_sec": remaining,
                            "realized_pnl_usd": realized if sell_order_id else None,
                            "cumulative_realized_pnl_usd": cum if sell_order_id else _to_float(state.get("cumulative_realized_pnl"), 0.0),
                        })
                        _emit_trading_analysis(
                            "SELL_SUBMIT" if sell_order_id else "SELL_FAILED",
                            reason="stop_loss",
                            slug=slug,
                            action="SELL",
                            status="sell",
                            shares_type=pos_side,
                            share_price=xp,
                            share_amount=position_size,
                            entry_share_price=ep,
                            exit_share_price=xp,
                            take_profit=tp_trigger_prob,
                            stop_loss=stop_prob,
                            order_id=sell_order_id or "",
                            btc_price=btc if btc > 0 else None,
                            chainlink_btc=btc if btc > 0 else None,
                            ptb=ptb if ptb > 0 else None,
                            btc_minus_ptb=_btc_ptb_snapshot(btc if btc > 0 else None, ptb if ptb > 0 else None),
                            diff_rule=diff,
                            remaining_sec=remaining,
                            pnl_trade_usd=realized if sell_order_id else None,
                            pnl_total_usd=cum if sell_order_id else _to_float(state.get("cumulative_realized_pnl"), 0.0),
                        )
                        state.pop("position", None)
                        state.pop("take_profit_order", None)
                        save_state(state)
                        _dashboard_set(
                            position={},
                            pending_order=_dashboard_pending_order_from_state(state),
                            trade_history=list(state.get("trade_history") or []),
                            cumulative_realized_pnl=cum if sell_order_id else _to_float(state.get("cumulative_realized_pnl"), 0.0),
                        )
                        _sync_dashboard_account_snapshot(dashboard_user)
                        log(f"Stop-loss sell done: {pos_side} @ {sell_price*100:.2f}%", "TRADE")
            
            time.sleep(LOOP_INTERVAL_SEC)
            
    except KeyboardInterrupt:
        print("\n\nStopped.")
        if market_listener:
            market_listener.stop()
        redeemer.stop()

if __name__ == "__main__":
    main()
