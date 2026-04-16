# BTC 15-Minute Live Trading Bot - Complete Logic Documentation

**Suite:** [PolyBullLabs — polymakret-5min-15min-1hour-arbitrage-bot](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot) · [@terauss](https://t.me/terauss) · [README](README.md) · [CONFIG.md](CONFIG.md)

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Market Structure](#2-market-structure)
3. [Data Acquisition Layer](#3-data-acquisition-layer)
4. [Indicator Calculations (Formulas)](#4-indicator-calculations-formulas)
5. [Signal Generation Engine](#5-signal-generation-engine)
6. [Order Execution Pipeline](#6-order-execution-pipeline)
7. [Hedge Mechanism](#7-hedge-mechanism)
8. [Position Lifecycle and PnL Accounting](#8-position-lifecycle-and-pnl-accounting)
9. [Drawdown Tracking](#9-drawdown-tracking)
10. [Chainlink BTC/USD Oracle Integration](#10-chainlink-btcusd-oracle-integration)
11. [Auto-Redemption System](#11-auto-redemption-system)
12. [Configuration Reference](#12-configuration-reference)
13. [Fault Tolerance and Recovery](#13-fault-tolerance-and-recovery)
14. [File and Log Architecture](#14-file-and-log-architecture)

---

## 1. System Overview

The bot trades **Polymarket BTC Up/Down 15-minute binary markets**. Each market resolves to either "UP" (BTC price rose) or "DOWN" (BTC price fell) over a 15-minute window aligned to epoch boundaries (multiples of 900 seconds).

### Architecture

```
                         LiveTradingBot
  +----------------------------------------------------------+
  |                                                          |
  |  +----------+  +--------------+  +------------------+   |
  |  | Market   |  |  WebSocket   |  |  Chainlink RTDS  |   |
  |  | Finder   |  |  Client      |  |  Price Client    |   |
  |  | (HTTP)   |  |  (wss://)    |  |  (wss://)        |   |
  |  +----+-----+  +------+-------+  +--------+---------+   |
  |       |               |                    |             |
  |       v               v                    v             |
  |  +-------------------------------------------------+    |
  |  |            MarketState (shared)                  |    |
  |  |  up_token, down_token, btc_price, end_time      |    |
  |  +------------------------+------------------------+    |
  |                           |                              |
  |       +-------------------+-------------------+          |
  |       v                   v                   v          |
  |  +----------+  +---------------+  +------------+        |
  |  |Dashboard |  |  Signal       |  |  Order     |        |
  |  | (Rich)   |  |  Generator    |  |  Executor  |        |
  |  +----------+  +-------+-------+  +------+-----+        |
  |                         |                |               |
  |                         v                v               |
  |              +----------------+  +--------------+        |
  |              | TradingStats   |  | HedgeManager |        |
  |              | (Position/PnL) |  | (GTD orders) |        |
  |              +----------------+  +--------------+        |
  |                                                          |
  |  +--------------+  +------------------+                  |
  |  | AutoRedeemer |  | TelegramNotifier |                  |
  |  | (background) |  | (alerts/charts)  |                  |
  |  +--------------+  +------------------+                  |
  +----------------------------------------------------------+
```

### Main Loop (simplified)

```
while running:
    market = find_active_btc_15m_market()      # HTTP -> Gamma API
    subscribe_websocket(market.tokens)          # wss:// -> live prices

    while market.is_active:
        update_indicators()                     # every 250ms
        signal = evaluate_strategy()            # check all conditions

        if signal == BUY:
            execute_entry(signal)               # FAK order
            place_hedge()                       # GTD order (opposite token)

        track_drawdown()                        # update min_price_seen

        if time_left <= 10s:
            close_position()                    # record PnL
            break

    wait_for_next_market()                      # ~5-30 seconds
```

---

## 2. Market Structure

### Polymarket BTC Up/Down 15-Min Markets

Each market is a **binary outcome** contract:

- **UP token**: Pays $1.00 if BTC price is higher at market end vs. start. Otherwise $0.
- **DOWN token**: Pays $1.00 if BTC price is lower at market end vs. start. Otherwise $0.

Tokens trade between $0.01 and $0.99. At any time:

```
P_UP + P_DOWN ~ 1.00
```

### Market Timing

Markets are aligned to 15-minute epoch boundaries:

```
T_start = floor(T_now / 900) * 900
T_end   = T_start + 900
```

Market slug format: `btc-updown-15m-{T_start}`

Example: `btc-updown-15m-1770831900` starts at Unix timestamp 1770831900.

### Market Discovery

The bot searches the Gamma API for active markets using offsets from the current 15-minute window:

```python
for offset in [0, 900, -900, 1800]:
    target_ts = current_window + offset
    slug = f"btc-updown-15m-{target_ts}"
    # Query: GET /markets?slug={slug}&active=true&closed=false
```

---

## 3. Data Acquisition Layer

### 3.1 Market Data WebSocket

**URL**: `wss://ws-subscriptions-clob.polymarket.com/ws/market`

Subscribes to both UP and DOWN token IDs. Processes three event types:

#### `last_trade_price` - Trade Execution

Each trade is stored as `Trade(timestamp, price, size, side)` in a deque per token.

Tracked aggregates:
- `trade_count`: Total number of trades
- `volume_total`: Total contract volume
- `volume_buy`: Volume from buy-side
- `volume_sell`: Volume from sell-side

#### `price_change` - Best Bid/Ask Updates

Updates `best_bid` and `best_ask` for each token.

#### `book` - Order Book Snapshots

Parses bids and asks arrays, extracts top-of-book:
- `best_bid`, `best_bid_size`
- `best_ask`, `best_ask_size`

Spread:

```
Spread = P_ask - P_bid
```

### 3.2 User WebSocket (Order Tracking)

**URL**: Polymarket User Channel (authenticated via API credentials)

Tracks order lifecycle: `PLACEMENT -> MATCHED -> MINED -> CONFIRMED`

Used for:
- Fill confirmation after entry orders
- Hedge fill detection
- Timeout recovery (checking if order filled despite timeout)

### 3.3 Chainlink BTC/USD Price Stream

**URL**: `wss://ws-live-data.polymarket.com` (Polymarket RTDS)

**Topic**: `crypto_prices_chainlink` filtered for `btc/usd` symbol.

See Section 10 for full details.

---

## 4. Indicator Calculations (Formulas)

All indicators are calculated from the live trade stream. Each token (UP and DOWN) has its own independent indicator set.

### 4.1 VWAP (Volume-Weighted Average Price)

VWAP over a configurable time window W (default 30 seconds):

```
                 SUM(P_i * V_i)   for all trades where (T_now - T_i) <= W
VWAP_W  =  -------------------------
                 SUM(V_i)
```

Where:
- `P_i` = price of trade i
- `V_i` = size (volume) of trade i
- `trades(W)` = set of trades within the last W seconds

Returns 0.0 if no trades in window.

### 4.2 Deviation from VWAP

Percentage deviation of the current last-trade price from VWAP:

```
            P_last - VWAP
D  =  ---------------------- * 100%
              VWAP
```

Where:
- `D > 0`: Price is **above** VWAP (bullish pressure)
- `D < 0`: Price is **below** VWAP (bearish pressure)
- `D = 0`: Price equals VWAP

### 4.3 Momentum

Momentum compares the current price to the average price W seconds ago (default 60s), using a band of +/-1.5 seconds to smooth:

```
P_ago  =  mean({P_i  where  T_now - W - d  <=  T_i  <=  T_now - W + d})

              P_last - P_ago
M  =  ------------------------- * 100%
              P_ago
```

Where:
- `W` = momentum_window_sec (default 60)
- `d` = averaging band (1.5 seconds)
- Returns `None` if no trades exist in the band window

Interpretation:
- `M > 0`: Price has risen over the window (positive momentum)
- `M < 0`: Price has fallen (negative momentum)

### 4.4 Z-Score

Statistical z-score of the current price relative to recent trade prices over a 5-second window:

```
        P_last - mean(prices_5s)
z  =  ----------------------------
           stdev(prices_5s)
```

Where:
- `mean(prices_5s)` = arithmetic mean of all trade prices in last 5 seconds
- `stdev(prices_5s)` = standard deviation, with minimum floor of 0.001

Interpretation:
- `z > 2`: Price significantly above recent mean (overbought short-term)
- `z < -2`: Price significantly below recent mean (oversold short-term)

### 4.5 Win Rate Lookup

Historical win rates are stored in `data/win_rate.csv` as a 10x15 matrix:

| Price Range | min_0  | min_1  | ... | min_14 |
|-------------|--------|--------|-----|--------|
| 0.50-0.54   | 52.2%  | 50.2%  | ... | 52.7%  |
| 0.75-0.79   | 71.1%  | 76.4%  | ... | 75.0%  |
| 0.85-0.89   | 68.0%  | 73.0%  | ... | 93.3%  |
| 0.95-0.99   | 63.2%  | 68.2%  | ... | 100%   |

**Time bin** calculation:

```
bin = floor(14 - T_remaining / 60)
```

Where `bin` is in [0, 14], with bin 0 = first minute, bin 14 = last minute.

**Lookup**: Given favorite token price P_fav and time bin, the table returns the historical win probability.

---

## 5. Signal Generation Engine

The signal generator runs inside `Dashboard.create_strategy_panel()`, evaluated every 250ms (4 Hz refresh).

### 5.1 Favorite Token Selection

The "favorite" is the token with the higher last-trade price:

```
            | UP     if P_UP > P_DOWN
favorite =  |
            | DOWN   otherwise
```

The favorite's indicators are used for signal evaluation:
- `P_fav` = favorite price
- `D_fav` = favorite deviation from VWAP
- `M_fav` = favorite momentum

### 5.2 Entry Conditions (ALL must be true)

| #  | Condition               | Formula                        | Config Parameter          |
|----|-------------------------|--------------------------------|---------------------------|
| 1  | Price in range          | P_min <= P_fav <= P_max        | min_price, max_price      |
| 2  | Sufficient time elapsed | T_elapsed >= T_min_elapsed     | min_elapsed_sec           |
| 3  | Deviation in range      | D_min < D_fav < D_max         | min/max_deviation_pct     |
| 4  | Positive momentum       | M_fav > 0                      | -                         |
| 5  | Not too close to end    | T_remaining > T_no_entry       | no_entry_before_end_sec   |

Where:
- `T_elapsed = 900 - T_remaining`
- `T_remaining = T_end - T_now`

### 5.3 Signal States

```
if T_remaining <= T_no_entry:
    -> NO ENTRY (cutoff reached, no further entry this market)

elif ALL 5 conditions TRUE:
    -> BUY {UP|DOWN} (signal triggers execute_entry)

elif P_fav >= 0.70 AND T_elapsed >= T_min_elapsed:
    if M_fav <= 0:      -> ALMOST (need Mom>0%)
    if D_fav >= D_max:   -> ALMOST (Dev too high)
    else:                -> ALMOST (need dev)

else:
    -> WAIT (with specific reason: elapsed/price/dev/mom)
```

### 5.4 Signal Flow

```
Dashboard.create_strategy_panel()
    |
    +-- Evaluates conditions every 250ms
    +-- If BUY: sets self.last_signal = "BUY_UP" or "BUY_DOWN"
    |
    v
Main loop (run_session)
    |
    +-- Reads self.dashboard.last_signal
    +-- Clears signal (one-shot)
    +-- Creates asyncio task: _safe_execute_entry(signal)
    |
    v
execute_entry("BUY_UP" or "BUY_DOWN")
```

**Important**: Only ONE entry per market. `can_enter()` returns False once a position is recorded OR entry is blocked.

---

## 6. Order Execution Pipeline

### 6.1 Pre-Execution Guards

Before placing any order, three guards are checked:

1. **Position check**: `stats.can_enter()` - no existing position, not closed this market, not blocked
2. **Time cutoff**: `T_remaining > T_no_entry`
3. **Token data available**: Both UP and DOWN tokens must have data

### 6.2 Order Configuration

| Parameter        | Value   | Description                              |
|------------------|---------|------------------------------------------|
| bet_amount_usd   | 50      | USD to risk per trade                    |
| price_offset     | 0.02    | Added to best bid for aggressive fill    |
| order_type       | FAK     | Fill-And-Kill (immediate or cancel)      |
| max_retries      | 3       | Retry count on failure                   |
| retry_delay_ms   | 300     | Delay between retries                    |
| fill_timeout_ms  | 1000    | Max wait for fill confirmation           |
| min_contracts    | 5       | Polymarket minimum                       |
| max_entry_price  | 0.88    | Hard price ceiling                       |

### 6.3 Contract Calculation

```
contracts = floor(bet_amount_usd / P_entry)
```

Where `P_entry = min(P_best_ask, P_max_entry)`

The order is placed at:

```
P_order = P_best_bid + price_offset
```

### 6.4 FAK Order Flow

```
1. Fetch best_bid from orderbook
2. Calculate: P_order = best_bid + price_offset
3. Validate: P_order <= max_entry_price
4. Place FAK BUY order
5. Wait fill_timeout_ms for fill confirmation via WebSocket
6. If filled: record position -> place hedge -> done
7. If timeout: enter recovery mode (see Section 13)
8. If rejected: retry up to max_retries
```

### 6.5 Signal Logging

At the moment of execution, a comprehensive snapshot is logged to `signals.log`:

- Timestamp, market slug, signal direction, token
- Elapsed/remaining time, time bin
- For each token (UP and DOWN):
  - LAST, BID, ASK prices
  - VWAP, Deviation, Z-Score, Momentum
  - Trade count, Total/Buy/Sell volume
- Win rate lookup value
- Strategy config parameters
- Chainlink BTC/USD price, anchor, and deviation

---

## 7. Hedge Mechanism

### 7.1 Purpose

After buying the favorite token (e.g., UP at $0.85), the bot places a **hedge order** on the **opposite token** (DOWN) at a very low price ($0.02).

If the trade loses (UP resolves to $0), the hedge may fill, providing the opposite token at $0.02 which resolves to $1.00 -- a $0.98 profit per contract that partially offsets the loss.

### 7.2 Hedge PnL Math

**Without hedge** (unhedged loss):

```
PnL_loss = -C * P_entry
```

Where C = contracts, P_entry = entry price.

**With hedge** (if hedge fills before resolution):

```
PnL_hedged_loss = -C * P_entry  +  C_hedge * (1.00 - P_hedge)
```

With P_hedge = 0.02:

```
PnL_hedged_loss = -C * P_entry  +  C_hedge * 0.98
```

### 7.3 Hedge Order Type

- **GTD (Good-Till-Date)**: Limit order that stays on the book until expiry
- Placed at `hedge_price` ($0.02) on the opposite token
- Expires in 1 hour (market resolves in <=15 minutes)
- Only fills if opposite token price drops to $0.02 (i.e., our side is winning strongly)

### 7.4 Hedge Fill Tracking

The User WebSocket monitors for fill events matching the hedge order ID:

```
on_trade(data):
    if data.order_id == hedge_order_id AND status == "MATCHED":
        hedge_mgr.on_hedge_fill(size, price)
        if hedge_mgr.is_fully_hedged:
            stats.record_hedge(contracts, price)
```

---

## 8. Position Lifecycle and PnL Accounting

### 8.1 Position States

```
  NO POSITION                    OPEN POSITION
  +----------+   execute_entry   +--------------+
  | can_enter | --------------->  |   LONG UP    |
  |  = true   |                  |   or DOWN    |
  +----------+                   |              |
                                 | entry_price  |
                                 | contracts    |
                                 | hedged?      |
                                 +------+-------+
                                        |
                         check_market_end (T_left <= 10s)
                                        |
                                        v
                                 +--------------+
                                 |  CLOSED      |
                                 |  TradeRecord |
                                 |  (PnL, DD)   |
                                 +--------------+
```

### 8.2 PnL Calculation

At market end (10 seconds before expiry), the bot reads the final token price.

**Win condition**: `P_final >= 0.70`

**Win PnL** (token resolves to ~$1.00):

```
PnL_win = C * 1.00 - C * P_entry = C * (1 - P_entry)
```

**Loss PnL** (token resolves to ~$0.00):

```
PnL_loss = 0 - C * P_entry = -C * P_entry
```

**Examples** with C = 64 contracts:

| Entry Price | Win PnL  | Loss PnL  |
|-------------|----------|-----------|
| $0.75       | +$16.00  | -$48.00   |
| $0.81       | +$12.16  | -$51.84   |
| $0.88       | +$7.68   | -$56.32   |

### 8.3 Win Rate and Session Statistics

```
Win Rate = W / (W + L) * 100%

Total PnL = SUM(PnL_i)  for all trades i = 1..N

Avg Win  = SUM(PnL_w) / count(wins)

Avg Loss = SUM(PnL_l) / count(losses)
```

### 8.4 Break-Even Win Rate

For a given entry price P, the minimum win rate needed to break even:

```
WR_breakeven = P / 1.00 = P
```

| Entry Price | Break-Even WR |
|-------------|---------------|
| $0.75       | 75%           |
| $0.80       | 80%           |
| $0.85       | 85%           |
| $0.88       | 88%           |

This is why the win rate CSV is critical -- the bot only enters when historical win rate exceeds the break-even threshold for the given price and time bin.

---

## 9. Drawdown Tracking

### 9.1 Per-Trade Drawdown

After entry, the bot tracks the minimum price seen every 250ms:

```
P_min = min(P_min, P_current)    # updated every 250ms
```

Initialized at entry: `P_min = P_entry`

At position close, drawdown is calculated:

**Absolute drawdown**:

```
DD_abs = max(0,  P_entry - P_min)
```

**Percentage drawdown**:

```
DD_pct = (DD_abs / P_entry) * 100%
```

**Dollar drawdown** (total exposure):

```
DD_usd = DD_abs * C
```

### 9.2 Logging

At market end, logged to `signals.log`:

```
Max Drawdown: -0.0500 (-6.17%)
Max DD ($): -$3.20 (min price: 0.7600)
```

### 9.3 Live Dashboard

While position is open, the dashboard shows real-time drawdown:

```
LONG UP @ 0.810 (64 contracts)
   Unrealized: +$3.84 (price: 0.870)
   Max DD: -$1.92 (-3.7%) (low: 0.780)
```

---

## 10. Chainlink BTC/USD Oracle Integration

### 10.1 Purpose

The Chainlink price feed provides the **actual BTC/USD price** used by Polymarket to resolve markets. The bot tracks this independently for:

1. **Dashboard display**: Shows real-time BTC price and deviation from market start
2. **Signal logging**: Records BTC deviation at the moment of each trade entry
3. **Analysis**: Understanding how BTC price movement correlates with market outcomes

### 10.2 Connection

```
URL:     wss://ws-live-data.polymarket.com
Topic:   crypto_prices_chainlink
Symbol:  btc/usd (filtered in code)
```

### 10.3 Anchor Price and Deviation

At each 15-minute boundary, the **anchor price** is captured as the first tick of the new window:

```
Window = floor(T_chainlink / 900) * 900
```

When Window changes (new 15-minute period), the first tick's price becomes the anchor:

```
P_anchor = price of first tick where Window(T_tick) != Window_previous
```

**BTC Deviation**:

```
Delta_abs = P_current - P_anchor

Delta_pct = (Delta_abs / P_anchor) * 100%
```

### 10.4 Calibration Logging

For calibration purposes, every tick within [-15s, +5s] of a 15-minute boundary is logged:

```
BTC_TICK 16:59:59.000 (local 17:00:00.653) $69,481.26 [-1.000s before 17:00:00]
BTC_TICK 17:00:00.000 (local 17:00:01.578) $69,483.32 [+0.000s after 17:00:00]
```

Fields:
- **Chainlink timestamp**: From the oracle data (millisecond precision)
- **Local timestamp**: Server clock time when message was processed
- **Price**: BTC/USD price from Chainlink
- **Offset**: Seconds before/after the 15-minute boundary

### 10.5 Watchdog

If no Chainlink messages are received for 30 seconds, the watchdog forces a WebSocket reconnection:

```python
if time.time() - last_msg_time > DATA_TIMEOUT:  # 30 seconds
    ws.close()  # Triggers reconnection in connect() loop
```

---

## 11. Auto-Redemption System

### 11.1 Purpose

After a market resolves, winning positions must be **redeemed** on-chain to collect the $1.00 payout per contract.

### 11.2 Flow

```
Every 180 seconds:
    1. Fetch all positions from Polymarket Data API
    2. Categorize: active, pending, redeemable
    3. For each redeemable position:
       a. Check oracle resolution (payoutDenominator)
       b. Submit redemption transaction on Polygon
       c. Wait for confirmation
```

### 11.3 Implementation Details

- Runs as a background asyncio task
- File lock prevents concurrent redemptions
- Supports both EOA (direct) and Gnosis Safe (proxy) wallets
- Blockchain transactions require POL (MATIC) for gas fees
- Runs in a dedicated thread pool to avoid blocking the main event loop

---

## 12. Configuration Reference

### Strategy Parameters

| Parameter           | config.json | Dataclass Default | Description                       |
|---------------------|-------------|-------------------|-----------------------------------|
| min_price           | 0.75        | 0.65              | Min favorite token price to enter |
| max_price           | 0.88        | 0.91              | Max favorite token price to enter |
| min_elapsed_sec     | 500         | 480               | Min seconds since market start    |
| min_deviation_pct   | 0           | 5.0               | Min VWAP deviation (%)            |
| max_deviation_pct   | 100         | 100.0             | Max VWAP deviation (%)            |
| no_entry_before_end | 335         | 90                | Min seconds remaining for entry   |
| momentum_window_sec | 60          | 120               | Momentum lookback window          |
| vwap_window_sec     | 30          | 30                | VWAP calculation window           |

> **Note**: "config.json" = active value. "Dataclass Default" = fallback if field is missing from JSON.

### Timing Constraints Visualization

```
Market: 900 seconds (15 minutes)

0s ----------- 500s ---- 565s ----------- 900s
|               |         |                |
|   NO ENTRY    |  ENTRY  |   NO ENTRY     |
|   (too early) | WINDOW  |  (too late)    |
|               |         |                |
<-min_elapsed-> |         |                |
                |         <---335s cutoff-->|
                |         |                |
                <-- 65s -->
                  allowed
```

Entry is allowed when:
- `T_elapsed >= 500` seconds AND
- `T_remaining > 335` seconds

This creates a **65-second entry window** (from 500s to 565s elapsed).

---

## 13. Fault Tolerance and Recovery

### 13.1 Order Timeout Recovery

When a FAK order times out (no fill confirmation within fill_timeout_ms):

```
1. Check User WebSocket for recent fills on the token
2. Wait up to ws_recovery_timeout_sec (10s)
3. If fills found:
   -> RECOVERY: Record position from WS fill data
   -> Place hedge as normal
4. If no fills found:
   -> Block entry for rest of market (prevent duplicates)
   -> Log: "Network timeout - no fill detected"
```

### 13.2 Entry Blocking

After any failed entry attempt, `stats.block_entry()` prevents further attempts on the same market. This avoids:
- Duplicate orders from timeout+retry
- Repeated failures hitting rate limits

Reset on new market: `entry_blocked = False`

### 13.3 WebSocket Reconnection

**Market Data WebSocket**: On ConnectionClosed, reconnects after 2 seconds. On any other exception, reconnects after 5 seconds.

**Chainlink RTDS WebSocket**: Same reconnection logic plus a 30-second **watchdog** that detects silent disconnections (TCP alive but no data flowing).

### 13.4 Config Validation

At startup, `validate_config()` checks:
- Private key exists and starts with "0x"
- API credentials are set
- `min_price < max_price`
- `max_entry_price <= max_price`
- `max_deviation_pct > min_deviation_pct`

Bot refuses to start if any validation fails.

---

## 14. File and Log Architecture

### Directory Structure

```
btc_15m_live/
+-- main.py                    # Main bot (2000+ lines, all core logic)
+-- config.json                # Runtime configuration
+-- .env                       # Secrets (API keys, private key)
+-- chart_pnl.py               # PnL chart generator
+-- PROJECT_LOGIC.md           # This document
+-- data/
|   +-- win_rate.csv           # Historical win rate matrix (10x15)
+-- logs/
|   +-- bot.log                # Main application log
|   +-- signals.log            # Trade signal snapshots
|   +-- orders.log             # Order execution details
|   +-- trading_log.json       # Trade history (JSON persistence)
|   +-- api_activity.json      # API call log
|   +-- pnl_chart.png          # Generated PnL chart
|   +-- equity_chart.png       # Equity curve chart
+-- src/
    +-- config_loader.py       # Configuration loading & validation
    +-- order_executor.py      # FAK order execution with retry
    +-- hedge_manager.py       # GTD hedge order management
    +-- market_finder.py       # Gamma API market discovery
    +-- position_tracker.py    # Position & PnL tracking
    +-- auto_redeemer.py       # On-chain position redemption
    +-- telegram_notifier.py   # Telegram alerts & charts
    +-- user_websocket.py      # User channel WebSocket
    +-- websocket_client.py    # Market data WebSocket
    +-- signal_generator.py    # (Legacy, unused)
    +-- realtime_dashboard.py  # (Legacy, unused)
```

### Log Contents

| Log File           | Contents                                                            |
|--------------------|---------------------------------------------------------------------|
| bot.log            | All events: connections, market changes, errors, BTC ticks, anchors |
| signals.log        | Full indicator snapshot at each trade + market end with PnL and DD  |
| orders.log         | Detailed order execution: prices, retries, fills, rejections        |
| trading_log.json   | Persistent trade array with entry/exit, PnL, drawdown, win/loss    |

### trading_log.json Structure

```json
{
  "trades": [
    {
      "market_slug": "btc-updown-15m-1770831900",
      "token_name": "UP",
      "entry_price": 0.81,
      "exit_price": 0.03,
      "contracts": 64,
      "pnl": -51.84,
      "won": false,
      "timestamp": 1770832790.165,
      "max_drawdown_abs": 0.05,
      "max_drawdown_pct": 6.17
    }
  ],
  "markets_seen": 27
}
```
