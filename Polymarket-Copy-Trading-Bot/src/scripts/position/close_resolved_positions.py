#!/usr/bin/env python3
"""
Close resolved positions
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style
from src.config.env import ENV

init(autoreset=True)


async def close_resolved_positions():
    """
    Close resolved positions (positions that have reached ~$1 or ~$0)
    
    This script identifies positions that have resolved (price near $1 or $0)
    and closes them.
    """
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Closing Resolved Positions")
    print()
    
    RESOLVED_HIGH = 0.99  # Position won (price ~$1)
    RESOLVED_LOW = 0.01   # Position lost (price ~$0)
    
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching positions...")
    
    try:
        wallet = ENV.PROXY_WALLET
        url = f'https://data-api.polymarket.com/positions?user={wallet}'
        
        from src.utils.fetch_data import fetch_data_async
        positions = await fetch_data_async(url)
        
        if not isinstance(positions, list):
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch positions")
            return
        
        # Filter resolved positions
        resolved_positions = []
        for pos in positions:
            price = pos.get('curPrice', 0)
            if price >= RESOLVED_HIGH or price <= RESOLVED_LOW:
                resolved_positions.append(pos)
        
        if not resolved_positions:
            print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} No resolved positions found")
            return
        
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Found {len(resolved_positions)} resolved positions:")
        for pos in resolved_positions:
            price = pos.get('curPrice', 0)
            status = "WON" if price >= RESOLVED_HIGH else "LOST"
            print(f"  - {pos.get('title', 'Unknown')}: ${pos.get('currentValue', 0):.2f} ({status})")
        
        print()
        print(f"{Fore.YELLOW}[NOTE]{Style.RESET_ALL} CLOB client implementation is required to execute sells")
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} See src/utils/create_clob_client.py for implementation")
        
        # TODO: When CLOB client is ready:
        # 1. For each resolved position, create sell order at market price
        # 2. Post orders via CLOB client
        # 3. Report results
        
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to process positions: {e}")


if __name__ == '__main__':
    asyncio.run(close_resolved_positions())

