# Configuration Guide

Part of the **[PolyBullLabs Polymarket suite](https://github.com/PolyBullLabs/polymakret-5min-15min-1hour-arbitrage-bot)** · [@terauss](https://t.me/terauss) · [Suite README (all bots)](../README.md)

This file explains **every parameter** in `config.json`. The bot is highly configurable -- you can fine-tune the strategy, risk, execution speed, hedging, and notifications without touching any code.

---

## market -- Which Polymarket window to trade

```
"interval_minutes": 5
```

**BTC up/down market length on Polymarket.** Must be **5** or **15**.

- **5** — slug pattern `btc-updown-5m-<unix_start>` (300s window). Example strategy: `min_elapsed_sec` ~150–210, `no_entry_before_end_sec` ~90–120.
- **15** — slug pattern `btc-updown-15m-<unix_start>` (900s window). Example strategy: `min_elapsed_sec` ~480–530, `no_entry_before_end_sec` ~300–335.

The bot aligns Chainlink anchor resets, market discovery, and elapsed-time logic to this interval. **Always** set `min_elapsed_sec` and `no_entry_before_end_sec` so they fit inside the market length (e.g. for 5m, `min_elapsed_sec` must be &lt; 300).

---

## simulation -- Paper trading (no real money)

```
"enabled": false
```

**When `true`:** the bot still connects to market WebSockets, RTDS Chainlink, runs the dashboard, and evaluates the same entry rules. **No** orders are sent to Polymarket, **no** User WebSocket for fills, **no** auto-redeemer loop. Entries are logged as instant hypothetical fills at **best ask + `entry.price_offset`**, subject to `max_entry_price` and the same contract sizing as live. Optional hedge is simulated as a placed GTD with id `SIM-HEDGE` (no on-chain or CLOB effect).

```
"separate_trading_log": true,
"trading_log_path": "logs/trading_log_sim.json"
```

If `separate_trading_log` is **true**, simulated P&L and trades are written only to `trading_log_path`, so your live `logs/trading_log.json` stays untouched. Set to **false** to append simulation results to the same file as live (not recommended if you also run live).

**Trading history for analysis (simulation only):**

- `history_csv_path` — Append-only CSV with **OPEN** rows (each simulated entry) and **CLOSE** rows (each resolved position). CLOSE rows include **trade_pnl_usd**, **cumulative_pnl_usd** after that trade, **win_rate_pct**, and **total_closed_trades**. Open in Excel / pandas.
- `history_jsonl_path` — One JSON object per line (`type`: `open` or `close`) for streaming tools. Set to `""` to disable.
- `history_summary_path` — Rewritten after every close: rolling **summary** (total PnL, wins/losses, win rate, best/worst trade) plus the full **trades** array (same data as `trading_log_path`, convenient for a single analysis file).

The main `trading_log_path` JSON also includes a **`summary`** block (totals and win rate) on each save, for both live and sim logs.

**Credentials:** With `simulation.enabled` true, `PRIVATE_KEY` and Polymarket API keys in `.env` are **not** required. You can still set Telegram tokens for notifications.

---

## strategy -- When to enter a trade

These parameters control **which signals the bot acts on**. Think of them as filters: a trade is only placed when ALL conditions pass simultaneously.

```
"min_price": 0.75
```
**Minimum token price to enter.** The bot only buys tokens priced at or above this value. Lower prices mean higher potential profit but lower probability of winning. At $0.75, you need a 75% win rate to break even. Range: 0.50 - 0.95. Start with 0.75.

```
"max_price": 0.88
```
**Maximum token price to enter.** The bot rejects tokens priced above this. Higher prices mean higher probability but tiny profit margin. At $0.88, you profit only $0.12 per contract on a win but lose $0.88 on a loss (need 88% win rate). Range: 0.80 - 0.95. Start with 0.88.

```
"min_elapsed_sec": 530
```
**Minimum seconds elapsed since market opened before allowing entry.** Each market lasts 900 seconds (15 min). This prevents entering too early when the market direction is unclear. At 530, the bot waits ~8.8 minutes. Range: 300 - 800. Higher = safer but fewer opportunities.

```
"min_deviation_pct": 3
```
**Minimum VWAP deviation (%) to trigger a signal.** VWAP = volume-weighted average price. Deviation measures how far the current price has moved from this average. A deviation of 3% means the token price is 3% above its recent average, indicating strong directional movement. Range: 0 - 15. Set to 0 to disable this filter. Higher = stricter, fewer trades.

```
"max_deviation_pct": 100
```
**Maximum VWAP deviation (%) allowed.** Rejects signals where deviation is abnormally high (potential spike/manipulation). Set to 100 to effectively disable the upper bound. To cap, try 15-25. Range: must be greater than min_deviation_pct.

```
"no_entry_before_end_sec": 335
```
**Stop entering trades if fewer than this many seconds remain.** At 335, the bot stops entering after ~9 min 25 sec (with 5 min 35 sec left). This protects against entering too late when there is not enough time for the position to be meaningful. Range: 60 - 500.

> **Entry window example:** With min_elapsed_sec=530 and no_entry_before_end_sec=335, the bot can only enter between 530s and 565s elapsed -- a 35-second window each market.

```
"momentum_window_sec": 60
```
**Lookback window for momentum calculation (seconds).** Momentum compares current price to the price N seconds ago. At 60, it asks: "Is the price higher than 1 minute ago?" Shorter windows = more reactive, noisier. Longer = smoother, slower to react. Range: 15 - 300.

```
"vwap_window_sec": 30
```
**Lookback window for VWAP calculation (seconds).** Only trades from the last N seconds are used to compute VWAP. Shorter = more responsive to recent trades. Longer = smoother average. Range: 10 - 120.

```
"win_rate_csv": "data/win_rate.csv"
```
**Path to the historical win rate table.** A CSV file containing win probabilities by price range and time bin. The bot uses this to display win rate on the dashboard. Generally no need to change this unless you build your own win rate data.

---

## entry -- How to execute orders

These parameters control **order mechanics**: how much to bet, how aggressively to fill, and what to do on failure.

```
"bet_amount_usd": 5
```
**How much USD to risk per trade.** The bot divides this by the entry price to get the number of contracts. Example: $5 at price $0.80 = 6 contracts. Start small ($1-5) while learning. Scale up only after consistent results. Range: 1 - any amount you are comfortable losing.

```
"price_offset": 0.02
```
**Price offset added to best bid for FAK orders.** FAK (Fill-And-Kill) orders must cross the spread to fill immediately. An offset of 0.02 means: if best bid is $0.80, the order is placed at $0.82. Higher offset = more aggressive fill but worse entry price. Range: 0.01 - 0.05.

```
"order_type": "FAK"
```
**Order type for entry.** FAK = Fill-And-Kill. The order fills immediately at the specified price or gets cancelled. This is the recommended type for fast-moving 15-minute markets. Alternative: "GTC" (Good-Till-Cancel) which stays on the book.

```
"max_retries": 3
```
**How many times to retry a failed order.** If the first attempt fails (rejected, no fill), the bot retries up to this many times. Range: 1 - 10. More retries = better chance of filling but uses more time.

```
"retry_delay_ms": 300
```
**Milliseconds to wait between retry attempts.** Range: 100 - 2000. Shorter = faster retries. Don't set too low or you may hit rate limits.

```
"fill_timeout_ms": 1000
```
**How long to wait for fill confirmation (ms).** After placing a FAK order, the bot waits this long for a WebSocket fill message. If no fill arrives in time, it enters recovery mode. Range: 500 - 5000.

```
"min_contracts": 5
```
**Minimum number of contracts per order.** Polymarket requires at least 5 contracts. If bet_amount_usd / price results in fewer than 5 contracts, the order is skipped. Generally no need to change.

```
"min_order_usd": 1
```
**Minimum order value in USD.** Orders below this value are skipped. Generally no need to change.

```
"max_entry_price": 0.88
```
**Hard price ceiling for entry.** Even if the signal says BUY, the order is rejected if the execution price exceeds this. Acts as a safety net. Should be equal to or less than strategy.max_price.

```
"ws_recovery_timeout_sec": 10
```
**Timeout for WebSocket fill recovery (seconds).** When an order times out, the bot checks the User WebSocket for fills. This is how long it waits during recovery. Range: 5 - 30.

---

## hedge -- Automatic hedging (advanced)

Hedging places a cheap order on the **opposite** token after entry. If your main trade loses, the hedge may fill and partially offset the loss.

```
"enabled": false
```
**Enable or disable automatic hedging.** Set to true to activate. When enabled, after each entry the bot places a GTD order on the opposite token. Recommended to leave false until you understand the mechanics.

```
"hedge_price": 0.02
```
**Price to place the hedge order at.** The hedge buys the opposite token at this price. At $0.02, you pay $0.02 per contract. If your main trade loses, the opposite token resolves to $1.00, netting $0.98 per contract. The hedge only fills if the market strongly moves in your favor (opposite token drops to $0.02). Range: 0.01 - 0.10.

```
"order_type": "GTD"
```
**Hedge order type.** GTD = Good-Till-Date. A limit order that sits on the book until it fills or expires. Expires in 1 hour (market resolves in 15 minutes). No need to change.

```
"max_retries": 3
```
**Retry count for hedge order placement.** If hedge placement fails, retry up to this many times.

```
"retry_delay_ms": 1000
```
**Delay between hedge retry attempts (ms).** Hedge placement is less time-critical than entry, so a longer delay is fine.

---

## redeem -- Automatic on-chain redemption

After a market resolves, winning positions must be redeemed on the blockchain to collect your payout.

```
"enabled": true
```
**Enable automatic redemption.** When true, the bot periodically checks for resolved positions and redeems them. If false, you must redeem manually on polymarket.com. Recommended: true.

```
"interval_seconds": 180
```
**How often to check for redeemable positions (seconds).** Every 180 seconds (3 minutes), the bot scans for positions that can be redeemed. Range: 60 - 600. Lower = more frequent checks but more API calls.

```
"auto_confirm": true
```
**Automatically confirm redemptions.** When true, redemptions happen without manual approval. When false, redemptions are logged but not executed.

---

## telegram -- Notifications

Optional Telegram integration for trade alerts and equity charts. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.

```
"enabled": false
```
**Enable Telegram notifications.** Set to true after configuring bot token and chat ID in .env. You will receive messages on trade entry, market end results, and periodic equity charts.

```
"chart_every_n_trades": 5
```
**Send an equity chart every N trades.** After every 5 trades (by default), the bot generates a P&L chart and sends it to your Telegram. Range: 1 - 50.

---

## logging -- Log settings

```
"level": "INFO"
```
**Logging verbosity.** Options: "DEBUG" (very verbose), "INFO" (normal), "WARNING" (errors only). Use DEBUG for troubleshooting, INFO for normal operation.

```
"file_rotation_hours": 3
```
**Rotate log files every N hours.** Prevents log files from growing indefinitely. Range: 1 - 24.

---

## Quick Presets

### Conservative (low risk, fewer trades)
```json
{
  "strategy": {
    "min_price": 0.80,
    "max_price": 0.85,
    "min_elapsed_sec": 600,
    "min_deviation_pct": 5,
    "no_entry_before_end_sec": 300
  },
  "entry": { "bet_amount_usd": 2 },
  "hedge": { "enabled": true }
}
```

### Moderate (balanced)
```json
{
  "strategy": {
    "min_price": 0.75,
    "max_price": 0.88,
    "min_elapsed_sec": 530,
    "min_deviation_pct": 3,
    "no_entry_before_end_sec": 335
  },
  "entry": { "bet_amount_usd": 10 },
  "hedge": { "enabled": true }
}
```

### Aggressive (more trades, higher risk)
```json
{
  "strategy": {
    "min_price": 0.70,
    "max_price": 0.90,
    "min_elapsed_sec": 480,
    "min_deviation_pct": 0,
    "no_entry_before_end_sec": 120
  },
  "entry": { "bet_amount_usd": 50 },
  "hedge": { "enabled": false }
}
```
