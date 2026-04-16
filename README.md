# Polymarket 5min, 15min, 1hour Trading Bot — Polymarket Arbitrage Trading Bot & Automation Toolkit



**Polymarket trading bot** tooling for short-horizon crypto **Up / Down** markets: this repo ships **three** production-style Python **Polymarket bot** implementations you can run, study, and extend. Whether you search for a **polymarket arbitrage trading bot**, a **prediction market bot**, or a **Polymarket API bot** for automated execution, you get readable strategies, WebSocket market data, and CLOB-style order flow patterns built for speed and reliability in research and live-like testing.

This suite is **educational and experimental**. Use **simulation / dry-run** first, size small, and own your risk.


 **Contact (Telegram)** — [@terauss](https://t.me/terauss)

This repository is hosted under **[PolyBullLabs](https://github.com/PolyBullLabs)** ([polymakret-5min-15min-1hour-arbitrage-bot](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot)). The **[Poly-Tutor](https://github.com/Poly-Tutor)** org also publishes **Rust** Polymarket bots on **5m**, **15m**, and **1h** horizons with **different strategies** than this Python suite—see the table below.



**Proof**
![photo_2026-02-26_11-48-37](https://github.com/user-attachments/assets/edd8e6ef-7e9d-4c7d-883a-5193274e5235)

![photo_2026-02-26_11-48-43](https://github.com/user-attachments/assets/6016d9bc-6ba8-465d-ae9b-843116f8ed95)

![photo_2026-02-26_11-48-47](https://github.com/user-attachments/assets/6d91f233-5cde-4779-af2a-949bb384b979)

<img width="1420" height="875" alt="5min-3-6-1" src="https://github.com/user-attachments/assets/51ff0a72-2d97-4c38-b703-22dc2c4cf7a6" />
<img width="1307" height="781" alt="5min-3-6" src="https://github.com/user-attachments/assets/e73b00a1-5893-4d0e-94ae-6086ba81340c" />




https://github.com/user-attachments/assets/29ae399d-6ee1-455a-8caf-e30deef7eae7


https://github.com/user-attachments/assets/f17f4012-557d-4e58-ad82-6b705cdbecc0


https://github.com/user-attachments/assets/0e9bfcf2-950a-41bc-8318-a20f8de78866

---
---

## Why traders and developers use this Polymarket bot suite

- **Automation-first:** Each **automated trading bot** targets repeatable rules instead of manual clicking—ideal if you want a **crypto trading bot** workflow on a **prediction market bot** stack.
- **Execution-aware design:** FAK/FOK patterns, retries, caps, and dashboards where applicable—built for traders who care about **latency, fills, and guardrails**.
- **Three philosophies:** Microstructure + VWAP (BTC), multi-asset late consensus (BTC/ETH/SOL/XRP), and oracle-vs-strike (PTB)—so you can compare approaches in one **Polymarket trading bot** codebase.
- **Developer-friendly:** Clear layout (one Python project per bot at the repo root), per-bot READMEs, and env-driven config—extend signals or wire your own **arbitrage bot** and **Polymarket API bot** integrations.

If you want **additional strategies**, **custom deployment**, or **professional risk and sizing** beyond this public suite, reach out on **[Telegram @terauss](https://t.me/terauss)**. For **bots oriented toward live profitability**—more advanced signals, sizing, and execution—contact the same channel; availability and terms are discussed individually.

---
---

## Screenshots & demo

Visual references for dashboards and flows (replace or extend with your own recordings as the **Polymarket arbitrage trading bot** suite evolves).

### VWAP / momentum (BTC binary bot)

https://github.com/user-attachments/assets/4c528411-6d88-4843-adf8-26c26f63288e

<img width="1224" height="487" alt="Polymarket trading bot VWAP momentum dashboard" src="https://github.com/user-attachments/assets/450211b1-531f-4abc-aaf0-3d7ab28937d2" />

<img width="1204" height="702" alt="Polymarket bot terminal UI" src="https://github.com/user-attachments/assets/250c75e5-93ea-4e04-9d29-9912a93deced" />

### Meridian / late consensus (`late_v3`)

https://github.com/user-attachments/assets/c811e320-3a0a-4cbe-9cec-8b7a42c0cf6d

<img width="1159" height="522" alt="Polymarket arbitrage trading bot Meridian spread view" src="https://github.com/user-attachments/assets/e60063c1-67a4-4298-b72f-063ac2bfb94d" />

<img width="1240" height="899" alt="Prediction market bot multi-asset dashboard" src="https://github.com/user-attachments/assets/158b038c-2952-4fb6-9278-f3d6dfd1afe6" />

### PTB bot (5m / 15m)

https://github.com/user-attachments/assets/bfdf7590-5458-4883-88cf-b8343a316f6f

<img width="1369" height="914" alt="Polymarket API bot PTB web dashboard" src="https://github.com/user-attachments/assets/1c1e654b-e79f-4f3f-b159-14681c07ac6c" />

<img width="1359" height="906" alt="Automated trading bot PTB controls" src="https://github.com/user-attachments/assets/3291ca28-51a5-45e2-983f-748bd6bcbb76" />

---

## Table of contents

- [Related Rust Polymarket bots (Poly-Tutor)](#related-rust-polymarket-bots-poly-tutor)
- [Features](#features)
- [How it works](#how-it-works)
- [Bots in this repository](#bots-in-this-repository)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Screenshots & demo](#screenshots--demo)
- [Risk management snapshot](#risk-management-snapshot)
- [Which Polymarket bot should I run?](#which-polymarket-bot-should-i-run)
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Extended strategies (separate offerings)](#extended-strategies-separate-offerings)
- [Disclaimer](#disclaimer)
- [License](#license)
- [Contact](#contact)

---

## Features

- **Multi-strategy Polymarket trading bot collection** — VWAP/momentum, late-window consensus with structured exits, and PTB-driven triggers.
- **Polymarket API bot patterns** — REST + WebSocket usage, order execution helpers, and configs suitable for paper and small live tests.
- **Risk controls** — dry run / simulation modes, investment caps, stop-loss and flip-stop (where implemented), entry windows, and spread or confidence gates.
- **Dashboards & UX** — Rich terminal UI (VWAP bot), web dashboards (PTB and Meridian paths), logging for operational review.
- **Educational depth** — Mechanics explained (why entries can work and how they can fail); aimed at serious traders and builders, not hype.

---

## How it works

1. **Connect** — Configure wallet/API credentials and Polymarket-compatible endpoints per the bot README (never commit secrets).
2. **Select a market window** — Short-horizon **5m / 15m** crypto Up/Down markets; parameters differ by **polymarket bot** (BTC-only vs multi-asset).
3. **Ingest & signal** — Live quotes and/or oracle-aligned inputs feed rules (VWAP deviation, late-book skew, PTB vs spot distance, etc.).
4. **Execute with guardrails** — Orders respect caps, max prices, simulation flags, and stop logic—treat this as an **automated trading bot** with explicit failure modes, not magic alpha.

None of this is investment advice; it is **mechanics** and software behavior.

---

## Bots in this repository

All runnable bots live as **top-level folders** next to this README. Each has its own **README**, `requirements.txt`, and configuration (`.env` / `config.json` / `config.env`).

| Directory | Focus | Markets | Core idea |
|-----------|--------|---------|-----------|
| [`btc-binary-VWAP-Momentum-bot/`](btc-binary-VWAP-Momentum-bot/) | VWAP, deviation, momentum, z-score | BTC **5m** or **15m** | Enter the **favorite** when price has **pulled above VWAP** with **positive momentum** in a **late, narrow window**—filtering for “consensus + short-term continuation.” |
| [`up-down-spread-bot/`](up-down-spread-bot/) (**Meridian**) | Late Entry V3 (`late_v3`) | BTC, ETH, SOL, XRP — **5m** or **15m** | In the **last minutes**, buy the side the book **already favors**, if **spread** and **confidence** (ask skew) pass checks; **stop-loss** and **flip-stop** cut bad paths before expiry. |
| [`5min-15min-PTB-bot/`](5min-15min-PTB-bot/) | PTB diff + probability triggers | BTC **5m** or **15m** | Compare **live BTC** to Polymarket’s **price-to-beat (PTB)**; fire when **time**, **dollar diff**, and **implied probability** align; manage risk with **take-profit / stop-loss** on token prices. |

---

## Installation

```bash
git clone https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot.git
cd polymakret-5min-15min-1hour-arbitrage-bot
```

Then enter the bot you want and create a virtual environment:

```bash
cd btc-binary-VWAP-Momentum-bot   # or: up-down-spread-bot / 5min-15min-PTB-bot
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Follow the **README inside that bot** for exact entrypoints, dependencies, and any extra setup (dashboards, env files).

---

## Usage

1. Pick a bot folder at the repo root and open its README (e.g. [`btc-binary-VWAP-Momentum-bot/README.md`](btc-binary-VWAP-Momentum-bot/README.md)).
2. Copy example config / `.env` as documented; set **`SIMULATION_MODE`** or **dry run** when offered.
3. Run the documented command (often `python main.py` or the bot-specific script—see each README).
4. Monitor logs and dashboards; scale size only after you trust behavior end-to-end.

**Operational hygiene:** dedicated wallet, **never commit keys**, private **RPC** where relevant, monitor **logs**, start with **minimum size**.

---

## Configuration

Configuration is **per bot**:

- **Environment variables** — API keys, RPC URLs, Telegram hooks, simulation flags (see each bot’s `.env.example` or README).
- **JSON / config files** — Market choice, windows, price bands, bet sizing, stop-loss and flip-stop parameters.
- **Runtime flags** — Some bots expose CLI flags (e.g. web dashboard); check the bot README.

You can run more than one **polymarket trading bot** only if you understand **collateral**, **nonce / rate limits**, and **position overlap**—typically use **separate wallets** or **non-overlapping** markets.



## Risk management snapshot

| Bot | Primary levers |
|-----|----------------|
| **VWAP / momentum** | Price band (`min_price` / `max_price`), **narrow entry window**, **bet size**, optional **hedge** (opposite-side GTD), **FAK** execution with retries, **max entry price** cap. |
| **Meridian** | **Dry run**, **max order / total investment**, **entry window**, **confidence** and **spread** gates, **stop-loss**, **flip-stop**, **entry frequency**, **FAK / FOK** execution behavior. |
| **PTB bot** | **Simulation mode**, **per-trade USDC**, **TP/SL** on probability, **trigger** windows, **market lag** limits, **loop** cadence. |

---

## Which Polymarket bot should I run?

| Situation | Sensible starting point |
|-----------|-------------------------|
| You want **one asset (BTC)** and **indicator-style** rules with a **terminal dashboard** | `btc-binary-VWAP-Momentum-bot` |
| You want **several coins** from **one wallet** and **late-window consensus** with **structured exits** | `up-down-spread-bot` (Meridian) |
| You care about **PTB vs Chainlink BTC** and **rule-based** triggers with a **web dashboard** | `5min-15min-PTB-bot` |

---
---

## Related Rust Polymarket bots (Poly-Tutor)

This repository is the **Python** toolkit (VWAP, Meridian, PTB). The same org maintains separate repos optimized for **pair-cost / hedging**, **dump-and-hedge**, and **hourly pre-limit + merge** flows.

| Timeframe | Repository | Language | Strategy (summary) |
|-----------|------------|----------|-------------------|
| **5 min** | [**5min-btc-polymarket-trading-bot**](https://github.com/Poly-Tutor/5min-btc-polymarket-trading-bot) | Rust | **BTC 5m** Up/Down: lock when **combined cost per pair** stays under your cap (e.g. Up + Down &lt; $1), plus **hedging**, expansion when the opposite side rises, **ride-the-winner**, and PnL rebalance. |
| **15 min** | [**Polymarket-15min-arbitrage-bot**](https://github.com/Poly-Tutor/Polymarket-15min-arbitrage-bot) | Rust | **15m** Up/Down (BTC, ETH, SOL, XRP): **dump-and-hedge**—detect a sharp drop, leg in, then **hedge** when pair cost meets targets; optional production CLOB mode. |
| **1 hour** | [**1hour-crypto-polymarket-trading-bot**](https://github.com/Poly-Tutor/1hour-crypto-polymarket-trading-bot) | Rust | **Hourly** Up/Down (BTC, ETH, SOL, XRP, Eastern Time): **limit buys** on both sides before the hour, optional **merge** for a small locked edge, **risk exit** if only one side fills. |

Clone URLs:

- `git clone https://github.com/Poly-Tutor/5min-btc-polymarket-trading-bot.git`
- `git clone https://github.com/Poly-Tutor/Polymarket-15min-arbitrage-bot.git`
- `git clone https://github.com/Poly-Tutor/1hour-crypto-polymarket-trading-bot.git`


---

## Roadmap

- Broader **paper-trading** defaults and clearer “first run” checklists per bot.
- Additional **observability** (structured logs, optional metrics hooks) for production-minded users of this **crypto trading bot** toolkit.
- Documentation cross-links and version pins where it helps reproducibility.
- Community-driven examples (strategies as plugins) where it fits the architecture.

---

## FAQ

### What is a Polymarket trading bot?

A **Polymarket trading bot** is software that connects to Polymarket’s APIs, reads market data, and places or manages orders according to rules—so you can automate entries, exits, and risk limits instead of trading only by hand.

### Is this a polymarket arbitrage trading bot?

This repository is framed as **polymarket arbitrage trading bot** *tooling*: strategies that seek **edge** in short-horizon Up/Down markets using execution and timing rules. It is **not** a guarantee of arbitrage in the strict sense on every tick—**slippage, fees, and adverse selection** apply.

### How is this different from a generic crypto trading bot?

A **crypto trading bot** on CEXes trades spot or perps; this suite is built for **prediction market** mechanics on Polymarket (binary outcomes, CLOB, resolution). The overlap is **automation and risk controls**; the market model is different.

### Do I need a Polymarket API bot setup?

Yes, for serious automation you should plan for API keys, signing, and rate-limit-aware clients. These bots follow **Polymarket API bot** patterns (REST/WebSocket, order helpers)—see each bot’s README for specifics.

### Can I use this as a fully automated trading bot out of the box?

You can run the code and automation paths, but you must **configure** markets, sizes, and risk. Start with **simulation / dry-run**, validate fills and logs, then scale. **No automated trading bot** removes market or operational risk.

### Is this prediction market bot software safe?

Software has bugs; markets have tail risk. Use small size, isolated wallets, and monitoring. Past backtests or demos **do not** predict live results.

### Who is this for?

**Developers** who want to learn or extend a **polymarket bot**, and **traders** who accept that **no bot guarantees profit** and who will test responsibly.

### Where do I get help or custom strategies?

For **custom deployment**, **additional strategies**, or **professional risk frameworks**, contact **[Telegram @terauss](https://t.me/terauss)**.

---

## Extended strategies (separate offerings)

Beyond these three open folders, **PolyBull Labs** works on advanced quant-style ideas (sizing sequences, TA combinations, execution-aware models, inventory/skew concepts, Monte Carlo for drawdown, etc.). These are **not** all shipped as drop-in modules here. For **access, customization, or collaboration**, use **[Telegram: @terauss](https://t.me/terauss)**.

---

## Disclaimer

Trading prediction markets can result in **total loss** of capital deployed. Everything here is provided **for education and experimentation**. Authors and contributors are **not** responsible for trading losses, bugs, exchange or protocol rule changes, or regulatory issues in your jurisdiction.

**Not financial advice.** **No warranty.** Use **simulation / dry-run** until you trust the full stack.

---

## License

Individual bots may ship their own **LICENSE**; where none is specified, treat usage as **at your own risk**.

---

## Contact

- **Telegram:** [@terauss](https://t.me/terauss)

---

**If this Polymarket trading bot toolkit is useful, please star the repo** to improve discoverability for other builders and traders—and open issues if you want to contribute improvements to docs or code.
