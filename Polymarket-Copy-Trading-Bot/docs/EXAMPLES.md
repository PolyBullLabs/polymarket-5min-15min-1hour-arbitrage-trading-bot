# Usage Examples

Practical examples for common tasks with the Polymarket Copy Trading Bot.

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Finding and Adding Traders](#finding-and-adding-traders)
3. [Running Simulations](#running-simulations)
4. [Monitoring and Analysis](#monitoring-and-analysis)
5. [Troubleshooting Examples](#troubleshooting-examples)

## Initial Setup

### Complete First-Time Setup

```bash
# 1. Clone and install
git clone https://github.com/sinusflow/copy-trading-bot-hub.git
cd copy-trading-bot-hub/Polymarket-Copy-Trading-Bot
pip install -r requirements.txt

# 2. Run setup wizard
python -m src.scripts.setup.setup

# 3. Verify configuration
python -m src.scripts.setup.system_status

# 4. Check wallet and set allowance
python -m src.scripts.wallet.check_my_stats
python -m src.scripts.wallet.check_allowance

# 5. Start the bot
python -m src.main
```

### Setting Up with Specific Traders

```bash
# 1. Find good traders first
python -m src.scripts.research.find_best_traders

# 2. Simulate their performance
python -m src.scripts.simulation.simulate_profitability
# Enter trader address when prompted

# 3. If satisfied, add to .env
# Edit .env file:
# USER_ADDRESSES=0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b,0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292

# 4. Restart bot
python -m src.main
```

## Finding and Adding Traders

### Example 1: Find Top Performers

```bash
# Find best traders by ROI
python -m src.scripts.research.find_best_traders

# Output:
# Rank | Address          | ROI    | Win Rate | P&L
# -----|------------------|--------|----------|-----
# 1    | 0x7c3d...        | 45.2%  | 62.5%    | $1,234
# 2    | 0x6bab...        | 38.7%  | 58.3%    | $987
```

### Example 2: Find Low-Risk Traders

```bash
# Find conservative traders
python -m src.scripts.research.find_low_risk_traders

# Output shows:
# - Sharpe ratio
# - Max drawdown
# - Volatility
# - Win rate
```

### Example 3: Scan Active Markets

```bash
# Discover traders from active markets
python -m src.scripts.research.scan_traders_from_markets

# Output:
# Found 25 active traders
# Top 5 by activity:
# 1. 0xABC... - 45 trades today
# 2. 0xDEF... - 32 trades today
```

### Example 4: Test Before Adding

```bash
# Simulate copying a trader
python -m src.scripts.simulation.simulate_profitability

# Enter: 0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b
# Days: 30
# Multiplier: 1.0

# Output:
# Simulating 30 days of trading...
# [OK] Simulation complete
# 
# Results:
# - ROI: 12.5%
# - Total P&L: $125.50
# - Win Rate: 58.3%
# - Max Drawdown: 8.2%
# - Sharpe Ratio: 1.45
```

## Running Simulations

### Example 1: Quick Simulation

```bash
# Run quick 7-day simulation
python -m src.scripts.simulation.run_simulations quick

# Tests:
# - 7 days of history
# - 2 multipliers (1.0, 2.0)
# - Fast results
```

### Example 2: Standard Simulation

```bash
# Run comprehensive 30-day simulation
python -m src.scripts.simulation.run_simulations standard

# Tests:
# - 30 days of history
# - 3 multipliers (0.5, 1.0, 2.0)
# - Recommended for most cases
```

### Example 3: Custom Simulation

```bash
# Custom simulation for specific trader
python -m src.scripts.simulation.run_simulations custom 0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b 30 2.0

# Parameters:
# - Trader: 0x7c3d...
# - Days: 30
# - Multiplier: 2.0
```

### Example 4: Compare Results

```bash
# After running simulations, compare results
python -m src.scripts.simulation.compare_results

# Show top 5
python -m src.scripts.simulation.compare_results best 5

# Detailed view
python -m src.scripts.simulation.compare_results detail std_m2p0
```

## Monitoring and Analysis

### Example 1: Daily Check Routine

```bash
# Morning routine
python -m src.scripts.wallet.check_my_stats
python -m src.scripts.wallet.check_recent_activity
python -m src.scripts.wallet.check_positions_detailed
```

### Example 2: Performance Analysis

```bash
# Check overall performance
python -m src.scripts.wallet.check_my_stats

# Output:
# Wallet Statistics
# ================
# Total Balance: 1,250.50 USDC
# Active Positions: 12
# Total P&L: +$125.50 (+11.1%)
# Win Rate: 58.3%
# Best Position: +$45.20
# Worst Position: -$12.30
```

### Example 3: Compare with Trader

```bash
# Compare your performance with a trader
python -m src.scripts.wallet.check_both_wallets \
  0xYOUR_WALLET \
  0xTRADER_WALLET

# Shows:
# - Balance comparison
# - Position comparison
# - Activity comparison
```

### Example 4: P&L Analysis

```bash
# Check for P&L discrepancies
python -m src.scripts.wallet.check_pnl_discrepancy

# Output:
# P&L Discrepancy Analysis
# =======================
# Expected P&L: $125.50
# Actual P&L: $123.20
# Discrepancy: -$2.30 (-1.8%)
# 
# Possible causes:
# - Slippage
# - Gas fees
# - Timing differences
```

## Troubleshooting Examples

### Example 1: Connection Issues

```bash
# Check system status
python -m src.scripts.setup.system_status

# If MongoDB fails:
# 1. Verify MONGO_URI in .env
# 2. Check IP whitelist in MongoDB Atlas
# 3. Test connection manually

# If RPC fails:
# 1. Verify RPC_URL in .env
# 2. Check API key is valid
# 3. Try different RPC endpoint
```

### Example 2: Balance Issues

```bash
# Check current balance
python -m src.scripts.wallet.check_my_stats

# If insufficient USDC:
# 1. Add USDC to wallet
# 2. Verify balance updated
# 3. Check allowance

# If insufficient MATIC:
# 1. Add MATIC for gas
# 2. Recommended: 1-2 MATIC
```

### Example 3: Bot Not Trading

```bash
# Check if traders are active
python -m src.scripts.wallet.check_recent_activity

# Verify trader addresses
python -m src.scripts.setup.system_status

# Check if traders are actually trading
# Visit Polymarket and check their activity

# Verify bot is running
# Check logs: logs/bot-YYYY-MM-DD.log
```

### Example 4: Allowance Issues

```bash
# Check current allowance
python -m src.scripts.wallet.verify_allowance

# If insufficient, set allowance
python -m src.scripts.wallet.check_allowance

# Follow prompts:
# Current allowance: 0 USDC
# Required: 1000 USDC
# [?] Set allowance? (y/n): y
# [INFO] Approving USDC...
# [OK] Allowance set successfully
```

## Advanced Examples

### Example 1: Batch Simulation Analysis

```bash
# 1. Run multiple simulations
python -m src.scripts.simulation.run_simulations standard

# 2. Aggregate results
python -m src.scripts.simulation.aggregate_results

# 3. Compare strategies
python -m src.scripts.simulation.compare_results stats
```

### Example 2: Pre-caching Historical Data

```bash
# Fetch historical data for multiple traders
python -m src.scripts.simulation.fetch_historical_trades

# Data is cached to trader_data_cache/
# Speeds up future simulations
```

### Example 3: Audit Bot Performance

```bash
# Audit copy trading algorithm
python -m src.scripts.simulation.audit_copy_trading

# Compares:
# - Simulated results
# - Actual bot performance
# - Identifies discrepancies
```

### Example 4: Multi-Trader Strategy

```bash
# 1. Find multiple good traders
python -m src.scripts.research.find_best_traders
python -m src.scripts.research.find_low_risk_traders

# 2. Test each one
python -m src.scripts.simulation.simulate_profitability
# Test trader 1
python -m src.scripts.simulation.simulate_profitability
# Test trader 2

# 3. Add best performers to .env
# USER_ADDRESSES=0xTRADER1,0xTRADER2,0xTRADER3

# 4. Start bot with diversified traders
python -m src.main
```

## Workflow Examples

### Daily Trading Workflow

```bash
# Morning (9 AM)
python -m src.scripts.wallet.check_my_stats
python -m src.scripts.wallet.check_recent_activity

# Start bot
python -m src.main

# Evening (6 PM)
# Stop bot (Ctrl+C)
python -m src.scripts.wallet.check_my_stats
python -m src.scripts.wallet.check_positions_detailed
```

### Weekly Review Workflow

```bash
# Monday: Review performance
python -m src.scripts.wallet.check_my_stats
python -m src.scripts.wallet.check_pnl_discrepancy

# Tuesday: Research new traders
python -m src.scripts.research.find_best_traders
python -m src.scripts.research.scan_traders_from_markets

# Wednesday: Test new traders
python -m src.scripts.simulation.simulate_profitability

# Thursday: Update configuration if needed
python -m src.scripts.setup.setup

# Friday: Run comprehensive analysis
python -m src.scripts.simulation.run_simulations standard
python -m src.scripts.simulation.compare_results
```

### Monthly Analysis Workflow

```bash
# 1. Run full simulation
python -m src.scripts.simulation.run_simulations full

# 2. Aggregate all results
python -m src.scripts.simulation.aggregate_results

# 3. Audit bot performance
python -m src.scripts.simulation.audit_copy_trading

# 4. Review and optimize
python -m src.scripts.simulation.compare_results stats
```

---

For more information:
- [Getting Started Guide](GETTING_STARTED.md)
- [Command Reference](COMMAND_REFERENCE.md)
- [Advanced Features](ADVANCED_FEATURES.md)

