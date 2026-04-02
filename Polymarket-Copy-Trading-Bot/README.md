# Polymarket Copy Trading Bot - Python Edition

Part of [copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub). Bugs, features, and questions: use [Issues](https://github.com/sinusflow/copy-trading-bot-hub/issues).

> Automated copy trading bot for Polymarket that mirrors trades from top performers with intelligent position sizing and real-time execution.

[![License: ISC](https://img.shields.io/badge/License-ISC-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-brightgreen.svg)](https://www.python.org/)

## Overview

This is the Python version of the Polymarket Copy Trading Bot. It automatically replicates trades from successful Polymarket traders to your wallet. It monitors trader activity 24/7, calculates proportional position sizes based on your capital, and executes matching orders in real-time.

### How It Works

1. **Select Traders** - Choose top performers from [Polymarket leaderboard](https://polymarket.com/leaderboard) or [Predictfolio](https://predictfolio.com)
2. **Monitor Activity** - Bot continuously watches for new positions opened by selected traders using Polymarket Data API
3. **Calculate Size** - Automatically scales trades based on your balance vs. trader's balance
4. **Execute Orders** - Places matching orders on Polymarket using your wallet
5. **Track Performance** - Maintains complete trade history in MongoDB

## Quick Start

### Prerequisites

- Python 3.10+
- MongoDB database ([MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) free tier works)
- Polygon wallet with USDC and POL/MATIC for gas
- RPC endpoint ([Infura](https://infura.io) or [Alchemy](https://www.alchemy.com) free tier)

### Installation

```bash
# Clone the hub and enter this bot
git clone https://github.com/sinusflow/copy-trading-bot-hub.git
cd copy-trading-bot-hub/Polymarket-Copy-Trading-Bot

# Install dependencies
pip install -r requirements.txt

# Run interactive setup wizard
python -m src.scripts.setup.setup

# Verify system status
python -m src.scripts.setup.system_status

# Start trading bot
python -m src.main
```

📖 **For detailed setup instructions, see [Getting Started Guide](docs/GETTING_STARTED.md)**

## Available Commands

### Setup & Configuration
```bash
python -m src.scripts.setup.setup              # Interactive setup wizard
python -m src.scripts.setup.system_status       # Verify system status and configuration
python -m src.scripts.setup.help              # Display all available commands
```

### Main Bot
```bash
python -m src.main                       # Start the copy trading bot
```

### Wallet Management
```bash
python -m src.scripts.wallet.check_proxy_wallet        # Check proxy and main wallet activity
python -m src.scripts.wallet.check_both_wallets        # Compare two wallet addresses
python -m src.scripts.wallet.check_my_stats            # View wallet statistics
python -m src.scripts.wallet.check_recent_activity     # Check recent trading activity
python -m src.scripts.wallet.check_positions_detailed  # View detailed position information
python -m src.scripts.wallet.check_pnl_discrepancy     # Check P&L discrepancy analysis
python -m src.scripts.wallet.verify_allowance         # Verify USDC token allowance
python -m src.scripts.wallet.check_allowance          # Check and set USDC allowance
python -m src.scripts.wallet.set_token_allowance      # Set ERC1155 token allowance
python -m src.scripts.wallet.find_my_eoa              # Find and analyze EOA wallet
python -m src.scripts.wallet.find_gnosis_safe_proxy   # Find Gnosis Safe proxy wallet
```

### Position Management (⚠️ Requires CLOB Client Implementation)
```bash
# Note: These scripts exist but require full CLOB client implementation
python -m src.scripts.position.manual_sell            # Manually sell a specific position
python -m src.scripts.position.sell_large_positions   # Sell large positions
python -m src.scripts.position.close_stale_positions # Close stale/old positions
python -m src.scripts.position.close_resolved_positions # Close resolved positions
python -m src.scripts.position.redeem_resolved_positions # Redeem resolved positions
```

### Trader Research & Analysis
```bash
python -m src.scripts.research.find_best_traders      # Find best performing traders
python -m src.scripts.research.find_low_risk_traders  # Find low-risk traders with good metrics
python -m src.scripts.research.scan_best_traders      # Scan and analyze top traders
python -m src.scripts.research.scan_traders_from_markets # Scan traders from active markets
```

### Simulation & Backtesting
```bash
python -m src.scripts.simulation.simulate_profitability # Simulate profitability for a trader
python -m src.scripts.simulation.simulate_profitability_old # Old simulation logic
python -m src.scripts.simulation.run_simulations        # Run comprehensive batch simulations
python -m src.scripts.simulation.compare_results        # Compare simulation results
python -m src.scripts.simulation.aggregate_results      # Aggregate trading results across strategies
python -m src.scripts.simulation.audit_copy_trading     # Audit copy trading algorithm
python -m src.scripts.simulation.fetch_historical_trades # Fetch and cache historical trade data
```

## Configuration

### Essential Variables

Create a `.env` file with the following variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `USER_ADDRESSES` | Traders to copy (comma-separated) | `'0xABC..., 0xDEF...'` |
| `PROXY_WALLET` | Your Polygon wallet address | `'0x123...'` |
| `PRIVATE_KEY` | Wallet private key (no 0x prefix) | `'abc123...'` |
| `MONGO_URI` | MongoDB connection string | `'mongodb+srv://...'` |
| `RPC_URL` | Polygon RPC endpoint | `'https://polygon...'` |
| `USDC_CONTRACT_ADDRESS` | USDC contract on Polygon | `'0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'` |
| `CLOB_HTTP_URL` | Polymarket CLOB API URL | `'https://clob.polymarket.com'` |
| `TRADE_MULTIPLIER` | Position size multiplier (default: 1.0) | `2.0` |
| `FETCH_INTERVAL` | Check interval in seconds (default: 1) | `1` |
| `TRADE_AGGREGATION_ENABLED` | Enable trade aggregation (default: false) | `true` |
| `TRADE_AGGREGATION_WINDOW_SECONDS` | Aggregation window (default: 30) | `30` |

### Finding Traders

1. Visit [Polymarket Leaderboard](https://polymarket.com/leaderboard)
2. Look for traders with positive P&L, win rate >55%, and active trading history
3. Verify detailed stats on [Predictfolio](https://predictfolio.com)
4. Add wallet addresses to `USER_ADDRESSES` in `.env`

## Features

- **Multi-Trader Support** - Track and copy trades from multiple traders simultaneously
- **Smart Position Sizing** - Automatically adjusts trade sizes based on your capital
- **Tiered Multipliers** - Apply different multipliers based on trade size
- **Position Tracking** - Accurately tracks purchases and sells even after balance changes
- **Trade Aggregation** - Combines multiple small trades into larger executable orders
- **Real-time Execution** - Monitors trades every second and executes instantly
- **MongoDB Integration** - Persistent storage of all trades and positions
- **Price Protection** - Built-in slippage checks to avoid unfavorable fills
- **Colored Logging** - Beautiful colored console output for better monitoring

## Project Structure

```
polymarket-copy-trading-bot/
│
├── 📄 Configuration Files
│   ├── .env                    # Environment variables (create via setup)
│   ├── .env.example            # Example environment file
│   ├── requirements.txt        # Python dependencies
│   ├── pyproject.toml          # Python project metadata
│   ├── package.json            # Legacy reference (Python project)
│   └── docker-compose.yml      # Docker configuration
│
├── 📚 Documentation
│   ├── README.md               # Main documentation
│   ├── README_PYTHON.md        # This file - Python-specific documentation
│   ├── PYTHON_SCRIPTS_STATUS.md # Script conversion status
│   ├── PROJECT_STRUCTURE.md    # Detailed project structure
│   └── docs/                   # Additional documentation
│       ├── GETTING_STARTED.md
│       ├── QUICK_START.md
│       ├── SIMULATION_GUIDE.md
│       └── ...
│
├── 🐍 Source Code
│   └── src/
│       │
│       ├── 🚀 Entry Point
│       │   └── main.py                    # Main bot entry point
│       │
│       ├── ⚙️ Configuration
│       │   └── config/
│       │       ├── __init__.py
│       │       ├── env.py                 # Environment variable loading & validation
│       │       ├── db.py                  # MongoDB connection management
│       │       └── copy_strategy.py        # Copy trading strategy logic
│       │
│       ├── 📊 Data Models
│       │   └── models/
│       │       ├── __init__.py
│       │       └── user_history.py         # MongoDB models for user activity & positions
│       │
│       ├── 🔌 Type Definitions
│       │   └── interfaces/
│       │       ├── __init__.py
│       │       └── user.py                 # Type definitions (UserActivity, UserPosition)
│       │
│       ├── 🔄 Core Services
│       │   └── services/
│       │       ├── __init__.py
│       │       ├── trade_monitor.py        # Monitor trader activity (RTDS/API polling)
│       │       └── trade_executor.py       # Execute trades based on monitored activity
│       │
│       ├── 🛠️ Utilities
│       │   └── utils/
│       │       ├── __init__.py
│       │       ├── __main__.py
│       │       ├── logger.py               # Colored logging & console output
│       │       ├── fetch_data.py           # HTTP requests with retry logic
│       │       ├── get_my_balance.py       # Get USDC balance from blockchain
│       │       ├── create_clob_client.py   # Create Polymarket CLOB client
│       │       ├── post_order.py           # Calculate & post orders to Polymarket
│       │       └── system_status.py        # System status & diagnostics
│       │
│       └── 📜 Management Scripts
│           └── scripts/
│               ├── __init__.py
│               ├── __main__.py
│               │
│               └── Note: All scripts are located directly in `src/scripts/`.
│                   The organization below is logical grouping by category.
│               │
│               ├── 🔧 Setup & Configuration (setup/)
│               │   ├── setup.py                  # Interactive setup wizard
│               │   ├── system_status.py          # Verify system status & connections
│               │   └── help.py                   # Display all available commands
│               │
│               ├── 💰 Wallet Management (wallet/)
│               │   ├── check_proxy_wallet.py     # Check proxy & main wallet
│               │   ├── check_both_wallets.py     # Compare two wallets
│               │   ├── check_my_stats.py         # View wallet statistics
│               │   ├── check_recent_activity.py  # Check recent trading activity
│               │   ├── check_positions_detailed.py # View detailed positions
│               │   ├── check_pnl_discrepancy.py  # P&L discrepancy analysis
│               │   ├── verify_allowance.py       # Verify USDC allowance
│               │   ├── check_allowance.py         # Check & set USDC allowance
│               │   ├── set_token_allowance.py    # Set ERC1155 token allowance
│               │   ├── find_my_eoa.py            # Find & analyze EOA wallet
│               │   └── find_gnosis_safe_proxy.py # Find Gnosis Safe proxy
│               │
│               ├── 📊 Position Management (position/)
│               │   ├── manual_sell.py           # Manually sell position
│               │   ├── sell_large_positions.py   # Sell large positions
│               │   ├── close_stale_positions.py  # Close stale positions
│               │   ├── close_resolved_positions.py # Close resolved positions
│               │   └── redeem_resolved_positions.py # Redeem resolved positions
│               │   ⚠️  Note: Requires full CLOB client implementation
│               │
│               ├── 🔍 Trader Research (research/)
│               │   ├── find_best_traders.py      # Find best performing traders
│               │   ├── find_low_risk_traders.py  # Find low-risk traders
│               │   ├── scan_best_traders.py      # Scan and analyze top traders
│               │   └── scan_traders_from_markets.py # Scan traders from markets
│               │
│               └── 📈 Simulation & Analysis (simulation/)
│                   ├── simulate_profitability.py # Simulate profitability
│                   ├── simulate_profitability_old.py # Old simulation logic
│                   ├── run_simulations.py        # Run batch simulations
│                   ├── compare_results.py        # Compare simulation results
│                   ├── aggregate_results.py      # Aggregate trading results
│                   ├── audit_copy_trading.py      # Audit copy trading algorithm
│                   └── fetch_historical_trades.py # Fetch historical trade data
│
├── 📁 Runtime Directories
│   ├── logs/                    # Application logs (auto-created)
│   │   └── bot-YYYY-MM-DD.log  # Daily log files
│   │
│   ├── trader_data_cache/       # Cached trader data (auto-created)
│   │   └── {address}_{days}d_{date}.json
│   │
│   ├── simulation_results/      # Simulation results (auto-created)
│   │   └── {strategy}_{trader}_{date}.json
│   │
│   ├── audit_results/           # Audit reports (auto-created)
│   │   └── audit_{timestamp}.json
│   │
│   └── strategy_factory_results/ # Strategy analysis results (auto-created)
│       └── aggregated_results.json
│
└── 🐳 Deployment
    ├── Dockerfile               # Docker image definition
    └── docker-compose.yml       # Docker Compose configuration
```

### Directory Roles

#### **Configuration (`src/config/`)**
- **env.py**: Loads and validates environment variables from `.env` file
- **db.py**: Manages MongoDB connection, database extraction, and connection lifecycle
- **copy_strategy.py**: Implements copy trading logic (position sizing, multipliers, limits)

#### **Data Models (`src/models/`)**
- **user_history.py**: MongoDB collections and models for storing user trading activity and positions

#### **Type Definitions (`src/interfaces/`)**
- **user.py**: Type definitions for UserActivity and UserPosition interfaces

#### **Core Services (`src/services/`)**
- **trade_monitor.py**: Monitors trader activity via RTDS WebSocket or API polling
- **trade_executor.py**: Executes trades based on monitored activity with aggregation support

#### **Utilities (`src/utils/`)**
- **logger.py**: Colored console logging with various log levels
- **fetch_data.py**: Async HTTP requests with retry logic and error handling
- **get_my_balance.py**: Get USDC balance from Polygon blockchain
- **create_clob_client.py**: Create and configure Polymarket CLOB client (needs full implementation)
- **post_order.py**: Calculate order sizes and post orders to Polymarket
- **system_status.py**: System status and diagnostics utilities

#### **Management Scripts (`src/scripts/`)**

**Setup & Configuration:**
- **setup.py**: Interactive setup wizard for initial configuration
- **system_status.py**: Verify system status, connections, and configuration
- **help.py**: Display all available commands and usage information

**Wallet Management:**
- **check_proxy_wallet.py**: Check proxy wallet balance and positions
- **check_both_wallets.py**: Compare two wallet addresses
- **check_my_stats.py**: View trading statistics
- **check_recent_activity.py**: See recent trading activity
- **check_positions_detailed.py**: View detailed position information
- **check_pnl_discrepancy.py**: Check P&L discrepancy analysis
- **verify_allowance.py**: Verify USDC token allowance
- **check_allowance.py**: Check and set USDC allowance
- **set_token_allowance.py**: Set ERC1155 token allowance
- **find_my_eoa.py**: Find and analyze EOA wallet
- **find_gnosis_safe_proxy.py**: Find Gnosis Safe proxy wallet

**Position Management:**
- **manual_sell.py**: Manually sell a specific position
- **sell_large_positions.py**: Sell large positions
- **close_stale_positions.py**: Close stale/old positions
- **close_resolved_positions.py**: Close resolved positions
- **redeem_resolved_positions.py**: Redeem resolved positions
- ⚠️ **Note**: These require full CLOB client implementation

**Trader Research:**
- **find_best_traders.py**: Find best performing traders by ROI and metrics
- **find_low_risk_traders.py**: Find low-risk traders with good risk metrics
- **scan_best_traders.py**: Scan and analyze top traders from markets
- **scan_traders_from_markets.py**: Scan traders from active markets

**Simulation & Analysis:**
- **simulate_profitability.py**: Simulate profitability for a trader
- **simulate_profitability_old.py**: Old simulation logic (legacy algorithm)
- **run_simulations.py**: Run comprehensive batch simulations with presets
- **compare_results.py**: Compare simulation results side-by-side
- **aggregate_results.py**: Aggregate trading results across strategies
- **audit_copy_trading.py**: Audit copy trading algorithm performance
- **fetch_historical_trades.py**: Fetch and cache historical trade data

#### **Entry Point (`src/main.py`)**
- Main application entry point that initializes services and handles graceful shutdown

## Key Differences from TypeScript Version

- **Async/Await**: Python uses `asyncio` for async operations
- **Type System**: Python uses type hints instead of TypeScript types
- **MongoDB**: Uses `pymongo` instead of `mongoose`
- **Web3**: Uses `web3.py` instead of `ethers.js`
- **HTTP Client**: Uses `httpx` instead of `axios`
- **Logging**: Uses `colorama` for colored output
- **Package Management**: Uses `pip` and `requirements.txt` instead of `npm` and `package.json`

## Important Notes

### CLOB Client Implementation

The Polymarket CLOB (Central Limit Order Book) client is a critical component that requires full implementation. The current Python version includes a placeholder structure. For production use, you have two options:

**Implement full Python CLOB client**
   - This requires implementing Polymarket's order signing protocol
   - See the Polymarket documentation for API details
   - The structure is in `src/utils/create_clob_client.py`

## Safety & Risk Management

⚠️ **Important Disclaimers:**

- **Use at your own risk** - This bot executes real trades with real money
- **Start small** - Test with minimal funds before scaling up
- **Diversify** - Don't copy just one trader; track multiple strategies
- **Monitor regularly** - Check bot logs daily to ensure proper execution
- **No guarantees** - Past performance doesn't guarantee future results

### Best Practices

1. Use a dedicated wallet separate from your main funds
2. Only allocate capital you can afford to lose
3. Research traders thoroughly before copying
4. Set up monitoring and alerts
5. Know how to stop the bot quickly (Ctrl+C)
6. Run system status check before starting: `python -m src.scripts.setup.system_status`

## Troubleshooting

### Common Issues

**Missing environment variables** → Run `python -m src.scripts.setup.setup` to create `.env` file

**MongoDB connection failed** → Verify `MONGO_URI`, whitelist IP in MongoDB Atlas

**Bot not detecting trades** → Verify trader addresses and check recent activity

**Insufficient balance** → Add USDC to wallet and ensure POL/MATIC for gas fees

**CLOB client errors** → The CLOB client needs full implementation (see Important Notes above)

**Import errors** → Make sure you're running from the project root directory

**Run system status check:** `python -m src.scripts.setup.system_status`

## Development

### Running Tests

```bash
# Run tests (when implemented)
pytest
```

### Code Style

This project follows PEP 8 style guidelines. Consider using:
- `black` for code formatting
- `flake8` or `pylint` for linting
- `mypy` for type checking

### Dependencies

Key Python packages:
- `web3` - Ethereum/Polygon blockchain interaction
- `pymongo` - MongoDB database operations
- `httpx` - Async HTTP client
- `colorama` - Cross-platform colored terminal output
- `python-dotenv` - Environment variable management
- `asyncio` - Asynchronous programming (built-in)
- `websockets` - WebSocket client for RTDS

See `requirements.txt` for complete list.

## Contributing

Contributions are welcome against [copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub):

1. Fork the hub repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a pull request

## License

ISC License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on [Polymarket CLOB Client](https://github.com/Polymarket/clob-client) (JavaScript SDK)
- Uses [Predictfolio](https://predictfolio.com) for trader analytics
- Powered by Polygon network

---

**Disclaimer:** This software is for educational purposes only. Trading involves risk of loss. You are solely responsible for any financial losses incurred while using this bot.

**Note:** This Python version is a complete conversion from the original TypeScript version. All TypeScript files have been removed. For production use, ensure the CLOB client is fully implemented or use the JavaScript SDK bridge.

**📊 Conversion Status:** See [PYTHON_SCRIPTS_STATUS.md](./PYTHON_SCRIPTS_STATUS.md) for a complete list of converted scripts and their status.

**📁 Project Structure:** See [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) for detailed file and folder organization by role.

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Getting Started Guide](docs/GETTING_STARTED.md)** - Complete step-by-step setup and first run
- **[Strategy Guide](docs/STRATEGY.md)** ⭐ - Understanding copy trading strategy and configuration
- **[Trading Strategies Detailed](docs/TRADING_STRATEGIES_DETAILED.md)** - Step-by-step examples, exact calculations, and ready-to-use `.env` configs
- **[Command Reference](docs/COMMAND_REFERENCE.md)** - Detailed reference for all commands
- **[Usage Examples](docs/EXAMPLES.md)** - Practical examples for common tasks

### Quick Links

- 🚀 [Getting Started](docs/GETTING_STARTED.md) - Start here for first-time setup
- 📊 [Strategy Guide](docs/STRATEGY.md) - Understand how the bot works and configure strategy
- 📋 [Trading Strategies Detailed](docs/TRADING_STRATEGIES_DETAILED.md) - Examples, calculations, copy-paste configs
- 📖 [Command Reference](docs/COMMAND_REFERENCE.md) - All available commands explained
- 💡 [Examples](docs/EXAMPLES.md) - Real-world usage examples
- 📁 [Project Structure](PROJECT_STRUCTURE.md) - File organization
- 📊 [Script Status](PYTHON_SCRIPTS_STATUS.md) - Conversion status
