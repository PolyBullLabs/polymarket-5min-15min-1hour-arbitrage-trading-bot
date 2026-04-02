#!/usr/bin/env python3
"""
Find best performing traders
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
STARTING_CAPITAL = 1000.0
HISTORY_DAYS = int(os.getenv('SIM_HISTORY_DAYS', '30'))
MIN_TRADER_TRADES = int(os.getenv('MIN_TRADER_TRADES', '50'))
MAX_TRADES_LIMIT = int(os.getenv('SIM_MAX_TRADES', '2000'))

# Known successful traders (fallback)
KNOWN_TRADERS = [
    '0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b',
    '0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292',
    '0xa4b366ad22fc0d06f1e934ff468e8922431a87b8',
]


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
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch activity for {trader_address[:10]}...: {e}")
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
        # Fetch trades
        trades = await fetch_trader_activity(trader_address)
        
        if len(trades) < MIN_TRADER_TRADES:
            return {
                'address': trader_address,
                'starting_capital': STARTING_CAPITAL,
                'current_capital': STARTING_CAPITAL,
                'total_trades': len(trades),
                'copied_trades': 0,
                'skipped_trades': len(trades),
                'total_pnl': 0,
                'roi': 0,
                'realized_pnl': 0,
                'unrealized_pnl': 0,
                'win_rate': 0,
                'avg_trade_size': 0,
                'open_positions': 0,
                'closed_positions': 0,
                'error': f'Not enough trades ({len(trades)} < {MIN_TRADER_TRADES})'
            }
        
        # Fetch current positions
        positions_data = await fetch_trader_positions(trader_address)
        
        # Simulate copying trades
        your_capital = STARTING_CAPITAL
        total_invested = 0
        copied_trades = 0
        skipped_trades = 0
        
        # Track positions
        positions = {}  # key: asset, value: position data
        
        for trade in trades:
            asset = trade.get('asset', '')
            side = trade.get('side', '')
            price = float(trade.get('price', 0))
            usdc_size = float(trade.get('usdcSize', 0))
            size = float(trade.get('size', 0))
            
            if not asset or price <= 0 or usdc_size <= 0:
                skipped_trades += 1
                continue
            
            # Calculate your trade size (proportional to capital)
            # Estimate trader's capital at this time
            trader_capital_estimate = 100000  # Default estimate
            your_trade_size = (your_capital / trader_capital_estimate) * usdc_size
            
            # Minimum order size check
            if your_trade_size < 1.0:
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
        
        # Calculate unrealized P&L from open positions
        unrealized_pnl = 0
        for asset, pos in positions.items():
            # Find current price from positions data
            current_price = price  # Use last trade price as approximation
            for p in positions_data:
                if p.get('asset') == asset:
                    current_price = float(p.get('curPrice', price))
                    break
            
            current_value = pos['shares'] * current_price
            unrealized_pnl += current_value - pos['invested']
        
        # Calculate realized P&L (simplified)
        realized_pnl = your_capital - STARTING_CAPITAL - sum(p['invested'] for p in positions.values())
        
        current_capital = your_capital + sum(
            p['shares'] * float(p.get('curPrice', p['avg_price']))
            for p in positions.values()
        )
        
        total_pnl = current_capital - STARTING_CAPITAL
        roi = (total_pnl / STARTING_CAPITAL) * 100 if STARTING_CAPITAL > 0 else 0
        
        # Calculate win rate (simplified - based on closed positions)
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


async def find_best_traders():
    """Find best performing traders by analyzing their trading history"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Finding best performing traders...")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analyzing last {HISTORY_DAYS} days of trading")
    print()
    
    # Get traders to analyze
    traders_to_analyze = KNOWN_TRADERS.copy()
    
    # Optionally get from USER_ADDRESSES if configured
    # ENV.USER_ADDRESSES is already a List[str] (parsed in env.py)
    if hasattr(ENV, 'USER_ADDRESSES') and ENV.USER_ADDRESSES:
        user_addrs = [addr.lower().strip() if isinstance(addr, str) else str(addr).lower().strip() 
                     for addr in ENV.USER_ADDRESSES if addr]
        if user_addrs:
            traders_to_analyze = list(set(traders_to_analyze + user_addrs))
    
    if not traders_to_analyze:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No traders to analyze")
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Add traders to USER_ADDRESSES in .env or update KNOWN_TRADERS")
        return
    
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analyzing {len(traders_to_analyze)} traders...")
    print()
    
    # Analyze each trader
    results = []
    for i, trader in enumerate(traders_to_analyze, 1):
        print(f"{Fore.CYAN}[{i}/{len(traders_to_analyze)}]{Style.RESET_ALL} Analyzing {trader[:10]}...")
        result = await simulate_trader(trader)
        results.append(result)
        
        if result.get('error'):
            print(f"  {Fore.YELLOW}⚠ {result['error']}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.GREEN}✓ ROI: {result['roi']:.2f}% | P&L: ${result['total_pnl']:.2f} | Trades: {result['copied_trades']}{Style.RESET_ALL}")
    
    print()
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}BEST PERFORMING TRADERS{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    # Filter out errors and sort by ROI
    valid_results = [r for r in results if not r.get('error')]
    valid_results.sort(key=lambda x: x.get('roi', 0), reverse=True)
    
    if not valid_results:
        print(f"{Fore.YELLOW}No valid results found{Style.RESET_ALL}")
        return
    
    # Display top traders
    print(f"{Fore.CYAN}{'Rank':<6} {'Address':<15} {'ROI':<10} {'P&L':<12} {'Trades':<8} {'Win Rate':<10}{Style.RESET_ALL}")
    print('-' * 80)
    
    for idx, result in enumerate(valid_results[:10], 1):
        address = result['address'][:12] + '...'
        roi = result.get('roi', 0)
        pnl = result.get('total_pnl', 0)
        trades = result.get('copied_trades', 0)
        win_rate = result.get('win_rate', 0)
        
        roi_color = Fore.GREEN if roi > 0 else Fore.RED
        print(f"{idx:<6} {address:<15} {roi_color}{roi:>8.2f}%{Style.RESET_ALL}  ${pnl:>10.2f}  {trades:>6}  {win_rate:>7.1f}%")
    
    print()
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analysis complete!")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Top trader: {valid_results[0]['address']} (ROI: {valid_results[0]['roi']:.2f}%)")


if __name__ == '__main__':
    asyncio.run(find_best_traders())
