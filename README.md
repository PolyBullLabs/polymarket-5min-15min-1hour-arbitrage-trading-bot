# Polymarket 5min, 15min, 1hour Trading Bot — Polymarket Arbitrage Trading Bot & Automation Toolkit

**Languages / 语言:** English (this page, top to bottom) plus a **[Simplified Chinese section (简体中文)](#zh-cn)** at the end. / 页面主体为英文，文末提供**简体中文**完整说明与表格。

---

**Polymarket trading bot** tooling for short-horizon crypto **Up / Down** markets: this repo ships **three** production-style Python **Polymarket bot** implementations you can run, study, and extend. Whether you search for a **polymarket arbitrage trading bot**, a **prediction market bot**, or a **Polymarket API bot** for automated execution, you get readable strategies, WebSocket market data, and CLOB-style order flow patterns built for speed and reliability in research and live-like testing.

This suite is **educational and experimental**. Use **simulation / dry-run** first, size small, and own your risk.

**（中文摘要）** 本仓库提供三个可运行的 Python **Polymarket 短线（5m/15m）Up/Down** 机器人实现，含 WebSocket、下单与风控范式；仅供**学习与研究**，请优先**模拟 / 小资金**并自担风险。完整安装、机器人对照表与策略目录见文末 [简体中文](#zh-cn)。

 **Contact (Telegram)** — [@terauss](https://t.me/terauss) · **联系（Telegram）** — [@terauss](https://t.me/terauss)

This repository is hosted under **[PolyBullLabs](https://github.com/PolyBullLabs)** ([polymarket-5min-15min-1hour-arbitrage-trading-bot](https://github.com/PolyBullLabs/polymarket-5min-15min-1hour-arbitrage-trading-bot)). The org also publishes **Rust** Polymarket bots on **5m**, **15m**, and **1h** horizons with **different strategies** than this Python suite—see the table below.



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

## Additional strategy catalog

The strategies below are **examples of directions** PolyBull Labs builds or discusses as **separate offerings**, custom deployments, or research tracks. They are **not guaranteed** to exist as public drop-ins in this repository—availability, implementation language, and terms are handled individually on **[Telegram @terauss](https://t.me/terauss)**.

下表为**策略方向示例**（可定制开发或单独交付），**不一定**以本仓库公开子目录形式提供；是否落地、技术栈与商务条款请在 **[Telegram @terauss](https://t.me/terauss)** 沟通。

| Strategy (EN) | 策略（中文） | Idea (EN) | 思路（中文） |
|----------------|-------------|-----------|-------------|
| **1c buy** | **1 美分买入** | Seek **ultra-cheap** bids (near **$0.01**) when microstructure or book updates create dislocations; **high variance**, needs **hard notional caps** and kill switches. | 在盘口/流动性短暂失衡时捕捉**极低价**（约 **1 美分**）一侧；**方差极大**，必须配合**严格资金上限**与熔断。 |
| **99c sniper** | **99 美分狙击** | Target **near-resolution** asks around **$0.99** when you believe the outcome is effectively settled but liquidity still prints; **tail risk** if the market flips. | 在临近结算、认为结果已高度确定时参与**约 99 美分**一侧；若结果反转则**尾部风险**显著。 |
| **Low-side dual reversion** | **弱势双边均值回归** | Work **both** underdog sides when prices are **compressed**, betting on **mean reversion** or late **volatility expansion** with paired risk controls. | 在两侧价格**受压**时，对**弱势/低价**双边做**均值回归**或博弈尾盘**波动放大**，需配对风控。 |
| **Pre-order market** | **预挂单 / 盘前布局** | Place **limits ahead** of the active window (or refresh ladders early) to **shape queue position** before competing flow arrives. | 在窗口正式激烈博弈**之前**挂出限价或刷新阶梯，以**排队与价位**占据主动。 |
| **Cross-market bot** | **跨市场机器人** | Link **two or more** related markets (same asset, different horizons, or correlated events) for **hedge**, **spread**, or **arbitrage-style** books. | 将**多个相关市场**（同资产不同周期、或相关事件）联动，做**对冲、价差或类套利**组合。 |
| **Martingale & anti-martingale @ ~45c** | **约 45¢ 马丁 / 反马丁** | Around **mid prices (~45¢)**, either **add on adverse moves** (martingale-style, very dangerous) or **pyramid into strength / cut into weakness** (anti-martingale); must be **regime-gated**. | 在**中段价位（约 45 美分）**附近，按规则做**亏损加仓（马丁，极高风险）**或**顺势加码 / 逆势减仓（反马丁）**；必须有**行情过滤**与**爆仓防护**。 |
| **Fibonacci strategy bot** | **斐波那契策略机器人** | Size entries or grids using **Fibonacci retracement/extension** levels relative to a swing anchor; combines **TA structure** with prediction-market **binary payoffs**. | 以波段锚点计算**斐波那契回撤/扩展**位，用于**分批建仓或网格**；将**技术结构**与二元**盈亏不对称**结合。 |
| **Binary momentum (MACD, RSI, VWAP)** | **二元动量（MACD / RSI / VWAP）** | **Momentum** stack on binary Up/Down: **MACD** for trend impulse, **RSI** for stretch / mean-revert filter, **VWAP** for intraday fair value—similar spirit to the shipped VWAP bot but **multi-indicator**. | 在二元 Up/Down 上叠加**动量**：**MACD** 看趋势动能，**RSI** 看过热/回调过滤，**VWAP** 看日内公允；理念接近本仓库 VWAP 机器人但为**多指标融合**。 |
| **Dump-hedge** | **急跌对冲** | Detect a **sharp dump**, leg in, then **hedge** the other side when **combined pair cost** clears your edge threshold (see also the **Rust 15m** repo in [Related Rust Polymarket bots](#related-rust-polymarket-bots-poly-tutor)). | 识别**急跌**后先进一侧，再在**组合成本**达标时**对冲**另一侧锁定结构（亦可对照上文 **Rust 15m** 仓库的 **dump-and-hedge** 思路）。 |

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
- [Additional strategy catalog](#additional-strategy-catalog)
- [Extended strategies (separate offerings)](#extended-strategies-separate-offerings)
- [Disclaimer](#disclaimer)
- [License](#license)
- [Contact](#contact)
- [Simplified Chinese (简体中文)](#zh-cn)

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
git clone https://github.com/PolyBullLabs/polymarket-5min-15min-1hour-arbitrage-trading-bot.git
cd polymarket-5min-15min-1hour-arbitrage-trading-bot
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

## Additional strategy catalog

The strategies below are **examples of directions** PolyBull Labs builds or discusses as **separate offerings**, custom deployments, or research tracks. They are **not guaranteed** to exist as public drop-ins in this repository—availability, implementation language, and terms are handled individually on **[Telegram @terauss](https://t.me/terauss)**.

下表为**策略方向示例**（可定制开发或单独交付），**不一定**以本仓库公开子目录形式提供；是否落地、技术栈与商务条款请在 **[Telegram @terauss](https://t.me/terauss)** 沟通。

| Strategy (EN) | 策略（中文） | Idea (EN) | 思路（中文） |
|----------------|-------------|-----------|-------------|
| **1c buy** | **1 美分买入** | Seek **ultra-cheap** bids (near **$0.01**) when microstructure or book updates create dislocations; **high variance**, needs **hard notional caps** and kill switches. | 在盘口/流动性短暂失衡时捕捉**极低价**（约 **1 美分**）一侧；**方差极大**，必须配合**严格资金上限**与熔断。 |
| **99c sniper** | **99 美分狙击** | Target **near-resolution** asks around **$0.99** when you believe the outcome is effectively settled but liquidity still prints; **tail risk** if the market flips. | 在临近结算、认为结果已高度确定时参与**约 99 美分**一侧；若结果反转则**尾部风险**显著。 |
| **Low-side dual reversion** | **弱势双边均值回归** | Work **both** underdog sides when prices are **compressed**, betting on **mean reversion** or late **volatility expansion** with paired risk controls. | 在两侧价格**受压**时，对**弱势/低价**双边做**均值回归**或博弈尾盘**波动放大**，需配对风控。 |
| **Pre-order market** | **预挂单 / 盘前布局** | Place **limits ahead** of the active window (or refresh ladders early) to **shape queue position** before competing flow arrives. | 在窗口正式激烈博弈**之前**挂出限价或刷新阶梯，以**排队与价位**占据主动。 |
| **Cross-market bot** | **跨市场机器人** | Link **two or more** related markets (same asset, different horizons, or correlated events) for **hedge**, **spread**, or **arbitrage-style** books. | 将**多个相关市场**（同资产不同周期、或相关事件）联动，做**对冲、价差或类套利**组合。 |
| **Martingale & anti-martingale @ ~45c** | **约 45¢ 马丁 / 反马丁** | Around **mid prices (~45¢)**, either **add on adverse moves** (martingale-style, very dangerous) or **pyramid into strength / cut into weakness** (anti-martingale); must be **regime-gated**. | 在**中段价位（约 45 美分）**附近，按规则做**亏损加仓（马丁，极高风险）**或**顺势加码 / 逆势减仓（反马丁）**；必须有**行情过滤**与**爆仓防护**。 |
| **Fibonacci strategy bot** | **斐波那契策略机器人** | Size entries or grids using **Fibonacci retracement/extension** levels relative to a swing anchor; combines **TA structure** with prediction-market **binary payoffs**. | 以波段锚点计算**斐波那契回撤/扩展**位，用于**分批建仓或网格**；将**技术结构**与二元**盈亏不对称**结合。 |
| **Binary momentum (MACD, RSI, VWAP)** | **二元动量（MACD / RSI / VWAP）** | **Momentum** stack on binary Up/Down: **MACD** for trend impulse, **RSI** for stretch / mean-revert filter, **VWAP** for intraday fair value—similar spirit to the shipped VWAP bot but **multi-indicator**. | 在二元 Up/Down 上叠加**动量**：**MACD** 看趋势动能，**RSI** 看过热/回调过滤，**VWAP** 看日内公允；理念接近本仓库 VWAP 机器人但为**多指标融合**。 |
| **Dump-hedge** | **急跌对冲** | Detect a **sharp dump**, leg in, then **hedge** the other side when **combined pair cost** clears your edge threshold (see also the **Rust 15m** repo in [Related Rust Polymarket bots](#related-rust-polymarket-bots-poly-tutor)). | 识别**急跌**后先进一侧，再在**组合成本**达标时**对冲**另一侧锁定结构（亦可对照上文 **Rust 15m** 仓库的 **dump-and-hedge** 思路）。 |

---

## Extended strategies (separate offerings)

Beyond these three open folders, **PolyBull Labs** works on advanced quant-style ideas (sizing sequences, TA combinations, execution-aware models, inventory/skew concepts, Monte Carlo for drawdown, etc.). These are **not** all shipped as drop-in modules here. The **[strategy catalog](#additional-strategy-catalog)** above summarizes **frequently requested** tracks in **English and Chinese**. For **access, customization, or collaboration**, use **[Telegram: @terauss](https://t.me/terauss)**.

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

<a id="zh-cn"></a>

## 简体中文（Simplified Chinese）

### 项目简介

本仓库是 **PolyBullLabs** 旗下的 **Polymarket 5 分钟 / 15 分钟 / 1 小时**相关 **Python 交易机器人**套件（公开部分为 **三个** 可运行子项目），面向加密 **Up/Down** 短期预测市场：含 REST/WebSocket、下单与风控范式，适合学习、二次开发与**小资金模拟**。**不构成投资建议**；请务必先 **dry-run / 模拟**，并自行承担全部风险。

- **仓库地址：** [github.com/PolyBullLabs/polymarket-5min-15min-1hour-arbitrage-trading-bot](https://github.com/PolyBullLabs/polymarket-5min-15min-1hour-arbitrage-trading-bot)  
- **联系：** [Telegram @terauss](https://t.me/terauss)

### 本仓库内的机器人（公开目录）

| 目录 | 侧重点 | 市场 | 核心思路 |
|------|--------|------|----------|
| [`btc-binary-VWAP-Momentum-bot/`](btc-binary-VWAP-Momentum-bot/) | VWAP、偏离、动量、z-score | BTC **5m** 或 **15m** | 在**较晚的窄窗口**内，当价格**站上 VWAP** 且**动量为正**时倾向**强势侧**；强调“共识 + 短线延续”过滤。 |
| [`up-down-spread-bot/`](up-down-spread-bot/)（**Meridian**） | Late Entry V3（`late_v3`） | BTC、ETH、SOL、XRP — **5m** 或 **15m** | **尾盘**若点差与**置信度（卖盘偏斜等）**过关，则跟随订单簿已偏向的一侧；**止损 / 翻转止损**在到期前截断劣路径。 |
| [`5min-15min-PTB-bot/`](5min-15min-PTB-bot/) | PTB 差值 + 概率触发 | BTC **5m** 或 **15m** | 对比**链上/现货 BTC** 与 Polymarket **PTB（price-to-beat）**；在**时间、价差、隐含概率**共振时触发；可用 **TP/SL** 管理仓位。 |

### 附加策略目录（与上表一致 · EN/中文）

与英文章节 **[Additional strategy catalog](#additional-strategy-catalog)** 相同，便于中文读者直接阅读：

| Strategy (EN) | 策略（中文） | Idea (EN) | 思路（中文） |
|----------------|-------------|-----------|-------------|
| **1c buy** | **1 美分买入** | Seek **ultra-cheap** bids (near **$0.01**) when microstructure or book updates create dislocations; **high variance**, needs **hard notional caps** and kill switches. | 在盘口/流动性短暂失衡时捕捉**极低价**（约 **1 美分**）一侧；**方差极大**，必须配合**严格资金上限**与熔断。 |
| **99c sniper** | **99 美分狙击** | Target **near-resolution** asks around **$0.99** when you believe the outcome is effectively settled but liquidity still prints; **tail risk** if the market flips. | 在临近结算、认为结果已高度确定时参与**约 99 美分**一侧；若结果反转则**尾部风险**显著。 |
| **Low-side dual reversion** | **弱势双边均值回归** | Work **both** underdog sides when prices are **compressed**, betting on **mean reversion** or late **volatility expansion** with paired risk controls. | 在两侧价格**受压**时，对**弱势/低价**双边做**均值回归**或博弈尾盘**波动放大**，需配对风控。 |
| **Pre-order market** | **预挂单 / 盘前布局** | Place **limits ahead** of the active window (or refresh ladders early) to **shape queue position** before competing flow arrives. | 在窗口正式激烈博弈**之前**挂出限价或刷新阶梯，以**排队与价位**占据主动。 |
| **Cross-market bot** | **跨市场机器人** | Link **two or more** related markets (same asset, different horizons, or correlated events) for **hedge**, **spread**, or **arbitrage-style** books. | 将**多个相关市场**（同资产不同周期、或相关事件）联动，做**对冲、价差或类套利**组合。 |
| **Martingale & anti-martingale @ ~45c** | **约 45¢ 马丁 / 反马丁** | Around **mid prices (~45¢)**, either **add on adverse moves** (martingale-style, very dangerous) or **pyramid into strength / cut into weakness** (anti-martingale); must be **regime-gated**. | 在**中段价位（约 45 美分）**附近，按规则做**亏损加仓（马丁，极高风险）**或**顺势加码 / 逆势减仓（反马丁）**；必须有**行情过滤**与**爆仓防护**。 |
| **Fibonacci strategy bot** | **斐波那契策略机器人** | Size entries or grids using **Fibonacci retracement/extension** levels relative to a swing anchor; combines **TA structure** with prediction-market **binary payoffs**. | 以波段锚点计算**斐波那契回撤/扩展**位，用于**分批建仓或网格**；将**技术结构**与二元**盈亏不对称**结合。 |
| **Binary momentum (MACD, RSI, VWAP)** | **二元动量（MACD / RSI / VWAP）** | **Momentum** stack on binary Up/Down: **MACD** for trend impulse, **RSI** for stretch / mean-revert filter, **VWAP** for intraday fair value—similar spirit to the shipped VWAP bot but **multi-indicator**. | 在二元 Up/Down 上叠加**动量**：**MACD** 看趋势动能，**RSI** 看过热/回调过滤，**VWAP** 看日内公允；理念接近本仓库 VWAP 机器人但为**多指标融合**。 |
| **Dump-hedge** | **急跌对冲** | Detect a **sharp dump**, leg in, then **hedge** the other side when **combined pair cost** clears your edge threshold (see also the **Rust 15m** repo in [Related Rust Polymarket bots](#related-rust-polymarket-bots-poly-tutor)). | 识别**急跌**后先进一侧，再在**组合成本**达标时**对冲**另一侧锁定结构（亦可对照英文区 **Rust 15m** 仓库的 **dump-and-hedge** 描述）。 |

### 克隆与安装（摘要）

```bash
git clone https://github.com/PolyBullLabs/polymarket-5min-15min-1hour-arbitrage-trading-bot.git
cd polymarket-5min-15min-1hour-arbitrage-trading-bot
cd btc-binary-VWAP-Momentum-bot   # 或: up-down-spread-bot / 5min-15min-PTB-bot
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

各子目录另有 **README** 与示例环境变量，请**勿将密钥提交到 Git**。

### 相关 Rust 仓库（Poly-Tutor）

英文主文档见 **[Related Rust Polymarket bots (Poly-Tutor)](#related-rust-polymarket-bots-poly-tutor)**：含 **5m / 15m / 1h** 的 **pair-cost、dump-hedge、限价+merge** 等 Rust 实现链接与 `git clone` 命令。

### 免责声明（中文）

预测市场交易可能导致**本金全部亏损**。本仓库内容仅供**教育与实验**；作者与贡献者**不对**因使用代码产生的交易亏损、程序错误、交易所或协议规则变更、以及您所在司法辖区的合规问题承担责任。**非投资建议。无担保。** 在充分理解行为与风险前，请持续使用**模拟 / 小资金**。

### 联系（中文）

- **Telegram：** [@terauss](https://t.me/terauss)

---

**If this Polymarket trading bot toolkit is useful, please star the repo** to improve discoverability for other builders and traders—and open issues if you want to contribute improvements to docs or code.

**若本仓库对您有帮助，欢迎点 Star**，方便其他开发者与交易者发现本项目；也欢迎通过 Issue 贡献文档与代码改进。
