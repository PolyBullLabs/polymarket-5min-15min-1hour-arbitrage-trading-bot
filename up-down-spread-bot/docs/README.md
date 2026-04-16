# Meridian — Polymarket Multi-Asset Crypto Desk (Complete Guide)

**Meridian** is the product name for this Python system: it trades **Polymarket 5- or 15-minute** crypto Up/Down markets for **BTC, ETH, SOL, and XRP** in parallel, using a **late-window entry** model (implementation: **Late Entry V3** / `late_v3`).

| Suite | [github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot) · [@terauss](https://t.me/terauss) · [Top-level README](../../README.md) |

**Educational use:** This guide explains **mechanics**, **risk**, and **configuration**. It is **not** financial advice. **No edge is guaranteed.**

---

## Table of Contents

1. [What Is This Bot?](#1-what-is-this-bot)
2. [How Polymarket 15-Minute Markets Work](#2-how-polymarket-15-minute-markets-work)
3. [How to Run the Bot (Step by Step)](#3-how-to-run-the-bot-step-by-step)
4. [Strategy: Late Entry V3 (Detailed)](#4-strategy-late-entry-v3-detailed)
5. [Exit Mechanisms (Detailed)](#5-exit-mechanisms-detailed)
6. [Order Execution (Detailed)](#6-order-execution-detailed)
7. [Data Feed & WebSocket](#7-data-feed--websocket)
8. [Configuration Reference](#8-configuration-reference)
9. [Environment Variables Reference](#9-environment-variables-reference)
10. [Dashboard & Terminal UI](#10-dashboard--terminal-ui)
11. [Web Dashboard (Browser)](#11-web-dashboard-browser)
12. [Telegram Integration](#12-telegram-integration)
13. [Safety Features](#13-safety-features)
14. [Project Structure](#14-project-structure)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What Is This Bot?

**Meridian** runs **four parallel traders** — one for each coin (BTC, ETH, SOL, XRP) — sharing a single Polygon wallet. Each trader independently watches its own Polymarket 15-minute prediction market and makes buy/sell decisions.

**What it trades:** Conditional outcome tokens (UP vs DOWN) on Polymarket markets with slugs like `btc-updown-15m-1711234500`.

**Core idea:** Wait until the last 4 minutes of a 15-minute market window, identify which side (UP or DOWN) the market favors, and buy the favorite. Then hold until the market resolves (and collect winnings) or exit early if the position turns bad.

---

## 2. How Polymarket 15-Minute Markets Work

Polymarket offers crypto prediction markets that resolve every 15 minutes:

- A new market opens every 15 minutes (aligned to epoch: 00, 15, 30, 45 past the hour).
- Each market has two outcomes: **UP** (price goes up) and **DOWN** (price goes down).
- Each outcome token trades between $0.00 and $1.00.
- When the market resolves, the winning token pays **$1.00** and the losing token pays **$0.00**.

**Example timeline:**

```
12:00 ─── Market opens: "Will BTC go up in the next 15 min?"
         UP ask: $0.50, DOWN ask: $0.50 (no consensus yet)
         ...
12:11 ─── Late Entry window starts (4 min before close)
         UP ask: $0.72, DOWN ask: $0.33 (market thinks UP)
         Bot buys 10 UP tokens at $0.72 → cost = $7.20
         ...
12:15 ─── Market resolves
         BTC went up → UP wins → 10 tokens x $1.00 = $10.00
         Profit = $10.00 - $7.20 = $2.80
```

---

## 3. How to Run the Bot (Step by Step)

### Prerequisites

- Python 3.10 or higher
- A Polygon wallet with **USDC (Bridged)** — not USDC.e (Native)
- A small amount of **POL/MATIC** for gas fees
- Polymarket API credentials (API key, secret, passphrase)
- A VPN if you're in a geo-restricted region

### Step 1: Clone the Repository

```bash
git clone https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot.git
cd polymakret-5min-15min-1hour-arbitrage-bot/up-down-spread-bot
```

### Step 2: Create a Virtual Environment

```bash
# Create
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

```bash
# Copy the example file
cp .env.example .env       # Linux/macOS
copy .env.example .env     # Windows
```

Open `.env` and fill in your credentials:

```env
# REQUIRED — your Polygon wallet private key
PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE

# Polygon network
RPC_URL=https://polygon-rpc.com
CHAIN_ID=137

# REQUIRED — Polymarket API credentials
CLOB_HOST=https://clob.polymarket.com
POLYMARKET_API_KEY=your_api_key
POLYMARKET_API_SECRET=your_api_secret
POLYMARKET_API_PASSPHRASE=your_api_passphrase

# OPTIONAL — Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Step 5: Set Up Configuration

```bash
# Copy the example config
cp config/config.example.json config/config.json       # Linux/macOS
copy config\config.example.json config\config.json     # Windows
```

Open `config/config.json` and review/adjust settings. The most important setting for first-time users:

```json
{
  "safety": {
    "dry_run": true    // <-- Keep this TRUE to test without real money
  }
}
```

### Step 6: Run the Bot

```bash
cd src
python main.py
```

With the **browser dashboard** (settings editor + live analytics on **http://127.0.0.1:5050**):

```bash
cd src
python main.py --web
```

The bot will:
1. Validate configuration and sizing formulas
2. Connect to Polymarket WebSocket for live orderbook data
3. Start the dashboard in your terminal
4. Begin monitoring markets and trading when conditions are met

### Step 7: Switch to Live Trading (When Ready)

Once you've verified the bot works correctly in dry-run mode:

1. Edit `config/config.json`
2. Change `"dry_run": true` to `"dry_run": false`
3. Restart the bot

---

## 4. Strategy: Late Entry V3 (Detailed)

The Late Entry V3 strategy is a **momentum-following, time-constrained** strategy. It only enters positions near market expiry, betting on the **crowd favorite** (the side the market already leans toward).

### Why "Late Entry"?

By waiting until the last 4 minutes, the bot:
- Gets a clearer signal about which side will win (higher confidence)
- Reduces time exposed to risk
- Avoids paying inflated prices during the middle of the market when outcomes are uncertain

### Entry Decision Flow (Step by Step)

Here is exactly what happens every time the bot evaluates whether to buy:

#### Step 1: Check Time Window

```
Is seconds_till_end > 0 AND seconds_till_end <= 240?
  YES → continue
  NO  → skip (too early or market already closed)
```

The bot only trades in the **last 240 seconds** (4 minutes) of each 15-minute window.

**Example:** Market closes at 12:15:00. Entry window is 12:11:00 to 12:15:00.

#### Step 2: Check Entry Frequency

```
Has it been at least 7 seconds since last entry in this market?
  YES → continue
  NO  → skip (too soon, wait)
```

This prevents the bot from spamming orders. Default: one entry attempt per 7 seconds per market.

#### Step 3: Calculate Spread

```
spread = up_ask + down_ask
Is spread <= 1.05 AND spread > 0?
  YES → continue
  NO  → skip (spread too wide, orderbook unreliable)
```

**Example:**
- UP ask = $0.72, DOWN ask = $0.30 → spread = 1.02 (good)
- UP ask = $0.80, DOWN ask = $0.35 → spread = 1.15 (too wide, skip)

In a healthy market, the sum of UP and DOWN asks is close to $1.00. A spread much above $1.05 means the orderbook is thin or stale.

#### Step 4: Calculate Confidence

```
confidence = |up_ask - down_ask|
Is confidence >= 0.30?
  YES → continue
  NO  → skip (not enough market consensus)
```

**Example:**
- UP ask = $0.72, DOWN ask = $0.30 → confidence = 0.42 (good, market clearly favors UP)
- UP ask = $0.55, DOWN ask = $0.48 → confidence = 0.07 (too close, skip)

A confidence of 0.30 means the market prices one side at least 30 cents higher than the other — a strong lean.

#### Step 5: Identify the Favorite

```
If up_ask > down_ask → favorite = UP, price = up_ask
If down_ask > up_ask → favorite = DOWN, price = down_ask
```

The bot always buys the side with the **higher ask price** — the side the market consensus believes will win.

#### Step 6: Check Price Cap

```
Is favorite_price <= 0.92?
  YES → continue
  NO  → skip (too expensive, risk/reward ratio too poor)
```

**Example:**
- UP ask = $0.88 → buy (still profitable if wins: $1.00 - $0.88 = $0.12 profit per token)
- UP ask = $0.95 → skip (only $0.05 potential profit, not worth the risk)

#### Step 7: Check Investment Cap

```
Is total_invested_in_this_market < $300?
  YES → continue
  NO  → skip (maximum investment per market reached)
```

This prevents over-concentration in a single market.

#### Step 8: Calculate Position Size (Contracts)

The number of contracts depends on how much time is left:

| Time Remaining | Contracts |
|---------------|-----------|
| > 180 seconds | 8 contracts |
| > 120 seconds | 10 contracts |
| <= 120 seconds | 12 contracts |

**Why increase size later?** Closer to expiry, the prices are more "settled" and the signal is stronger, so the bot takes larger positions.

**Example:**
- 200 seconds left, UP ask = $0.72 → Buy 8 UP contracts → cost = 8 x $0.72 = $5.76
- 100 seconds left, UP ask = $0.78 → Buy 12 UP contracts → cost = 12 x $0.78 = $9.36

### Complete Entry Example

```
Market: btc-updown-15m-1711234500 (closes at 12:15:00)
Time: 12:12:30 (150 seconds remaining)

Orderbook:
  UP  ask: $0.72
  DOWN ask: $0.30

Step 1: 150s remaining, within [0, 240] → PASS
Step 2: Last entry was 10s ago, >= 7s → PASS
Step 3: Spread = 0.72 + 0.30 = 1.02 <= 1.05 → PASS
Step 4: Confidence = |0.72 - 0.30| = 0.42 >= 0.30 → PASS
Step 5: Favorite = UP (0.72 > 0.30), price = $0.72
Step 6: Price $0.72 <= $0.92 → PASS
Step 7: Total invested = $5.76 < $300 → PASS
Step 8: 150s remaining (> 120s) → 10 contracts

SIGNAL: BUY 10 UP contracts at $0.72
Cost: 10 x $0.72 = $7.20
```

---

## 5. Exit Mechanisms (Detailed)

There are three ways the bot exits a position:

### Exit 1: Natural Resolution (Hold to Expiry)

This is the default. If no stop-loss or flip-stop triggers, the bot holds until the market resolves:

- **Winning side**: Tokens pay $1.00 each. The bot redeems them automatically.
- **Losing side**: Tokens become worthless ($0.00).

**Example:**
```
Bought: 10 UP contracts at $0.72 → cost $7.20
Market resolves: BTC went UP
Payout: 10 x $1.00 = $10.00
Profit: $10.00 - $7.20 = $2.80 (+38.9%)
```

```
Bought: 10 UP contracts at $0.72 → cost $7.20
Market resolves: BTC went DOWN
Payout: 10 x $0.00 = $0.00
Loss: $0.00 - $7.20 = -$7.20 (-100%)
```

### Exit 2: Per-Coin Stop-Loss

Each coin has its own stop-loss threshold. When the **unrealized PnL** (mark-to-market loss) reaches the threshold, the bot immediately sells.

**How unrealized PnL is calculated:**

```
total_value = (up_shares x up_ask) + (down_shares x down_ask)
unrealized_pnl = total_value - total_invested
```

**Two stop-loss types:**

| Type | Config | Triggers When |
|------|--------|---------------|
| **Fixed** | `"type": "fixed", "value": -12.0` | `unrealized_pnl <= -$12.00` |
| **Percent** | `"type": "percent", "value": 15` | `unrealized_pnl <= -(15% of total_invested)` |

**Default config:** BTC/ETH/SOL use fixed -$12, XRP uses fixed -$11.

**Example (Fixed Stop-Loss):**
```
Position: 15 UP contracts bought at avg $0.70 → total invested = $10.50
Current: UP ask = $0.40, DOWN ask = $0.55
Value: 15 x $0.40 + 0 x $0.55 = $6.00
Unrealized PnL: $6.00 - $10.50 = -$4.50

Stop-loss threshold: -$12.00
-$4.50 > -$12.00 → no trigger yet

Later... UP ask drops to $0.15:
Value: 15 x $0.15 = $2.25
Unrealized PnL: $2.25 - $10.50 = -$8.25

-$8.25 > -$12.00 → still no trigger

Later... UP ask drops to $0.05:
Value: 15 x $0.05 = $0.75
Unrealized PnL: $0.75 - $10.50 = -$9.75

-$9.75 > -$12.00 → still no trigger

(This shows that with small position sizes like $10.50,
 a $12 fixed stop-loss may never trigger before expiry)
```

**Example (Percent Stop-Loss):**
```
Position: 20 UP contracts bought at avg $0.70 → total invested = $14.00
Stop-loss: 15% → threshold = -(14.00 x 0.15) = -$2.10

UP ask drops to $0.60:
Value: 20 x $0.60 = $12.00
Unrealized PnL: $12.00 - $14.00 = -$2.00
-$2.00 > -$2.10 → no trigger

UP ask drops to $0.59:
Value: 20 x $0.59 = $11.80
Unrealized PnL: $11.80 - $14.00 = -$2.20
-$2.20 <= -$2.10 → STOP-LOSS TRIGGERED → sell all UP tokens
```

### Exit 3: Flip-Stop (Price Reversal Protection)

The flip-stop detects when the market sentiment has **reversed** against your position. If you hold UP tokens and the UP price drops below the flip threshold, the bot sells immediately.

**How it works:**

```
our_side = whichever side we hold more contracts of
our_price = current ask price of our side

If our_price <= flip_stop_price (default $0.48) → TRIGGER
```

**Why $0.48?** If UP was trading at $0.72 when you bought and now it's at $0.48, the market no longer considers UP the favorite. The sentiment has flipped.

**Example:**
```
Bought: 10 UP contracts at $0.72

Later: UP ask drops to $0.52, DOWN ask rises to $0.50
Our price ($0.52) > $0.48 → no trigger

Later: UP ask drops to $0.47, DOWN ask rises to $0.55
Our price ($0.47) <= $0.48 → FLIP-STOP TRIGGERED
→ Bot sells all UP tokens immediately
→ Saves remaining value instead of riding to $0.00
```

### Price Validation Before Any Exit

Before checking stop-loss or flip-stop, the bot validates that prices are reliable:

1. Both UP and DOWN ask prices must be **fresh** (updated within last 2 seconds)
2. UP and DOWN timestamps must be **within 2 seconds** of each other
3. `up_ask + down_ask` must be between **$0.95 and $1.15**

If any check fails, exit decisions are skipped for that tick (to avoid selling on stale/bad data).

---

## 6. Order Execution (Detailed)

### Buying: FAK Orders (Fill-And-Kill)

FAK (Fill-And-Kill) orders try to fill immediately against existing orderbook liquidity. Whatever doesn't fill is cancelled.

**Buy flow:**

1. Calculate aggressive price: `ask_price x 1.05` (5% above ask for slippage tolerance)
2. Submit FAK order for the full contract amount
3. If partially filled, submit another FAK for the remaining amount
4. Repeat up to 3 attempts (configurable)
5. Stop when >= 98% of requested contracts are filled, or remaining value < $1.00

**Example:**
```
Want: 10 contracts at ask $0.72
Aggressive price: $0.72 x 1.05 = $0.756 → rounded up to $0.76

Attempt 1: FAK order for 10 contracts at $0.76
  Result: 7 filled at $0.72-$0.74
  Remaining: 3 contracts

Attempt 2: FAK order for 3 contracts at $0.76
  Result: 3 filled at $0.73
  Remaining: 0

Total: 10/10 filled (100%) → done
```

### Selling: FOK Chunked (Fill-Or-Kill in Chunks)

When the bot needs to exit (stop-loss, flip-stop, or market close), it sells in chunks:

1. Read actual ERC-20 token balance from the blockchain
2. Split into chunks of 50 contracts each
3. Each chunk: FOK order at $0.01 (sell at any price)
4. Up to 5 retries per chunk if it fails
5. After all chunks: sweep any remaining dust

**Why $0.01?** This is a "market sell" — accept any price to exit quickly. In an emergency exit, speed matters more than getting the best price.

**Example:**
```
Position: 120 UP tokens to sell

Chunk 1: FOK sell 50 at $0.01 → filled
Chunk 2: FOK sell 50 at $0.01 → filled
Chunk 3: FOK sell 20 at $0.01 → filled
Sweep: 0 remaining → done

Total sold: 120 tokens
```

### Dust Sweeping

After selling, tiny fractional balances might remain (e.g., 0.3 tokens). The bot runs a multi-stage sweep:

1. **FOK sweep**: Try up to 3 times
2. **FAK fallback**: Try up to 3 times
3. **GTC order**: Place a Good-Till-Cancelled order at $0.01
4. **Delayed sweep**: Wait 1 second, re-check balance, try FOK/FAK again

### Automatic Redemption

After a market resolves, winning tokens can be redeemed for $1.00 each. The bot runs a background thread:

- **First check**: 8 minutes after startup
- **Subsequent checks**: Every 5 minutes
- Queries Polymarket API for redeemable positions
- Redeems automatically with configurable gas settings

---

## 7. Data Feed & WebSocket

### How Market Data Flows

```
Polymarket Gamma API               Polymarket WebSocket
(REST - market metadata)           (Realtime orderbook)
        │                                  │
        ▼                                  ▼
   _fetch_tokens()                  on_message()
   Gets token IDs,                  Parses "book" events,
   condition IDs                    extracts best ask/bid
        │                                  │
        └────────────┬─────────────────────┘
                     ▼
              DataFeed object
              (up_ask, down_ask, timestamps)
                     │
                     ▼
            on_price_update callback
            (called on every orderbook update)
                     │
                     ▼
         Strategy → Entry/Exit decisions
```

### Market Slot Calculation

Markets align to fixed-length epoch boundaries. Length is **`data_sources.polymarket.market_interval_sec`** (default **900** = 15 minutes; **300** = 5 minutes):

```
interval = 900   # or 300 for 5m
current_time = 1711234567 (Unix timestamp)
slot = (current_time // interval) * interval
market_slug = "btc-updown-15m-<slot>"   # or "btc-updown-5m-<slot>"
market_end = slot + interval
```

### WebSocket Reconnection

When a market expires, the bot automatically:
1. Calculates the next slot for the configured interval
2. Fetches new token IDs from Gamma API
3. Reconnects WebSocket with new asset IDs
4. Timer resets for the new market window

---

## 8. Configuration Reference

All settings live in `config/config.json`. Here is every section:

### `safety` — Risk Controls

| Key | Default | Description |
|-----|---------|-------------|
| `dry_run` | `true` | If true, simulates trades without real money |
| `max_order_size_usd` | `150` | Maximum single order size (contracts x price) |
| `max_orders_per_minute` | `100` | Rate limit for orders |
| `max_total_investment` | `1000` | Maximum cumulative investment per market slug |

### `trading` — Coin Enable/Disable

| Key | Default | Description |
|-----|---------|-------------|
| `btc.enabled` | `true` | Enable BTC trading |
| `eth.enabled` | `true` | Enable ETH trading |
| `sol.enabled` | `true` | Enable SOL trading |
| `xrp.enabled` | `false` | Enable XRP trading (disabled by default — less liquid) |

### `strategy` — Entry Parameters

| Key | Default | Description |
|-----|---------|-------------|
| `name` | `late_entry_v3` | Strategy identifier |
| `entry_window_sec` | `240` | Only enter in last N seconds of market |
| `entry_frequency_sec` | `7` | Minimum seconds between entries in same market |
| `min_confidence` | `0.30` | Minimum \|up_ask - down_ask\| to enter |
| `max_spread` | `1.05` | Maximum up_ask + down_ask allowed |
| `price_max` | `0.92` | Maximum price to pay for favorite side |
| `max_investment_per_market` | `300` | Maximum USD invested per market |
| `sizing.above_180_sec` | `8` | Contracts when > 180s remaining |
| `sizing.above_120_sec` | `10` | Contracts when > 120s remaining |
| `sizing.below_120_sec` | `12` | Contracts when <= 120s remaining |

### `exit.flip_stop` — Flip-Stop Settings

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable flip-stop exit |
| `price_threshold` | `0.48` | Sell when our side's ask drops to this |
| `check_realtime` | `true` | Check on every price update |

### `exit.stop_loss` — Per-Coin Stop-Loss

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable stop-loss |
| `per_coin.btc.type` | `fixed` | `fixed` = dollar amount, `percent` = % of invested |
| `per_coin.btc.value` | `-12.0` | Threshold (negative = loss amount) |
| `per_coin.eth.value` | `-12.0` | ETH stop-loss threshold |
| `per_coin.sol.value` | `-12.0` | SOL stop-loss threshold |
| `per_coin.xrp.value` | `-11.0` | XRP stop-loss threshold |

### `execution.buy` — Buy Order Settings

| Key | Default | Description |
|-----|---------|-------------|
| `order_type` | `FAK` | Fill-And-Kill order type |
| `max_fak_attempts` | `3` | Retry attempts per buy |
| `retry_delay_sec` | `0.3` | Delay between retries |
| `min_order_usd` | `1.0` | Minimum remaining order value to continue |
| `target_fill_percent` | `98.0` | Stop retrying when this % is filled |

### `execution.sell` — Sell Order Settings

| Key | Default | Description |
|-----|---------|-------------|
| `strategy` | `FOK_CHUNKED` | Sell in FOK chunks |
| `chunk_size` | `50` | Contracts per chunk |
| `chunk_delay_sec` | `0.1` | Delay between chunks |
| `max_chunk_retries` | `5` | Retries per chunk |
| `price` | `0.01` | Sell price (market sell) |
| `min_dust_threshold` | `0.1` | Ignore balances below this |
| `sweep_max_attempts` | `3` | FOK sweep retry count |
| `sweep_enable_fallback` | `true` | Enable FAK/GTC fallback |
| `delayed_sweep_enabled` | `true` | Re-check balance after delay |
| `delayed_sweep_delay_sec` | `1` | Seconds to wait before delayed sweep |

### `execution.redeem` — Redemption Settings

| Key | Default | Description |
|-----|---------|-------------|
| `startup_check_delay_sec` | `60` | Wait before first redeem check |
| `first_check_delay_sec` | `480` | First regular check (8 min after start) |
| `check_interval_sec` | `300` | Check every 5 minutes after that |
| `sizeThreshold` | `0.1` | Minimum token balance to redeem |
| `gas_limit` | `500000` | Gas limit for redeem transactions |
| `gas_price_multiplier` | `1.5` | Gas price multiplier |

### `execution.rpc_config` — Polygon RPC

| Key | Default | Description |
|-----|---------|-------------|
| `endpoints` | `["https://polygon-rpc.com"]` | RPC endpoint(s) |
| `retry_attempts` | `10` | Max retries for RPC calls |
| `enable_parallel_requests` | `true` | Query multiple endpoints in parallel |

### `data_sources.polymarket` — Market window length

| Key | Default | Description |
|-----|---------|-------------|
| `gamma_api` | `https://gamma-api.polymarket.com` | Gamma REST base URL |
| `ws_url` | `wss://ws-subscriptions-clob.polymarket.com/ws/market` | Orderbook WebSocket |
| **`market_window`** | **`"15m"`** | **Choose here:** `"5m"` = 5-minute Up/Down (`{coin}-updown-5m-{slot}`), `"15m"` = 15-minute (`{coin}-updown-15m-{slot}`). |
| `market_interval_sec` | (derived) | Set automatically from `market_window` (300 or 900). You can set this instead of `market_window` if you need raw seconds; if both are set, **`market_window` wins**. |

For **5-minute** markets, set `"market_window": "5m"` and tune `strategy.entry_window_sec` if needed (for example **90–120** seconds). The strategy scales time-based sizing tiers to shorter windows automatically (e.g. 60s/40s for 5m).

### `display` — Terminal Dashboard

| Key | Default | Description |
|-----|---------|-------------|
| `width` | `160` | Dashboard width in characters |
| `update_interval` | `1` | Dashboard refresh interval (seconds) |

### `logging` — Log File Paths

| Key | Default | Description |
|-----|---------|-------------|
| `trades_file` | `logs/trades.jsonl` | Trade log (JSON Lines) |
| `session_file` | `logs/session.json` | Session state file |

---

## 9. Environment Variables Reference

All environment variables are set in the `.env` file at the project root.

### Required for Live Trading

| Variable | Example | Description |
|----------|---------|-------------|
| `PRIVATE_KEY` | `0xabcdef...` | Polygon wallet private key (64 hex chars after 0x) |
| `RPC_URL` | `https://polygon-rpc.com` | Polygon RPC endpoint |
| `CHAIN_ID` | `137` | Polygon chain ID (always 137) |
| `CLOB_HOST` | `https://clob.polymarket.com` | Polymarket CLOB API host |
| `POLYMARKET_API_KEY` | `abc-123-...` | Your Polymarket API key |
| `POLYMARKET_API_SECRET` | `base64string==` | Your Polymarket API secret |
| `POLYMARKET_API_PASSPHRASE` | `passphrase` | Your Polymarket API passphrase |

### Optional

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat ID to receive messages |

### How to Get Polymarket API Credentials

1. Go to [Polymarket](https://polymarket.com) and log in
2. Navigate to your account settings
3. Generate API credentials (key, secret, passphrase)
4. Your private key is the Polygon wallet key linked to your Polymarket account

---

## 10. Dashboard & Terminal UI

When running, the bot displays a live terminal dashboard (refreshes every second):

```
═══════════════════════════════════════════════════════════════════
 Runtime: 00:45:23  |  BTC | ETH | SOL | XRP  (Polymarket orderbooks)
═══════════════════════════════════════════════════════════════════

 Strategy: late_v3
 Balance: $487.32  |  Trades: 12  |  W/L: 8/4  |  Win Rate: 66.7%

 BTC  [15m-1711234500]  Time: 142s   UP: $0.72  DN: $0.30  Fav: UP  Conf: 0.42
      Position: 10 UP @ $0.72  |  PnL: +$1.20  |  Max DD: -$0.80
      If UP wins: +$2.80  |  If DN wins: -$7.20

 ETH  [15m-1711234500]  Time: 142s   UP: $0.65  DN: $0.38  Fav: UP  Conf: 0.27
      (waiting for confidence >= 0.30)

 SOL  [15m-1711234500]  Time: 142s   UP: $0.80  DN: $0.22  Fav: UP  Conf: 0.58
      Position: 12 UP @ $0.78  |  PnL: +$0.24  |  Max DD: -$0.60

 XRP  [disabled]

 Recent trades:
   btc-updown-15m-1711233600  UP  WIN   +$3.40
   sol-updown-15m-1711233600  UP  LOSS  -$6.20

 [M] Manual Redeem All  |  [Ctrl+C] Stop
═══════════════════════════════════════════════════════════════════
```

**What each line shows:**
- **Per coin:** Market ID suffix, time remaining, UP/DOWN asks, favorite side, confidence score
- **Position:** Number of contracts, average entry price, current unrealized PnL, maximum drawdown
- **Scenarios:** What happens if UP wins vs if DOWN wins (helps you understand your exposure)
- **Recent trades:** Last closed trades with win/loss result and PnL

---

## 11. Web Dashboard (Browser)

Install dependencies (`flask` is listed in `requirements.txt`). From the `src` directory, start the bot with the web UI enabled:

```bash
cd src
python main.py --web
```

Open **http://127.0.0.1:5050/** (or `--web-port` / `--web-host` as needed).

| Feature | Description |
|--------|-------------|
| **Live analytics** | Session uptime, mode (dry run / live), wallet balance, total PnL, ROI, per-coin orderbook (UP/DN asks, favorite, confidence), open position with unrealized PnL and scenario PnL |
| **Recent trades** | Last closed trades across strategies |
| **Settings** | Load and edit `config/config.json` in the browser; **save writes the file** — **restart the bot** to apply changes |
| **Request stop** | Sends the same graceful stop as **Ctrl+C** (shutdown handler saves positions) |

**Security:** By default the server binds to `127.0.0.1` only. Use `--web-host 0.0.0.0` only on trusted networks (add a reverse proxy and authentication if exposing to the internet).

**API (for your own tools):** `GET /api/status` (JSON snapshot), `GET/POST /api/config`, `POST /api/bot/stop`, `GET /api/health`.

You can also run the Flask app alone for a read-only view when `logs/bot_state.json` is being updated: `cd src` then `python -m web_dashboard.server` (snapshot appears after the bot has run with `--web` at least once).

---

## 12. Telegram Integration

If configured, the bot sends notifications and accepts commands via Telegram.

### Commands

| Command | Description |
|---------|-------------|
| `/chart` or `/pnl` | Generate and send a PnL chart image |
| `/b` or `/balance` | Show wallet USDC and POL balance |
| `/t` or `/positions` | Show all active positions |
| `/r` or `/redeem` | Manually trigger redemption of resolved markets |
| `/off` or `/stop` | Emergency shutdown (asks for confirmation) |
| `/help` | List all available commands |

### Notifications Sent Automatically

- Trade entries (coin, side, contracts, price)
- Trade exits (reason, PnL)
- Stop-loss and flip-stop triggers
- Market resolution results
- Error alerts

---

## 13. Safety Features

### Dry Run Mode

When `safety.dry_run` is `true`:
- All buy orders are **simulated** (no real transactions)
- All sell orders are **simulated**
- The bot behaves identically otherwise (prices, signals, dashboard)
- Use this to verify the bot works before risking real money

### Order Size Limits

- **Per order:** `max_order_size_usd` (default $150) — rejects any single order above this
- **Per market:** `max_total_investment` (default $1000) — tracks cumulative investment per market slug
- **Per strategy:** `max_investment_per_market` (default $300) — checked by the strategy before signaling

### Rate Limiting

- Maximum `max_orders_per_minute` (default 100) orders per minute
- Entry frequency: one signal per 7 seconds per market (prevents order spam)

### Emergency Stop

- Press **Ctrl+C** to gracefully shut down (saves positions as emergency saves)
- Use `/off` in Telegram for remote shutdown
- `SafetyGuard.activate_emergency_stop()` blocks all future orders

### Price Validation

Before any exit decision, prices are validated:
- Must be **fresh** (< 2 seconds old)
- UP and DOWN timestamps must be **synchronized** (< 2 seconds apart)
- Sum of asks must be **reasonable** (between $0.95 and $1.15)

This prevents the bot from making exit decisions on stale or corrupted data.

---

## 14. Project Structure

```
up-down-spread-bot/
├── src/
│   ├── main.py                    # Entry point, main loop, callbacks, config loading
│   ├── market_config.py           # market_window "5m"/"15m" → market_interval_sec
│   ├── strategy.py                # Late Entry V3 strategy logic
│   ├── trader.py                  # Per-coin position management and PnL tracking
│   ├── multi_trader.py            # Manages multiple Trader instances (one per coin)
│   ├── data_feed.py               # Gamma API + WebSocket orderbook feed
│   ├── order_executor.py          # CLOB client: FAK buys, FOK sells, sweeps, redeems
│   ├── polymarket_api.py          # Gamma API helper for market resolution
│   ├── safety_guard.py            # Dry run, order limits, rate limiting, emergency stop
│   ├── position_tracker.py        # Position model (for WebSocket user channel)
│   ├── trade_logger.py            # Logs trades to logs/trades.log
│   ├── dashboard_multi_ab.py      # Terminal UI rendering
│   ├── telegram_notifier.py       # Telegram bot notifications and commands
│   ├── simple_redeem_collector.py # Background thread for automatic redemption
│   ├── pnl_chart_generator.py     # Matplotlib PnL chart generation
│   ├── keyboard_listener.py       # Non-blocking keyboard input (cross-platform)
│   ├── web_dashboard_state.py     # Thread-safe snapshot for browser dashboard
│   └── web_dashboard/             # Flask app: API + static UI (python main.py --web)
├── config/
│   ├── config.json                # Your trading configuration (create from example)
│   └── config.example.json        # Example configuration template
├── logs/                          # Log files (created automatically)
│   ├── trades.jsonl               # Trade history (JSON Lines)
│   ├── safety.log                 # Safety guard events
│   ├── bot_state.json             # Written when using --web (optional monitoring file)
│   └── session.json               # Session state
├── docs/                          # Documentation
│   └── README.md                  # This file
├── requirements.txt               # Python dependencies
├── .env                           # Your environment variables (create from example)
├── .env.example                   # Example environment template
├── .gitignore                     # Git ignore rules
└── README.md                      # Project overview
```

---

## 15. Troubleshooting

### `ModuleNotFoundError: No module named 'termios'`

This happens on Windows. The `keyboard_listener.py` uses Unix-only modules. Make sure you have the latest version which includes Windows support via `msvcrt`.

### `FileNotFoundError: config/config.json`

You need to create the config file from the example:

```bash
cp config/config.example.json config/config.json     # Linux/macOS
copy config\config.example.json config\config.json   # Windows
```

### `UnicodeEncodeError: 'charmap' codec can't encode character`

This happens on Windows when writing emoji characters to log files. Make sure all `open()` calls in `safety_guard.py` use `encoding='utf-8'`.

### "Rate limit exceeded"

The public Polygon RPC has rate limits. Use a private RPC:

```env
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY
```

### "Invalid signature"

1. Verify your API credentials are correct in `.env`
2. Make sure the private key matches your Polymarket account
3. Regenerate API credentials on Polymarket if needed

### WebSocket Disconnects

The bot auto-reconnects between market windows. If connections drop frequently:
1. Check your internet connection
2. Try a VPN
3. Change DNS to `1.1.1.1` or `8.8.8.8`

### Positions Not Redeeming

1. Oracle resolution takes 1-2 minutes after market close
2. Use `/r` in Telegram to manually trigger
3. Check `logs/` directory for error details
4. The bot checks for redeemable positions every 5 minutes automatically

---

## Disclaimer

This software is for **educational purposes only**. Trading on prediction markets involves **substantial risk of loss**. Past performance **does not** indicate future results. Use at your own risk and never trade with money you cannot afford to lose. **Extended strategies** (martingale / anti-martingale / Fibonacci sizing, full TA stacks, Bayesian edge, Avellaneda–Stoikov-style inventory, Kelly, Monte Carlo, and related) are offered **separately**—see the [repository README](../../README.md) and Telegram [@terauss](https://t.me/terauss).
