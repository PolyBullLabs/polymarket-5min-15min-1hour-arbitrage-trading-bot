#!/usr/bin/env python3
"""
Simulate profitability of copying a trader
"""
import sys
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style
from src.config.env import ENV
from src.utils.fetch_data import fetch_data_async

init(autoreset=True)

# Configuration
STARTING_CAPITAL = float(os.getenv('SIM_STARTING_CAPITAL', '1000.0'))
HISTORY_DAYS = int(os.getenv('SIM_HISTORY_DAYS', '30'))
MULTIPLIER = float(os.getenv('TRADE_MULTIPLIER', '1.0'))
MIN_ORDER_SIZE = float(os.getenv('SIM_MIN_ORDER_USD', '1.0'))
MAX_TRADES_LIMIT = int(os.getenv('SIM_MAX_TRADES', '2000'))


async def fetch_trader_activity(trader_address: str) -> List[Dict[str, Any]]:
    """Fetch trading activity for a trader"""
    try:
        since_timestamp = int((datetime.now() - timedelta(days=HISTORY_DAYS)).timestamp())
        url = f'https://data-api.polymarket.com/activity?user={trader_address}&type=TRADE'
        
        all_trades = []
        offset = 0
        limit = 100
        
        while len(all_trades) < MAX_TRADES_LIMIT:
            batch_url = f'{url}&limit={limit}&offset={offset}'
            trades = await fetch_data_async(batch_url)
            
            if not isinstance(trades, list) or not trades:
                break
            
            # Filter by timestamp
            filtered = [t for t in trades if t.get('timestamp', 0) >= since_timestamp]
            if not filtered:
                break
            
            all_trades.extend(filtered)
            
            if len(trades) < limit:
                break
            
            offset += limit
        
        # Sort by timestamp
        all_trades.sort(key=lambda x: x.get('timestamp', 0))
        return all_trades[:MAX_TRADES_LIMIT]
    
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch activity: {e}")
        return []


async def fetch_trader_positions(trader_address: str) -> List[Dict[str, Any]]:
    """Fetch current positions for a trader"""
    try:
        url = f'https://data-api.polymarket.com/positions?user={trader_address}'
        positions = await fetch_data_async(url)
        return positions if isinstance(positions, list) else []
    except Exception:
        return []


async def simulate_trader(trader_address: str) -> Dict[str, Any]:
    """Simulate copying a trader's trades"""
    start_time = datetime.now()
    
    try:
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching trades for {trader_address[:10]}...")
        trades = await fetch_trader_activity(trader_address)
        
        if not trades:
            return {
                'address': trader_address,
                'error': 'No trades found',
                'roi': 0,
                'total_pnl': 0
            }
        
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Found {len(trades)} trades, simulating...")
        
        # Simulate copying trades
        your_capital = STARTING_CAPITAL
        total_invested = 0
        copied_trades = 0
        skipped_trades = 0
        
        positions = {}  # key: asset, value: position data
        
        for i, trade in enumerate(trades, 1):
            if i % 100 == 0:
                print(f"  Processing trade {i}/{len(trades)}...")
            
            asset = trade.get('asset', '')
            side = trade.get('side', '')
            price = float(trade.get('price', 0))
            usdc_size = float(trade.get('usdcSize', 0))
            size = float(trade.get('size', 0))
            
            if not asset or price <= 0 or usdc_size <= 0:
                skipped_trades += 1
                continue
            
            # Calculate your trade size (proportional to capital with multiplier)
            trader_capital_estimate = 100000  # Default estimate
            your_trade_size = (your_capital / trader_capital_estimate) * usdc_size * MULTIPLIER
            
            # Minimum order size check
            if your_trade_size < MIN_ORDER_SIZE:
                skipped_trades += 1
                continue
            
            if side == 'BUY':
                if your_capital >= your_trade_size:
                    your_capital -= your_trade_size
                    total_invested += your_trade_size
                    copied_trades += 1
                    
                    # Track position
                    if asset not in positions:
                        positions[asset] = {
                            'invested': 0,
                            'shares': 0,
                            'avg_price': 0
                        }
                    
                    pos = positions[asset]
                    total_shares = pos['shares'] + size
                    pos['invested'] += your_trade_size
                    pos['avg_price'] = pos['invested'] / total_shares if total_shares > 0 else price
                    pos['shares'] = total_shares
                else:
                    skipped_trades += 1
            
            elif side == 'SELL':
                if asset in positions and positions[asset]['shares'] > 0:
                    pos = positions[asset]
                    sell_ratio = min(size / pos['shares'], 1.0)
                    sell_value = pos['invested'] * sell_ratio
                    proceeds = your_trade_size
                    
                    your_capital += proceeds
                    pos['invested'] -= sell_value
                    pos['shares'] -= size * sell_ratio
                    
                    if pos['shares'] <= 0.001:
                        del positions[asset]
                    
                    copied_trades += 1
                else:
                    skipped_trades += 1
        
        # Get current positions for unrealized P&L
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching current positions...")
        positions_data = await fetch_trader_positions(trader_address)
        unrealized_pnl = 0
        
        for asset, pos in positions.items():
            # Find current price from positions data
            current_price = pos['avg_price']  # Default to avg price
            for p in positions_data:
                if p.get('asset') == asset:
                    current_price = float(p.get('curPrice', current_price))
                    break
            
            current_value = pos['shares'] * current_price
            unrealized_pnl += current_value - pos['invested']
        
        # Calculate realized P&L
        realized_pnl = your_capital - STARTING_CAPITAL - sum(p['invested'] for p in positions.values())
        
        current_capital = your_capital + sum(
            p['shares'] * float(p.get('curPrice', p['avg_price']))
            for p in positions.values()
        )
        
        total_pnl = current_capital - STARTING_CAPITAL
        roi = (total_pnl / STARTING_CAPITAL) * 100 if STARTING_CAPITAL > 0 else 0
        
        # Calculate win rate (simplified)
        closed_count = copied_trades - len(positions)
        win_rate = 50.0  # Default estimate
        
        # Calculate average trade size
        avg_trade_size = total_invested / copied_trades if copied_trades > 0 else 0
        
        simulation_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            'address': trader_address,
            'starting_capital': STARTING_CAPITAL,
            'current_capital': current_capital,
            'total_trades': len(trades),
            'copied_trades': copied_trades,
            'skipped_trades': skipped_trades,
            'total_pnl': total_pnl,
            'roi': roi,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'win_rate': win_rate,
            'avg_trade_size': avg_trade_size,
            'open_positions': len(positions),
            'closed_positions': closed_count,
            'simulation_time': simulation_time
        }
    
    except Exception as e:
        return {
            'address': trader_address,
            'error': str(e),
            'roi': 0,
            'total_pnl': 0
        }


async def simulate_profitability():
    """Simulate profitability by analyzing historical trades"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Simulating profitability...")
    print()
    
    # Get trader address
    trader_address = os.getenv('SIM_TRADER_ADDRESS', '').strip()
    
    # If not set, try to get from USER_ADDRESSES
    if not trader_address and hasattr(ENV, 'USER_ADDRESSES') and ENV.USER_ADDRESSES:
        if isinstance(ENV.USER_ADDRESSES, list) and ENV.USER_ADDRESSES:
            trader_address = ENV.USER_ADDRESSES[0].strip()
        elif isinstance(ENV.USER_ADDRESSES, str):
            addresses = [addr.strip() for addr in ENV.USER_ADDRESSES.split(',') if addr.strip()]
            if addresses:
                trader_address = addresses[0]
    
    # If still not set, prompt user
    if not trader_address:
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} No trader address specified")
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Options:")
        print(f"  1. Set SIM_TRADER_ADDRESS environment variable")
        print(f"  2. Add trader to USER_ADDRESSES in .env file")
        print(f"  3. Enter trader address now")
        print()
        
        trader_address = input("Enter trader address (or press Enter to exit): ").strip()
        
        if not trader_address:
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Exiting...")
            return
    
    if not trader_address.startswith('0x') or len(trader_address) != 42:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Invalid Ethereum address format")
        return
    
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Configuration:")
    print(f"  Trader: {trader_address}")
    print(f"  History Days: {HISTORY_DAYS}")
    print(f"  Multiplier: {MULTIPLIER}x")
    print(f"  Min Order Size: ${MIN_ORDER_SIZE}")
    print(f"  Starting Capital: ${STARTING_CAPITAL}")
    print()
    
    # Run simulation
    result = await simulate_trader(trader_address)
    
    if result.get('error'):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {result['error']}")
        return
    
    # Display results
    print()
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}SIMULATION RESULTS{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    print(f"{Fore.CYAN}Trader:{Style.RESET_ALL} {result['address']}")
    print(f"{Fore.CYAN}Profile:{Style.RESET_ALL} https://polymarket.com/profile/{result['address']}")
    print()
    
    print(f"{Fore.CYAN}Capital:{Style.RESET_ALL}")
    print(f"  Starting: ${result['starting_capital']:.2f}")
    print(f"  Current:  ${result['current_capital']:.2f}")
    print()
    
    roi = result.get('roi', 0)
    roi_color = Fore.GREEN if roi > 0 else Fore.RED
    
    print(f"{Fore.CYAN}Performance:{Style.RESET_ALL}")
    print(f"  Total P&L: {roi_color}${result.get('total_pnl', 0):.2f} ({roi:.2f}%){Style.RESET_ALL}")
    print(f"  Realized P&L: ${result.get('realized_pnl', 0):.2f}")
    print(f"  Unrealized P&L: ${result.get('unrealized_pnl', 0):.2f}")
    print()
    
    print(f"{Fore.CYAN}Trading Stats:{Style.RESET_ALL}")
    print(f"  Total Trades: {result.get('total_trades', 0)}")
    print(f"  Copied Trades: {result.get('copied_trades', 0)}")
    print(f"  Skipped Trades: {result.get('skipped_trades', 0)}")
    print(f"  Average Trade Size: ${result.get('avg_trade_size', 0):.2f}")
    print()
    
    print(f"{Fore.CYAN}Positions:{Style.RESET_ALL}")
    print(f"  Open Positions: {result.get('open_positions', 0)}")
    print(f"  Closed Positions: {result.get('closed_positions', 0)}")
    print()
    
    print(f"{Fore.CYAN}Simulation Time:{Style.RESET_ALL} {result.get('simulation_time', 0):.0f}ms")
    print()
    
    # Summary
    if roi > 0:
        print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Simulation shows positive ROI: {roi:.2f}%")
    else:
        print(f"{Fore.RED}[WARNING]{Style.RESET_ALL} Simulation shows negative ROI: {roi:.2f}%")


if __name__ == '__main__':
    asyncio.run(simulate_profitability())
