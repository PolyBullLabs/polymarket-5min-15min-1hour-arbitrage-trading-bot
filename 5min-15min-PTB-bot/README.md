# Polymarket BTC Auto-Trader — PTB, Diff & Probability (5m / 15m)

A Python bot for Polymarket **BTC Up/Down** markets in **5-minute** or **15-minute** windows. It merges **Binance** and **Polymarket CLOB** WebSockets, compares **live BTC** to Polymarket’s **price-to-beat (PTB)** for the active event, and can **auto-buy** when **time**, **dollar gap**, and **implied probability** rules align. After a fill, it supports **probability-based take-profit and stop-loss**, optional **auto-redeem** (Builder relayer flow), and a **browser dashboard**.

| Resource | Link |
|----------|------|
| **Suite overview** | [Repository README](../README.md) |
| **GitHub** | [PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot.git) |
| **Telegram** | [@terauss](https://t.me/terauss) |

---

## Why this strategy can work (and what breaks it)

**Economic story:** Each market defines a **reference path** for BTC (PTB) over the window. **Chainlink** (or the bot’s configured spot reference) and **outcome token prices** should **co-move** as the window ages. If **spot** is **far on one side** of PTB **late** in the window while the **UP or DOWN token** is still **cheap enough**, a rule-based buy can capture **misalignment** between **physical gap** and **implied probability**.

**What actually makes money:** Positive expectancy only appears if, **after fees and slippage**, wins and sizes combine so that **average PnL per trade > 0**. That requires either **calibrated triggers** (your `CONDITION_*` bands) or **good exit discipline** (TP/SL). **Simulation** helps estimate behavior; **live** liquidity differs.

**Failure modes:** **Feed lag** (Binance vs Chainlink vs Polymarket), **stale books**, **PTB definition** nuances (`variant=fifteen` alignment with the site), **partial fills**, and **regime change** (trending vs chop). **Always** start with `SIMULATION_MODE=true`.

---

## Risk management

| Layer | What it does |
|--------|----------------|
| **`SIMULATION_MODE`** | Runs rules with **instant** simulated fills at book prices—**no** CLOB orders, **no** auto-redeem. Cumulative simulated PnL in `state.json`. |
| **`AUTO_TRADE`** | Master switch for **live** order placement (still respect simulation). |
| **`TRADE_AMOUNT`** | Caps **USDC per buy**—start minimal. |
| **TP / SL** | After entry, **take-profit** and **stop-loss** are tracked in **probability** (0–1) space on the position token—see `config.env` comments. |
| **`MARKET_DATA_MAX_LAG_SEC`** | Skips or guards actions when data is **too stale**. |
| **Builder keys** | Optional keys for **auto-redeem**—treat like secrets. |

**Operational:** Use a **dedicated wallet**, **private RPC**, and **proxy** if your network blocks or throttles Polymarket.

---

## When to use this bot

| Use this bot when… | Consider another suite bot when… |
|--------------------|----------------------------------|
| You care about **PTB vs BTC** and **explicit trigger rows** (`CONDITION_1` … `CONDITION_4`) | You want **multi-asset** late consensus → **Meridian** (`up-down-spread-bot`) |
| You want a **web dashboard** at `http://localhost:5080` (default) | You want a **Rich terminal** + **VWAP/momentum** → `btc-binary-VWAP-Momentum-bot` |
| You will **paper** first with `SIMULATION_MODE=true` | You need **only** redeem / manual tools—trim features accordingly |

---

## Features

- **Live prices:** Binance and Polymarket CLOB for BTC and outcome tokens.
- **Auto trading:** Up to **four** configurable trigger rule groups; **any** matching rule can fire a buy.
- **TP / SL:** Probability-based take-profit and stop-loss after a fill.
- **Auto redeem:** Optional Polymarket **Builder** relayer flow for winning positions.
- **Dashboard:** Browser UI for balance, positions, history, logs, and **5m / 15m** toggle.
- **Structured logging:** `TRADING_ANALYSIS_LOG` (default `trading_analysis.jsonl`) — JSON Lines with `schema_version: 2` for research and replay.

---

## Requirements

- **Python** 3.8+ recommended.
- **Dependencies:** `pip install -r requirements.txt` (includes `py-clob-client`; redeem path uses `web3` / builder libraries as applicable).

---

## Configuration (`config.env`)

### Wallet & network

- `PRIVATE_KEY` — signing key (**never** commit).
- `FUNDER_ADDRESS` — proxy / funder when using signature type 1.
- `POLYGON_RPC_URL` — Polygon RPC (**private** endpoint recommended).
- `SIGNATURE_TYPE` — e.g. `1` = Gnosis Safe, `2` = EOA (see your setup).

### Proxy (optional)

- `HTTP_PROXY` / `HTTPS_PROXY` — e.g. `http://host:port` or `http://user:pass@host:port`.

### Trading

- `BTC_MARKET_MINUTES` — `5` or `15` (which Polymarket BTC window). PTB uses Polymarket’s crypto-price API with event start/end from Gamma (`variant=fifteen` for both intervals so PTB matches the site).
- `AUTO_TRADE` — `true` / `false` (live orders; ignored when simulation handles placement).
- `SIMULATION_MODE` — `true` / `false`. Paper mode: **no** CLOB orders / auto-redeem; PnL tracked in `state.json`.
- `TRADING_ANALYSIS_LOG` — optional path; default `trading_analysis.jsonl` next to `polymarket_auto_trade.py`. Relative paths resolve from that script’s directory. Each line is JSON with stable keys: `slug`, `shares_type` (UP/DOWN), `share_price`, `share_amount`, `ptb`, `btc_price`, `difference` (BTC−PTB USD), `status`, `take_profit` / `stop_loss`, `time`, `pnl_trade_usd`, `pnl_total_usd`, `simulation`, etc.
- `TRADE_AMOUNT` — USDC per buy.

### Triggers

- `CONDITION_1_*` … `CONDITION_4_*` — time window, min/max diff vs PTB, probability bands for UP/DOWN (see inline comments in `config.env`).

### Risk & loop

- `STOP_LOSS_PROB_PCT`, `TAKE_PROFIT_RR`, `TAKE_PROFIT_CAP`, `MARKET_DATA_MAX_LAG_SEC`, `LOOP_INTERVAL_SEC`, `BUY_RETRY_STEP`, etc.
- `CHECK_INTERVAL` — auxiliary check interval where used.
- Builder API keys for auto-redeem: `POLY_BUILDER_API_KEY`, `POLY_BUILDER_SECRET`, `POLY_BUILDER_PASSPHRASE`.

---

## Run

```bash
python polymarket_auto_trade.py
```

Use the dashboard **Market 5m / 15m** toggle or `BTC_MARKET_MINUTES` in `config.env` to switch horizons.

---

## Web dashboard

Default: **http://localhost:5080** (or `http://<your-ip>:5080` if bound externally).

Includes balances, live prices, manual trading panel, history, round summary, and log stream.

---

## Project layout (essential)

| Path | Role |
|------|------|
| `polymarket_auto_trade.py` | Main loop, feeds, rules, orders, dashboard server |
| `config.env` | Secrets and trading switches (**gitignore** in your fork) |
| `static/dashboard.html` | Dashboard UI |
| `state.json` | Persisted runtime / simulation PnL state |
| `trading_analysis.jsonl` | Append-only analysis log (optional path) |

---

## Extended strategies (contact)

This folder ships the **PTB / diff / probability** design. **Separate professional offerings** from the same author include advanced **risk and sizing** (martingale, anti-martingale, Fibonacci), **TA** (RSI, MACD, Bollinger Bands), and **quant** tooling (Bayesian belief updates, edge vs market, spread modeling, Avellaneda–Stoikov-style inventory skew, Kelly / fractional Kelly, Monte Carlo). These are **not** all included here—reach out on **[Telegram @terauss](https://t.me/terauss)**.

---

## Disclaimer

**Educational and research use only.** You are solely responsible for trading outcomes. **No warranty.** Prediction markets can **zero** your position. Never share **private keys** or **API secrets**. See the [repository README](../README.md) for the full three-bot map and risk overview.
