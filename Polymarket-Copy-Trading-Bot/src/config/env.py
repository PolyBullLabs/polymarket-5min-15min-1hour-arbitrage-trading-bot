"""
Environment configuration and validation
"""
import os
import re
from typing import List, Optional
from dotenv import load_dotenv
from .copy_strategy import CopyStrategy, CopyStrategyConfig, parse_tiered_multipliers

load_dotenv()


def is_valid_ethereum_address(address: str) -> bool:
    """Validate Ethereum address format"""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


def validate_required_env() -> None:
    """Validate required environment variables"""
    required = [
        'USER_ADDRESSES',
        'PROXY_WALLET',
        'PRIVATE_KEY',
        'CLOB_HTTP_URL',
        'CLOB_WS_URL',
        'MONGO_URI',
        'RPC_URL',
        'USDC_CONTRACT_ADDRESS',
    ]

    missing = [key for key in required if not os.getenv(key)]

    if missing:
        print('\n\033[31m[ERROR]\033[0m Configuration Error: Missing required environment variables\n')
        print(f'Missing variables: {", ".join(missing)}\n')
        print('Quick fix:')
        print('   1. Run the setup wizard: python -m src.scripts.setup.setup')
        print('   2. Or manually create .env file with all required variables\n')
        print('See docs/QUICK_START.md for detailed instructions\n')
        raise ValueError(f'Missing required environment variables: {", ".join(missing)}')


def validate_addresses() -> None:
    """Validate Ethereum addresses"""
    proxy_wallet = os.getenv('PROXY_WALLET')
    if proxy_wallet and not is_valid_ethereum_address(proxy_wallet):
        print('\n[ERROR] Invalid Wallet Address\n')
        print(f'Your PROXY_WALLET: {proxy_wallet}')
        print('Expected format:    0x followed by 40 hexadecimal characters\n')
        print('Example: 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0\n')
        print('Tips:')
        print('   • Copy your wallet address from MetaMask')
        print('   • Make sure it starts with 0x')
        print('   • Should be exactly 42 characters long\n')
        raise ValueError(f'Invalid PROXY_WALLET address format: {proxy_wallet}')

    usdc_contract = os.getenv('USDC_CONTRACT_ADDRESS')
    if usdc_contract and not is_valid_ethereum_address(usdc_contract):
        print('\n[ERROR] Invalid USDC Contract Address\n')
        print(f'Current value: {usdc_contract}')
        print('Default value: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174\n')
        print('[WARNING] Unless you know what you\'re doing, use the default value!\n')
        raise ValueError(f'Invalid USDC_CONTRACT_ADDRESS format: {usdc_contract}')


def validate_numeric_config() -> None:
    """Validate numeric configuration values"""
    fetch_interval = int(os.getenv('FETCH_INTERVAL', '1'))
    if fetch_interval <= 0:
        raise ValueError(f'Invalid FETCH_INTERVAL: {os.getenv("FETCH_INTERVAL")}. Must be a positive integer.')

    retry_limit = int(os.getenv('RETRY_LIMIT', '3'))
    if retry_limit < 1 or retry_limit > 10:
        raise ValueError(f'Invalid RETRY_LIMIT: {os.getenv("RETRY_LIMIT")}. Must be between 1 and 10.')

    too_old_timestamp = int(os.getenv('TOO_OLD_TIMESTAMP', '24'))
    if too_old_timestamp < 1:
        raise ValueError(f'Invalid TOO_OLD_TIMESTAMP: {os.getenv("TOO_OLD_TIMESTAMP")}. Must be a positive integer (hours).')

    request_timeout = int(os.getenv('REQUEST_TIMEOUT_MS', '10000'))
    if request_timeout < 1000:
        raise ValueError(f'Invalid REQUEST_TIMEOUT_MS: {os.getenv("REQUEST_TIMEOUT_MS")}. Must be at least 1000ms.')

    network_retry_limit = int(os.getenv('NETWORK_RETRY_LIMIT', '3'))
    if network_retry_limit < 1 or network_retry_limit > 10:
        raise ValueError(f'Invalid NETWORK_RETRY_LIMIT: {os.getenv("NETWORK_RETRY_LIMIT")}. Must be between 1 and 10.')


def validate_urls() -> None:
    """Validate URL formats"""
    clob_http_url = os.getenv('CLOB_HTTP_URL')
    if clob_http_url and not clob_http_url.startswith('http'):
        print('\n[ERROR] Invalid CLOB_HTTP_URL\n')
        print(f'Current value: {clob_http_url}')
        print('Default value: https://clob.polymarket.com/\n')
        print('[WARNING] Use the default value unless you have a specific reason to change it!\n')
        raise ValueError(f'Invalid CLOB_HTTP_URL: {clob_http_url}. Must be a valid HTTP/HTTPS URL.')

    clob_ws_url = os.getenv('CLOB_WS_URL')
    if clob_ws_url and not clob_ws_url.startswith('ws'):
        print('\n[ERROR] Invalid CLOB_WS_URL\n')
        print(f'Current value: {clob_ws_url}')
        print('Default value: wss://ws-subscriptions-clob.polymarket.com/ws\n')
        print('[WARNING] Use the default value unless you have a specific reason to change it!\n')
        raise ValueError(f'Invalid CLOB_WS_URL: {clob_ws_url}. Must be a valid WebSocket URL (ws:// or wss://).')

    rpc_url = os.getenv('RPC_URL')
    if rpc_url and not rpc_url.startswith('http'):
        print('\n[ERROR] Invalid RPC_URL\n')
        print(f'Current value: {rpc_url}')
        print('Must start with: http:// or https://\n')
        print('Get a free RPC endpoint from:')
        print('   • Infura:  https://infura.io')
        print('   • Alchemy: https://www.alchemy.com')
        print('   • Ankr:    https://www.ankr.com\n')
        print('Example: https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID\n')
        raise ValueError(f'Invalid RPC_URL: {rpc_url}. Must be a valid HTTP/HTTPS URL.')

    mongo_uri = os.getenv('MONGO_URI')
    if mongo_uri and not mongo_uri.startswith('mongodb'):
        print('\n[ERROR] Invalid MONGO_URI\n')
        print(f'Current value: {mongo_uri}')
        print('Must start with: mongodb:// or mongodb+srv://\n')
        print('Setup MongoDB Atlas (free):')
        print('   1. Visit https://www.mongodb.com/cloud/atlas/register')
        print('   2. Create a free cluster')
        print('   3. Create database user with password')
        print('   4. Whitelist IP: 0.0.0.0/0 (or your IP)')
        print('   5. Get connection string from "Connect" button\n')
        print('Example: mongodb+srv://username:password@cluster.mongodb.net/database\n')
        raise ValueError(f'Invalid MONGO_URI: {mongo_uri}. Must be a valid MongoDB connection string.')


def parse_user_addresses(input_str: str) -> List[str]:
    """Parse USER_ADDRESSES: supports both comma-separated string and JSON array"""
    trimmed = input_str.strip()
    addresses: List[str] = []

    # Check if it's JSON array format
    if trimmed.startswith('[') and trimmed.endswith(']'):
        try:
            import json
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                addresses = [addr.lower().strip() for addr in parsed if addr.strip()]
                # Validate each address
                for addr in addresses:
                    if not is_valid_ethereum_address(addr):
                        print('\n[ERROR] Invalid Trader Address in USER_ADDRESSES\n')
                        print(f'Invalid address: {addr}')
                        print('Expected format: 0x followed by 40 hexadecimal characters\n')
                        print('Where to find trader addresses:')
                        print('   • Polymarket Leaderboard: https://polymarket.com/leaderboard')
                        print('   • Predictfolio: https://predictfolio.com\n')
                        print('Example: USER_ADDRESSES=\'0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b\'\n')
                        raise ValueError(f'Invalid Ethereum address in USER_ADDRESSES: {addr}')
                return addresses
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid JSON format for USER_ADDRESSES: {e}')
    else:
        # Otherwise treat as comma-separated
        addresses = [addr.lower().strip() for addr in trimmed.split(',') if addr.strip()]
        # Validate each address
        for addr in addresses:
            if not is_valid_ethereum_address(addr):
                print('\n[ERROR] Invalid Trader Address in USER_ADDRESSES\n')
                print(f'Invalid address: {addr}')
                print('Expected format: 0x followed by 40 hexadecimal characters\n')
                print('Where to find trader addresses:')
                print('   • Polymarket Leaderboard: https://polymarket.com/leaderboard')
                print('   • Predictfolio: https://predictfolio.com\n')
                print('Example: USER_ADDRESSES=\'0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b\'\n')
                raise ValueError(f'Invalid Ethereum address in USER_ADDRESSES: {addr}')

    return addresses


def parse_copy_strategy() -> CopyStrategyConfig:
    """Parse copy strategy configuration"""
    # Support legacy COPY_PERCENTAGE + TRADE_MULTIPLIER for backward compatibility
    copy_percentage = os.getenv('COPY_PERCENTAGE')
    copy_strategy = os.getenv('COPY_STRATEGY')
    has_legacy_config = copy_percentage and not copy_strategy

    if has_legacy_config:
        print('[WARNING] Using legacy COPY_PERCENTAGE configuration. Consider migrating to COPY_STRATEGY.')
        copy_percentage_val = float(copy_percentage or '10.0')
        trade_multiplier = float(os.getenv('TRADE_MULTIPLIER', '1.0'))
        effective_percentage = copy_percentage_val * trade_multiplier

        config = CopyStrategyConfig(
            strategy=CopyStrategy.PERCENTAGE,
            copy_size=effective_percentage,
            max_order_size_usd=float(os.getenv('MAX_ORDER_SIZE_USD', '100.0')),
            min_order_size_usd=float(os.getenv('MIN_ORDER_SIZE_USD', '1.0')),
            max_position_size_usd=float(os.getenv('MAX_POSITION_SIZE_USD')) if os.getenv('MAX_POSITION_SIZE_USD') else None,
            max_daily_volume_usd=float(os.getenv('MAX_DAILY_VOLUME_USD')) if os.getenv('MAX_DAILY_VOLUME_USD') else None,
        )

        # Parse tiered multipliers if configured (even for legacy mode)
        tiered_multipliers_str = os.getenv('TIERED_MULTIPLIERS')
        if tiered_multipliers_str:
            try:
                config.tiered_multipliers = parse_tiered_multipliers(tiered_multipliers_str)
                print(f'[OK] Loaded {len(config.tiered_multipliers)} tiered multipliers')
            except Exception as error:
                raise ValueError(f'Failed to parse TIERED_MULTIPLIERS: {error}')
        elif trade_multiplier != 1.0:
            # If using legacy single multiplier, store it
            config.trade_multiplier = trade_multiplier

        return config

    # Parse new copy strategy configuration
    strategy_str = (os.getenv('COPY_STRATEGY') or 'PERCENTAGE').upper()
    try:
        strategy = CopyStrategy[strategy_str]
    except KeyError:
        strategy = CopyStrategy.PERCENTAGE

    config = CopyStrategyConfig(
        strategy=strategy,
        copy_size=float(os.getenv('COPY_SIZE', '10.0')),
        max_order_size_usd=float(os.getenv('MAX_ORDER_SIZE_USD', '100.0')),
        min_order_size_usd=float(os.getenv('MIN_ORDER_SIZE_USD', '1.0')),
        max_position_size_usd=float(os.getenv('MAX_POSITION_SIZE_USD')) if os.getenv('MAX_POSITION_SIZE_USD') else None,
        max_daily_volume_usd=float(os.getenv('MAX_DAILY_VOLUME_USD')) if os.getenv('MAX_DAILY_VOLUME_USD') else None,
    )

    # Add adaptive strategy parameters if applicable
    if strategy == CopyStrategy.ADAPTIVE:
        config.adaptive_min_percent = float(os.getenv('ADAPTIVE_MIN_PERCENT', str(config.copy_size)))
        config.adaptive_max_percent = float(os.getenv('ADAPTIVE_MAX_PERCENT', str(config.copy_size)))
        config.adaptive_threshold = float(os.getenv('ADAPTIVE_THRESHOLD_USD', '500.0'))

    # Parse tiered multipliers if configured
    tiered_multipliers_str = os.getenv('TIERED_MULTIPLIERS')
    if tiered_multipliers_str:
        try:
            config.tiered_multipliers = parse_tiered_multipliers(tiered_multipliers_str)
            print(f'[OK] Loaded {len(config.tiered_multipliers)} tiered multipliers')
        except Exception as error:
            raise ValueError(f'Failed to parse TIERED_MULTIPLIERS: {error}')
    else:
        trade_multiplier_str = os.getenv('TRADE_MULTIPLIER')
        if trade_multiplier_str:
            # Fall back to single multiplier if no tiers configured
            single_multiplier = float(trade_multiplier_str)
            if single_multiplier != 1.0:
                config.trade_multiplier = single_multiplier
                print(f'[OK] Using single trade multiplier: {single_multiplier}x')

    return config


# Run all validations
validate_required_env()
validate_addresses()
validate_numeric_config()
validate_urls()

# Export ENV object
class ENV:
    """Environment configuration"""
    USER_ADDRESSES: List[str] = parse_user_addresses(os.getenv('USER_ADDRESSES', ''))
    PROXY_WALLET: str = os.getenv('PROXY_WALLET', '')
    PRIVATE_KEY: str = os.getenv('PRIVATE_KEY', '')
    CLOB_HTTP_URL: str = os.getenv('CLOB_HTTP_URL', '')
    CLOB_WS_URL: str = os.getenv('CLOB_WS_URL', '')
    FETCH_INTERVAL: int = int(os.getenv('FETCH_INTERVAL', '1'))
    TOO_OLD_TIMESTAMP: int = int(os.getenv('TOO_OLD_TIMESTAMP', '24'))
    RETRY_LIMIT: int = int(os.getenv('RETRY_LIMIT', '3'))
    # Legacy parameters (kept for backward compatibility)
    TRADE_MULTIPLIER: float = float(os.getenv('TRADE_MULTIPLIER', '1.0'))
    COPY_PERCENTAGE: float = float(os.getenv('COPY_PERCENTAGE', '10.0'))
    # New copy strategy configuration
    COPY_STRATEGY_CONFIG: CopyStrategyConfig = parse_copy_strategy()
    # Network settings
    REQUEST_TIMEOUT_MS: int = int(os.getenv('REQUEST_TIMEOUT_MS', '10000'))
    NETWORK_RETRY_LIMIT: int = int(os.getenv('NETWORK_RETRY_LIMIT', '3'))
    # Trade aggregation settings
    TRADE_AGGREGATION_ENABLED: bool = os.getenv('TRADE_AGGREGATION_ENABLED', '').lower() == 'true'
    TRADE_AGGREGATION_WINDOW_SECONDS: int = int(os.getenv('TRADE_AGGREGATION_WINDOW_SECONDS', '300'))  # 5 minutes default
    MONGO_URI: str = os.getenv('MONGO_URI', '')
    RPC_URL: str = os.getenv('RPC_URL', '')
    USDC_CONTRACT_ADDRESS: str = os.getenv('USDC_CONTRACT_ADDRESS', '')

