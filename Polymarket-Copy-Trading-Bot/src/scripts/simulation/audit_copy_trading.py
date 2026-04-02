#!/usr/bin/env python3
"""
Audit copy trading algorithm

This script performs a comprehensive audit of the copy trading bot:
- Simulates trading for all configured traders
- Compares simulated results with actual bot performance (if available)
- Identifies discrepancies
- Analyzes trade execution accuracy
- Generates audit report
"""
import sys
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style
from src.config.env import ENV
from src.utils.fetch_data import fetch_data_async

init(autoreset=True)

# Configuration
AUDIT_DAYS = int(os.getenv('AUDIT_DAYS', '14'))
AUDIT_MULTIPLIER = float(os.getenv('AUDIT_MULTIPLIER', '1.0'))
AUDIT_STARTING_CAPITAL = float(os.getenv('AUDIT_STARTING_CAPITAL', '1000.0'))
MIN_ORDER_SIZE = float(os.getenv('SIM_MIN_ORDER_USD', '1.0'))
MAX_TRADES_LIMIT = int(os.getenv('SIM_MAX_TRADES', '3000'))
COPY_PERCENTAGE = float(os.getenv('COPY_PERCENTAGE', '1.0'))  # Copy 1% of trader's order size


def parse_trader_addresses() -> List[str]:
    """Parse trader addresses from environment"""
    addresses = []
    
    # Try AUDIT_ADDRESSES first
    if hasattr(ENV, 'AUDIT_ADDRESSES') and ENV.AUDIT_ADDRESSES:
        if isinstance(ENV.AUDIT_ADDRESSES, list):
            addresses = [addr.lower().strip() for addr in ENV.AUDIT_ADDRESSES]
        elif isinstance(ENV.AUDIT_ADDRESSES, str):
            addresses = [addr.lower().strip() for addr in ENV.AUDIT_ADDRESSES.split(',') if addr.strip()]
    
    # Fall back to USER_ADDRESSES
    if not addresses and hasattr(ENV, 'USER_ADDRESSES') and ENV.USER_ADDRESSES:
        if isinstance(ENV.USER_ADDRESSES, list):
            addresses = [addr.lower().strip() for addr in ENV.USER_ADDRESSES]
        elif isinstance(ENV.USER_ADDRESSES, str):
            addresses = [addr.lower().strip() for addr in ENV.USER_ADDRESSES.split(',') if addr.strip()]
    
    # Default test addresses if none found
    if not addresses:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No AUDIT_ADDRESSES or USER_ADDRESSES found")
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Using default test addresses...")
        addresses = [
            '0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b',
            '0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292',
        ]
    
    return addresses


async def fetch_trader_activity(trader_address: str) -> List[Dict[str, Any]]:
    """Fetch trading activity for a trader"""
    try:
        since_timestamp = int((datetime.now() - timedelta(days=AUDIT_DAYS)).timestamp())
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


async def simulate_trader(trader_address: str, starting_capital: float) -> Dict[str, Any]:
    """Simulate copying a trader's trades"""
    start_time = datetime.now()
    short_address = f"{trader_address[:6]}...{trader_address[-4]}"
    
    try:
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching trades for {short_address}...")
        trades = await fetch_trader_activity(trader_address)
        
        if not trades:
            return {
                'address': trader_address,
                'short_address': short_address,
                'starting_capital': starting_capital,
                'current_capital': starting_capital,
                'total_trades': 0,
                'copied_trades': 0,
                'skipped_trades': 0,
                'total_pnl': 0,
                'roi': 0,
                'realized_pnl': 0,
                'unrealized_pnl': 0,
                'win_rate': 0,
                'avg_trade_size': 0,
                'open_positions': 0,
                'closed_positions': 0,
                'simulation_time': (datetime.now() - start_time).total_seconds() * 1000,
                'trades': [],
                'positions': {},
                'error': 'No trades found'
            }
        
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Simulating {len(trades)} trades for {short_address}...")
        
        your_capital = starting_capital
        total_invested = 0.0
        copied_trades = 0
        skipped_trades = 0
        
        positions = {}  # key: position_key, value: position data
        
        for trade in trades:
            # Copy fixed percentage of trader's order size
            base_order_size = float(trade.get('usdcSize', 0)) * (COPY_PERCENTAGE / 100)
            order_size = base_order_size * AUDIT_MULTIPLIER
            
            if order_size < MIN_ORDER_SIZE:
                skipped_trades += 1
                continue
            
            if order_size > your_capital * 0.95:
                order_size = your_capital * 0.95
                if order_size < MIN_ORDER_SIZE:
                    skipped_trades += 1
                    continue
            
            asset = trade.get('asset', '')
            outcome = trade.get('outcome', 'Unknown')
            side = trade.get('side', '')
            price = float(trade.get('price', 0))
            size = float(trade.get('size', 0))
            
            if not asset or price <= 0:
                skipped_trades += 1
                continue
            
            position_key = f"{asset}:{outcome}"
            
            if side == 'BUY':
                shares_received = order_size / price if price > 0 else 0
                
                if position_key not in positions:
                    positions[position_key] = {
                        'market': trade.get('market', trade.get('slug', 'Unknown market')),
                        'outcome': outcome,
                        'entry_price': price,
                        'exit_price': None,
                        'invested': 0.0,
                        'current_value': 0.0,
                        'pnl': 0.0,
                        'closed': False,
                        'shares_held': 0.0,
                        'trades': []
                    }
                
                pos = positions[position_key]
                pos['trades'].append({
                    'timestamp': trade.get('timestamp', 0),
                    'side': 'BUY',
                    'price': price,
                    'size': shares_received,
                    'usdc_size': order_size,
                    'trader_size': float(trade.get('usdcSize', 0)),
                    'your_size': order_size
                })
                
                pos['invested'] += order_size
                pos['shares_held'] += shares_received
                pos['current_value'] = pos['shares_held'] * price
                your_capital -= order_size
                total_invested += order_size
                copied_trades += 1
            
            elif side == 'SELL':
                if position_key in positions:
                    pos = positions[position_key]
                    
                    if pos['shares_held'] > 0:
                        # Sell proportionally
                        trader_sell_percent = size / (size + 1)  # Approximate
                        shares_to_sell = min(pos['shares_held'] * trader_sell_percent, pos['shares_held'])
                        sell_value = shares_to_sell * price
                        
                        pos['trades'].append({
                            'timestamp': trade.get('timestamp', 0),
                            'side': 'SELL',
                            'price': price,
                            'size': shares_to_sell,
                            'usdc_size': sell_value,
                            'trader_size': float(trade.get('usdcSize', 0)),
                            'your_size': sell_value
                        })
                        
                        pos['shares_held'] -= shares_to_sell
                        pos['current_value'] = pos['shares_held'] * price
                        pos['exit_price'] = price
                        your_capital += sell_value
                        
                        if pos['shares_held'] < 0.001:
                            pos['closed'] = True
                            pos['shares_held'] = 0
                            pos['current_value'] = 0
                        
                        copied_trades += 1
                    else:
                        skipped_trades += 1
                else:
                    skipped_trades += 1
        
        # Calculate current values
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching current positions for {short_address}...")
        trader_positions = await fetch_trader_positions(trader_address)
        unrealized_pnl = 0.0
        realized_pnl = 0.0
        
        for key, sim_pos in positions.items():
            if not sim_pos['closed'] and sim_pos['shares_held'] > 0:
                asset_id = key.split(':')[0]
                trader_pos = next((tp for tp in trader_positions if tp.get('asset') == asset_id), None)
                
                if trader_pos and trader_pos.get('size', 0) > 0:
                    trader_size = float(trader_pos.get('size', 0))
                    trader_current_value = float(trader_pos.get('currentValue', 0))
                    current_price = trader_current_value / trader_size if trader_size > 0 else sim_pos['entry_price']
                    sim_pos['current_value'] = sim_pos['shares_held'] * current_price
                
                sim_pos['pnl'] = sim_pos['current_value'] - sim_pos['invested']
                unrealized_pnl += sim_pos['pnl']
            else:
                total_bought = sum(t['usdc_size'] for t in sim_pos['trades'] if t['side'] == 'BUY')
                total_sold = sum(t['usdc_size'] for t in sim_pos['trades'] if t['side'] == 'SELL')
                sim_pos['pnl'] = total_sold - total_bought
                realized_pnl += sim_pos['pnl']
        
        current_capital = your_capital + sum(
            p['current_value'] for p in positions.values() if not p['closed'] and p['shares_held'] > 0
        )
        
        total_pnl = current_capital - starting_capital
        roi = (total_pnl / starting_capital) * 100 if starting_capital > 0 else 0
        
        closed_positions = [p for p in positions.values() if p['closed']]
        winning_positions = [p for p in closed_positions if p['pnl'] > 0]
        win_rate = (len(winning_positions) / len(closed_positions) * 100) if closed_positions else 0
        
        avg_trade_size = total_invested / copied_trades if copied_trades > 0 else 0
        
        return {
            'address': trader_address,
            'short_address': short_address,
            'starting_capital': starting_capital,
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
            'open_positions': len([p for p in positions.values() if not p['closed']]),
            'closed_positions': len(closed_positions),
            'simulation_time': (datetime.now() - start_time).total_seconds() * 1000,
            'trades': trades,
            'positions': positions
        }
    
    except Exception as e:
        return {
            'address': trader_address,
            'short_address': short_address,
            'error': str(e),
            'roi': 0,
            'total_pnl': 0
        }


async def audit_copy_trading():
    """Main audit function"""
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  📊 COPY TRADING ALGORITHM AUDIT{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    # Parse trader addresses
    traders = parse_trader_addresses()
    
    if not traders:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No traders to audit")
        return
    
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Configuration:")
    print(f"  Traders: {len(traders)}")
    print(f"  Audit Days: {AUDIT_DAYS}")
    print(f"  Multiplier: {AUDIT_MULTIPLIER}x")
    print(f"  Copy Percentage: {COPY_PERCENTAGE}%")
    print(f"  Starting Capital: ${AUDIT_STARTING_CAPITAL}")
    print(f"  Min Order Size: ${MIN_ORDER_SIZE}")
    print()
    
    # Calculate capital per trader
    capital_per_trader = AUDIT_STARTING_CAPITAL / len(traders) if traders else AUDIT_STARTING_CAPITAL
    
    # Simulate each trader
    individual_results = []
    
    for trader in traders:
        result = await simulate_trader(trader, capital_per_trader)
        individual_results.append(result)
        print()
    
    # Calculate combined results
    combined_starting = sum(r.get('starting_capital', 0) for r in individual_results)
    combined_current = sum(r.get('current_capital', 0) for r in individual_results)
    combined_pnl = combined_current - combined_starting
    combined_roi = (combined_pnl / combined_starting * 100) if combined_starting > 0 else 0
    combined_realized = sum(r.get('realized_pnl', 0) for r in individual_results)
    combined_unrealized = sum(r.get('unrealized_pnl', 0) for r in individual_results)
    total_trades = sum(r.get('total_trades', 0) for r in individual_results)
    total_copied = sum(r.get('copied_trades', 0) for r in individual_results)
    total_skipped = sum(r.get('skipped_trades', 0) for r in individual_results)
    total_open = sum(r.get('open_positions', 0) for r in individual_results)
    total_closed = sum(r.get('closed_positions', 0) for r in individual_results)
    avg_win_rate = sum(r.get('win_rate', 0) for r in individual_results) / len(individual_results) if individual_results else 0
    
    # Analysis
    best_trader = max(individual_results, key=lambda r: r.get('roi', 0))
    worst_trader = min(individual_results, key=lambda r: r.get('roi', 0))
    
    # Expected combined ROI (weighted average)
    expected_roi = sum(
        (r.get('roi', 0) * r.get('starting_capital', 0)) / combined_starting
        for r in individual_results
    ) if combined_starting > 0 else 0
    
    roi_deviation = combined_roi - expected_roi
    
    # Print report
    print()
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  AUDIT REPORT{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    print(f"{Style.BRIGHT}Configuration:{Style.RESET_ALL}")
    print(f"  Traders: {', '.join([t[:10] + '...' for t in traders])}")
    print(f"  Days: {AUDIT_DAYS}")
    print(f"  Multiplier: {AUDIT_MULTIPLIER}x")
    print(f"  Copy Percentage: {COPY_PERCENTAGE}%")
    print(f"  Starting Capital: ${AUDIT_STARTING_CAPITAL}")
    print(f"  Capital per Trader: ${capital_per_trader:.2f}")
    print()
    
    print(f"{Style.BRIGHT}Individual Results:{Style.RESET_ALL}")
    print()
    
    for result in individual_results:
        if result.get('error'):
            print(f"  {Fore.RED}✗ {result.get('short_address', result.get('address', 'unknown'))}: {result['error']}{Style.RESET_ALL}")
            continue
        
        roi = result.get('roi', 0)
        roi_color = Fore.GREEN if roi > 0 else Fore.RED
        roi_sign = '+' if roi >= 0 else ''
        
        print(f"  {Fore.CYAN}{result.get('short_address', result.get('address', 'unknown'))}{Style.RESET_ALL}:")
        print(f"    ROI: {roi_color}{roi_sign}{roi:.2f}%{Style.RESET_ALL}")
        print(f"    P&L: ${result.get('total_pnl', 0):.2f}")
        print(f"    Trades: {result.get('copied_trades', 0)}/{result.get('total_trades', 0)} copied")
        print(f"    Positions: {result.get('open_positions', 0)} open, {result.get('closed_positions', 0)} closed")
        print()
    
    print(f"{Style.BRIGHT}Combined Results:{Style.RESET_ALL}")
    combined_roi_color = Fore.GREEN if combined_roi > 0 else Fore.RED
    combined_roi_sign = '+' if combined_roi >= 0 else ''
    print(f"  Starting Capital: ${combined_starting:.2f}")
    print(f"  Current Capital: ${combined_current:.2f}")
    print(f"  Total P&L: {combined_roi_color}{combined_roi_sign}${combined_pnl:.2f}{Style.RESET_ALL}")
    print(f"  ROI: {combined_roi_color}{combined_roi_sign}{combined_roi:.2f}%{Style.RESET_ALL}")
    print(f"  Realized P&L: ${combined_realized:.2f}")
    print(f"  Unrealized P&L: ${combined_unrealized:.2f}")
    print(f"  Total Trades: {total_trades}")
    print(f"  Copied: {total_copied}, Skipped: {total_skipped}")
    print(f"  Positions: {total_open} open, {total_closed} closed")
    print(f"  Avg Win Rate: {avg_win_rate:.1f}%")
    print()
    
    print(f"{Style.BRIGHT}Analysis:{Style.RESET_ALL}")
    print(f"  Best Trader: {best_trader.get('short_address', best_trader.get('address', 'unknown'))} ({best_trader.get('roi', 0):.2f}% ROI)")
    print(f"  Worst Trader: {worst_trader.get('short_address', worst_trader.get('address', 'unknown'))} ({worst_trader.get('roi', 0):.2f}% ROI)")
    print(f"  Expected Combined ROI: {expected_roi:.2f}%")
    print(f"  Actual Combined ROI: {combined_roi:.2f}%")
    print(f"  ROI Deviation: {roi_deviation:.2f}%")
    print()
    
    # Save report
    output_dir = project_root / 'audit_results'
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'config': {
            'traders': traders,
            'days': AUDIT_DAYS,
            'multiplier': AUDIT_MULTIPLIER,
            'starting_capital': AUDIT_STARTING_CAPITAL,
            'min_order_size': MIN_ORDER_SIZE,
            'capital_per_trader': capital_per_trader,
            'copy_percentage': COPY_PERCENTAGE,
        },
        'individual_results': individual_results,
        'combined_result': {
            'starting_capital': combined_starting,
            'current_capital': combined_current,
            'total_pnl': combined_pnl,
            'roi': combined_roi,
            'realized_pnl': combined_realized,
            'unrealized_pnl': combined_unrealized,
            'total_trades': total_trades,
            'copied_trades': total_copied,
            'skipped_trades': total_skipped,
            'open_positions': total_open,
            'closed_positions': total_closed,
            'win_rate': avg_win_rate,
            'capital_per_trader': capital_per_trader,
        },
        'analysis': {
            'total_profit': combined_pnl,
            'total_roi': combined_roi,
            'best_trader': best_trader.get('address', ''),
            'worst_trader': worst_trader.get('address', ''),
            'avg_win_rate': avg_win_rate,
            'expected_combined_roi': expected_roi,
            'actual_combined_roi': combined_roi,
            'roi_deviation': roi_deviation,
        }
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"{Fore.GREEN}✓ Audit report saved: {Fore.CYAN}{output_path}{Style.RESET_ALL}")
    print()


if __name__ == '__main__':
    try:
        asyncio.run(audit_copy_trading())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[INFO]{Style.RESET_ALL} Interrupted by user")
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Audit failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
