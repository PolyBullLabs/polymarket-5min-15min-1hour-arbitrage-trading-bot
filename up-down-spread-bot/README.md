# Meridian — Polymarket Multi-Asset Crypto Desk

Automated execution for Polymarket **5- or 15-minute** crypto Up/Down markets. Runs **four parallel traders** (BTC, ETH, SOL, XRP) from **one Polygon wallet**, using **Late Entry V3** (`late_v3`): entries only in the **final minutes**, when **spread** and **confidence** (ask skew) show a **clear favorite**, with **stop-loss**, **flip-stop**, and **safety guard** limits.

| Resource | Link |
|----------|------|
| **Suite overview** | [Repository README](../README.md) |
| **Full guide** | [docs/README.md](docs/README.md) |
| **GitHub** | [PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot.git) |
| **Telegram** | [@terauss](https://t.me/terauss) |

---

## Why this strategy can work (and what breaks it)

**Idea:** Very late in the window, token prices often **embed** a view on how the underlying will fix vs the strike. Meridian **follows the book’s favorite** (higher ask) but **filters** noise: **tight sum of asks** (liquidity sanity), **minimum skew** (`min_confidence`), and **max price** cap so you do not pay **too much** for the last bit of certainty.

**Profit source (when it exists):** If the **favorite wins** more often than its **entry price** implies (e.g. buy at $0.72 and wins >72% in that regime), expectancy can be positive. **Shorter exposure** vs early entry can reduce **path risk** but usually **increases** average entry price.

**Risk controls:** **Dry run**, **per-order and per-market caps**, **stop-loss** (fixed $ or % of stake), **flip-stop** when your side loses leadership, **entry cooldown**, and validated prices before exits (fresh book, ask sum in range). See [docs/README.md](docs/README.md) for exact formulas.

**When to use:** You want **several coins**, **one wallet**, **terminal + optional web dashboard**, and **explicit exit rules**. **When not to:** You need **BTC-only VWAP/momentum** filters—use `btc-binary-VWAP-Momentum-bot`—or **PTB vs spot diff** rules—use `5min-15min-PTB-bot`.

---

## Features

- **Multi-Market Trading** — Trade 4 cryptocurrencies in parallel (BTC, ETH, SOL, XRP)
- **Late Entry Strategy** — Enter positions in the last 4 minutes before market close
- **Real-time WebSocket Data** — Live orderbook updates from Polymarket
- **Automatic Redeem** — Background collection of winnings after market resolution
- **Telegram Integration** — Commands for monitoring, charts, balance, and emergency shutdown
- **Safety Guard** — Protection layer with order limits and emergency stop
- **Position Tracking** — Real-time position monitoring via REST API
- **Stop-Loss & Flip-Stop** — Configurable exit strategies per coin
- **PnL Charts** — Visual performance tracking with matplotlib

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    MAIN TRADING LOOP                         │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │   BTC   │  │   ETH   │  │   SOL   │  │   XRP   │         │
│  │ Trader  │  │ Trader  │  │ Trader  │  │ Trader  │         │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘         │
│       └──────────┬─┴───────────┬┘──────────┘                 │
│              ┌───┴───┐    ┌────┴────┐                        │
│              │ Order │    │  Data   │                        │
│              │Executor│   │  Feed   │                        │
│              └───────┘    └─────────┘                        │
└──────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.10 or higher
- Polygon wallet with USDC (bridged)
- Small amount of POL/MATIC for gas fees
- Polymarket API credentials
- VPN (if needed for geo-restrictions)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot.git
cd polymakret-5min-15min-1hour-arbitrage-bot/up-down-spread-bot
```

### 2. Create Virtual Environment

**IMPORTANT: You must use a virtual environment (venv)!**

```bash
# Create venv
python3 -m venv venv

# Activate venv
# Linux/macOS:
source venv/bin/activate

# Windows:
.\venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configuration

```bash
# Copy configuration files
cp .env.example .env
cp config/config.example.json config/config.json

# Edit .env with your credentials
nano .env

# Edit config.json for trading parameters
nano config/config.json
```

## Configuration

### Environment Variables (.env)

```env
# Wallet (REQUIRED)
PRIVATE_KEY=0x...your_private_key...

# Polygon Network
RPC_URL=https://polygon-rpc.com
CHAIN_ID=137

# Polymarket API (REQUIRED)
CLOB_HOST=https://clob.polymarket.com
POLYMARKET_API_KEY=your_api_key
POLYMARKET_API_SECRET=your_api_secret
POLYMARKET_API_PASSPHRASE=your_api_passphrase

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Trading Configuration (config/config.json)

Key parameters:

| Section | Parameter | Description |
|---------|-----------|-------------|
| `safety.dry_run` | `true/false` | Enable dry run mode (no real trades) |
| `safety.max_order_size_usd` | `150` | Maximum single order size in USD |
| `safety.max_total_investment` | `1000` | Maximum investment per market |
| `trading.btc/eth/sol/xrp.enabled` | `true/false` | Enable/disable specific coins |
| `data_sources.polymarket.market_window` | `"15m"` or `"5m"` | **Which Polymarket horizon:** 15-minute or 5-minute Up/Down markets |
| `strategy.entry_window_sec` | `240` | Entry window (last 4 minutes) |
| `strategy.min_confidence` | `0.30` | Minimum price difference to enter |
| `strategy.price_max` | `0.92` | Maximum entry price |
| `exit.stop_loss.per_coin.*.value` | `-12` | Stop-loss threshold in USD |

## Usage

### Start Trading

```bash
# Activate virtual environment
source venv/bin/activate

# Run the trading bot
cd src
python3 main.py
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `Q` | Quit gracefully |
| `E` | Emergency stop (blocks all trading) |

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/chart` or `/pnl` | Generate current PnL chart |
| `/b` or `/balance` | Show wallet balance (USDC + POL) |
| `/t` or `/positions` | Show active positions |
| `/r` or `/redeem` | Redeem completed markets (interactive) |
| `/off` or `/stop` | Emergency shutdown (with confirmation) |
| `/help` | Show all available commands |

## Project Structure

```
up-down-spread-bot/
├── src/
│   ├── main.py                 # Main entry point
│   ├── strategy.py             # Late Entry V3 strategy
│   ├── data_feed.py            # WebSocket data feeds
│   ├── multi_trader.py         # Multi-market trader manager
│   ├── trader.py               # Individual trader logic
│   ├── order_executor.py       # Order execution engine
│   ├── position_tracker.py     # Real-time position tracking
│   ├── safety_guard.py         # Safety limits and emergency stop
│   ├── simple_redeem_collector.py  # Automatic redeem collection
│   ├── telegram_notifier.py    # Telegram bot integration
│   ├── dashboard_multi_ab.py   # Terminal dashboard
│   ├── polymarket_api.py       # Polymarket API wrapper
│   ├── pnl_chart_generator.py  # PnL chart generation
│   ├── trade_logger.py         # Trade logging
│   └── keyboard_listener.py    # Keyboard input handler
├── config/
│   └── config.json             # Trading configuration
├── logs/                       # Log files
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables
└── README.md                   # This file
```

## Strategy: late-window entry (Late Entry V3)

Meridian uses the Late Entry V3 / `late_v3` entry rules:

1. **Entry Window**: Only enter positions in the last 4 minutes (240 seconds) before market close
2. **Favorite Detection**: Buy the side with higher ask price (market consensus)
3. **Confidence Filter**: Only enter when price difference exceeds 30%
4. **Time-based Sizing**:
   - Above 180s remaining: 8 contracts
   - Above 120s remaining: 10 contracts
   - Below 120s remaining: 12 contracts
5. **Exit Strategies**:
   - Natural close (market resolution)
   - Stop-loss (configurable per coin)
   - Flip-stop (when our position becomes underdog)

## Safety Features

- **Dry Run Mode**: Test without real trades
- **Order Size Limits**: Maximum per-order and per-market limits
- **Rate Limiting**: Maximum orders per minute
- **Emergency Stop**: Keyboard shortcut to halt all trading
- **Investment Tracking**: Per-market investment limits
- **Position Persistence**: Save positions on shutdown

## Logs

Logs are stored in the `logs/` directory:

- `trades.jsonl` — All executed trades (JSON Lines format)
- `orders.jsonl` — Order execution details
- `safety.log` — Safety guard events
- `session.json` — Current session state
- `error.log` — Error messages

## Troubleshooting

### "Rate limit exceeded"

Use a private RPC endpoint:
```env
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY
```

### "Invalid signature"

1. Check that API credentials are correct
2. Verify the private key matches the Polymarket account
3. Regenerate API credentials on Polymarket

### WebSocket connection drops

The bot automatically reconnects. If persistent:
1. Check internet connection
2. Use a VPN
3. Change DNS to 1.1.1.1 or 8.8.8.8

### Positions not redeeming

1. Wait for oracle resolution (1-2 minutes after market close)
2. Use `/r` command in Telegram to manually trigger
3. Check `logs/` for error messages

## Important Notes

1. **USDC Type**: Polymarket uses USDC (Bridged), not USDC.e (Native)
2. **Gas Fees**: Keep POL/MATIC balance for transactions
3. **API Limits**: Public RPCs have rate limits — use private RPC for stability
4. **Risks**: Cryptocurrency trading involves significant risks

## License

MIT License

## Disclaimer

This software is for **educational and research purposes only**. Trading on prediction markets involves **substantial risk**; you may lose **all** funds you deploy. **Past results do not guarantee future performance.** Authors are **not** liable for losses. For **licensing**, **custom strategies**, or **advanced quant tooling** (Kelly, Monte Carlo, martingale / anti-martingale frameworks, RSI/MACD/Bollinger stacks, Bayesian edge models, etc.), contact [@terauss](https://t.me/terauss). See the [repository README](../README.md).
