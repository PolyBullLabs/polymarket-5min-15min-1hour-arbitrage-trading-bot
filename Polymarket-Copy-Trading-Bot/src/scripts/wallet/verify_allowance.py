#!/usr/bin/env python3
"""
Verify USDC allowance status
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from web3 import Web3
from src.config.env import ENV
from colorama import init, Fore, Style

init(autoreset=True)

# Polymarket's CTF Exchange contract address on Polygon
POLYMARKET_EXCHANGE = '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E'

# USDC ABI (only the functions we need)
USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]


async def verify_allowance():
    """Verify USDC allowance status"""
    print(f'{Fore.CYAN}[INFO]{Style.RESET_ALL} Verifying USDC allowance status...\n')
    
    # Connect to Polygon
    w3 = Web3(Web3.HTTPProvider(ENV.RPC_URL))
    
    if not w3.is_connected():
        print(f'{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to connect to RPC endpoint')
        sys.exit(1)
    
    # Create USDC contract instance (read-only, no wallet needed)
    usdc_address = Web3.to_checksum_address(ENV.USDC_CONTRACT_ADDRESS)
    exchange_address = Web3.to_checksum_address(POLYMARKET_EXCHANGE)
    usdc_contract = w3.eth.contract(address=usdc_address, abi=USDC_ABI)
    
    try:
        # Get USDC decimals
        decimals = usdc_contract.functions.decimals().call()
        
        # Check balance
        wallet_address = Web3.to_checksum_address(ENV.PROXY_WALLET)
        balance = usdc_contract.functions.balanceOf(wallet_address).call()
        balance_formatted = balance / (10 ** decimals)
        
        # Check current allowance
        current_allowance = usdc_contract.functions.allowance(wallet_address, exchange_address).call()
        allowance_formatted = current_allowance / (10 ** decimals)
        
        print('=' * 70)
        print(f'{Fore.CYAN}WALLET STATUS{Style.RESET_ALL}')
        print('=' * 70)
        print(f'Wallet:     {ENV.PROXY_WALLET}')
        print(f'USDC:       {balance_formatted:.6f} USDC')
        if current_allowance == 0:
            print(f'{Fore.RED}Allowance:  0 USDC (NOT SET!){Style.RESET_ALL}')
        else:
            print(f'{Fore.GREEN}Allowance:  {allowance_formatted:.6f} USDC (SET!){Style.RESET_ALL}')
        print(f'Exchange:   {POLYMARKET_EXCHANGE}')
        print('=' * 70)
        
        if current_allowance == 0:
            print(f'\n{Fore.RED}[ERROR]{Style.RESET_ALL} PROBLEM: Allowance is NOT set!')
            print('\nTo fix: Run the following command:')
            print('  python -m src.scripts.wallet.check_allowance')
            print('\nOR wait for your pending transaction to confirm:')
            print(f'  https://polygonscan.com/address/{ENV.PROXY_WALLET}')
            sys.exit(1)
        elif current_allowance < balance:
            print(f'\n{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Allowance is less than your balance!')
            print('   You may not be able to trade your full balance.')
            print(f'\n   Balance:   {balance_formatted:.6f} USDC')
            print(f'   Allowance: {allowance_formatted:.6f} USDC')
            print('\n   Consider setting unlimited allowance:')
            print('  python -m src.scripts.wallet.check_allowance')
            sys.exit(1)
        else:
            print(f'\n{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Allowance is properly set!')
            print('   You can start trading now.')
            print('\nStart the bot:')
            print('  python -m src.main')
            sys.exit(0)
    except Exception as error:
        print(f'\n{Fore.RED}[ERROR]{Style.RESET_ALL} Error: {error}')
        sys.exit(1)


if __name__ == '__main__':
    import asyncio
    asyncio.run(verify_allowance())

