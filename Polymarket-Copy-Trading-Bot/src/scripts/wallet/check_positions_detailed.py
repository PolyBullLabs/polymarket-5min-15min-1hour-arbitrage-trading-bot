#!/usr/bin/env python3
"""
Check detailed positions information
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
from src.config.env import ENV
from src.utils.fetch_data import fetch_data_async
from colorama import init, Fore, Style

init(autoreset=True)

PROXY_WALLET = ENV.PROXY_WALLET


async def check_positions():
    """Check detailed positions"""
    print(f'\n{Fore.CYAN}CURRENT POSITIONS:{Style.RESET_ALL}\n')
    
    positions = await fetch_data_async(
        f'https://data-api.polymarket.com/positions?user={PROXY_WALLET}'
    )
    
    if not isinstance(positions, list) or not positions:
        print(f'{Fore.RED}No open positions{Style.RESET_ALL}')
        return
    
    print(f'{Fore.GREEN}Found positions: {len(positions)}{Style.RESET_ALL}\n')
    
    # Sort by current value
    sorted_positions = sorted(positions, key=lambda p: p.get('currentValue', 0), reverse=True)
    
    total_value = 0
    
    for pos in sorted_positions:
        total_value += pos.get('currentValue', 0)
        
        print('─' * 48)
        print(f'Market: {pos.get("title", "Unknown")}')
        print(f'Outcome: {pos.get("outcome", "Unknown")}')
        asset_id = pos.get('asset', '')
        print(f'Asset ID: {asset_id[:10]}...' if asset_id else 'Asset ID: N/A')
        print(f'Size: {pos.get("size", 0):.2f} shares')
        print(f'Avg Price: ${pos.get("avgPrice", 0):.4f}')
        print(f'Current Price: ${pos.get("curPrice", 0):.4f}')
        print(f'Initial Value: ${pos.get("initialValue", 0):.2f}')
        print(f'Current Value: ${pos.get("currentValue", 0):.2f}')
        cash_pnl = pos.get('cashPnl', 0) or 0
        percent_pnl = pos.get('percentPnl', 0) or 0
        print(f'PnL: ${cash_pnl:.2f} ({percent_pnl:.2f}%)')
        if pos.get('slug'):
            print(f'URL: https://polymarket.com/event/{pos.get("slug")}')
    
    print(f'\n{"─" * 48}')
    print(f'{Fore.CYAN}TOTAL CURRENT VALUE: ${total_value:.2f}{Style.RESET_ALL}')
    print('─' * 48 + '\n')
    
    # Identify large positions (greater than $5)
    large_positions = [p for p in sorted_positions if p.get('currentValue', 0) > 5]
    
    if large_positions:
        print(f'\n{Fore.YELLOW}LARGE POSITIONS (> $5): {len(large_positions)}{Style.RESET_ALL}\n')
        for pos in large_positions:
            print(
                f'• {pos.get("title", "Unknown")} [{pos.get("outcome", "N/A")}]: '
                f'${pos.get("currentValue", 0):.2f} '
                f'({pos.get("size", 0):.2f} shares @ ${pos.get("curPrice", 0):.4f})'
            )
        
        print(f'\n{Fore.CYAN}To sell 80% of these positions, use:{Style.RESET_ALL}\n')
        print('   python -m src.scripts.position.manual_sell\n')
        
        print(f'{Fore.CYAN}Data for selling:{Style.RESET_ALL}\n')
        for pos in large_positions:
            sell_size = int(pos.get('size', 0) * 0.8)
            print(f'   Asset ID: {pos.get("asset")}')
            print(f'   Size to sell: {sell_size} (80% of {pos.get("size", 0):.2f})')
            print(f'   Market: {pos.get("title")} [{pos.get("outcome")}]')
            print('')
    else:
        print(f'\n{Fore.GREEN}No large positions (> $5){Style.RESET_ALL}')


if __name__ == '__main__':
    asyncio.run(check_positions())

