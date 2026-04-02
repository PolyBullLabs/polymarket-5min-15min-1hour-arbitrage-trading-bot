#!/usr/bin/env python3
"""
Manually sell a specific position
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


async def manual_sell():
    """
    Manually sell a specific position
    
    This script allows you to manually sell a position by providing:
    - Position asset ID (token ID)
    - Amount to sell (optional, defaults to full position)
    """
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Manual Position Sell")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} This feature requires CLOB client implementation")
    print()
    
    # Get position details from user
    print(f"{Fore.YELLOW}Enter position details:{Style.RESET_ALL}")
    asset_id = input("Asset ID (token ID): ").strip()
    
    if not asset_id:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Asset ID is required")
        return
    
    amount = input("Amount to sell (leave empty for full position): ").strip()
    
    print()
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Position details:")
    print(f"  Asset ID: {asset_id}")
    print(f"  Amount: {amount if amount else 'Full position'}")
    print()
    
    # TODO: Implement when CLOB client is ready
    # 1. Create CLOB client
    # 2. Get current position balance
    # 3. Get order book for the position
    # 4. Create sell order
    # 5. Post order via CLOB client
    # 6. Monitor order status
    
    print(f"{Fore.YELLOW}[NOTE]{Style.RESET_ALL} CLOB client implementation is required to execute trades")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} See src/utils/create_clob_client.py for implementation")


if __name__ == '__main__':
    asyncio.run(manual_sell())

