# Copy Trading Strategy Guide

Complete guide to understanding and configuring the copy trading bot's strategy system.

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Strategy Types](#strategy-types)
3. [Position Sizing Logic](#position-sizing-logic)
4. [Multipliers](#multipliers)
5. [Safety Limits](#safety-limits)
6. [Trade Aggregation](#trade-aggregation)
7. [Configuration Examples](#configuration-examples)
8. [Recommended Strategies](#recommended-strategies)
9. [Advanced Configuration](#advanced-configuration)

**→ [TRADING_STRATEGIES_DETAILED.md](TRADING_STRATEGIES_DETAILED.md)** — More detail with step-by-step examples, exact calculations, and ready-to-use `.env` snippets for each strategy.

## Strategy Overview

The Polymarket Copy Trading Bot uses a sophisticated strategy system to determine how much capital to allocate when copying trades from followed traders. The strategy system consists of:

1. **Base Strategy** - How to calculate the initial order size
2. **Multipliers** - Optional scaling factors based on trade size
3. **Safety Limits** - Maximum and minimum constraints
4. **Trade Aggregation** - Combining multiple small trades

### How It Works

When a followed trader opens a new position, the bot:

1. **Detects the trade** - Monitors trader activity in real-time
2. **Calculates base size** - Uses your configured strategy to determine initial order size
3. **Applies multiplier** - Scales the order based on trade size (if configured)
4. **Applies limits** - Ensures the order fits within safety constraints
5. **Checks balance** - Verifies sufficient funds are available
6. **Executes order** - Places the trade on Polymarket

## Strategy Types

The bot supports three main strategy types:

### 1. PERCENTAGE Strategy

**Description:** Copy a fixed percentage of the trader's order size.

**Best For:**
- Consistent position sizing relative to trader
- Proportional risk management
- Most common use case

**Configuration:**
```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=10.0  # Copy 10% of trader's order
```

**Example:**
- Trader opens $100 position
- Your order: $100 × 10% = **$10**

**Use Cases:**
- Small to medium balances
- Want proportional exposure
- Following multiple traders

---

### 2. FIXED Strategy

**Description:** Copy a fixed dollar amount regardless of trader's order size.

**Best For:**
- Consistent position sizes
- Risk control
- Small balance management

**Configuration:**
```env
COPY_STRATEGY=FIXED
COPY_SIZE=50.0  # Always copy $50
```

**Example:**
- Trader opens $100 position → Your order: **$50**
- Trader opens $500 position → Your order: **$50**
- Trader opens $10 position → Your order: **$50** (if within limits)

**Use Cases:**
- Limited capital
- Want fixed risk per trade
- Conservative approach

---

### 3. ADAPTIVE Strategy

**Description:** Dynamically adjust percentage based on trader's order size.

**Best For:**
- Large balances
- Sophisticated risk management
- Optimizing position sizes

**How It Works:**
- **Small orders** (< threshold): Use higher percentage
- **Large orders** (> threshold): Use lower percentage
- **Medium orders**: Linear interpolation

**Configuration:**
```env
COPY_STRATEGY=ADAPTIVE
COPY_SIZE=10.0              # Base percentage
ADAPTIVE_MIN_PERCENT=5.0    # Minimum for large orders
ADAPTIVE_MAX_PERCENT=15.0   # Maximum for small orders
ADAPTIVE_THRESHOLD_USD=500.0  # Threshold in USD
```

**Example with threshold = $500:**
- Trader opens $50 order → Your order: ~15% = **$7.50** (higher %)
- Trader opens $500 order → Your order: ~10% = **$50** (base %)
- Trader opens $2000 order → Your order: ~5% = **$100** (lower %)

**Use Cases:**
- Large balances ($2000+)
- Want to scale down on large trades
- Optimize risk/reward

## Position Sizing Logic

The bot calculates order sizes through a multi-step process:

### Step 1: Calculate Base Amount

Based on your strategy:
- **PERCENTAGE**: `base = trader_size × (copy_size / 100)`
- **FIXED**: `base = copy_size`
- **ADAPTIVE**: `base = trader_size × (adaptive_percent / 100)`

### Step 2: Apply Multiplier

If multipliers are configured:
- **Single multiplier**: `amount = base × multiplier`
- **Tiered multipliers**: `amount = base × tier_multiplier` (based on trader's order size)

### Step 3: Apply Maximum Order Size Limit

```python
if amount > MAX_ORDER_SIZE_USD:
    amount = MAX_ORDER_SIZE_USD
```

### Step 4: Apply Maximum Position Size Limit

If configured, ensures total position doesn't exceed limit:
```python
if (current_position + amount) > MAX_POSITION_SIZE_USD:
    amount = MAX_POSITION_SIZE_USD - current_position
```

### Step 5: Check Available Balance

With 1% safety buffer:
```python
max_affordable = balance × 0.99
if amount > max_affordable:
    amount = max_affordable
```

### Step 6: Check Minimum Order Size

```python
if amount < MIN_ORDER_SIZE_USD:
    # Order too small, may be skipped
    amount = MIN_ORDER_SIZE_USD
```

## Multipliers

Multipliers allow you to scale orders based on trade size. Two types are supported:

### Single Multiplier

Simple scaling factor applied to all trades.

**Configuration:**
```env
TRADE_MULTIPLIER=2.0  # 2x all orders
```

**Example:**
- Base order: $10
- With 2.0x multiplier: **$20**

**Use Cases:**
- Simple scaling
- Uniform amplification
- Quick configuration

---

### Tiered Multipliers

Different multipliers based on trader's order size. More sophisticated risk management.

**Configuration:**
```env
TIERED_MULTIPLIERS=1-10:2.0,10-100:1.0,100-500:0.5,500+:0.2
```

**Format:** `min-max:multiplier` or `min+:multiplier`

**Example Breakdown:**
- `1-10:2.0` - Orders $1-$10: 2x multiplier
- `10-100:1.0` - Orders $10-$100: 1x multiplier (no change)
- `100-500:0.5` - Orders $100-$500: 0.5x multiplier (half size)
- `500+:0.2` - Orders $500+: 0.2x multiplier (20% size)

**Example Calculation:**
- Trader opens $5 order
  - Base: $5 × 10% = $0.50
  - Tier: 1-10 → 2.0x multiplier
  - Final: $0.50 × 2.0 = **$1.00**

- Trader opens $200 order
  - Base: $200 × 10% = $20
  - Tier: 100-500 → 0.5x multiplier
  - Final: $20 × 0.5 = **$10.00**

- Trader opens $1000 order
  - Base: $1000 × 10% = $100
  - Tier: 500+ → 0.2x multiplier
  - Final: $100 × 0.2 = **$20.00**

**Use Cases:**
- Risk management for large trades
- Scaling down on big positions
- Conservative approach to large orders

## Safety Limits

Safety limits protect your capital and prevent overexposure:

### Maximum Order Size

**Purpose:** Prevent single orders from being too large

**Configuration:**
```env
MAX_ORDER_SIZE_USD=100.0  # No single order > $100
```

**Example:**
- Calculated order: $150
- After limit: **$100** (capped)

---

### Minimum Order Size

**Purpose:** Avoid dust trades that cost more in gas than value

**Configuration:**
```env
MIN_ORDER_SIZE_USD=1.0  # No orders < $1
```

**Example:**
- Calculated order: $0.50
- Result: Order skipped (below minimum)

---

### Maximum Position Size

**Purpose:** Limit total exposure to a single market/position

**Configuration:**
```env
MAX_POSITION_SIZE_USD=500.0  # Max $500 per position
```

**Example:**
- Current position: $450
- New order: $100
- After limit: **$50** (reduced to fit limit)

---

### Maximum Daily Volume

**Purpose:** Limit total trading volume per day

**Configuration:**
```env
MAX_DAILY_VOLUME_USD=1000.0  # Max $1000 traded per day
```

**Note:** Currently tracked but not enforced in execution (planned feature)

## Trade Aggregation

Trade aggregation combines multiple small trades into larger, more efficient orders.

### How It Works

1. **Collect trades** - Small trades are collected in a buffer
2. **Group by criteria** - Same trader, market, side (BUY/SELL)
3. **Wait for window** - Accumulate trades within time window
4. **Execute aggregate** - Place single larger order

### Configuration

```env
TRADE_AGGREGATION_ENABLED=true
TRADE_AGGREGATION_WINDOW_SECONDS=30  # 30 second window
```

### Example

**Without Aggregation:**
- Trade 1: $2 (executed immediately)
- Trade 2: $3 (executed immediately)
- Trade 3: $1 (executed immediately)
- **Total gas fees:** 3 × gas cost

**With Aggregation:**
- Trade 1: $2 (buffered)
- Trade 2: $3 (buffered)
- Trade 3: $1 (buffered)
- After 30s: Single order $6
- **Total gas fees:** 1 × gas cost

**Benefits:**
- Lower gas costs
- Better execution prices
- Reduced transaction count

**When to Use:**
- Following active traders
- Many small trades
- Want to optimize costs

## Configuration Examples

### Example 1: Conservative Small Balance

**Balance:** $200
**Goal:** Safe, controlled trading

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=5.0
TRADE_MULTIPLIER=1.0
MAX_ORDER_SIZE_USD=20.0
MIN_ORDER_SIZE_USD=1.0
MAX_POSITION_SIZE_USD=50.0
TRADE_AGGREGATION_ENABLED=true
```

**Result:**
- Copy 5% of trader orders
- Max $20 per order
- Max $50 per position
- Aggregates small trades

---

### Example 2: Balanced Medium Balance

**Balance:** $1000
**Goal:** Balanced growth

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=10.0
TRADE_MULTIPLIER=1.0
MAX_ORDER_SIZE_USD=50.0
MIN_ORDER_SIZE_USD=1.0
MAX_POSITION_SIZE_USD=200.0
TRADE_AGGREGATION_ENABLED=true
```

**Result:**
- Copy 10% of trader orders
- Max $50 per order
- Max $200 per position
- Good balance of risk/reward

---

### Example 3: Aggressive with Multiplier

**Balance:** $2000
**Goal:** Amplified returns

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=10.0
TRADE_MULTIPLIER=2.0
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
MAX_POSITION_SIZE_USD=500.0
TRADE_AGGREGATION_ENABLED=false
```

**Result:**
- Copy 10% of trader orders
- 2x multiplier = 20% effective
- Max $100 per order
- Faster execution (no aggregation)

---

### Example 4: Sophisticated Large Balance

**Balance:** $5000
**Goal:** Optimized risk management

```env
COPY_STRATEGY=ADAPTIVE
COPY_SIZE=10.0
ADAPTIVE_MIN_PERCENT=5.0
ADAPTIVE_MAX_PERCENT=15.0
ADAPTIVE_THRESHOLD_USD=500.0
TIERED_MULTIPLIERS=1-10:2.0,10-100:1.0,100-500:0.5,500+:0.2
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
MAX_POSITION_SIZE_USD=1000.0
TRADE_AGGREGATION_ENABLED=true
```

**Result:**
- Adaptive percentage (5-15%)
- Tiered multipliers
- Scales down on large trades
- Sophisticated risk management

---

### Example 5: Fixed Amount Strategy

**Balance:** $500
**Goal:** Consistent position sizes

```env
COPY_STRATEGY=FIXED
COPY_SIZE=25.0
MAX_ORDER_SIZE_USD=25.0
MIN_ORDER_SIZE_USD=1.0
MAX_POSITION_SIZE_USD=100.0
TRADE_AGGREGATION_ENABLED=true
```

**Result:**
- Always $25 per trade
- Predictable risk
- Simple to understand

## Recommended Strategies

### Small Balance (< $500)

**Recommended:** Conservative PERCENTAGE

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=5.0
MAX_ORDER_SIZE_USD=20.0
MAX_POSITION_SIZE_USD=50.0
TRADE_AGGREGATION_ENABLED=true
```

**Rationale:**
- Low risk per trade
- Preserves capital
- Aggregation saves gas

---

### Medium Balance ($500 - $2000)

**Recommended:** Balanced PERCENTAGE

```env
COPY_STRATEGY=PERCENTAGE
COPY_SIZE=10.0
MAX_ORDER_SIZE_USD=50.0
MAX_POSITION_SIZE_USD=200.0
TRADE_AGGREGATION_ENABLED=true
```

**Rationale:**
- Good risk/reward balance
- Room for growth
- Efficient execution

---

### Large Balance ($2000+)

**Recommended:** ADAPTIVE with Tiered Multipliers

```env
COPY_STRATEGY=ADAPTIVE
COPY_SIZE=10.0
ADAPTIVE_MIN_PERCENT=5.0
ADAPTIVE_MAX_PERCENT=15.0
ADAPTIVE_THRESHOLD_USD=500.0
TIERED_MULTIPLIERS=1-10:2.0,10-100:1.0,100-500:0.5,500+:0.2
MAX_ORDER_SIZE_USD=100.0
MAX_POSITION_SIZE_USD=1000.0
```

**Rationale:**
- Optimizes position sizes
- Scales down on large trades
- Sophisticated risk management

## Advanced Configuration

### Combining Strategies

You can combine multiple features:

```env
# Adaptive strategy
COPY_STRATEGY=ADAPTIVE
COPY_SIZE=10.0
ADAPTIVE_MIN_PERCENT=5.0
ADAPTIVE_MAX_PERCENT=15.0

# Tiered multipliers
TIERED_MULTIPLIERS=1-10:2.0,10-100:1.0,100-500:0.5,500+:0.2

# Safety limits
MAX_ORDER_SIZE_USD=100.0
MIN_ORDER_SIZE_USD=1.0
MAX_POSITION_SIZE_USD=1000.0

# Aggregation
TRADE_AGGREGATION_ENABLED=true
TRADE_AGGREGATION_WINDOW_SECONDS=30
```

### Calculation Flow Example

Let's trace through a complete calculation:

**Input:**
- Trader order: $300
- Your balance: $2000
- Current position: $100
- Strategy: ADAPTIVE (10% base, 5-15% range, $500 threshold)
- Tiered multipliers: 1-10:2.0, 10-100:1.0, 100-500:0.5, 500+:0.2
- Limits: MAX_ORDER=$100, MIN_ORDER=$1, MAX_POSITION=$1000

**Step 1: Calculate adaptive percentage**
- Trader order: $300 < $500 threshold
- Interpolate: ~12% (between 10% base and 15% max)
- Base amount: $300 × 12% = **$36**

**Step 2: Apply tiered multiplier**
- Trader order: $300
- Tier: 100-500 → 0.5x multiplier
- After multiplier: $36 × 0.5 = **$18**

**Step 3: Apply max order limit**
- $18 < $100 limit ✓
- Amount: **$18**

**Step 4: Apply max position limit**
- Current: $100, New: $18, Total: $118
- $118 < $1000 limit ✓
- Amount: **$18**

**Step 5: Check balance**
- Available: $2000 × 0.99 = $1980
- $18 < $1980 ✓
- Amount: **$18**

**Step 6: Check minimum**
- $18 > $1 minimum ✓
- **Final order: $18**

## Best Practices

### 1. Start Conservative

- Begin with small percentages (5-10%)
- Use low multipliers (1.0-1.5x)
- Set strict limits

### 2. Monitor and Adjust

- Track performance regularly
- Adjust based on results
- Scale up gradually

### 3. Use Safety Limits

- Always set MAX_ORDER_SIZE_USD
- Consider MAX_POSITION_SIZE_USD
- Don't skip MIN_ORDER_SIZE_USD

### 4. Enable Aggregation

- Saves gas costs
- Better execution
- Especially for active traders

### 5. Test with Simulations

- Use `simulate_profitability` before live trading
- Test different configurations
- Compare strategies

## Troubleshooting

### Orders Too Small

**Problem:** Orders being skipped due to minimum size

**Solution:**
- Lower MIN_ORDER_SIZE_USD
- Increase COPY_SIZE or multiplier
- Check if balance is sufficient

### Orders Too Large

**Problem:** Orders hitting maximum limits

**Solution:**
- Increase MAX_ORDER_SIZE_USD
- Lower COPY_SIZE or multiplier
- Adjust tiered multipliers

### Not Copying Trades

**Problem:** Bot not executing trades

**Check:**
- Balance sufficient
- Allowance set
- Limits not too restrictive
- Traders are actually trading

### Unexpected Order Sizes

**Problem:** Orders don't match expectations

**Debug:**
- Check strategy configuration
- Verify multiplier settings
- Review limit settings
- Check balance constraints

## Summary

The copy trading strategy system provides:

✅ **Flexible strategies** - PERCENTAGE, FIXED, ADAPTIVE
✅ **Smart multipliers** - Single or tiered
✅ **Safety limits** - Protect your capital
✅ **Trade aggregation** - Optimize execution
✅ **Sophisticated logic** - Multi-step calculation

Choose the strategy that matches your:
- Balance size
- Risk tolerance
- Trading goals
- Experience level

Remember: Start conservative, monitor performance, and adjust gradually!

---

For more information:
- [Getting Started Guide](GETTING_STARTED.md)
- [Command Reference](COMMAND_REFERENCE.md)
- [Examples](EXAMPLES.md)

