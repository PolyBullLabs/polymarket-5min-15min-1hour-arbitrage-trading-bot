# Command Reference Guide

Complete reference for all available commands in the Polymarket Copy Trading Bot.

## Table of Contents

1. [Setup & Configuration](#setup--configuration)
2. [Main Bot](#main-bot)
3. [Wallet Management](#wallet-management)
4. [Position Management](#position-management)
5. [Trader Research](#trader-research)
6. [Simulation & Analysis](#simulation--analysis)
7. [Quick Reference](#quick-reference)

## Setup & Configuration

### Interactive Setup Wizard

```bash
python -m src.scripts.setup.setup
```

**Purpose:** Guided configuration wizard to create `.env` file

**What it does:**
- Prompts for all required configuration
- Validates inputs (addresses, keys, etc.)
- Creates `.env` file with your settings
- Provides helpful defaults

**When to use:**
- First-time setup
- Changing configuration
- Adding new traders

**Example:**
```bash
$ python -m src.scripts.setup.setup

[INFO] Starting setup wizard...
Enter MongoDB URI: mongodb+srv://user:pass@cluster.mongodb.net/
Enter RPC URL: https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
...
[OK] Setup complete!
```

---

### System Status Check

```bash
python -m src.scripts.setup.system_status
```

**Purpose:** Verify system configuration and connections

**What it checks:**
- ✅ MongoDB connection
- ✅ RPC endpoint connectivity
- ✅ Wallet balance (USDC and MATIC)
- ✅ CLOB API accessibility
- ✅ Trader addresses validity

**When to use:**
- Before starting the bot
- Troubleshooting connection issues
- Verifying configuration changes

**Example Output:**
```
[✓] MongoDB: Connected successfully
[✓] RPC: Connected to Polygon network
[✓] Wallet Balance: 100.50 USDC, 1.25 MATIC
[✓] CLOB API: Accessible
[✓] Traders: 2 addresses configured
```

---

### Help Command

```bash
python -m src.scripts.setup.help
```

**Purpose:** Display all available commands and usage

**What it shows:**
- All available commands
- Command categories
- Quick start guide
- Important reminders

**When to use:**
- Learning available commands
- Quick reference
- Getting started

---

## Main Bot

### Start Trading Bot

```bash
python -m src.main
```

**Purpose:** Start the copy trading bot

**What it does:**
- Connects to MongoDB
- Initializes CLOB client
- Starts monitoring trader activity
- Executes trades automatically

**When to use:**
- After setup is complete
- To start copying trades
- Resume trading after stopping

**Example:**
```bash
$ python -m src.main

========================================
  POLYMARKET COPY TRADING BOT
========================================

[INFO] Connecting to MongoDB...
[OK] Connected to database
[INFO] Monitoring traders: 0xABC..., 0xDEF...
[INFO] Bot is running. Press Ctrl+C to stop.
```

**Stopping:** Press `Ctrl+C` for graceful shutdown

---

## Wallet Management

### Check Proxy Wallet

```bash
python -m src.scripts.wallet.check_proxy_wallet
```

**Purpose:** Check proxy wallet balance and positions

**What it shows:**
- USDC balance
- MATIC balance
- Active positions
- Recent activity

**When to use:**
- Verify wallet funding
- Check current positions
- Monitor balance changes

---

### Check Both Wallets

```bash
python -m src.scripts.wallet.check_both_wallets <address1> <address2>
```

**Purpose:** Compare two wallet addresses

**What it shows:**
- Balance comparison
- Position comparison
- Activity comparison

**When to use:**
- Comparing trader vs your wallet
- Analyzing different wallets
- Research purposes

**Example:**
```bash
python -m src.scripts.wallet.check_both_wallets 0xABC... 0xDEF...
```

---

### Check My Stats

```bash
python -m src.scripts.wallet.check_my_stats
```

**Purpose:** View comprehensive wallet statistics

**What it shows:**
- Total balance
- Active positions
- P&L summary
- Trading statistics
- Recent activity summary

**When to use:**
- Regular performance check
- Quick status overview
- Monitoring progress

---

### Check Recent Activity

```bash
python -m src.scripts.wallet.check_recent_activity
```

**Purpose:** View recent trading activity

**What it shows:**
- Recent trades
- Position opens/closes
- Timestamps
- Market information

**When to use:**
- Verify bot is working
- Review recent trades
- Debugging

---

### Check Positions Detailed

```bash
python -m src.scripts.wallet.check_positions_detailed
```

**Purpose:** View detailed position information

**What it shows:**
- All open positions
- Position details (market, outcome, size)
- Current value
- P&L per position

**When to use:**
- Detailed position analysis
- Managing positions
- Review before closing

---

### Check P&L Discrepancy

```bash
python -m src.scripts.wallet.check_pnl_discrepancy
```

**Purpose:** Analyze P&L discrepancies

**What it shows:**
- Expected vs actual P&L
- Discrepancy analysis
- Potential issues

**When to use:**
- Verifying bot accuracy
- Debugging P&L issues
- Performance audit

---

### Verify Allowance

```bash
python -m src.scripts.wallet.verify_allowance
```

**Purpose:** Verify USDC token allowance

**What it shows:**
- Current allowance
- Required allowance
- Approval status

**When to use:**
- Before starting bot
- Troubleshooting trade failures
- After changing wallet

---

### Check Allowance

```bash
python -m src.scripts.wallet.check_allowance
```

**Purpose:** Check and set USDC allowance

**What it does:**
- Checks current allowance
- Prompts to set if insufficient
- Guides through approval process

**When to use:**
- Initial setup
- After allowance expires
- Setting new allowance

**Example:**
```bash
$ python -m src.scripts.wallet.check_allowance

Current allowance: 0 USDC
Required: 1000 USDC
[?] Set allowance? (y/n): y
[INFO] Approving USDC...
[OK] Allowance set successfully
```

---

### Set Token Allowance

```bash
python -m src.scripts.wallet.set_token_allowance
```

**Purpose:** Set ERC1155 token allowance

**What it does:**
- Sets allowance for Polymarket tokens
- Required for position management

**When to use:**
- Before selling positions
- Before closing positions
- Position management setup

---

### Find My EOA

```bash
python -m src.scripts.wallet.find_my_eoa
```

**Purpose:** Find and analyze EOA wallet

**What it shows:**
- EOA wallet address
- Wallet type
- Associated addresses

**When to use:**
- Understanding wallet structure
- Troubleshooting
- Research

---

### Find Gnosis Safe Proxy

```bash
python -m src.scripts.wallet.find_gnosis_safe_proxy
```

**Purpose:** Find Gnosis Safe proxy wallet

**What it shows:**
- Proxy wallet address
- Safe address
- Wallet structure

**When to use:**
- Using Gnosis Safe
- Multi-sig setups
- Advanced wallet management

---

## Position Management

⚠️ **Note:** These commands require full CLOB client implementation.

### Manual Sell

```bash
python -m src.scripts.position.manual_sell <market_id> <outcome> <amount>
```

**Purpose:** Manually sell a specific position

**Parameters:**
- `market_id`: Market identifier
- `outcome`: Outcome to sell (YES/NO)
- `amount`: Amount to sell

**When to use:**
- Manual position management
- Emergency exits
- Partial position closure

---

### Sell Large Positions

```bash
python -m src.scripts.position.sell_large_positions
```

**Purpose:** Sell large positions automatically

**What it does:**
- Identifies large positions
- Sells them automatically
- Risk management

**When to use:**
- Risk reduction
- Portfolio rebalancing
- Automated position management

---

### Close Stale Positions

```bash
python -m src.scripts.position.close_stale_positions
```

**Purpose:** Close stale/old positions

**What it does:**
- Finds old positions
- Closes them automatically
- Cleanup tool

**When to use:**
- Portfolio cleanup
- Removing old positions
- Maintenance

---

### Close Resolved Positions

```bash
python -m src.scripts.position.close_resolved_positions
```

**Purpose:** Close resolved market positions

**What it does:**
- Finds resolved markets
- Closes positions
- Collects winnings

**When to use:**
- After markets resolve
- Collecting winnings
- Cleanup

---

### Redeem Resolved Positions

```bash
python -m src.scripts.position.redeem_resolved_positions
```

**Purpose:** Redeem resolved positions

**What it does:**
- Redeems winning positions
- Collects payouts
- Blockchain interaction

**When to use:**
- After markets resolve
- Collecting payouts
- Final settlement

---

## Trader Research

### Find Best Traders

```bash
python -m src.scripts.research.find_best_traders
```

**Purpose:** Find best performing traders

**What it shows:**
- Top traders by ROI
- Performance metrics
- Trading statistics
- Ranking table

**When to use:**
- Finding traders to copy
- Research
- Performance analysis

**Example Output:**
```
Rank | Address          | ROI    | Win Rate | P&L
-----|------------------|--------|----------|-----
1    | 0x7c3d...        | 45.2%  | 62.5%    | $1,234
2    | 0x6bab...        | 38.7%  | 58.3%    | $987
```

---

### Find Low Risk Traders

```bash
python -m src.scripts.research.find_low_risk_traders
```

**Purpose:** Find low-risk traders with good metrics

**What it shows:**
- Low-risk traders
- Risk metrics (Sharpe, drawdown)
- Conservative performers
- Filtered by risk criteria

**When to use:**
- Conservative strategy
- Risk-averse trading
- Stable performers

---

### Scan Best Traders

```bash
python -m src.scripts.research.scan_best_traders
```

**Purpose:** Scan and analyze top traders

**What it does:**
- Scans active markets
- Identifies top traders
- Analyzes performance
- Generates report

**When to use:**
- Market research
- Finding active traders
- Performance discovery

---

### Scan Traders from Markets

```bash
python -m src.scripts.research.scan_traders_from_markets
```

**Purpose:** Scan traders from active markets

**What it does:**
- Scans active markets
- Extracts trader addresses
- Analyzes activity
- Generates list

**When to use:**
- Market-based discovery
- Finding active traders
- Research

---

## Simulation & Analysis

### Simulate Profitability

```bash
python -m src.scripts.simulation.simulate_profitability
```

**Purpose:** Simulate profitability for a trader

**What it does:**
- Fetches trader history
- Simulates copying trades
- Calculates ROI, P&L
- Generates report

**When to use:**
- Before copying a trader
- Performance testing
- Strategy validation

**Example:**
```bash
$ python -m src.scripts.simulation.simulate_profitability

Enter trader address: 0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b
Simulating 30 days...
[OK] Simulation complete
ROI: 12.5%
Total P&L: $125.50
Win Rate: 58.3%
```

---

### Simulate Profitability (Old Logic)

```bash
python -m src.scripts.simulation.simulate_profitability_old
```

**Purpose:** Old simulation algorithm (legacy)

**What it does:**
- Uses legacy simulation logic
- Different position sizing
- Historical comparison

**When to use:**
- Comparing algorithms
- Historical analysis
- Legacy testing

---

### Run Simulations

```bash
python -m src.scripts.simulation.run_simulations [preset] [options]
```

**Purpose:** Run comprehensive batch simulations

**Presets:**
- `quick` - 7 days, 2 multipliers
- `standard` - 30 days, 3 multipliers (recommended)
- `full` - 90 days, 4 multipliers
- `custom` - Custom parameters

**When to use:**
- Comprehensive testing
- Multiple traders
- Strategy comparison

**Examples:**
```bash
# Quick simulation
python -m src.scripts.simulation.run_simulations quick

# Standard simulation
python -m src.scripts.simulation.run_simulations standard

# Custom simulation
python -m src.scripts.simulation.run_simulations custom 0xABC... 30 2.0
```

---

### Compare Results

```bash
python -m src.scripts.simulation.compare_results [mode] [options]
```

**Purpose:** Compare simulation results

**Modes:**
- (no args) - Show all results
- `best [N]` - Show top N results
- `worst [N]` - Show worst N results
- `stats` - Aggregate statistics
- `detail <name>` - Detailed view

**When to use:**
- Analyzing simulations
- Finding best strategies
- Performance comparison

**Examples:**
```bash
# Show all results
python -m src.scripts.simulation.compare_results

# Show top 5
python -m src.scripts.simulation.compare_results best 5

# Detailed view
python -m src.scripts.simulation.compare_results detail std_m2p0
```

---

### Aggregate Results

```bash
python -m src.scripts.simulation.aggregate_results
```

**Purpose:** Aggregate trading results across strategies

**What it does:**
- Scans result directories
- Aggregates statistics
- Generates summary report
- Saves to `strategy_factory_results/`

**When to use:**
- Comprehensive analysis
- Strategy comparison
- Performance summary

---

### Audit Copy Trading

```bash
python -m src.scripts.simulation.audit_copy_trading
```

**Purpose:** Audit copy trading algorithm performance

**What it does:**
- Simulates trading
- Compares with actual bot
- Identifies discrepancies
- Generates audit report

**When to use:**
- Performance verification
- Algorithm validation
- Debugging

---

### Fetch Historical Trades

```bash
python -m src.scripts.simulation.fetch_historical_trades
```

**Purpose:** Fetch and cache historical trade data

**What it does:**
- Fetches trader history
- Caches to `trader_data_cache/`
- Supports parallel processing
- Handles rate limiting

**When to use:**
- Data collection
- Pre-caching for simulations
- Historical analysis

**Options:**
- `--force` - Force refresh (bypass cache)
- `--days N` - Number of days to fetch

---

## Quick Reference

### Most Common Commands

```bash
# Setup
python -m src.scripts.setup.setup              # Initial setup
python -m src.scripts.setup.system_status       # Check status

# Trading
python -m src.main                              # Start bot

# Monitoring
python -m src.scripts.wallet.check_my_stats     # View stats
python -m src.scripts.wallet.check_recent_activity # Recent trades

# Research
python -m src.scripts.research.find_best_traders # Find traders
python -m src.scripts.simulation.simulate_profitability # Test trader
```

### Command Categories

| Category | Commands |
|----------|----------|
| Setup | `setup.setup`, `setup.system_status`, `setup.help` |
| Wallet | `wallet.check_*`, `wallet.verify_*`, `wallet.find_*` |
| Position | `position.manual_sell`, `position.close_*`, `position.redeem_*` |
| Research | `research.find_*`, `research.scan_*` |
| Simulation | `simulation.simulate_*`, `simulation.run_*`, `simulation.compare_*` |

### Getting Help

```bash
# View all commands
python -m src.scripts.setup.help

# Check system status
python -m src.scripts.setup.system_status
```

---

For more detailed information, see:
- [Getting Started Guide](GETTING_STARTED.md)
- [Examples](EXAMPLES.md)
- [Advanced Features](ADVANCED_FEATURES.md)

