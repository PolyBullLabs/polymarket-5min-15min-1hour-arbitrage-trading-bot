#!/usr/bin/env python3
"""
Close stale/old positions
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style
from src.config.env import ENV

init(autoreset=True)


async def close_stale_positions():
    """
    Close stale/old positions
    
    This script identifies and closes positions that are older than a specified number of days.
    """
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Closing Stale Positions")
    print()
    
    # Get age threshold from user or use default
    days_input = input(f"Close positions older than (days, default: 30): ").strip()
    days_threshold = int(days_input) if days_input else 30
    
    print()
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching positions...")
    
    try:
        wallet = ENV.PROXY_WALLET
        url = f'https://data-api.polymarket.com/positions?user={wallet}'
        
        from src.utils.fetch_data import fetch_data_async
        positions = await fetch_data_async(url)
        
        if not isinstance(positions, list):
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch positions")
            return
        
        # Calculate cutoff timestamp
        from datetime import datetime, timedelta
        cutoff_time = (datetime.now() - timedelta(days=days_threshold)).timestamp()
        
        # Filter stale positions (would need timestamp from position data)
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Looking for positions older than {days_threshold} days...")
        
        print()
        print(f"{Fore.YELLOW}[NOTE]{Style.RESET_ALL} CLOB client implementation is required to execute sells")
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} See src/utils/create_clob_client.py for implementation")
        
        # TODO: When CLOB client is ready:
        # 1. Filter positions by age (need to track position open time)
        # 2. For each stale position, create sell order
        # 3. Post orders via CLOB client
        # 4. Report results
        
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to process positions: {e}")


if __name__ == '__main__':
    asyncio.run(close_stale_positions())

