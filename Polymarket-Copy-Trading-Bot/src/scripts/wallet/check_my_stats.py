#!/usr/bin/env python3
"""
Check wallet statistics on Polymarket
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
from src.utils.get_my_balance import get_my_balance_async
from colorama import init, Fore, Style

init(autoreset=True)

PROXY_WALLET = ENV.PROXY_WALLET


async def check_my_stats():
    """Check wallet statistics"""
    print(f'{Fore.CYAN}Checking your wallet statistics on Polymarket{Style.RESET_ALL}\n')
    print(f'Wallet: {PROXY_WALLET}\n')
    print('─' * 65 + '\n')
    
    try:
        # 1. USDC Balance
        print(f'{Fore.CYAN}USDC BALANCE{Style.RESET_ALL}')
        balance = await get_my_balance_async(PROXY_WALLET)
        print(f'   Available: ${balance:.2f}\n')
        
        # 2. Open Positions
        print(f'{Fore.CYAN}OPEN POSITIONS{Style.RESET_ALL}')
        positions_url = f'https://data-api.polymarket.com/positions?user={PROXY_WALLET}'
        positions = await fetch_data_async(positions_url)
        
        if not isinstance(positions, list):
            positions = []
        
        if positions:
            print(f'   Total positions: {len(positions)}\n')
            
            total_value = sum(pos.get('currentValue', 0) or 0 for pos in positions)
            total_initial_value = sum(pos.get('initialValue', 0) or 0 for pos in positions)
            total_unrealized_pnl = sum(pos.get('cashPnl', 0) or 0 for pos in positions)
            total_realized_pnl = sum(pos.get('realizedPnl', 0) or 0 for pos in positions)
            
            print(f'   Current value: ${total_value:.2f}')
            print(f'   Initial value: ${total_initial_value:.2f}')
            if total_initial_value > 0:
                pnl_percent = (total_unrealized_pnl / total_initial_value) * 100
                print(f'   Unrealized P&L: ${total_unrealized_pnl:.2f} ({pnl_percent:.2f}%)')
            print(f'   Realized P&L: ${total_realized_pnl:.2f}\n')
            
            # Top 5 positions by profit
            print('   Top-5 positions by profit:\n')
            top_positions = sorted(
                positions,
                key=lambda p: p.get('percentPnl', 0) or 0,
                reverse=True
            )[:5]
            
            for idx, pos in enumerate(top_positions, 1):
                pnl = pos.get('percentPnl', 0) or 0
                pnl_sign = '📈' if pnl >= 0 else '📉'
                print(f'   {idx}. {pnl_sign} {pos.get("title", "Unknown")}')
                print(f'      {pos.get("outcome", "N/A")}')
                print(f'      Size: {pos.get("size", 0):.2f} tokens @ ${pos.get("avgPrice", 0):.3f}')
                cash_pnl = pos.get('cashPnl', 0) or 0
                print(f'      P&L: ${cash_pnl:.2f} ({pnl:.2f}%)')
                print(f'      Current price: ${pos.get("curPrice", 0):.3f}')
                if pos.get('slug'):
                    print(f'      https://polymarket.com/event/{pos.get("slug")}')
                print('')
        else:
            print(f'   {Fore.YELLOW}No open positions{Style.RESET_ALL}\n')
        
        # 3. Trading Activity
        print('─' * 65 + '\n')
        print(f'{Fore.CYAN}TRADING ACTIVITY{Style.RESET_ALL}')
        activity_url = f'https://data-api.polymarket.com/activity?user={PROXY_WALLET}&type=TRADE'
        activities = await fetch_data_async(activity_url)
        
        if not isinstance(activities, list):
            activities = []
        
        if activities:
            buy_trades = [a for a in activities if a.get('side') == 'BUY']
            sell_trades = [a for a in activities if a.get('side') == 'SELL']
            total_buy_volume = sum(t.get('usdcSize', 0) for t in buy_trades)
            total_sell_volume = sum(t.get('usdcSize', 0) for t in sell_trades)
            
            print(f'   Total trades: {len(activities)}')
            print(f'   Buys: {len(buy_trades)} (${total_buy_volume:.2f})')
            print(f'   Sells: {len(sell_trades)} (${total_sell_volume:.2f})')
            print(f'   Total volume: ${(total_buy_volume + total_sell_volume):.2f}\n')
            
            # Recent trades
            print('   Recent trades (last 5):\n')
            for idx, trade in enumerate(activities[:5], 1):
                from datetime import datetime
                date = datetime.fromtimestamp(trade.get('timestamp', 0))
                side = trade.get('side', 'UNKNOWN')
                side_color = Fore.GREEN if side == 'BUY' else Fore.RED
                print(f'   {idx}. {side_color}{side}{Style.RESET_ALL} - {trade.get("title", "Unknown")}')
                print(f'      ${trade.get("usdcSize", 0):.2f} @ {date.strftime("%Y-%m-%d %H:%M")}\n')
        else:
            print(f'   {Fore.YELLOW}No trading activity found{Style.RESET_ALL}\n')
        
        print('─' * 65 + '\n')
        print(f'{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Statistics check complete!\n')
        
    except Exception as error:
        print(f'\n{Fore.RED}[ERROR]{Style.RESET_ALL} Error: {error}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(check_my_stats())

