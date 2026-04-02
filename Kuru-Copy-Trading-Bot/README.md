## Kuru copy trading bot

Part of [copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub).

> Educational project with optimization opportunities. Multiple RPC calls per signal introduce latency between source order and bot execution.

Copy trading bot for Kuru DEX on Monad blockchain. Monitors specified wallets and Kuru DEX markets and mirrors their **limit orders** via direct smart contract interaction (Kuru margin account, Kuru markets).

Please use the hub repository issue tracker for feedback and requests.

## What gets copied

The bot listens to `OrderCreated`, `Trade` and `OrdersCanceled` events and mirrors an action (places and cancels orders). `Trade` event is used to log activity for statistics.

Market orders are not supported.

## Installation

```bash
git clone https://github.com/sinusflow/copy-trading-bot-hub.git
cd copy-trading-bot-hub/Kuru-Copy-Trading-Bot
uv sync
```

## Important: margin account setup

The bot trades using your Kuru margin account balance, not wallet balance. Before running, deposit tokens to your margin account. See [margin account management](#margin-account-management) for instructions and helper scripts.

## Configuration

Copy `.env.example` to `.env` and configure:
- RPC endpoint (WebSocket)
- Source wallet addresses
- Market addresses
- Copy ratio and risk limits

## Usage

```bash
# Run bot
uv run python -m src.kuru_copytr_bot.main

# Custom config
uv run python -m src.kuru_copytr_bot.main --env-file .env.prod

# Debug logging
uv run python -m src.kuru_copytr_bot.main --log-level DEBUG

# JSON logs
uv run python -m src.kuru_copytr_bot.main --json-logs
```

Stop with `Ctrl+C`.

## Development

Install dev dependencies:
```bash
uv sync --extra dev
```

Lint and format:
```bash
uvx ruff check --fix .
uvx ruff format .
uvx mypy src/
```

Run tests:
```bash
uv run pytest
uv run pytest --cov
```

Install pre-commit hooks:
```bash
uv run pre-commit install
```

## Requirements

- Python 3.10+
- uv package manager
- Monad RPC access (WebSocket endpoint)
- Private key with MON for gas

## Margin account management

### Understanding margin accounts

Kuru DEX uses margin accounts for trading. The bot checks your margin balance (not wallet balance) when placing orders. Before starting, deposit tokens from your wallet to your margin account. Each market requires a specific quote asset - verify which token your target markets use.

Orders are skipped if margin balance is insufficient. The bot continues monitoring and resumes placing orders when balance is available.

### Helper scripts

Three scripts in `scripts/` directory manage margin accounts:

- **check_margin_balance.py** - view margin balances
- **deposit_margin.py** - transfer tokens from wallet to margin account
- **withdraw_margin.py** - transfer tokens from margin account to wallet
