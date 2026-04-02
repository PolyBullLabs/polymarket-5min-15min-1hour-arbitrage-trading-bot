# Four.meme Copy Trading Bot – PancakeSwap & Four.meme

Part of [copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub).

**The open-source Four.meme copy trading bot** for BNB Chain. Automatically mirror target wallets on Four.meme and PancakeSwap in real time. Use this **four.meme copy trading bot** to copy trades from chosen wallets or run a **PancakeSwap copy trading bot**. TypeScript and Rust implementations.

## What is this Four.meme Copy Trading Bot?

This **Four.meme copy trading bot** monitors target wallets on BNB Chain and automatically mirrors their trades on PancakeSwap and **Four.meme**. When they buy or sell on Four.meme, your copy wallets execute the same move. It works as both a **four.meme copy trading bot** and a PancakeSwap copy trading bot, with multiple copy wallets, configurable sizing, slippage, and gas.

### Key Capabilities

- **Multi-DEX Support**: Trade on PancakeSwap (v2) and Four.meme
- **Real-time Monitoring**: WebSocket-based event listening
- **Target Wallet Filtering**: Only mirror trades from whitelisted wallets
- **Multiple Copy Wallets**: Execute trades across multiple wallets simultaneously
- **Configurable Sizing**: Adjust trade sizes by percentage
- **Gas Optimization**: Smart gas price management
- **Error Handling**: Robust error handling and retry logic

## Features

### Core Features

- WebSocket event subscription for real-time trading
- Automatic trade detection and execution
- Multi-wallet support with individual settings
- PancakeSwap router integration (v2)
- Four.meme contract integration
- Automatic token approvals
- Slippage protection
- Gas price management
- Comprehensive logging
- Error recovery and retry mechanisms

### Supported Operations

**PancakeSwap:**
- Token swaps (any pair)
- Native BNB swaps (handles WBNB conversion)

**Four.meme:**
- Token purchase
- Token sale

### Why use this Four.meme copy trading bot?

- **Free and open source** – no paid subscriptions; run your own Four.meme copy trading bot.
- **Real-time** – WebSocket events so your four.meme copy trading bot mirrors trades as fast as the chain.
- **Multi-wallet** – run one Four.meme copy trading bot and copy into several wallets.
- **Dual DEX** – Four.meme + PancakeSwap in one codebase.

Search terms this repo targets: **four.meme copy trading bot**, **four meme copy trading**, **Four.meme copy trading**, **PancakeSwap copy trading**, **BNB Chain copy trading**.

## Architecture

```
Four.meme-Copy-Trading-Bot/
├── typescript-bot/           # TypeScript implementation
│   ├── src/
│   │   ├── core/            # Core bot logic
│   │   ├── pancakeswap/     # PancakeSwap integration
│   │   ├── fourmeme/        # Four.meme integration
│   │   ├── utils/           # Utilities
│   │   └── types/           # TypeScript types
│   ├── tests/               # Test suite
│   ├── package.json
│   └── tsconfig.json
├── rust-bot/                 # Rust implementation
│   ├── src/
│   │   ├── core/            # Core bot logic
│   │   ├── pancakeswap/     # PancakeSwap integration
│   │   ├── fourmeme/        # Four.meme integration
│   │   ├── utils/           # Utilities
│   │   └── types/           # Rust types
│   ├── tests/               # Test suite
│   └── Cargo.toml
├── .env.example             # Environment configuration template
└── README.md               # This file
```

## Quick Start – Run the Four.meme Copy Trading Bot

### Prerequisites

- Node.js 18+ (for TypeScript bot)
- Rust 1.70+ (for Rust bot)
- BNB Chain RPC endpoints (WebSocket + HTTP)
- Wallets funded with BNB for gas

### Installation

**TypeScript Bot:**
```bash
cd typescript-bot
npm install
```

**Rust Bot:**
```bash
cd rust-bot
cargo build --release
```

## TypeScript Bot Setup

### Configuration

Create a `.env` file in the `typescript-bot` directory:

```env
# RPC Endpoints
WS_URL=wss://bsc-mainnet.nodereal.io/ws/v1/YOUR_API_KEY
BSC_RPC_URL=https://bsc-mainnet.nodereal.io/v1/YOUR_API_KEY

# Optional Fallback Endpoints
WS_URL_2=wss://bsc-dataseed.binance.org
BSC_RPC_URL_2=https://bsc-dataseed1.binance.org

# PancakeSwap Contracts
PANCAKE_SWAP_ROUTER_ADDR=0x10ED43C718714eb63d5aA57B78B54704E256024E
PANCAKE_SWAP_FACTORY_ADDR=0xCA143Ce32Fe78f1f7019d7d551a6402fC5350c73

# Four.meme Contract
FOUR_MEME_ADDRESS=0xYourFourMemeContractAddress

# Copy Wallets (comma-separated private keys)
COPY_KEYS=0xYourPrivateKey1,0xYourPrivateKey2

# Target Wallets to Follow (comma-separated addresses, lowercase)
TARGET_WALLETS=0xTargetWallet1,0xTargetWallet2

# Trading Parameters
COPY_PERCENT=1.0              # Copy 100% of trade size (1.0 = 100%)
SLIPPAGE_BPS=300              # 3% slippage tolerance
GAS_MULTIPLIER=1.0            # Gas price multiplier
MIN_GAS_PRICE_GWEI=5          # Minimum gas price

# Advanced Settings
ENABLE_PANCAKESWAP=true
ENABLE_FOURMEME=true
LOG_LEVEL=info
```

### Running the Bot

```bash
# Development mode
npm run dev

# Production mode
npm start

# Run specific DEX only
npm run pancakeswap
npm run fourmeme
```

## Rust Bot Setup

### Configuration

Create a `.env` file in the `rust-bot` directory:

```env
# RPC Endpoints
WS_URL=wss://bsc-mainnet.nodereal.io/ws/v1/YOUR_API_KEY
BSC_RPC_URL=https://bsc-mainnet.nodereal.io/v1/YOUR_API_KEY

# Contracts
PANCAKE_SWAP_ROUTER_ADDR=0x10ED43C718714eb63d5aA57B78B54704E256024E
FOUR_MEME_ADDRESS=0xYourFourMemeContractAddress

# Wallets
COPY_KEYS=0xYourPrivateKey1,0xYourPrivateKey2
TARGET_WALLETS=0xTargetWallet1,0xTargetWallet2

# Trading Parameters
COPY_PERCENT=1.0
COPY_PERCENTS=1.0,0.5,2.0     # Per-wallet copy percentages
SLIPPAGE_BPS=300
GAS_MULTIPLIER=1.0
MIN_GAS_PRICE_GWEI=5
GAS_LIMIT_OVERRIDE=400000
```

### Running the Bot

```bash
# Development mode
cargo run

# Release mode (optimized)
cargo run --release

# Run with specific log level
RUST_LOG=info cargo run --release
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `WS_URL` | WebSocket RPC URL | - | Yes |
| `BSC_RPC_URL` | HTTP RPC URL | - | Yes |
| `PANCAKE_SWAP_ROUTER_ADDR` | PancakeSwap router address | - | Yes |
| `FOUR_MEME_ADDRESS` | Four.meme contract address | - | Yes |
| `COPY_KEYS` | Private keys (comma-separated) | - | Yes |
| `TARGET_WALLETS` | Target wallet addresses | - | Yes |
| `COPY_PERCENT` | Copy size percentage | 1.0 | Yes |
| `SLIPPAGE_BPS` | Slippage in basis points | 300 | No |
| `GAS_MULTIPLIER` | Gas price multiplier | 1.0 | No |
| `MIN_GAS_PRICE_GWEI` | Minimum gas price (Gwei) | 5 | No |

### Trading Parameters

**COPY_PERCENT**: Multiplier for trade size
- `1.0` = 100% (same size)
- `0.5` = 50% (half size)
- `2.0` = 200% (double size)

**SLIPPAGE_BPS**: Maximum acceptable slippage
- `300` = 3% slippage
- `100` = 1% slippage
- `500` = 5% slippage

## Usage

### Basic Usage

1. **Configure your environment**: Edit `.env` with your settings
2. **Fund your copy wallets**: Ensure sufficient BNB for gas
3. **Start the bot**: Run `npm start` (TS) or `cargo run --release` (Rust)
4. **Monitor logs**: Watch for trade executions in the console

### Advanced Usage

#### Copy Different Sizes per Wallet (Rust only)

```env
COPY_PERCENTS=1.0,0.5,2.0
```

This sets 100%, 50%, and 200% copy sizes for the three wallets respectively.

#### Gas Management

```env
GAS_MULTIPLIER=1.5          # Use 1.5x current gas price
MIN_GAS_PRICE_GWEI=10       # Never go below 10 Gwei
```

#### DEX-Specific Settings

Enable/disable specific DEXs:

```env
ENABLE_PANCAKESWAP=true
ENABLE_FOURMEME=false
```

## Considerations

### Important Warnings

⚠️ **CRITICAL**: This bot executes real transactions with your funds
- Test on testnet first
- Start with small amounts
- Monitor all transactions
- Keep private keys secure

### Best Practices

1. **Use dedicated wallets**: Never use your main wallet
2. **Limit funding**: Only fund wallets with what you're willing to lose
3. **Monitor regularly**: Check bot status frequently
4. **Secure environment**: Keep `.env` files secure and never commit them
5. **Reliable RPC**: Use premium RPC providers for stability
6. **Regular backups**: Backup your configuration and wallet files

### Private Key Security

- Never share your private keys
- Use environment variables for keys
- Consider using hardware wallets for larger amounts
- Rotate keys regularly

## Troubleshooting

### Common Issues

**No trades being mirrored:**
- Verify `TARGET_WALLETS` contains correct addresses (lowercase)
- Check that target wallets are actively trading
- Ensure WebSocket connection is stable

**Allowance errors:**
- Bot automatically handles approvals
- Wait for approval transactions to confirm
- Check wallet has sufficient token balance

**Router decode failures:**
- Bot uses fallback methods to decode trades
- Check PancakeSwap router address is correct
- Verify pair contract exists

**Gas estimation failures:**
- Increase `GAS_LIMIT_OVERRIDE` if set
- Check wallet has sufficient BNB for gas
- Verify token contracts are valid

**WebSocket disconnections:**
- Use reliable RPC providers
- Configure fallback endpoints
- Monitor connection status

### Debug Mode

Enable verbose logging:

**TypeScript:**
```bash
LOG_LEVEL=debug npm start
```

**Rust:**
```bash
RUST_LOG=debug cargo run --release
```

## Monitoring

### Log Levels

- `error`: Only errors
- `warn`: Warnings and errors
- `info`: General information (default)
- `debug`: Detailed debug information

### Key Metrics to Monitor

- Connection status
- Trade execution success rate
- Gas prices
- Wallet balances
- Error rates

## Testing

### Running Tests

**TypeScript:**
```bash
npm test
```

**Rust:**
```bash
cargo test
```

### Test Coverage

- Event detection
- Trade decoding
- Transaction execution
- Error handling

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new features
5. Submit a pull request

### Code Style

- TypeScript: Follow existing code style
- Rust: Run `cargo fmt` before committing

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Ethers.js team for the excellent library
- Ethers-rs team for the Rust implementation
- PancakeSwap team
- Four.meme team
- BNB Chain community

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section
---

**Four.meme copy trading bot · Four.meme copy trading · PancakeSwap copy trading · BNB Chain**

