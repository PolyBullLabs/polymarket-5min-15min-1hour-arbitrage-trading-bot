#!/usr/bin/env python3
"""
Find Gnosis Safe Proxy wallet
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
RPC_URL = ENV.RPC_URL


async def find_gnosis_safe_proxy():
    """Find Gnosis Safe Proxy wallet"""
    print(f'\n{Fore.CYAN}SEARCHING FOR GNOSIS SAFE PROXY WALLET{Style.RESET_ALL}\n')
    print('─' * 50 + '\n')
    
    # 1. Get EOA address from private key
    account = Account.from_key(PRIVATE_KEY)
    eoa_address = account.address
    
    print(f'{Fore.CYAN}STEP 1: Your EOA address (from private key){Style.RESET_ALL}\n')
    print(f'   {eoa_address}\n')
    
    # 2. Find positions on EOA
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}STEP 2: Positions on EOA address{Style.RESET_ALL}\n')
    
    try:
        eoa_positions = await fetch_data_async(
            f'https://data-api.polymarket.com/positions?user={eoa_address}'
        )
        if not isinstance(eoa_positions, list):
            eoa_positions = []
        print(f'   Positions: {len(eoa_positions)}\n')
        
        if eoa_positions:
            print(f'   {Fore.GREEN}There are positions on EOA!{Style.RESET_ALL}\n')
    except Exception as error:
        print(f'   {Fore.RED}Could not get positions{Style.RESET_ALL}\n')
    
    # 3. Find transactions from EOA to find proxy
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}STEP 3: Find Gnosis Safe Proxy through transactions{Style.RESET_ALL}\n')
    
    try:
        activities = await fetch_data_async(
            f'https://data-api.polymarket.com/activity?user={eoa_address}&type=TRADE'
        )
        if not isinstance(activities, list):
            activities = []
        
        if activities:
            first_trade = activities[0]
            proxy_wallet_from_trade = first_trade.get('proxyWallet')
            
            print(f'   EOA address:          {eoa_address}')
            print(f'   Proxy in trades:      {proxy_wallet_from_trade}\n')
            
            if proxy_wallet_from_trade and proxy_wallet_from_trade.lower() != eoa_address.lower():
                print(f'   {Fore.GREEN}GNOSIS SAFE PROXY FOUND!{Style.RESET_ALL}\n')
                print(f'   Proxy address: {proxy_wallet_from_trade}\n')
                
                # Check positions on proxy
                proxy_positions = await fetch_data_async(
                    f'https://data-api.polymarket.com/positions?user={proxy_wallet_from_trade}'
                )
                if not isinstance(proxy_positions, list):
                    proxy_positions = []
                
                print(f'   Positions on Proxy: {len(proxy_positions)}\n')
                
                if proxy_positions:
                    print(f'   {Fore.GREEN}HERE ARE YOUR POSITIONS!{Style.RESET_ALL}\n')
                    
                    print('─' * 50 + '\n')
                    print(f'{Fore.CYAN}SOLUTION:{Style.RESET_ALL}\n')
                    print('─' * 50 + '\n')
                    
                    print('Update .env file:\n')
                    print(f'PROXY_WALLET={proxy_wallet_from_trade}\n')
                    
                    print('Then the bot will use the correct Gnosis Safe proxy\n')
                    print('and positions will match the frontend!\n')
                    
                    print('─' * 50 + '\n')
                    print(f'{Fore.CYAN}CURRENT STATUS:{Style.RESET_ALL}\n')
                    print(f'   Bot uses:         {ENV.PROXY_WALLET}')
                    print(f'   Should use:      {proxy_wallet_from_trade}\n')
                    
                    if ENV.PROXY_WALLET.lower() == proxy_wallet_from_trade.lower():
                        print(f'   {Fore.GREEN}Addresses match! Everything is configured correctly.{Style.RESET_ALL}\n')
                    else:
                        print(f'   {Fore.RED}Addresses do not match!{Style.RESET_ALL}\n')
                        print('   This is why you see different positions on bot and frontend.\n')
            else:
                print(f'   {Fore.YELLOW}Proxy matches EOA (trading directly through EOA){Style.RESET_ALL}\n')
        else:
            print(f'   {Fore.RED}No transactions on this address{Style.RESET_ALL}\n')
    except Exception as error:
        print(f'   {Fore.RED}Error searching for transactions{Style.RESET_ALL}\n')
    
    # 4. Additional search through Polygon blockchain
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}STEP 4: Search through Polygon blockchain{Style.RESET_ALL}\n')
    
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if w3.is_connected():
            print('   Checking Gnosis Safe creation...\n')
            
            tx_count = w3.eth.get_transaction_count(Web3.to_checksum_address(eoa_address))
            print(f'   Transactions from EOA: {tx_count}\n')
            
            if tx_count > 0:
                print(f'   {Fore.YELLOW}EOA made transactions. Possibly has Gnosis Safe.{Style.RESET_ALL}\n')
        else:
            print(f'   {Fore.YELLOW}Could not connect to RPC{Style.RESET_ALL}\n')
    except Exception as error:
        print(f'   {Fore.YELLOW}Could not check blockchain directly{Style.RESET_ALL}\n')
    
    # 5. Final recommendations
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}RECOMMENDATIONS:{Style.RESET_ALL}\n')
    print('─' * 50 + '\n')
    
    print('1. Go to polymarket.com in browser\n')
    print('2. Connect wallet with the same private key\n')
    print('3. Copy the address that Polymarket shows\n')
    print('4. Update PROXY_WALLET in .env with this address\n')
    print('5. Restart the bot\n')
    
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}HOW TO FIND PROXY ADDRESS ON FRONTEND:{Style.RESET_ALL}\n')
    print('─' * 50 + '\n')
    
    print('On Polymarket after connecting:\n')
    print('1. Click on profile icon (top right corner)\n')
    print('2. There will be an address like 0x...\n')
    print('3. This is your Proxy Wallet address!\n')
    print('4. Copy it to PROXY_WALLET in .env\n')
    
    print('─' * 50 + '\n')
    print(f'{Fore.CYAN}Useful links:{Style.RESET_ALL}\n')
    print(f'   EOA profile:     https://polymarket.com/profile/{eoa_address}')
    print(f'   EOA Polygonscan: https://polygonscan.com/address/{eoa_address}\n')
    
    print('─' * 50 + '\n')


if __name__ == '__main__':
    asyncio.run(find_gnosis_safe_proxy())

