#!/usr/bin/env python3
"""
Check recent trading activity
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
from colorama import init, Fore, Style

init(autoreset=True)


async def check_recent_activity():
    """Check recent trading activity"""
    wallet = ENV.PROXY_WALLET
    url = f'https://data-api.polymarket.com/activity?user={wallet}&type=TRADE'
    activities = await fetch_data_async(url)
    
    if not isinstance(activities, list) or not activities:
        print(f'{Fore.YELLOW}[INFO]{Style.RESET_ALL} No trade data available')
        return
    
    # Redemption ended at 18:14:16 UTC (October 31, 2025)
    redemption_end_time = datetime(2025, 10, 31, 18, 14, 16).timestamp()
    
    print('=' * 63)
    print(f'{Fore.CYAN}CLOSED POSITIONS (Redeemed October 31, 2025 at 18:00-18:14){Style.RESET_ALL}')
    print('=' * 63 + '\n')
    print(f'{Fore.GREEN}TOTAL RECEIVED FROM REDEMPTION: $66.37 USDC{Style.RESET_ALL}\n')
    
    print('=' * 63)
    print(f'{Fore.CYAN}PURCHASES AFTER REDEMPTION (after 18:14 UTC October 31){Style.RESET_ALL}')
    print('=' * 63 + '\n')
    
    trades_after_redemption = [
        t for t in activities
        if t.get('timestamp', 0) > redemption_end_time and t.get('side') == 'BUY'
    ]
    
    if not trades_after_redemption:
        print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} No purchases after redemption!\n')
        print('This means funds should be in the balance.')
        return
    
    total_spent = 0
    
    for i, trade in enumerate(trades_after_redemption, 1):
        date = datetime.fromtimestamp(trade.get('timestamp', 0))
        value = trade.get('usdcSize', 0)
        total_spent += value
        
        print(f'{i}. {Fore.GREEN}BOUGHT:{Style.RESET_ALL} {trade.get("title") or trade.get("market") or "Unknown"}')
        print(f'   Spent: ${value:.2f}')
        print(f'   Size: {trade.get("size", 0):.2f} tokens @ ${trade.get("price", 0):.4f}')
        print(f'   Date: {date.strftime("%Y-%m-%d %H:%M:%S")}')
        tx_hash = trade.get('transactionHash', '')
        if tx_hash:
            print(f'   TX: https://polygonscan.com/tx/{tx_hash[:20]}...\n')
    
    print('=' * 63)
    print(f'{Fore.CYAN}TOTAL PURCHASES AFTER REDEMPTION:{Style.RESET_ALL}')
    print(f'   Number of trades: {len(trades_after_redemption)}')
    print(f'   SPENT: ${total_spent:.2f} USDC')
    print('=' * 63 + '\n')
    
    print(f'{Fore.CYAN}EXPLANATION OF WHERE THE MONEY WENT:{Style.RESET_ALL}\n')
    print(f'   Received from redemption: +$66.37')
    print(f'   Spent on new purchases: -${total_spent:.2f}')
    print(f'   Balance change: ${(66.37 - total_spent):.2f}')
    print('\n' + '=' * 63 + '\n')
    
    # Show recent sales too
    print(f'{Fore.CYAN}RECENT SALES:{Style.RESET_ALL}\n')
    recent_sells = [t for t in activities if t.get('side') == 'SELL'][:10]
    
    total_sold = 0
    for i, trade in enumerate(recent_sells, 1):
        date = datetime.fromtimestamp(trade.get('timestamp', 0))
        value = trade.get('usdcSize', 0)
        total_sold += value
        
        print(f'{i}. {Fore.RED}SOLD:{Style.RESET_ALL} {trade.get("title") or trade.get("market") or "Unknown"}')
        print(f'   Received: ${value:.2f}')
        print(f'   Date: {date.strftime("%Y-%m-%d %H:%M:%S")}\n')
    
    print('=' * 63)
    print(f'{Fore.CYAN}Sold in recent trades: ${total_sold:.2f}{Style.RESET_ALL}')
    print('=' * 63)


if __name__ == '__main__':
    asyncio.run(check_recent_activity())

