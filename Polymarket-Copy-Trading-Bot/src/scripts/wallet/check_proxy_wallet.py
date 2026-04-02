#!/usr/bin/env python3
"""
Check proxy wallet and main wallet activity
"""
import sys
from pathlib import Path
from datetime import datetime

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


async def check_proxy_wallet():
    """Check proxy wallet and main wallet"""
    print(f'{Fore.CYAN}CHECKING PROXY WALLET AND MAIN WALLET{Style.RESET_ALL}\n')
    print('─' * 65 + '\n')
    
    try:
        # 1. Get EOA (main wallet) from private key
        account = Account.from_key(ENV.PRIVATE_KEY)
        eoa_address = account.address
        
        print(f'{Fore.CYAN}YOUR ADDRESSES:{Style.RESET_ALL}\n')
        print(f'   EOA (Main wallet):  {eoa_address}')
        print(f'   Proxy Wallet (Contract): {ENV.PROXY_WALLET}\n')
        print('─' * 65 + '\n')
        
        # 2. Check activity on EOA
        print(f'{Fore.CYAN}CHECKING ACTIVITY ON MAIN WALLET (EOA):{Style.RESET_ALL}\n')
        eoa_activity_url = f'https://data-api.polymarket.com/activity?user={eoa_address}&type=TRADE'
        eoa_activities = await fetch_data_async(eoa_activity_url)
        
        if not isinstance(eoa_activities, list):
            eoa_activities = []
        
        print(f'   Address: {eoa_address}')
        print(f'   Trades: {len(eoa_activities)}')
        print(f'   Profile: https://polymarket.com/profile/{eoa_address}\n')
        
        if eoa_activities:
            buy_trades = [a for a in eoa_activities if a.get('side') == 'BUY']
            sell_trades = [a for a in eoa_activities if a.get('side') == 'SELL']
            total_buy_volume = sum(t.get('usdcSize', 0) for t in buy_trades)
            total_sell_volume = sum(t.get('usdcSize', 0) for t in sell_trades)
            
            print('   Statistics:')
            print(f'      • Buys: {len(buy_trades)} (${total_buy_volume:.2f})')
            print(f'      • Sells: {len(sell_trades)} (${total_sell_volume:.2f})')
            print(f'      • Volume: ${(total_buy_volume + total_sell_volume):.2f}\n')
            
            # Show last 3 trades
            print('   Last 3 trades:')
            for idx, trade in enumerate(eoa_activities[:3], 1):
                date = datetime.fromtimestamp(trade.get('timestamp', 0))
                print(f'      {idx}. {trade.get("side", "UNKNOWN")} - {trade.get("title", "Unknown")}')
                print(f'         ${trade.get("usdcSize", 0):.2f} @ {date.strftime("%Y-%m-%d")}')
            print('')
        else:
            print(f'   {Fore.YELLOW}No trades found on main wallet{Style.RESET_ALL}\n')
        
        print('─' * 65 + '\n')
        
        # 3. Check activity on Proxy Wallet
        print(f'{Fore.CYAN}CHECKING ACTIVITY ON PROXY WALLET (CONTRACT):{Style.RESET_ALL}\n')
        proxy_activity_url = f'https://data-api.polymarket.com/activity?user={ENV.PROXY_WALLET}&type=TRADE'
        proxy_activities = await fetch_data_async(proxy_activity_url)
        
        if not isinstance(proxy_activities, list):
            proxy_activities = []
        
        print(f'   Address: {ENV.PROXY_WALLET}')
        print(f'   Trades: {len(proxy_activities)}')
        print(f'   Profile: https://polymarket.com/profile/{ENV.PROXY_WALLET}\n')
        
        if proxy_activities:
            buy_trades = [a for a in proxy_activities if a.get('side') == 'BUY']
            sell_trades = [a for a in proxy_activities if a.get('side') == 'SELL']
            total_buy_volume = sum(t.get('usdcSize', 0) for t in buy_trades)
            total_sell_volume = sum(t.get('usdcSize', 0) for t in sell_trades)
            
            print('   Proxy Wallet Statistics:')
            print(f'      • Buys: {len(buy_trades)} (${total_buy_volume:.2f})')
            print(f'      • Sells: {len(sell_trades)} (${total_sell_volume:.2f})')
            print(f'      • Volume: ${(total_buy_volume + total_sell_volume):.2f}\n')
            
            # Show last 3 trades
            print('   Last 3 trades:')
            for idx, trade in enumerate(proxy_activities[:3], 1):
                date = datetime.fromtimestamp(trade.get('timestamp', 0))
                print(f'      {idx}. {trade.get("side", "UNKNOWN")} - {trade.get("title", "Unknown")}')
                print(f'         ${trade.get("usdcSize", 0):.2f} @ {date.strftime("%Y-%m-%d")}')
            print('')
        else:
            print(f'   {Fore.YELLOW}No trades found on proxy wallet{Style.RESET_ALL}\n')
        
        print('─' * 65 + '\n')
        print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Check complete!\n')
        
    except Exception as error:
        print(f'\n{Fore.RED}[ERROR]{Style.RESET_ALL} Error: {error}')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(check_proxy_wallet())

