git clone https://github.com/sinusflow/copy-trading-bot-hub.git
cd copy-trading-bot-hub# Copy Trading Bot Hub

Collection of copy-trading bots for different chains and venues. Source: [github.com/sinusflow/copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub).

## Clone this repository

```bash
git clone https://github.com/sinusflow/copy-trading-bot-hub.git
cd copy-trading-bot-hub
```

Open the folder for the bot you want; each project has its own `README.md` with setup steps.

## Bots in this hub

| Folder | Description |
|--------|-------------|
| [Axiom-Copy-Trading-Bot](./Axiom-Copy-Trading-Bot/) | Copy trading via Axiom.trade WebSocket signals on Solana (memecoins / Pump.fun & Raydium). |
| [Binance-Copy-Trading-Bot](./Binance-Copy-Trading-Bot/) | Monitors Binance Futures Leaderboard and mirrors trades with Bybit API; MongoDB, Telegram/Discord. |
| [Binance-Bybit-Copy-Trding-Bot](./Binance-Bybit-Copy-Trding-Bot/) | Multi-exchange copy trading (Binance, Bybit) with WebSocket master/follower flow. |
| [Fourme-Copy-Trading-Bot](./Fourme-Copy-Trading-Bot/) | Four.meme and PancakeSwap on BNB Chain — TypeScript and Rust implementations. |
| [Hyperliquid-Copy-Trading-Bot](./Hyperliquid-Copy-Trading-Bot/) | Hyperliquid perpetual futures copy trading (TypeScript, WebSocket fills). |
| [Kuru-Copy-Trading-Bot](./Kuru-Copy-Trading-Bot/) | Kuru DEX on Monad — mirrors limit orders from tracked wallets. |
| [Meteora-DLMM-Copy-Trading-Bot](./Meteora-DLMM-Copy-Trading-Bot/) | Meteora DLMM pools on Solana — leader/follower copy trading with risk controls. |
| [Polymarket-Copy-Trading-Bot](./Polymarket-Copy-Trading-Bot/) | Polymarket on Polygon — mirror traders from the leaderboard with proportional sizing, MongoDB, Python. |
| [Solana-Copy-Trading-Bot](./Solana-Copy-Trading-Bot/) | High-speed Solana copy trading (Pump.fun, PumpSwap, routing, multiple tx paths). |

## Disclaimer

Trading bots involve significant financial risk. None of this is financial advice. Use only on testnets or with capital you can afford to lose, and review each bot’s disclaimer in its own README.
