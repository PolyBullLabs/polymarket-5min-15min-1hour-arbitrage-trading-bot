# Getting Started Guide

Complete step-by-step guide to set up and use the Polymarket Copy Trading Bot.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Initial Setup](#initial-setup)
4. [Configuration](#configuration)
5. [First Run](#first-run)
6. [Finding Traders](#finding-traders)
7. [Running the Bot](#running-the-bot)
8. [Monitoring](#monitoring)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have:

### 1. Python 3.10 or Higher

Check your Python version:
```bash
python --version
# or
python3 --version
```

If you don't have Python 3.10+, download it from [python.org](https://www.python.org/downloads/).

### 2. MongoDB Database

You need a MongoDB database to store trade history. Options:

**Option A: MongoDB Atlas (Recommended - Free Tier Available)**
1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register)
2. Create a free account
3. Create a new cluster (free tier: M0)
4. Create a database user
5. Whitelist your IP address (or use `0.0.0.0/0` for development)
6. Get your connection string: `mongodb+srv://<username>:<password>@cluster.mongodb.net/`

**Option B: Local MongoDB**
```bash
# Install MongoDB locally
# Windows: Download from mongodb.com
# macOS: brew install mongodb-community
# Linux: sudo apt-get install mongodb
```

### 3. Polygon Wallet

You need a Polygon wallet with:
- **USDC** for trading (start with small amounts for testing)
- **POL/MATIC** for gas fees (recommended: 1-2 MATIC)

**Creating a Wallet:**
- Use MetaMask, Trust Wallet, or any Polygon-compatible wallet
- Export your private key (keep it secure!)
- Fund your wallet with USDC and MATIC

### 4. RPC Endpoint

You need a Polygon RPC endpoint. Options:

**Option A: Alchemy (Recommended - Free Tier)**
1. Go to [Alchemy](https://www.alchemy.com)
2. Create a free account
3. Create a new app on Polygon network
4. Copy your HTTP URL: `https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY`

**Option B: Infura (Free Tier)**
1. Go to [Infura](https://infura.io)
2. Create a free account
3. Create a new project
4. Select Polygon network
5. Copy your endpoint: `https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID`

**Option C: Public RPC (Not Recommended for Production)**
- `https://polygon-rpc.com`
- `https://rpc-mainnet.matic.network`

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/sinusflow/copy-trading-bot-hub.git
cd copy-trading-bot-hub/Polymarket-Copy-Trading-Bot
```

### Step 2: Install Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Verify Installation

```bash
# Check Python version
python --version

# Verify packages installed
pip list | grep -E "web3|pymongo|httpx|colorama"
```

## Initial Setup

### Run the Setup Wizard

The interactive setup wizard will guide you through configuration:

```bash
python -m src.scripts.setup.setup
```

The wizard will ask for:

1. **MongoDB URI**
   - Enter your MongoDB connection string
   - Example: `mongodb+srv://user:pass@cluster.mongodb.net/`

2. **RPC URL**
   - Enter your Polygon RPC endpoint
   - Example: `https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY`

3. **Wallet Address**
   - Your Polygon wallet address (0x...)
   - This is where trades will be executed

4. **Private Key**
   - Your wallet's private key (without 0x prefix)
   - ⚠️ **Keep this secure! Never share it!**

5. **USDC Contract Address**
   - Default: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` (Polygon USDC)
   - Press Enter to use default

6. **CLOB HTTP URL**
   - Default: `https://clob.polymarket.com`
   - Press Enter to use default

7. **Trader Addresses**
   - Enter wallet addresses of traders to copy (comma-separated)
   - Example: `0xABC...,0xDEF...`
   - You can add more later

8. **Trade Multiplier**
   - Default: `1.0` (same size as trader)
   - `2.0` = 2x trader's position size
   - `0.5` = half of trader's position size

9. **Fetch Interval**
   - Default: `1` second
   - How often to check for new trades

10. **Trade Aggregation**
    - Enable to combine multiple small trades
    - Default: `false`

The wizard creates a `.env` file with your configuration.

## Configuration

### Environment Variables

Your `.env` file contains all configuration. Here's what each variable does:

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_URI` | MongoDB connection string | `mongodb+srv://...` |
| `RPC_URL` | Polygon RPC endpoint | `https://polygon-mainnet...` |
| `PROXY_WALLET` | Your wallet address | `0x1234...` |
| `PRIVATE_KEY` | Wallet private key | `abc123...` (no 0x) |
| `USDC_CONTRACT_ADDRESS` | USDC contract | `0x2791Bca1f2de4661...` |
| `CLOB_HTTP_URL` | Polymarket CLOB API | `https://clob.polymarket.com` |
| `USER_ADDRESSES` | Traders to copy | `0xABC...,0xDEF...` |
| `TRADE_MULTIPLIER` | Position size multiplier | `1.0` |
| `FETCH_INTERVAL` | Check interval (seconds) | `1` |
| `TRADE_AGGREGATION_ENABLED` | Enable aggregation | `false` |
| `TRADE_AGGREGATION_WINDOW_SECONDS` | Aggregation window | `30` |

### Editing Configuration

You can edit `.env` directly or run the setup wizard again:

```bash
# Edit manually
nano .env  # or use any text editor

# Or run setup again
python -m src.scripts.setup.setup
```

## First Run

### Step 1: Verify System Status

Before starting the bot, verify everything is configured correctly:

```bash
python -m src.scripts.setup.system_status
```

This checks:
- ✅ MongoDB connection
- ✅ RPC endpoint connectivity
- ✅ Wallet balance (USDC and MATIC)
- ✅ CLOB API accessibility
- ✅ Trader addresses validity

**Fix any issues before proceeding!**

### Step 2: Check Wallet Balance

```bash
# Check your wallet statistics
python -m src.scripts.wallet.check_my_stats

# Check USDC balance specifically
python -m src.scripts.wallet.check_proxy_wallet
```

Ensure you have:
- At least 10-50 USDC for testing
- 1-2 MATIC for gas fees

### Step 3: Verify Allowance

The bot needs permission to spend your USDC:

```bash
# Check current allowance
python -m src.scripts.wallet.check_allowance

# If needed, set allowance
python -m src.scripts.wallet.check_allowance
# Follow prompts to approve
```

## Finding Traders

### Method 1: Polymarket Leaderboard

1. Visit [Polymarket Leaderboard](https://polymarket.com/leaderboard)
2. Look for traders with:
   - Positive P&L
   - Win rate > 55%
   - Active trading history
   - Consistent performance
3. Click on a trader to see their wallet address
4. Copy the address (0x...)

### Method 2: Predictfolio

1. Visit [Predictfolio](https://predictfolio.com)
2. Browse top performers
3. Check detailed statistics:
   - ROI
   - Win rate
   - Max drawdown
   - Sharpe ratio
4. Copy wallet addresses

### Method 3: Use Bot Tools

The bot includes tools to find traders:

```bash
# Find best performing traders
python -m src.scripts.research.find_best_traders

# Find low-risk traders
python -m src.scripts.research.find_low_risk_traders

# Scan markets for active traders
python -m src.scripts.research.scan_traders_from_markets
```

### Adding Traders

Add trader addresses to your `.env` file:

```bash
USER_ADDRESSES=0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b,0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292
```

Or use the setup wizard to update.

## Running the Bot

### Start the Bot

```bash
python -m src.main
```

You should see:
- Bot startup banner
- System status check
- Connected to MongoDB
- Monitoring traders...
- Ready to copy trades

### Bot Behavior

The bot will:
1. Monitor trader activity every second
2. Detect new positions opened by tracked traders
3. Calculate position size based on your balance
4. Execute matching orders automatically
5. Log all activity to console and `logs/` directory

### Stopping the Bot

Press `Ctrl+C` to stop gracefully. The bot will:
- Finish current operations
- Close database connections
- Save state
- Exit cleanly

## Monitoring

### Check Recent Activity

```bash
# View recent trades
python -m src.scripts.wallet.check_recent_activity

# View detailed positions
python -m src.scripts.wallet.check_positions_detailed

# Check P&L
python -m src.scripts.wallet.check_pnl_discrepancy
```

### View Statistics

```bash
# Overall wallet statistics
python -m src.scripts.wallet.check_my_stats
```

### Check Logs

Logs are saved in `logs/` directory:

```bash
# View latest log
cat logs/bot-$(date +%Y-%m-%d).log

# Windows PowerShell
Get-Content logs\bot-$(Get-Date -Format "yyyy-MM-dd").log
```

## Troubleshooting

### Common Issues

**1. MongoDB Connection Failed**
```
Error: Failed to connect to MongoDB
```
**Solution:**
- Verify `MONGO_URI` in `.env`
- Check IP whitelist in MongoDB Atlas
- Test connection: `python -m src.scripts.setup.system_status`

**2. RPC Connection Failed**
```
Error: RPC endpoint not responding
```
**Solution:**
- Verify `RPC_URL` in `.env`
- Check API key is valid
- Try a different RPC endpoint

**3. Insufficient Balance**
```
Error: Insufficient USDC balance
```
**Solution:**
- Add USDC to your wallet
- Check balance: `python -m src.scripts.wallet.check_my_stats`
- Ensure you have MATIC for gas

**4. Bot Not Detecting Trades**
```
No trades detected
```
**Solution:**
- Verify trader addresses are correct
- Check traders are actively trading
- Verify `USER_ADDRESSES` in `.env`
- Check recent activity: `python -m src.scripts.wallet.check_recent_activity`

**5. Import Errors**
```
ModuleNotFoundError: No module named 'src'
```
**Solution:**
- Run commands from project root directory
- Ensure you're in the correct directory: `cd polymarket-copy-trading-bot`
- Activate virtual environment if using one

### Getting Help

```bash
# View all available commands
python -m src.scripts.setup.help

# Check system status
python -m src.scripts.setup.system_status
```

### Next Steps

- Read [Command Reference Guide](COMMAND_REFERENCE.md)
- Learn about [Advanced Features](ADVANCED_FEATURES.md)
- See [Examples](EXAMPLES.md)

---

**⚠️ Important Reminders:**
- Start with small amounts to test
- Monitor the bot regularly
- Only trade what you can afford to lose
- Keep your private key secure
- Research traders before copying

