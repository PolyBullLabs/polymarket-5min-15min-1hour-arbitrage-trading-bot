# BTC 15-Minute Polymarket Bot — Full Beginner Guide

**Suite:** [PolyBullLabs — polymakret-5min-15min-1hour-arbitrage-bot](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot) · **Telegram:** [@terauss](https://t.me/terauss) · **Parent overview:** [`../README.md`](../README.md)

This document walks you from **zero to running**, explains the **trading strategy** with **numbers**, and lists **every important parameter** with **examples**.  
Shorter references: [`CONFIG.md`](../CONFIG.md) (parameter list), [`PROJECT_LOGIC.md`](../PROJECT_LOGIC.md) (implementation detail).

---

## Table of contents

1. [What you are trading](#1-what-you-are-trading)
2. [Trading strategy (logic + formulas)](#2-trading-strategy-logic--formulas)
3. [Prerequisites checklist](#3-prerequisites-checklist)
4. [Environment setup — Windows](#4-environment-setup--windows)
5. [Environment setup — Linux / macOS](#5-environment-setup--linux--macos)
6. [Get the project and install dependencies](#6-get-the-project-and-install-dependencies)
7. [Configure `.env` (secrets)](#7-configure-env-secrets)
8. [Configure `config.json` (strategy and execution)](#8-configure-configjson-strategy-and-execution)
9. [Run the bot](#9-run-the-bot)
10. [Optional: Telegram](#10-optional-telegram)
11. [Optional: P&amp;L chart](#11-optional-pnl-chart)
12. [Logs and files](#12-logs-and-files)
13. [Troubleshooting](#13-troubleshooting)
14. [Risk summary](#14-risk-summary)

---

## 1. What you are trading

### 1.1 The market

Polymarket lists **15-minute** BTC markets (slug pattern like `btc-updown-15m-<timestamp>`). Each market has two outcome tokens:

| Token | Pays if |
|--------|---------|
| **UP** | BTC finishes the window **above** the reference (market rules on Polymarket define the exact oracle) |
| **DOWN** | BTC finishes **below** |

In practice the bot reads **live token prices** from Polymarket (not a manual prediction). It buys the **favorite** — whichever side has the **higher** last traded price.

### 1.2 Payout math (simplified)

If you buy **N** contracts at price **P** (in dollars per contract, 0–1):

- **Cost** ≈ **N × P**
- If your side **wins**, each contract is worth **$1** → payout **N × $1**
- **Profit before fees** ≈ **N × (1 − P)** on a win; on a loss you lose the cost.

**Example (numbers only):**

- Buy **6** UP @ **$0.82** → cost **6 × 0.82 = $4.92**
- If UP wins → value **6 × $1 = $6.00** → gross profit **$6.00 − $4.92 = $1.08**

The bot does **not** guarantee profit; it automates entries when **its rules** are satisfied.

---

## 2. Trading strategy (logic + formulas)

### 2.1 Favorite

The bot compares **UP** and **DOWN** `last_price` (from the market WebSocket). The **favorite** is the side with the **higher** price. All deviation and momentum calculations below use the **favorite’s** trade history and price.

### 2.2 VWAP (volume-weighted average price)

Over the last **`vwap_window_sec`** seconds (e.g. **30**), take all trades on that token, then:

\[
\text{VWAP} = \frac{\sum (\text{price} \times \text{size})}{\sum \text{size}}
\]

**Example**

| Time | Price | Size |
|------|-------|------|
| T1 | 0.78 | 10 |
| T2 | 0.79 | 5 |

\[
\text{VWAP} = \frac{0.78 \times 10 + 0.79 \times 5}{10 + 5} = \frac{11.75}{15} \approx 0.7833
\]

### 2.3 Deviation (%)

Compare **last** traded price to VWAP:

\[
\text{Deviation (\%)} = \frac{\text{last\_price} - \text{VWAP}}{\text{VWAP}} \times 100
\]

**Example**

- Last price **0.82**, VWAP **0.78**  
- Deviation = \((0.82 - 0.78) / 0.78 × 100 ≈ 5.13\%\)

The bot requires deviation **strictly greater than** `min_deviation_pct` and **strictly less than** `max_deviation_pct` (see [§8.1](#81-strategy-block)).

### 2.4 Momentum (%)

Momentum uses a lookback of **`momentum_window_sec`** (e.g. **60**). The code takes trades whose timestamps fall in a **small band** around “now − 60s”, averages their prices, then compares **current** last price to that average:

\[
\text{Momentum (\%)} = \frac{\text{last\_price} - \text{avg\_price\_ago}}{\text{avg\_price\_ago}} \times 100
\]

If there are no trades in that window, momentum is **missing** (`None`) and the signal **cannot** fire.

**Important:** In code, momentum must be **> 5%** (not configurable in `config.json` today). So `momentum_window_sec` changes *how* momentum is measured, not the **5%** threshold.

**Example**

- Average price ~60s ago: **0.77**
- Current last price: **0.82**
- Momentum = \((0.82 - 0.77) / 0.77 × 100 ≈ 6.5\%\) → **passes** the &gt; 5% rule

### 2.5 Time window for entries (15 minutes = 900 seconds)

Each market lasts **900 seconds** from start to end.

- `min_elapsed_sec` — do **not** enter until at least this many seconds **after** the market started.  
  Elapsed = **900 − time_left** (seconds).

- `no_entry_before_end_sec` — do **not** enter if **time_left** ≤ this value (too close to expiry).

**Worked example** (matches `CONFIG.md`):

- `min_elapsed_sec = 530` → need elapsed **≥ 530**  
- `no_entry_before_end_sec = 335` → need time_left **> 335** → elapsed **< 565**

So entries are only possible when **530 ≤ elapsed &lt; 565** → about **35 seconds** per market (if all other filters pass).

| Variable | Value |
|----------|--------|
| `min_elapsed_sec` | 530 |
| `no_entry_before_end_sec` | 335 |
| Allowed elapsed | 530 … 564 |
| Allowed time_left | 336 … 370 |

If you widen the window (e.g. lower `min_elapsed_sec` or raise `no_entry_before_end_sec`), you get **more** opportunities and usually **more** risk.

### 2.6 Win rate table (`data/win_rate.csv`)

Rows are **price bands** (e.g. `0.75-0.79`), columns are **minutes** (`min_0` … `min_14`). The dashboard uses this to **display** a historical win rate for the current favorite price and time bin. It does **not** by itself block a trade in the main signal logic (the hard filters are price, time, deviation, momentum).

### 2.7 Entry checklist (all must pass)

| # | Rule | Typical config |
|---|------|----------------|
| 1 | Favorite price in `[min_price, max_price]` | e.g. 0.75–0.88 |
| 2 | `elapsed_sec ≥ min_elapsed_sec` | e.g. ≥ 530 |
| 3 | `min_deviation_pct < deviation < max_deviation_pct` | e.g. 3% &lt; dev &lt; 100% |
| 4 | Momentum **not** `None` and **> 5%** | fixed in code |
| 5 | `time_left > no_entry_before_end_sec` | e.g. &gt; 335 |

### 2.8 After a buy

1. **FAK** order: buy up to your size; unfilled part is cancelled.  
2. Optional **hedge** (if enabled): **GTD** limit on the **opposite** token at `hedge_price` (often **0.02**).  
3. Near market end, the bot **closes** the internal position for P&amp;L tracking using last prices.  
4. **Auto-redeem** (if enabled) periodically redeems winning positions on Polygon.

---

## 3. Prerequisites checklist

| Item | Why |
|------|-----|
| **Python 3.11+** (3.12 is fine) | Runs the bot |
| **pip / venv** | Install packages in isolation |
| **Polymarket account + USDC on Polygon** | Trading collateral |
| **Small amount of POL (MATIC)** | Gas for on-chain redemptions (if you use auto-redeem) |
| **CLOB API credentials** | key, secret, passphrase from Polymarket |
| **Wallet private key** (`0x…`) | Signs orders and redeem txs; **never share** |

---

## 4. Environment setup — Windows

### 4.1 Install Python

1. Download the installer from [https://www.python.org/downloads/](https://www.python.org/downloads/) (Windows 64-bit).
2. Run it. **Enable “Add Python to PATH”** (important).
3. Close and reopen **PowerShell** or **Command Prompt**.

### 4.2 Verify

```powershell
python --version
pip --version
```

You should see Python 3.11+ and pip. If `python` is not found, try `py` (Windows launcher):

```powershell
py --version
```

### 4.3 Git Bash / `sudo` / `apt`

This project is **not** installed with `sudo apt` on Windows. Use **Python for Windows** or **WSL** (Ubuntu) if you want Linux-style commands.

### 4.4 Execution policy (PowerShell venv)

If activation fails with “running scripts is disabled”:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try `.\venv\Scripts\Activate.ps1` again.

---

## 5. Environment setup — Linux / macOS

### 5.1 Linux (Debian/Ubuntu example)

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
python3 --version
```

### 5.2 macOS

Install Python 3 from [python.org](https://www.python.org/downloads/) or `brew install python`. Then:

```bash
python3 --version
```

---

## 6. Get the project and install dependencies

### 6.1 Go to the project folder

If you already have the folder (`btc-binary-VWAP-Momentum-bot`), **cd** into it:

```bash
cd "path/to/polymakret-5min-15min-1hour-arbitrage-bot/btc-binary-VWAP-Momentum-bot"
```

If you clone from git:

```bash
git clone https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot.git
cd polymakret-5min-15min-1hour-arbitrage-bot/btc-binary-VWAP-Momentum-bot
```

### 6.2 Create and activate a virtual environment

**Windows (PowerShell)**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
```

Your prompt should show `(venv)`.

### 6.3 Install Python packages

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Wait until it finishes without errors.

### 6.4 Quick sanity check

```bash
python -c "import rich, aiohttp, websockets; print('OK')"
```

If you see `OK`, dependencies are installed.

---

## 7. Configure `.env` (secrets)

### 7.1 Create `.env` from the example

**Windows**

```powershell
copy .env.example .env
```

**Linux / macOS**

```bash
cp .env.example .env
```

### 7.2 Fill each variable

| Variable | Required | Example / notes |
|----------|----------|-----------------|
| `PRIVATE_KEY` | **Yes** | `0x` + 64 hex chars. **Never** commit or share. |
| `SIGNATURE_TYPE` | **Yes** | `0` = EOA (normal wallet). `1` or `2` = proxy / magic — see Polymarket docs. |
| `FUNDER_ADDRESS` | If proxy | Your Polymarket proxy wallet address when `SIGNATURE_TYPE` is 1 or 2. |
| `POLY_API_KEY` | **Yes** | From CLOB API. |
| `POLY_API_SECRET` | **Yes** | From CLOB API. |
| `POLY_API_PASSPHRASE` | **Yes** | From CLOB API. |
| `RPC_URL` | Optional | Default `https://polygon-rpc.com`, Alchemy/Infura recommended for production. |
| `CHAIN_ID` | Optional | `137` for Polygon mainnet. |
| `CLOB_HOST` | Optional | Usually `https://clob.polymarket.com`. |
| `TELEGRAM_BOT_TOKEN` | Optional | From @BotFather. |
| `TELEGRAM_CHAT_ID` | Optional | Your numeric chat id (e.g. from @userinfobot). |

### 7.3 Where to get API keys

- Log in to Polymarket, open the **CLOB API** / developer settings, and create **API credentials** (key, secret, passphrase).  
- Official URL referenced in the repo: [https://clob.polymarket.com](https://clob.polymarket.com)

### 7.4 Example `.env` shape (fake values)

```env
PRIVATE_KEY=0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
SIGNATURE_TYPE=0
FUNDER_ADDRESS=

POLY_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
POLY_API_SECRET=your_secret_here
POLY_API_PASSPHRASE=your_passphrase_here

RPC_URL=https://polygon-rpc.com
CHAIN_ID=137
CLOB_HOST=https://clob.polymarket.com

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Save the file. **Confirm `.env` is gitignored** (do not commit).

---

## 8. Configure `config.json` (strategy and execution)

Edit **`config.json`** in the project root. Below: **what each block does**, **recommended ranges**, and **numeric examples**.

### 8.1 `strategy` block

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `min_price` | Minimum favorite token price to allow entry | `0.75` — ignore favorites below $0.75 |
| `max_price` | Maximum favorite token price | `0.88` — do not buy above $0.88 |
| `min_elapsed_sec` | Seconds after market open before entry | `530` — wait ~8.8 min |
| `min_deviation_pct` | Deviation must be **>** this | `3` — need more than 3% above VWAP |
| `max_deviation_pct` | Deviation must be **<** this | `100` — effectively no upper cap |
| `no_entry_before_end_sec` | Stop entering if `time_left ≤` this | `335` — no new entries in last ~5.6 min |
| `momentum_window_sec` | Seconds of history for momentum | `60` — compare to ~1 minute ago |
| `vwap_window_sec` | Seconds of trades for VWAP | `30` — short-term average |
| `win_rate_csv` | Path to CSV for dashboard win rate | `"data/win_rate.csv"` |

**Deviation example**

- VWAP (30s) = **0.78**, last = **0.80** → deviation ≈ **2.56%** → fails if `min_deviation_pct` is **3**  
- Last = **0.81** → deviation ≈ **3.85%** → passes if `min_deviation_pct` is **3**

### 8.2 `entry` block

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `bet_amount_usd` | Target spend per entry (subject to sizing rules) | `5` → roughly $5 notional |
| `price_offset` | Added to price when placing FAK (more aggressive fill) | `0.02` → pay up to +$0.02 vs reference |
| `order_type` | Entry type | `"FAK"` (fill and kill) |
| `max_retries` | Retries if order does not complete as expected | `3` |
| `retry_delay_ms` | Pause between retries | `300` |
| `fill_timeout_ms` | Used in executor / fill logic | `1000` |
| `min_contracts` | Polymarket minimum is often 5 | `5` |
| `min_order_usd` | Minimum order size in USD | `1` |
| `max_entry_price` | Hard cap on execution price | `0.88` — should align with `strategy.max_price` |
| `ws_recovery_timeout_sec` | After HTTP timeout, how long to watch User WS for fills | `10` |

**Sizing example**

- `bet_amount_usd = 5`, best ask ≈ **0.80** → rough contracts = floor(5 / 0.80) = **6** (subject to mins and API).

### 8.3 `hedge` block

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `enabled` | `true` / `false` | `false` for beginners |
| `hedge_price` | Limit price for opposite token | `0.02` |
| `order_type` | Usually `"GTD"` | passive limit |
| `max_retries` | Placement retries | `3` |
| `retry_delay_ms` | Delay between retries | `1000` |

**Hedge intuition (not financial advice)**  
After a long on UP, a **cheap** limit order on DOWN can act as a partial hedge if the market moves so that DOWN trades near your limit. **Costs and risks** are real; start with `enabled: false` until you understand fills.

### 8.4 `redeem` block

| Parameter | Meaning | Example |
|-----------|---------|---------|
| `enabled` | Run periodic on-chain redemption | `true` |
| `interval_seconds` | Seconds between scans | `180` |
| `auto_confirm` | Confirm in code path | `true` |

**Note:** On **Windows**, some Unix-only locking in redeem may fail; **Linux** or **WSL** is safer for production.

### 8.5 `telegram` block

| Parameter | Meaning |
|-----------|---------|
| `enabled` | `true` to send Telegram messages |
| `chart_every_n_trades` | Intended for periodic equity charts (see `TelegramNotifier.send_equity_chart`); **may not be wired** in `main.py` in all versions — check the code if you rely on auto-charts |

Tokens and chat id still come from **`.env`**.

### 8.6 `logging` block in `config.json`

The repo may include a `logging` section for documentation. **Current `main.py` sets logging in code** (e.g. `logs/bot.log`, `INFO` level). Do not assume `config.json` logging keys change behavior unless you wire them in code.

### 8.7 Preset ideas (copy-paste starting points)

**Conservative (fewer trades, tighter band)**

```json
"strategy": {
  "min_price": 0.80,
  "max_price": 0.85,
  "min_elapsed_sec": 600,
  "min_deviation_pct": 5,
  "max_deviation_pct": 100,
  "no_entry_before_end_sec": 300,
  "momentum_window_sec": 60,
  "vwap_window_sec": 30,
  "win_rate_csv": "data/win_rate.csv"
},
"entry": { "bet_amount_usd": 2 },
"hedge": { "enabled": false }
```

**Aggressive (more trades — higher risk)**

```json
"strategy": {
  "min_price": 0.70,
  "max_price": 0.90,
  "min_elapsed_sec": 400,
  "min_deviation_pct": 0,
  "max_deviation_pct": 100,
  "no_entry_before_end_sec": 120,
  "momentum_window_sec": 60,
  "vwap_window_sec": 30,
  "win_rate_csv": "data/win_rate.csv"
},
"entry": { "bet_amount_usd": 5 },
"hedge": { "enabled": false }
```

---

## 9. Run the bot

1. Activate **venv** (see [§6.2](#62-create-and-activate-a-virtual-environment)).  
2. Ensure `.env` and `config.json` are saved.  
3. From the **project root** (folder containing `main.py`):

```bash
python main.py
```

### 9.1 What you should see

- Startup messages (config summary, CLOB init).  
- A **live Rich dashboard**: timer, UP/DOWN token panels, indicators, **Strategy** line, P&amp;L.  
- When a **BUY UP** / **BUY DOWN** signal is valid, the bot fires an entry (real money if your keys are live).

### 9.2 Stop the bot

Press **Ctrl+C** in the terminal. On Windows, Unix signal handlers may be limited; **Ctrl+C** still stops the process.

### 9.3 First-time recommendation

- Set **`bet_amount_usd`** small.  
- Set **`hedge.enabled`** to **`false`** until you understand behavior.  
- Watch **`logs/`** while the market runs.

---

## 10. Optional: Telegram

1. **@BotFather** → `/newbot` → copy **token** → `TELEGRAM_BOT_TOKEN` in `.env`.  
2. **@userinfobot** → `/start` → copy **Id** → `TELEGRAM_CHAT_ID`.  
3. Open your bot in Telegram and tap **Start** (required).  
4. In `config.json`, set `"telegram": { "enabled": true, ... }`.

---

## 11. Optional: P&amp;L chart

After you have trades in **`logs/trading_log.json`**:

```bash
python chart_pnl.py
```

Output image: **`logs/pnl_chart.png`** (see `chart_pnl.py`).

---

## 12. Logs and files

| File / folder | Content |
|----------------|---------|
| `logs/bot.log` | General bot log |
| `logs/orders.log` | Order execution detail |
| `logs/hedges.log` | Hedge-related logs |
| `logs/signals.log` | Signal snapshots |
| `logs/trading_log.json` | Persisted trades + stats |
| `logs/pnl_chart.png` | Generated by `chart_pnl.py` |

---

## 13. Troubleshooting

| Problem | What to try |
|--------|-------------|
| `python` not found (Windows) | Reinstall Python with **Add to PATH**, or use `py -m venv venv` |
| `NotImplementedError` on `add_signal_handler` | Already fixed on Windows in `main.py` — use latest code |
| Config errors on startup | Read the printed message; usually missing `PRIVATE_KEY` or API fields |
| `python` works but imports fail | Activate **venv** and run `pip install -r requirements.txt` again |
| No trades for a long time | Strategy window is narrow (see [§2.5](#25-time-window-for-entries-15-minutes--900-seconds)); or market never satisfies all filters |
| Redeem errors on Windows | Prefer **WSL** or **Linux** for auto-redeem; or disable `redeem.enabled` and redeem manually on Polymarket |
| Telegram not sending | Bot token + chat id + user pressed **Start** on bot; `enabled: true` |

---

## 14. Risk summary

- **Real money** — you can lose your stake.  
- **No strategy edge is guaranteed** — this bot automates rules.  
- **Fees, slippage, and failed orders** happen.  
- **Protect your private key** — treat `.env` like a password.

For **multi-asset late-entry** trading, see **Meridian** (`up-down-spread-bot`) in the same repository. For **PTB / oracle-diff** rules and a web dashboard, see `5min-15min-PTB-bot`. Extended **quant** offerings (Kelly, Monte Carlo, advanced TA, sizing systems) are described in the [repository root README](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot) — contact [@terauss](https://t.me/terauss).

---

*For a single-page parameter list, see [`CONFIG.md`](../CONFIG.md). For internals, see [`PROJECT_LOGIC.md`](../PROJECT_LOGIC.md).*
