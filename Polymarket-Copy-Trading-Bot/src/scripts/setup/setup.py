#!/usr/bin/env python3
"""
Interactive Setup Script for Polymarket Copy Trading Bot
Helps users create their .env file with guided prompts
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def is_valid_ethereum_address(address: str) -> bool:
    """Validate Ethereum address format"""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


def is_valid_private_key(key: str) -> bool:
    """Validate private key format (with or without 0x prefix)"""
    # Remove 0x prefix if present for validation
    key_clean = key[2:] if key.startswith('0x') else key
    return bool(re.match(r'^[a-fA-F0-9]{64}$', key_clean))


def print_header():
    """Print setup wizard header"""
    print('\n' + '=' * 70)
    print('POLYMARKET COPY TRADING BOT - SETUP WIZARD')
    print('=' * 70)
    print('\nThis wizard will help you create your .env configuration file.')
    print('Press Ctrl+C at any time to cancel.\n')


def print_section(title: str):
    """Print section header"""
    print(f'\n{title}')
    print('-' * 70)


def setup_user_addresses() -> str:
    """Setup traders to copy"""
    print_section('STEP 1: TRADERS TO COPY')
    print('Find top traders on:')
    print('  - https://polymarket.com/leaderboard')
    print('  - https://predictfolio.com\n')
    
    print('Tip: Look for traders with:')
    print('  - Positive P&L (green numbers)')
    print('  - Win rate above 55%')
    print('  - Recent trading activity\n')
    
    addresses = []
    
    while True:
        address = input(f'Enter trader wallet address {len(addresses) + 1} (or press Enter to finish): ').strip()
        
        if not address:
            if len(addresses) == 0:
                print('[ERROR] You must add at least one trader address!\n')
                continue
            break
        
        if not is_valid_ethereum_address(address.lower()):
            print('[ERROR] Invalid Ethereum address format. Should be 0x followed by 40 hex characters.\n')
            continue
        
        addresses.append(address.lower())
        print(f'[OK] Added: {address}\n')
    
    print(f'\n[OK] Total traders to copy: {len(addresses)}')
    return ', '.join(addresses)


def setup_wallet() -> Dict[str, str]:
    """Setup trading wallet"""
    print_section('STEP 2: YOUR TRADING WALLET')
    print('[WARNING] IMPORTANT SECURITY TIPS:')
    print('  - Use a DEDICATED wallet for the bot')
    print('  - Never use your main wallet')
    print('  - Only keep trading capital in this wallet')
    print('  - Never share your private key!\n')
    
    wallet = ""
    while not wallet:
        wallet = input('Enter your Polygon wallet address: ').strip()
        
        if not is_valid_ethereum_address(wallet):
            print('[ERROR] Invalid wallet address format\n')
            wallet = ""
            continue
    
    print(f'[OK] Wallet: {wallet}\n')
    
    private_key = ""
    while not private_key:
        try:
            import getpass
            private_key = getpass.getpass('Enter your private key (without 0x prefix): ')
        except Exception:
            private_key = input('Enter your private key (without 0x prefix): ')
        
        if not is_valid_private_key(private_key):
            print('[ERROR] Invalid private key format\n')
            private_key = ""
            continue
        
        # Remove 0x prefix if present
        if private_key.startswith('0x'):
            private_key = private_key[2:]
    
    print('[OK] Private key saved')
    
    return {'wallet': wallet, 'private_key': private_key}


def setup_database() -> str:
    """Setup database connection"""
    print_section('STEP 3: DATABASE')
    print('Free MongoDB Atlas: https://www.mongodb.com/cloud/atlas/register\n')
    print('Setup steps:')
    print('  1. Create free account')
    print('  2. Create a cluster')
    print('  3. Create database user')
    print('  4. Whitelist IP: 0.0.0.0/0 (allow all)')
    print('  5. Get connection string\n')
    
    mongo_uri = ""
    while not mongo_uri:
        mongo_uri = input('Enter MongoDB connection string: ').strip()
        
        if not mongo_uri.startswith('mongodb'):
            print('[ERROR] Invalid MongoDB URI. Should start with "mongodb://" or "mongodb+srv://"\n')
            mongo_uri = ""
            continue
    
    print('[OK] MongoDB URI saved')
    return mongo_uri


def setup_rpc() -> str:
    """Setup RPC endpoint"""
    print_section('STEP 4: POLYGON RPC ENDPOINT')
    print('Get free RPC endpoint from:')
    print('  - Infura: https://infura.io (recommended)')
    print('  - Alchemy: https://www.alchemy.com')
    print('  - Ankr: https://www.ankr.com\n')
    
    rpc_url = ""
    while not rpc_url:
        rpc_url = input('Enter Polygon RPC URL: ').strip()
        
        if not rpc_url.startswith('http'):
            print('[ERROR] Invalid RPC URL. Should start with "http://" or "https://"\n')
            rpc_url = ""
            continue
    
    print('[OK] RPC URL saved')
    return rpc_url


def setup_strategy() -> Dict[str, str]:
    """Setup trading strategy"""
    print_section('STEP 5: TRADING STRATEGY (OPTIONAL)')
    
    use_defaults = input('Use default strategy settings? (Y/n): ').strip().lower()
    
    if use_defaults in ('n', 'no'):
        print('\nCopy Strategy Options:')
        print('  1. PERCENTAGE - Copy as % of trader position (recommended)')
        print('  2. FIXED - Fixed dollar amount per trade')
        print('  3. ADAPTIVE - Adjust based on trade size\n')
        
        strategy_choice = input('Choose strategy (1-3, default 1): ').strip() or '1'
        
        strategy = 'PERCENTAGE'
        if strategy_choice == '2':
            strategy = 'FIXED'
        elif strategy_choice == '3':
            strategy = 'ADAPTIVE'
        
        copy_size = input('Copy size (% for PERCENTAGE, $ for FIXED, default 10.0): ').strip() or '10.0'
        multiplier = input('Trade multiplier (1.0 = normal, 2.0 = 2x aggressive, 0.5 = conservative, default 1.0): ').strip() or '1.0'
        
        return {
            'copy_strategy': strategy,
            'copy_size': copy_size,
            'trade_multiplier': multiplier,
        }
    
    print('[OK] Using default strategy: PERCENTAGE, 10%, 1.0x multiplier')
    return {
        'copy_strategy': 'PERCENTAGE',
        'copy_size': '10.0',
        'trade_multiplier': '1.0',
    }


def setup_risk_limits() -> Dict[str, str]:
    """Setup risk limits"""
    print_section('STEP 6: RISK LIMITS (OPTIONAL)')
    
    use_defaults = input('Use default risk limits? (Y/n): ').strip().lower()
    
    if use_defaults in ('n', 'no'):
        max_order = input('Maximum order size in USD (default 100.0): ').strip() or '100.0'
        min_order = input('Minimum order size in USD (default 1.0): ').strip() or '1.0'
        
        return {
            'max_order': max_order,
            'min_order': min_order,
        }
    
    print('[OK] Using default limits: Max $100, Min $1')
    return {'max_order': '100.0', 'min_order': '1.0'}


def generate_env_file(config: Dict[str, str]) -> str:
    """Generate .env file content"""
    content = f"""# ================================================================
# POLYMARKET COPY TRADING BOT - CONFIGURATION
# Generated by setup wizard on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ================================================================

# ================================================================
# TRADERS TO COPY
# ================================================================
USER_ADDRESSES='{config['USER_ADDRESSES']}'

# ================================================================
# YOUR WALLET
# ================================================================
PROXY_WALLET='{config['PROXY_WALLET']}'
PRIVATE_KEY='{config['PRIVATE_KEY']}'

# ================================================================
# DATABASE
# ================================================================
MONGO_URI='{config['MONGO_URI']}'

# ================================================================
# BLOCKCHAIN RPC
# ================================================================
RPC_URL='{config['RPC_URL']}'

# ================================================================
# POLYMARKET ENDPOINTS (DO NOT CHANGE)
# ================================================================
CLOB_HTTP_URL='{config['CLOB_HTTP_URL']}'
CLOB_WS_URL='{config['CLOB_WS_URL']}'
USDC_CONTRACT_ADDRESS='{config['USDC_CONTRACT_ADDRESS']}'

# ================================================================
# TRADING STRATEGY
# ================================================================
COPY_STRATEGY='{config['COPY_STRATEGY']}'
COPY_SIZE='{config['COPY_SIZE']}'
TRADE_MULTIPLIER='{config['TRADE_MULTIPLIER']}'

# ================================================================
# RISK LIMITS
# ================================================================
MAX_ORDER_SIZE_USD='{config['MAX_ORDER_SIZE_USD']}'
MIN_ORDER_SIZE_USD='{config['MIN_ORDER_SIZE_USD']}'

# ================================================================
# BOT BEHAVIOR
# ================================================================
FETCH_INTERVAL='{config.get("FETCH_INTERVAL", "1")}'
RETRY_LIMIT='{config.get("RETRY_LIMIT", "3")}'
TOO_OLD_TIMESTAMP='24'

# ================================================================
# TRADE AGGREGATION
# ================================================================
TRADE_AGGREGATION_ENABLED='{config.get("TRADE_AGGREGATION_ENABLED", "false")}'
TRADE_AGGREGATION_WINDOW_SECONDS='300'

# ================================================================
# NETWORK SETTINGS
# ================================================================
REQUEST_TIMEOUT_MS='10000'
NETWORK_RETRY_LIMIT='3'
"""
    return content


def main():
    """Main setup function"""
    print_header()
    
    try:
        # Collect all configuration
        user_addresses = setup_user_addresses()
        wallet_info = setup_wallet()
        mongo_uri = setup_database()
        rpc_url = setup_rpc()
        strategy = setup_strategy()
        limits = setup_risk_limits()
        
        # Build config object
        config = {
            'USER_ADDRESSES': user_addresses,
            'PROXY_WALLET': wallet_info['wallet'],
            'PRIVATE_KEY': wallet_info['private_key'],
            'MONGO_URI': mongo_uri,
            'RPC_URL': rpc_url,
            'CLOB_HTTP_URL': 'https://clob.polymarket.com/',
            'CLOB_WS_URL': 'wss://ws-subscriptions-clob.polymarket.com/ws',
            'USDC_CONTRACT_ADDRESS': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
            'COPY_STRATEGY': strategy['copy_strategy'],
            'COPY_SIZE': strategy['copy_size'],
            'TRADE_MULTIPLIER': strategy['trade_multiplier'],
            'MAX_ORDER_SIZE_USD': limits['max_order'],
            'MIN_ORDER_SIZE_USD': limits['min_order'],
        }
        
        # Generate .env file
        print_section('CREATING CONFIGURATION FILE')
        env_content = generate_env_file(config)
        env_path = Path.cwd() / '.env'
        
        # Check if .env already exists
        if env_path.exists():
            overwrite = input('[WARNING] .env file already exists. Overwrite? (y/N): ').strip().lower()
            
            if overwrite not in ('y', 'yes'):
                print('\n[INFO] Setup cancelled. Your existing .env file was not modified.')
                return
            
            # Backup existing file
            backup_path = Path.cwd() / '.env.backup'
            try:
                # Try UTF-8 first
                env_content_backup = env_path.read_text(encoding='utf-8')
                backup_path.write_text(env_content_backup, encoding='utf-8')
            except UnicodeDecodeError:
                # If UTF-8 fails, try with error handling (replace invalid chars)
                env_content_backup = env_path.read_text(encoding='utf-8', errors='replace')
                backup_path.write_text(env_content_backup, encoding='utf-8')
            except Exception as e:
                # If all else fails, try system default with error handling
                env_content_backup = env_path.read_text(errors='replace')
                backup_path.write_text(env_content_backup, encoding='utf-8')
            print('[OK] Backed up existing .env to .env.backup')
        
        # Write .env file
        env_path.write_text(env_content)
        
        # Success!
        print('\n' + '=' * 70)
        print('SETUP COMPLETE')
        print('=' * 70 + '\n')
        
        print(f'Configuration saved to: {env_path}\n')
        
        print('PRE-FLIGHT CHECKLIST:\n')
        print('  [ ] Fund your wallet with USDC on Polygon')
        print('  [ ] Get POL (MATIC) for gas fees (~$5-10)')
        print('  [ ] Verify traders are actively trading')
        print('  [ ] Test MongoDB connection\n')
        
        print('NEXT STEPS:\n')
        print('  1. Review your .env file: cat .env (or type .env on Windows)')
        print('  2. Install dependencies:   pip install -r requirements.txt')
        print('  3. Run system status check: python -m src.scripts.setup.system_status')
        print('  4. Start trading:          python -m src.main\n')
        
        print('DOCUMENTATION:\n')
        print('  - Quick Start:  README_PYTHON.md')
        print('  - Full Guide:   README.md\n')
        
        print('[WARNING] REMEMBER:')
        print('  - Start with small amounts to test')
        print('  - Monitor the bot regularly')
        print('  - Only trade what you can afford to lose\n')
        
        print('[OK] Setup complete. Ready to start trading.\n')
        
    except KeyboardInterrupt:
        print('\n[INFO] Setup cancelled by user.')
    except Exception as e:
        print(f'\n[ERROR] Setup error: {e}', file=sys.stderr)
        raise


if __name__ == '__main__':
    main()
