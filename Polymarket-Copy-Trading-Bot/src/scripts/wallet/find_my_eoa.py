#!/usr/bin/env python3
"""
Find and analyze EOA (Externally Owned Account) wallet
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
from web3 import Web3
from eth_account import Account
from src.config.env import ENV
from src.utils.fetch_data import fetch_data_async
from colorama import init, Fore, Style

init(autoreset=True)

PRIVATE_KEY = ENV.PRIVATE_KEY
PROXY_WALLET = ENV.PROXY_WALLET
RPC_URL = ENV.RPC_URL


async def analyze_wallets():
    """Analyze wallets and addresses"""
    print(f'\n{Fore.CYAN}WALLET AND ADDRESS ANALYSIS{Style.RESET_ALL}\n')
    print('─' * 50 + '\n')
    
    # 1. Get EOA address from private key
    account = Account.from_key(PRIVATE_KEY)
    eoa_address = account.address
    
    print(f'{Fore.CYAN}STEP 1: Address from private key (EOA){Style.RESET_ALL}\n')
    print(f'   {eoa_address}\n')
    
    # 2. Show PROXY_WALLET from .env
    print(f'{Fore.CYAN}STEP 2: PROXY_WALLET from .env{Style.RESET_ALL}\n')
    print(f'   {PROXY_WALLET}\n')
    
    # 3. Compare
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}COMPARISON:{Style.RESET_ALL}\n')
    
    if eoa_address.lower() == PROXY_WALLET.lower():
        print(f'   {Fore.YELLOW}EOA and PROXY_WALLET are the same address!{Style.RESET_ALL}\n')
        print('   This means .env has an EOA address, not a proxy wallet.\n')
        print('   Polymarket should have created a separate proxy wallet for this EOA,')
        print('   but the bot is using the EOA directly.\n')
    else:
        print(f'   {Fore.GREEN}EOA and PROXY_WALLET are different addresses{Style.RESET_ALL}\n')
        print(f'   EOA (owner):     {eoa_address}')
        print(f'   PROXY (trading): {PROXY_WALLET}\n')
    
    # 4. Check if PROXY_WALLET is a smart contract
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}STEP 3: Check PROXY_WALLET type{Style.RESET_ALL}\n')
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print(f'   {Fore.RED}Failed to connect to RPC{Style.RESET_ALL}\n')
    else:
        checksum_address = Web3.to_checksum_address(PROXY_WALLET)
        code = w3.eth.get_code(checksum_address)
        is_contract = code != b'0x'
        
        if is_contract:
            print(f'   {Fore.GREEN}PROXY_WALLET is a smart contract (Gnosis Safe){Style.RESET_ALL}\n')
            print('   This is the correct configuration for Polymarket.\n')
        else:
            print(f'   {Fore.YELLOW}PROXY_WALLET is NOT a smart contract!{Style.RESET_ALL}\n')
            print('   This is a regular EOA address.\n')
            print('   Polymarket usually uses a Gnosis Safe proxy.\n')
    
    # 5. Check activity on both addresses
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}STEP 4: Activity on Polymarket{Style.RESET_ALL}\n')
    
    try:
        proxy_positions = await fetch_data_async(
            f'https://data-api.polymarket.com/positions?user={PROXY_WALLET}'
        )
        if not isinstance(proxy_positions, list):
            proxy_positions = []
        print(f'   PROXY_WALLET ({PROXY_WALLET[:10]}...):')
        print(f'   • Positions: {len(proxy_positions)}\n')
        
        if eoa_address.lower() != PROXY_WALLET.lower():
            eoa_positions = await fetch_data_async(
                f'https://data-api.polymarket.com/positions?user={eoa_address}'
            )
            if not isinstance(eoa_positions, list):
                eoa_positions = []
            print(f'   EOA ({eoa_address[:10]}...):')
            print(f'   • Positions: {len(eoa_positions)}\n')
    except Exception as error:
        print(f'   {Fore.YELLOW}Could not get position data{Style.RESET_ALL}\n')
    
    # 6. Check connection through API activity
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}STEP 5: Check proxyWallet in transactions{Style.RESET_ALL}\n')
    
    try:
        activities = await fetch_data_async(
            f'https://data-api.polymarket.com/activity?user={PROXY_WALLET}&type=TRADE'
        )
        if not isinstance(activities, list):
            activities = []
        
        if activities:
            first_trade = activities[0]
            proxy_wallet_in_trade = first_trade.get('proxyWallet')
            
            print(f'   Address from .env:         {PROXY_WALLET}')
            print(f'   proxyWallet in trades:     {proxy_wallet_in_trade}\n')
            
            if proxy_wallet_in_trade and proxy_wallet_in_trade.lower() == PROXY_WALLET.lower():
                print(f'   {Fore.GREEN}Addresses match!{Style.RESET_ALL}\n')
            else:
                print(f'   {Fore.YELLOW}Addresses do not match!{Style.RESET_ALL}\n')
                print('   This may mean Polymarket uses a different proxy.\n')
    except Exception as error:
        print(f'   {Fore.YELLOW}Could not check transactions{Style.RESET_ALL}\n')
    
    # 7. Instructions
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}HOW TO ACCESS POSITIONS ON FRONTEND:{Style.RESET_ALL}\n')
    print('─' * 50 + '\n')
    
    print(f'{Fore.CYAN}OPTION 1: Import private key into MetaMask{Style.RESET_ALL}\n')
    print('   1. Open MetaMask')
    print('   2. Click account icon -> Import Account')
    print('   3. Paste your PRIVATE_KEY from .env file')
    print('   4. Connect to Polymarket with this account')
    print('   5. Polymarket will automatically show the correct proxy wallet\n')
    
    print(f'{Fore.YELLOW}WARNING: Never share your private key!{Style.RESET_ALL}\n')
    
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}OPTION 2: Find proxy wallet through URL{Style.RESET_ALL}\n')
    print(f'   Your positions are available at:\n')
    print(f'   https://polymarket.com/profile/{PROXY_WALLET}\n')
    print(f'   Open this link in browser to view.\n')
    
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}OPTION 3: Check through Polygon Explorer{Style.RESET_ALL}\n')
    print(f'   https://polygonscan.com/address/{PROXY_WALLET}\n')
    print(f'   Here you can see all transactions and tokens.\n')
    
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}ADDITIONAL INFORMATION:{Style.RESET_ALL}\n')
    print('   • EOA (Externally Owned Account) - your main wallet')
    print('   • Proxy Wallet - smart contract for trading on Polymarket')
    print('   • One EOA can have only one proxy wallet on Polymarket')
    print('   • All positions are stored in proxy wallet, not in EOA\n')
    
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}CONNECTION DATA:{Style.RESET_ALL}\n')
    print(f'   EOA address:       {eoa_address}')
    print(f'   Proxy address:     {PROXY_WALLET}')
    is_contract_str = 'Smart Contract (Gnosis Safe)' if is_contract else 'EOA (simple address)'
    print(f'   Proxy Type:        {is_contract_str}\n')
    
    print('─' * 50 + '\n')


if __name__ == '__main__':
    asyncio.run(analyze_wallets())

