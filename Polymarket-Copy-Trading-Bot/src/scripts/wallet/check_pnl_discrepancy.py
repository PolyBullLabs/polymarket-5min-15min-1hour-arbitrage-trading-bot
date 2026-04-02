#!/usr/bin/env python3
"""
Check P&L discrepancy between open and closed positions
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


async def check_discrepancy():
    """Check P&L discrepancy"""
    print(f'{Fore.CYAN}Detailed P&L discrepancy check{Style.RESET_ALL}\n')
    print(f'Wallet: {PROXY_WALLET}\n')
    print('─' * 65 + '\n')
    
    try:
        # 1. Get all positions (open and closed)
        print(f'{Fore.CYAN}Fetching data from Polymarket API...{Style.RESET_ALL}\n')
        
        positions_url = f'https://data-api.polymarket.com/positions?user={PROXY_WALLET}'
        positions = await fetch_data_async(positions_url)
        
        if not isinstance(positions, list):
            positions = []
        
        print(f'Fetched positions: {len(positions)}\n')
        
        # 2. Separate into open and closed
        open_positions = [p for p in positions if p.get('size', 0) > 0]
        closed_positions = [p for p in positions if p.get('size', 0) == 0]
        
        print(f'• Open: {len(open_positions)}')
        print(f'• Closed: {len(closed_positions)}\n')
        
        print('─' * 65 + '\n')
        
        # 3. Analysis of OPEN positions
        print(f'{Fore.CYAN}OPEN POSITIONS:{Style.RESET_ALL}\n')
        total_open_value = 0
        total_open_initial = 0
        total_unrealized_pnl = 0
        total_open_realized = 0
        
        for idx, pos in enumerate(open_positions, 1):
            total_open_value += pos.get('currentValue', 0) or 0
            total_open_initial += pos.get('initialValue', 0) or 0
            total_unrealized_pnl += pos.get('cashPnl', 0) or 0
            total_open_realized += pos.get('realizedPnl', 0) or 0
            
            print(f'{idx}. {pos.get("title", "Unknown")} - {pos.get("outcome", "N/A")}')
            print(f'   Size: {pos.get("size", 0):.2f} @ ${pos.get("avgPrice", 0):.3f}')
            print(f'   Current Value: ${pos.get("currentValue", 0):.2f}')
            print(f'   Initial Value: ${pos.get("initialValue", 0):.2f}')
            cash_pnl = pos.get('cashPnl', 0) or 0
            percent_pnl = pos.get('percentPnl', 0) or 0
            print(f'   Unrealized P&L: ${cash_pnl:.2f} ({percent_pnl:.2f}%)')
            print(f'   Realized P&L: ${pos.get("realizedPnl", 0) or 0:.2f}')
            print('')
        
        print(f'   TOTAL for open:')
        print(f'   • Current value: ${total_open_value:.2f}')
        print(f'   • Initial value: ${total_open_initial:.2f}')
        print(f'   • Unrealized P&L: ${total_unrealized_pnl:.2f}')
        print(f'   • Realized P&L: ${total_open_realized:.2f}\n')
        
        print('─' * 65 + '\n')
        
        # 4. Analysis of CLOSED positions
        print(f'{Fore.CYAN}CLOSED POSITIONS:{Style.RESET_ALL}\n')
        total_closed_realized = 0
        total_closed_initial = 0
        
        for idx, pos in enumerate(closed_positions, 1):
            total_closed_realized += pos.get('realizedPnl', 0) or 0
            total_closed_initial += pos.get('initialValue', 0) or 0
            
            print(f'{idx}. {pos.get("title", "Unknown")} - {pos.get("outcome", "N/A")}')
            print(f'   Initial Value: ${pos.get("initialValue", 0):.2f}')
            print(f'   Realized P&L: ${pos.get("realizedPnl", 0) or 0:.2f}')
            print('')
        
        print(f'   TOTAL for closed:')
        print(f'   • Initial value: ${total_closed_initial:.2f}')
        print(f'   • Realized P&L: ${total_closed_realized:.2f}\n')
        
        print('─' * 65 + '\n')
        
        # 5. Summary
        print(f'{Fore.CYAN}SUMMARY:{Style.RESET_ALL}\n')
        total_realized = total_open_realized + total_closed_realized
        total_initial = total_open_initial + total_closed_initial
        
        print(f'   Total Initial Value: ${total_initial:.2f}')
        print(f'   Total Current Value (open): ${total_open_value:.2f}')
        print(f'   Total Unrealized P&L: ${total_unrealized_pnl:.2f}')
        print(f'   Total Realized P&L: ${total_realized:.2f}')
        print(f'   Total P&L: ${total_unrealized_pnl + total_realized:.2f}\n')
        
        print('─' * 65 + '\n')
        print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Analysis complete!\n')
        
    except Exception as error:
        print(f'\n{Fore.RED}[ERROR]{Style.RESET_ALL} Error: {error}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(check_discrepancy())

