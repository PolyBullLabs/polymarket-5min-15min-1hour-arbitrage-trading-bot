# Trading Strategies – Detailed Guide with Examples

This document explains every trading strategy the Polymarket Copy Trading Bot supports, with **step-by-step examples**, exact calculations, and copy-paste `.env` configurations.

---

## Table of Contents

1. [Strategy Overview](#1-strategy-overview)
2. [PERCENTAGE Strategy](#2-percentage-strategy)
3. [FIXED Strategy](#3-fixed-strategy)
4. [ADAPTIVE Strategy](#4-adaptive-strategy)
5. [Multipliers (Single & Tiered)](#5-multipliers-single--tiered)
6. [Risk Limits in Practice](#6-risk-limits-in-practice)
7. [Combined Examples](#7-combined-examples)
8. [Ready-to-Use Configurations](#8-ready-to-use-configurations)

---

## 1. Strategy Overview

When a followed trader opens a trade, the bot:

1. **Calculates base amount** → Using your strategy (PERCENTAGE, FIXED, or ADAPTIVE)
2. **Applies multiplier** → Optional single or tiered multiplier
3. **Applies limits** → Max order, max position, balance check, min order
4. **Executes** → Places the order on Polymarket

All examples below use **USD** for order sizes.

---

## 2. PERCENTAGE Strategy

**Idea:** Copy a **fixed percentage** of the trader’s order size every time.

### Formula

```
Your order (base) = Trader's order × (COPY_SIZE / 100)
```

### Configuration

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=10.0
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
```

### Example 1: Basic (no limits hit)

| Trader's order | COPY_SIZE | Calculation        | Your order (base) |
|----------------|-----------|--------------------|-------------------|
| $50            | 10%       | 50 × 0.10          | **$5.00**         |
| $100           | 10%       | 100 × 0.10         | **$10.00**        |
| $250           | 10%       | 250 × 0.10         | **$25.00**        |
| $500           | 10%       | 500 × 0.10         | **$50.00**        |

### Example 2: Max order cap

```env
COPY_SIZE=10.0
MAX_ORDER_SIZE_USD=100.0
```

| Trader's order | Base (10%) | After MAX cap      | Your final order |
|----------------|------------|--------------------|------------------|
| $500           | $50        | No cap             | **$50**          |
| $1,000         | $100       | At cap             | **$100**         |
| $2,000         | $200       | Capped at $100     | **$100**         |
| $5,000         | $500       | Capped at $100     | **$100**         |

### Example 3: Min order / skip

```env
COPY_SIZE=5.0
MIN_ORDER_SIZE_USD=1.0
```

| Trader's order | Base (5%) | Below min? | Result                    |
|----------------|-----------|------------|---------------------------|
| $10            | $0.50     | Yes (<$1)  | Treated as min **$1** or skipped |
| $25            | $1.25     | No         | **$1.25**                 |
| $50            | $2.50     | No         | **$2.50**                 |

### Example 4: Different COPY_SIZE values

| COPY_SIZE | Trader $200 | Your order |
|-----------|-------------|------------|
| 5%        | $200        | **$10**    |
| 10%       | $200        | **$20**    |
| 15%       | $200        | **$30**    |
| 25%       | $200        | **$50**    |
| 50%       | $200        | **$100**   |

### When to use PERCENTAGE

- You want **proportional** exposure to the trader.
- Same **relative** risk whether they trade $50 or $500.
- **Default** strategy for most users.

---

## 3. FIXED Strategy

**Idea:** Copy a **fixed dollar amount** per trade, regardless of the trader’s size.

### Formula

```
Your order (base) = COPY_SIZE   (always the same)
```

### Configuration

```env
COPY_STRATEGY=FIXED
COPY_SIZE=50.0
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
```

### Example 1: Basic

| Trader's order | COPY_SIZE | Your order (base) |
|----------------|-----------|-------------------|
| $20            | $50       | **$50**           |
| $100           | $50       | **$50**           |
| $500           | $50       | **$50**           |
| $1,000         | $50       | **$50**           |

### Example 2: COPY_SIZE vs MAX_ORDER_SIZE

```env
COPY_SIZE=150.0
MAX_ORDER_SIZE_USD=100.0
```

| Trader's order | Base (fixed) | After MAX cap | Your final order |
|----------------|--------------|---------------|------------------|
| $50            | $150         | Capped        | **$100**         |
| $200           | $150         | Capped        | **$100**         |

So with FIXED, **COPY_SIZE** is the target; **MAX_ORDER_SIZE_USD** still caps it.

### Example 3: Small COPY_SIZE

```env
COPY_SIZE=25.0
MIN_ORDER_SIZE_USD=1.0
```

Every trade base = **$25** (above min), so you always get **$25** per copy (before balance/position limits).

### When to use FIXED

- You want **identical risk per trade** in dollars.
- You prefer **predictable** position sizes.
- Good for **smaller accounts** with a strict per-trade budget.

---

## 4. ADAPTIVE Strategy

**Idea:** The **percentage** changes with the trader’s order size:

- **Small orders** (< threshold) → **Higher** % (up to `ADAPTIVE_MAX_PERCENT`)
- **Large orders** (> threshold) → **Lower** % (down to `ADAPTIVE_MIN_PERCENT`)
- **Around threshold** → **Linear interpolation** between base % and min/max

### Configuration

```env
COPY_STRATEGY=ADAPTIVE
COPY_SIZE=10.0
ADAPTIVE_MIN_PERCENT=5.0
ADAPTIVE_MAX_PERCENT=15.0
ADAPTIVE_THRESHOLD_USD=500.0
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
```

### How the % is chosen

The bot uses **linear interpolation** (smooth transition) between percentages. Think of it as a **sliding scale** that smoothly transitions between the min and max percentages.

**Visual representation:**

```
For Small Orders (< $500):
┌─────────────────────────────────────────┐
│ Trader Order:  $0    $250    $500      │
│ Effective %:   15% ────→ 12.5% ────→ 10% │
│                (max)   (mid)   (base)   │
└─────────────────────────────────────────┘

For Large Orders (≥ $500):
┌─────────────────────────────────────────┐
│ Trader Order:  $500   $750   $1000+     │
│ Effective %:   10% ────→ 7.5% ────→ 5%   │
│                (base)  (mid)   (min)     │
└─────────────────────────────────────────┘
```

The bot uses **linear interpolation** (smooth transition) between percentages.

#### For Small Orders (< $500 threshold):

**Step 1:** Calculate the interpolation factor
```
factor = trader_order_size / threshold
```

**Step 2:** Interpolate between MAX_PERCENT and COPY_SIZE
```
effective_percent = MAX_PERCENT + (COPY_SIZE - MAX_PERCENT) × factor
```

**Simplified formula:**
```
effective_percent = MAX_PERCENT × (1 - factor) + COPY_SIZE × factor
```

**What this means:**
- When `trader_order = $0` → `factor = 0` → `effective_percent = MAX_PERCENT` (15%)
- When `trader_order = $500` → `factor = 1` → `effective_percent = COPY_SIZE` (10%)
- In between → smooth transition from 15% down to 10%

#### For Large Orders (≥ $500 threshold):

**Step 1:** Calculate the interpolation factor
```
factor = min(1, trader_order_size / threshold - 1)
```

**Step 2:** Interpolate between COPY_SIZE and MIN_PERCENT
```
effective_percent = COPY_SIZE + (MIN_PERCENT - COPY_SIZE) × factor
```

**What this means:**
- When `trader_order = $500` → `factor = 0` → `effective_percent = COPY_SIZE` (10%)
- When `trader_order = $1000` (2× threshold) → `factor = 1` → `effective_percent = MIN_PERCENT` (5%)
- In between → smooth transition from 10% down to 5%

---

### Example 1: Small orders (< $500) - Step-by-Step Calculations

**Configuration:**
- `ADAPTIVE_MAX_PERCENT = 15.0%`
- `COPY_SIZE = 10.0%`
- `ADAPTIVE_THRESHOLD_USD = 500.0`

**Formula for small orders:**
```
factor = trader_order / 500
effective_percent = 15.0 + (10.0 - 15.0) × factor
                  = 15.0 - 5.0 × factor
```

Let's calculate each example:

#### **Trader's order: $0**
```
factor = 0 / 500 = 0
effective_percent = 15.0 - 5.0 × 0 = 15.0%
Your order = $0 × 15% = $0
```

#### **Trader's order: $50**
```
factor = 50 / 500 = 0.1
effective_percent = 15.0 - 5.0 × 0.1 = 15.0 - 0.5 = 14.5%
Your order = $50 × 14.5% = $7.25
```

#### **Trader's order: $100**
```
factor = 100 / 500 = 0.2
effective_percent = 15.0 - 5.0 × 0.2 = 15.0 - 1.0 = 14.0%
Your order = $100 × 14% = $14.00
```

#### **Trader's order: $250**
```
factor = 250 / 500 = 0.5
effective_percent = 15.0 - 5.0 × 0.5 = 15.0 - 2.5 = 12.5%
Your order = $250 × 12.5% = $31.25
```

#### **Trader's order: $500** (at threshold)
```
factor = 500 / 500 = 1.0
effective_percent = 15.0 - 5.0 × 1.0 = 15.0 - 5.0 = 10.0%
Your order = $500 × 10% = $50.00
```

**Summary table:**

| Trader's order | Factor | Calculation | Effective % | Your order (base) |
|----------------|--------|-------------|-------------|-------------------|
| $0             | 0.0    | 15.0 - 5.0×0.0 | **15.0%** | **$0.00** |
| $50            | 0.1    | 15.0 - 5.0×0.1 | **14.5%** | **$7.25** |
| $100           | 0.2    | 15.0 - 5.0×0.2 | **14.0%** | **$14.00** |
| $250           | 0.5    | 15.0 - 5.0×0.5 | **12.5%** | **$31.25** |
| $500           | 1.0    | 15.0 - 5.0×1.0 | **10.0%** | **$50.00** |

### Example 2: Large orders (≥ $500) - Step-by-Step Calculations

**Configuration:**
- `COPY_SIZE = 10.0%`
- `ADAPTIVE_MIN_PERCENT = 5.0%`
- `ADAPTIVE_THRESHOLD_USD = 500.0`

**Formula for large orders:**
```
factor = min(1, trader_order / 500 - 1)
effective_percent = 10.0 + (5.0 - 10.0) × factor
                  = 10.0 - 5.0 × factor
```

Let's calculate each example:

#### **Trader's order: $500** (at threshold)
```
factor = min(1, 500/500 - 1) = min(1, 0) = 0
effective_percent = 10.0 - 5.0 × 0 = 10.0%
Your order = $500 × 10% = $50.00
```

#### **Trader's order: $750**
```
factor = min(1, 750/500 - 1) = min(1, 0.5) = 0.5
effective_percent = 10.0 - 5.0 × 0.5 = 10.0 - 2.5 = 7.5%
Your order = $750 × 7.5% = $56.25
```
*(Note: The table shows ~8.3%, but the actual calculation gives 7.5%. Let me verify...)*

Actually, let me recalculate $750 more carefully:
```
factor = 750/500 - 1 = 1.5 - 1 = 0.5
effective_percent = 10.0 + (5.0 - 10.0) × 0.5
                  = 10.0 + (-5.0) × 0.5
                  = 10.0 - 2.5 = 7.5%
Your order = $750 × 7.5% = $56.25
```

#### **Trader's order: $1,000** (2× threshold)
```
factor = min(1, 1000/500 - 1) = min(1, 1.0) = 1.0
effective_percent = 10.0 - 5.0 × 1.0 = 10.0 - 5.0 = 5.0%
Your order = $1,000 × 5% = $50.00
```

#### **Trader's order: $1,500**
```
factor = min(1, 1500/500 - 1) = min(1, 2.0) = 1.0
effective_percent = 10.0 - 5.0 × 1.0 = 5.0%
Your order = $1,500 × 5% = $75.00
```

#### **Trader's order: $2,000**
```
factor = min(1, 2000/500 - 1) = min(1, 3.0) = 1.0
effective_percent = 10.0 - 5.0 × 1.0 = 5.0%
Your order = $2,000 × 5% = $100.00
```

**Summary table:**

| Trader's order | Factor | Calculation | Effective % | Your order (base) |
|----------------|--------|-------------|-------------|-------------------|
| $500           | 0.0    | 10.0 - 5.0×0.0 | **10.0%** | **$50.00** |
| $750           | 0.5    | 10.0 - 5.0×0.5 | **7.5%** | **$56.25** |
| $1,000         | 1.0    | 10.0 - 5.0×1.0 | **5.0%** | **$50.00** |
| $1,500         | 1.0    | 10.0 - 5.0×1.0 | **5.0%** | **$75.00** |
| $2,000         | 1.0    | 10.0 - 5.0×1.0 | **5.0%** | **$100.00** |

**Note:** Once the trader's order is ≥ $1,000 (2× threshold), the factor caps at 1.0, so the effective % stays at the minimum (5.0%).

---

### Quick Formula Reference

**For Small Orders (< threshold):**
```
factor = trader_order / threshold
effective_percent = MAX_PERCENT - (MAX_PERCENT - COPY_SIZE) × factor
```

**For Large Orders (≥ threshold):**
```
factor = min(1, trader_order / threshold - 1)
effective_percent = COPY_SIZE - (COPY_SIZE - MIN_PERCENT) × factor
```

**Then calculate your order:**
```
your_order = trader_order × (effective_percent / 100)
```

---

### Example 3: With MAX_ORDER_SIZE_USD = $100

| Trader's order | Effective % | Base amount | After cap | Final |
|----------------|-------------|-------------|-----------|-------|
| $500           | 10%         | $50         | No        | **$50**  |
| $1,000         | ~7.5%       | $75         | No        | **$75**  |
| $2,000         | ~6.3%       | $126        | Yes       | **$100** |
| $5,000         | ~5.5%       | $275        | Yes       | **$100** |

### When to use ADAPTIVE

- You want **larger relative size** on small trades and **smaller relative size** on large trades.
- **Larger balances** and more nuanced risk control.
- Fine-tuning around a **threshold** (e.g. $500) that matches your risk tolerance.

---

## 5. Multipliers (Single & Tiered)

Multipliers **scale** the base amount **after** the strategy is applied. They work with **all** strategies.

### 5.1 Single multiplier

**Formula:** `Final base = Strategy base × TRADE_MULTIPLIER`

```env
TRADE_MULTIPLIER=2.0
```

#### Example: PERCENTAGE 10%, multiplier 2x

| Trader's order | Base (10%) | × 2.0 | Your order |
|----------------|------------|-------|------------|
| $100           | $10        | $20   | **$20**    |
| $300           | $30        | $60   | **$60**    |
| $600           | $60        | $120  | **$100** if MAX = $100 |

#### Example: Multiplier 0.5x (conservative)

| Trader's order | Base (10%) | × 0.5 | Your order |
|----------------|------------|-------|------------|
| $100           | $10        | $5    | **$5**     |
| $500           | $50        | $25   | **$25**    |

### 5.2 Tiered multipliers

Different multipliers for different **trader** order sizes.

**Format:** `min-max:multiplier` or `min+:multiplier` (comma-separated).

```env
TIERED_MULTIPLIERS=1-10:2.0,10-100:1.0,100-500:0.5,500+:0.2
```

| Tier      | Trader order size | Multiplier |
|-----------|-------------------|------------|
| 1–10      | $1 to $10         | 2.0x       |
| 10–100    | $10 to $100       | 1.0x       |
| 100–500   | $100 to $500      | 0.5x       |
| 500+      | $500 and above    | 0.2x       |

#### Example: PERCENTAGE 10% + tiered multipliers

**Trader buys $5:**

1. Base: $5 × 10% = **$0.50**
2. Tier: $5 ∈ [1, 10) → multiplier **2.0**
3. Amount: $0.50 × 2.0 = **$1.00**

**Trader buys $50:**

1. Base: $50 × 10% = **$5.00**
2. Tier: $50 ∈ [10, 100) → multiplier **1.0**
3. Amount: $5.00 × 1.0 = **$5.00**

**Trader buys $200:**

1. Base: $200 × 10% = **$20.00**
2. Tier: $200 ∈ [100, 500) → multiplier **0.5**
3. Amount: $20.00 × 0.5 = **$10.00**

**Trader buys $1,000:**

1. Base: $1,000 × 10% = **$100.00**
2. Tier: $1,000 ∈ 500+ → multiplier **0.2**
3. Amount: $100.00 × 0.2 = **$20.00**

### 5.3 Tiered + MAX_ORDER_SIZE

Same setup, `MAX_ORDER_SIZE_USD=50`:

| Trader's order | Base (10%) | Tier mult | Before cap | After cap |
|----------------|------------|-----------|------------|-----------|
| $200           | $20        | 0.5       | $10        | **$10**   |
| $400           | $40        | 0.5       | $20        | **$20**   |
| $1,000         | $100       | 0.2       | $20        | **$20**   |
| $2,000         | $200       | 0.2       | $40        | **$40**   |
| $5,000         | $500       | 0.2       | $100       | **$50** (capped) |

---

## 6. Risk Limits in Practice

These apply **after** strategy + multiplier.

### 6.1 MAX_ORDER_SIZE_USD

```env
MAX_ORDER_SIZE_USD=100.0
```

- Any single order **cannot exceed $100**.
- Already shown in earlier examples (capping base × multiplier).

### 6.2 MIN_ORDER_SIZE_USD

```env
MIN_ORDER_SIZE_USD=1.0
```

- Orders **below $1** are raised to min or skipped (implementation-dependent).
- Avoids tiny “dust” trades.

### 6.3 MAX_POSITION_SIZE_USD

```env
MAX_POSITION_SIZE_USD=300.0
```

**Example:** Same market, you already have **$250** in the position.

- New copy would add **$80**.
- $250 + $80 = $330 > $300 → **reduced**.
- Allowed addition: $300 − $250 = **$50**.
- Your order for this copy: **$50** (or skipped if $50 < min, depending on config).

### 6.4 Balance check (1% buffer)

- Usable balance = **balance × 0.99**.
- If computed order > usable balance → order is **reduced** to what you can afford.

**Example:** Balance $60, order would be $80.

- Max affordable: $60 × 0.99 = $59.40.
- Order becomes **$59.40** (or less if other limits apply).

---

## 7. Combined Examples

### 7.1 PERCENTAGE + single multiplier + limits

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=15.0
TRADE_MULTIPLIER=1.5
MAX_ORDER_SIZE_USD=75.0
MIN_ORDER_SIZE_USD=2.0
```

| Trader's order | Base (15%) | × 1.5 | After MAX $75 | Final |
|----------------|------------|-------|---------------|-------|
| $100           | $15        | $22.50| No            | **$22.50** |
| $200           | $30        | $45   | No            | **$45.00** |
| $400           | $60        | $90   | Capped        | **$75.00** |
| $20            | $3         | $4.50 | No            | **$4.50**  |
| $5             | $0.75      | $1.125| Below min     | **$2.00** (min) or skip |

### 7.2 FIXED + tiered multipliers

```env
COPY_STRATEGY=FIXED
COPY_SIZE=40.0
TIERED_MULTIPLIERS=1-50:1.5,50-200:1.0,200+:0.5
MAX_ORDER_SIZE_USD=80.0
```

- Base is always **$40** (FIXED).
- Multiplier depends on **trader’s** order size.

| Trader's order | Base | Tier mult | Amount | After MAX $80 |
|----------------|------|-----------|--------|---------------|
| $30            | $40 | 1.5       | $60    | **$60**       |
| $100           | $40 | 1.0       | $40    | **$40**       |
| $500           | $40 | 0.5       | $20    | **$20**       |

### 7.3 ADAPTIVE + single multiplier

```env
COPY_STRATEGY=ADAPTIVE
COPY_SIZE=10.0
ADAPTIVE_MIN_PERCENT=5.0
ADAPTIVE_MAX_PERCENT=15.0
ADAPTIVE_THRESHOLD_USD=500.0
TRADE_MULTIPLIER=2.0
MAX_ORDER_SIZE_USD=150.0
```

| Trader's order | Effective % | Base    | × 2.0 | After MAX $150 |
|----------------|-------------|---------|-------|----------------|
| $100           | ~14%        | ~$14    | ~$28  | **$28**        |
| $500           | 10%         | $50     | $100  | **$100**       |
| $2,000         | ~6%         | ~$120   | ~$240 | **$150** (capped) |

---

## 8. Ready-to-Use Configurations

Copy the block you need into your `.env` and adjust values if desired.

### Conservative (small balance)

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=5.0
TRADE_MULTIPLIER=1.0
MAX_ORDER_SIZE_USD=25.0
MIN_ORDER_SIZE_USD=1.0
```

- 5% of each trade, max **$25** per order.

### Default / recommended

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=10.0
TRADE_MULTIPLIER=1.0
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
```

- 10% of each trade, max **$100** per order.

### Aggressive (higher size)

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=20.0
TRADE_MULTIPLIER=1.5
MAX_ORDER_SIZE_USD=200.0
MIN_ORDER_SIZE_USD=2.0
```

- 20% base, then 1.5x, max **$200** per order.

### Fixed $50 per trade

```env
COPY_STRATEGY=FIXED
COPY_SIZE=50.0
TRADE_MULTIPLIER=1.0
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
```

- Always **$50** per copy (unless capped by max or balance).

### Adaptive (medium/large balance)

```env
COPY_STRATEGY=ADAPTIVE
COPY_SIZE=10.0
ADAPTIVE_MIN_PERCENT=5.0
ADAPTIVE_MAX_PERCENT=15.0
ADAPTIVE_THRESHOLD_USD=500.0
TRADE_MULTIPLIER=1.0
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
```

- **5–15%** depending on trade size, threshold **$500**.

### Tiered multipliers (scale down on large trades)

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=10.0
TIERED_MULTIPLIERS=1-10:2.0,10-100:1.0,100-500:0.5,500+:0.2
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
```

- 10% base, then **2x / 1x / 0.5x / 0.2x** by trader order size.

---

## Quick reference

| Strategy   | COPY_SIZE meaning | Your order (base)              |
|-----------|--------------------|---------------------------------|
| PERCENTAGE| % of trader        | Trader × (COPY_SIZE / 100)     |
| FIXED     | Fixed $            | COPY_SIZE                      |
| ADAPTIVE  | Base %             | Trader × (adaptive % / 100)    |

| Setting              | Purpose                          |
|----------------------|----------------------------------|
| TRADE_MULTIPLIER     | Scale all orders (single)        |
| TIERED_MULTIPLIERS   | Scale by trader order size       |
| MAX_ORDER_SIZE_USD   | Cap per order                    |
| MIN_ORDER_SIZE_USD   | Minimum size (or skip)           |
| MAX_POSITION_SIZE_USD| Cap total per position (opt.)    |
| MAX_DAILY_VOLUME_USD | Cap daily volume (opt.)          |

---

To see what your bot is **currently** using, run:

```bash
python -m src.scripts.setup.system_status
```

The report includes **Trading strategy (bot uses now)** and **Risk limits** with the active values.

