#!/usr/bin/env python3
"""
Check both wallet addresses for comparison
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
from src.config.env import ENV
from src.utils.fetch_data import fetch_data_async
from src.utils.get_my_balance import get_my_balance_async
from colorama import init, Fore, Style

init(autoreset=True)

PROXY_WALLET = ENV.PROXY_WALLET


async def check_both_wallets():
    """Check both wallet addresses"""
    print(f'{Fore.CYAN}CHECKING BOTH ADDRESSES{Style.RESET_ALL}\n')
    print('─' * 65 + '\n')
    
    # These addresses should be configured or passed as arguments
    # For now, using PROXY_WALLET as address 1
    ADDRESS_1 = PROXY_WALLET  # From .env
    ADDRESS_2 = '0xd62531bc536bff72394fc5ef715525575787e809'  # Example - should be configurable
    
    try:
        # 1. Check first address (from .env)
        print(f'{Fore.CYAN}ADDRESS 1 (from .env - PROXY_WALLET):{Style.RESET_ALL}\n')
        print(f'   {ADDRESS_1}')
        print(f'   Profile: https://polymarket.com/profile/{ADDRESS_1}\n')
        
        addr1_activities = await fetch_data_async(
            f'https://data-api.polymarket.com/activity?user={ADDRESS_1}&type=TRADE'
        )
        addr1_positions = await fetch_data_async(
            f'https://data-api.polymarket.com/positions?user={ADDRESS_1}'
        )
        
        if not isinstance(addr1_activities, list):
            addr1_activities = []
        if not isinstance(addr1_positions, list):
            addr1_positions = []
        
        print(f'   • Trades in API: {len(addr1_activities)}')
        print(f'   • Positions in API: {len(addr1_positions)}')
        
        if addr1_activities:
            buy_trades = [a for a in addr1_activities if a.get('side') == 'BUY']
            sell_trades = [a for a in addr1_activities if a.get('side') == 'SELL']
            total_volume = (
                sum(t.get('usdcSize', 0) for t in buy_trades) +
                sum(t.get('usdcSize', 0) for t in sell_trades)
            )
            
            print(f'   • Buys: {len(buy_trades)}')
            print(f'   • Sells: {len(sell_trades)}')
            print(f'   • Volume: ${total_volume:.2f}')
            
            # Show proxyWallet from first trade
            if addr1_activities[0].get('proxyWallet'):
                print(f'   • proxyWallet in trades: {addr1_activities[0]["proxyWallet"]}')
        
        # Balance
        try:
            balance1 = await get_my_balance_async(ADDRESS_1)
            print(f'   • USDC Balance: ${balance1:.2f}')
        except Exception as e:
            print('   • USDC Balance: failed to get')
        
        print('\n' + '─' * 65 + '\n')
        
        # 2. Check second address
        print(f'{Fore.CYAN}ADDRESS 2:{Style.RESET_ALL}\n')
        print(f'   {ADDRESS_2}')
        print(f'   Profile: https://polymarket.com/profile/{ADDRESS_2}\n')
        
        addr2_activities = await fetch_data_async(
            f'https://data-api.polymarket.com/activity?user={ADDRESS_2}&type=TRADE'
        )
        addr2_positions = await fetch_data_async(
            f'https://data-api.polymarket.com/positions?user={ADDRESS_2}'
        )
        
        if not isinstance(addr2_activities, list):
            addr2_activities = []
        if not isinstance(addr2_positions, list):
            addr2_positions = []
        
        print(f'   • Trades in API: {len(addr2_activities)}')
        print(f'   • Positions in API: {len(addr2_positions)}')
        
        if addr2_activities:
            buy_trades = [a for a in addr2_activities if a.get('side') == 'BUY']
            sell_trades = [a for a in addr2_activities if a.get('side') == 'SELL']
            total_volume = (
                sum(t.get('usdcSize', 0) for t in buy_trades) +
                sum(t.get('usdcSize', 0) for t in sell_trades)
            )
            
            print(f'   • Buys: {len(buy_trades)}')
            print(f'   • Sells: {len(sell_trades)}')
            print(f'   • Volume: ${total_volume:.2f}')
            
            # Show proxyWallet from first trade
            if addr2_activities[0].get('proxyWallet'):
                print(f'   • proxyWallet in trades: {addr2_activities[0]["proxyWallet"]}')
            
            # Last 5 trades for comparison
            print('\n   Last 5 trades:')
            for idx, trade in enumerate(addr2_activities[:5], 1):
                date = datetime.fromtimestamp(trade.get('timestamp', 0))
                print(f'      {idx}. {trade.get("side", "UNKNOWN")} - {trade.get("title", "Unknown")}')
                print(f'         ${trade.get("usdcSize", 0):.2f} @ {date.strftime("%Y-%m-%d %H:%M:%S")}')
                tx_hash = trade.get('transactionHash', '')
                if tx_hash:
                    print(f'         TX: {tx_hash[:10]}...{tx_hash[-6:]}')
        
        # Balance
        try:
            balance2 = await get_my_balance_async(ADDRESS_2)
            print(f'\n   • USDC Balance: ${balance2:.2f}')
        except Exception as e:
            print('\n   • USDC Balance: failed to get')
        
        print('\n' + '─' * 65 + '\n')
        
        # 3. Comparison
        print(f'{Fore.CYAN}ADDRESS COMPARISON:{Style.RESET_ALL}\n')
        
        addr1_has_data = len(addr1_activities) > 0 or len(addr1_positions) > 0
        addr2_has_data = len(addr2_activities) > 0 or len(addr2_positions) > 0
        
        print(f'   Address 1 ({ADDRESS_1[:8]}...):')
        print(f'   {Fore.GREEN if addr1_has_data else Fore.RED}{"Has data" if addr1_has_data else "No data"}{Style.RESET_ALL}')
        print(f'   • Trades: {len(addr1_activities)}')
        print(f'   • Positions: {len(addr1_positions)}\n')
        
        print(f'   Address 2 ({ADDRESS_2[:8]}...):')
        print(f'   {Fore.GREEN if addr2_has_data else Fore.RED}{"Has data" if addr2_has_data else "No data"}{Style.RESET_ALL}')
        print(f'   • Trades: {len(addr2_activities)}')
        print(f'   • Positions: {len(addr2_positions)}\n')
        
        # 4. Check connection through proxyWallet field
        print('─' * 65 + '\n')
        print(f'{Fore.CYAN}CONNECTION BETWEEN ADDRESSES:{Style.RESET_ALL}\n')
        
        if addr1_activities and addr1_activities[0].get('proxyWallet') and \
           addr2_activities and addr2_activities[0].get('proxyWallet'):
            proxy1 = addr1_activities[0]['proxyWallet'].lower()
            proxy2 = addr2_activities[0]['proxyWallet'].lower()
            
            print(f'   Address 1 uses proxyWallet: {proxy1}')
            print(f'   Address 2 uses proxyWallet: {proxy2}\n')
            
            if proxy1 == proxy2:
                print(f'   {Fore.GREEN}Both addresses linked to one proxy wallet!{Style.RESET_ALL}\n')
                print('   This explains why profiles show the same data.\n')
            elif proxy1 == ADDRESS_2.lower():
                print(f'   {Fore.GREEN}Connection found!{Style.RESET_ALL}\n')
                print(f'   Address 1 ({ADDRESS_1[:8]}...) uses')
                print(f'   Address 2 ({ADDRESS_2[:8]}...) as proxy wallet!\n')
            elif proxy2 == ADDRESS_1.lower():
                print(f'   {Fore.GREEN}Connection found!{Style.RESET_ALL}\n')
                print(f'   Address 2 ({ADDRESS_2[:8]}...) uses')
                print(f'   Address 1 ({ADDRESS_1[:8]}...) as proxy wallet!\n')
            else:
                print(f'   {Fore.YELLOW}Addresses use different proxy wallets{Style.RESET_ALL}\n')
        
        print('─' * 65 + '\n')
        print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Check complete!\n')
        
    except Exception as error:
        print(f'\n{Fore.RED}[ERROR]{Style.RESET_ALL} Error: {error}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(check_both_wallets())

