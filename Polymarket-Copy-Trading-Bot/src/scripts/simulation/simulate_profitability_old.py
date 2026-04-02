#!/usr/bin/env python3
"""
Old simulation logic (legacy version)

This uses the previous simulation algorithm before improvements.
The main difference is in how position sizing is calculated:
- OLD: ratio = my_balance / (trader_positions_value + trade.usdcSize)
- OLD: multiplier only applied if orderSize < MIN_ORDER_SIZE
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


def get_trader_positions_value_at_time(timestamp: int, trades: List[Dict[str, Any]]) -> float:
    """Calculate approximate position value based on trades up to this point"""
    past_trades = [t for t in trades if t.get('timestamp', 0) <= timestamp]
    positions_value = 0.0
    
    # Simple approximation: sum all BUY trades minus SELL trades
    for trade in past_trades:
        if trade.get('side') == 'BUY':
            positions_value += float(trade.get('usdcSize', 0))
        else:
            positions_value -= float(trade.get('usdcSize', 0))
    
    return max(positions_value, 0.0)


async def simulate_copy_trading_old_logic(trader_address: str, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simulate copying trades using OLD LOGIC"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Starting simulation with OLD LOGIC...")
    print(f"{Fore.YELLOW}[NOTE]{Style.RESET_ALL} OLD LOGIC: ratio = my_balance / (trader_positions_value + trade.usdcSize)")
    print(f"{Fore.YELLOW}[NOTE]{Style.RESET_ALL}           multiplier only applied to trades < ${MIN_ORDER_SIZE}")
    print()
    
    your_balance = STARTING_CAPITAL  # Available USDC balance
    total_invested = 0.0
    copied_trades = 0
    skipped_trades = 0
    
    positions = {}  # key: position_key, value: position data
    
    for i, trade in enumerate(trades, 1):
        if i % 100 == 0:
            print(f"  Processing trade {i}/{len(trades)}...")
        
        asset = trade.get('asset', '')
        outcome = trade.get('outcome', 'Unknown')
        side = trade.get('side', '')
        price = float(trade.get('price', 0))
        usdc_size = float(trade.get('usdcSize', 0))
        size = float(trade.get('size', 0))
        timestamp = trade.get('timestamp', 0)
        
        if not asset or price <= 0 or usdc_size <= 0:
            skipped_trades += 1
            continue
        
        # OLD LOGIC: Get trader's position value (not including USDC balance)
        trader_positions_value = get_trader_positions_value_at_time(timestamp, trades)
        
        # OLD LOGIC: Calculate ratio = my_balance / (trader_positions + trade.usdcSize)
        denominator = trader_positions_value + usdc_size
        if denominator <= 0:
            skipped_trades += 1
            continue
        
        ratio = your_balance / denominator
        order_size = usdc_size * ratio
        
        # OLD LOGIC: Only apply multiplier if below minimum
        if order_size < MIN_ORDER_SIZE:
            order_size = order_size * MULTIPLIER
        
        # Check if order meets minimum after multiplier
        if order_size < MIN_ORDER_SIZE:
            skipped_trades += 1
            continue
        
        # Check if we have enough balance (use 95% to avoid rounding issues)
        if order_size > your_balance * 0.95:
            order_size = your_balance * 0.95
            if order_size < MIN_ORDER_SIZE:
                skipped_trades += 1
                continue
        
        position_key = f"{asset}:{outcome}"
        
        if side == 'BUY':
            # BUY trade
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
                    'trades': []
                }
            
            pos = positions[position_key]
            pos['trades'].append({
                'timestamp': timestamp,
                'side': 'BUY',
                'price': price,
                'size': shares_received,
                'usdc_size': order_size,
                'trader_balance': trader_positions_value,
                'your_balance': your_balance,
                'ratio': ratio,
                'your_size': order_size
            })
            
            pos['invested'] += order_size
            pos['current_value'] += order_size
            your_balance -= order_size
            total_invested += order_size
            copied_trades += 1
        
        elif side == 'SELL':
            # SELL trade
            if position_key in positions:
                pos = positions[position_key]
                
                sell_amount = min(order_size, pos['current_value'])
                
                pos['trades'].append({
                    'timestamp': timestamp,
                    'side': 'SELL',
                    'price': price,
                    'size': sell_amount / price if price > 0 else 0,
                    'usdc_size': sell_amount,
                    'trader_balance': trader_positions_value,
                    'your_balance': your_balance,
                    'ratio': ratio,
                    'your_size': sell_amount
                })
                
                pos['current_value'] -= sell_amount
                pos['exit_price'] = price
                your_balance += sell_amount
                
                if pos['current_value'] < 0.01:
                    pos['closed'] = True
                    pos['pnl'] = your_balance + pos['current_value'] - pos['invested']
                
                copied_trades += 1
            else:
                skipped_trades += 1
    
    # Calculate current values based on trader's current positions
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching current positions...")
    trader_positions = await fetch_trader_positions(trader_address)
    
    total_current_value = your_balance
    unrealized_pnl = 0.0
    realized_pnl = 0.0
    
    for key, sim_pos in positions.items():
        if not sim_pos['closed']:
            # Find matching trader position to get current value
            asset_id = key.split(':')[0]
            trader_pos = next((tp for tp in trader_positions if tp.get('asset') == asset_id), None)
            
            if trader_pos:
                trader_size = float(trader_pos.get('size', 0))
                trader_current_value = float(trader_pos.get('currentValue', 0))
                current_price = trader_current_value / trader_size if trader_size > 0 else sim_pos['entry_price']
                
                # Calculate remaining shares
                total_shares = sum(t['size'] for t in sim_pos['trades'] if t['side'] == 'BUY')
                sold_shares = sum(t['size'] for t in sim_pos['trades'] if t['side'] == 'SELL')
                remaining_shares = total_shares - sold_shares
                
                sim_pos['current_value'] = remaining_shares * current_price
            
            sim_pos['pnl'] = sim_pos['current_value'] - sim_pos['invested']
            unrealized_pnl += sim_pos['pnl']
            total_current_value += sim_pos['current_value']
        else:
            # Closed position - calculate realized P&L
            total_bought = sum(t['usdc_size'] for t in sim_pos['trades'] if t['side'] == 'BUY')
            total_sold = sum(t['usdc_size'] for t in sim_pos['trades'] if t['side'] == 'SELL')
            sim_pos['pnl'] = total_sold - total_bought
            realized_pnl += sim_pos['pnl']
    
    current_capital = your_balance + sum(
        p['current_value'] for p in positions.values() if not p['closed']
    )
    
    total_pnl = current_capital - STARTING_CAPITAL
    roi = (total_pnl / STARTING_CAPITAL) * 100 if STARTING_CAPITAL > 0 else 0
    
    return {
        'address': trader_address,
        'starting_capital': STARTING_CAPITAL,
        'current_capital': current_capital,
        'total_trades': len(trades),
        'copied_trades': copied_trades,
        'skipped_trades': skipped_trades,
        'total_invested': total_invested,
        'current_value': total_current_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized_pnl,
        'total_pnl': total_pnl,
        'roi': roi,
        'positions': list(positions.values())
    }


async def simulate_profitability_old():
    """
    Old simulation logic (legacy version)
    
    This uses the previous simulation algorithm before improvements.
    """
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Running old simulation logic...")
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
    
    try:
        # Fetch trades
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Fetching trades...")
        trades = await fetch_trader_activity(trader_address)
        
        if not trades:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No trades found")
            return
        
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Found {len(trades)} trades")
        print()
        
        # Run simulation with old logic
        result = await simulate_copy_trading_old_logic(trader_address, trades)
        
        # Display results
        print()
        print('=' * 80)
        print(f"{Fore.CYAN}{Style.BRIGHT}COPY TRADING SIMULATION REPORT (OLD LOGIC){Style.RESET_ALL}")
        print('=' * 80)
        print()
        
        print(f"{Fore.CYAN}Trader:{Style.RESET_ALL} {result['address']}")
        print(f"{Fore.CYAN}Multiplier:{Style.RESET_ALL} {MULTIPLIER}x")
        print(f"{Fore.CYAN}Logic:{Style.RESET_ALL} {Fore.YELLOW}OLD (ratio = my_balance / trader_positions){Style.RESET_ALL}")
        print()
        
        print(f"{Fore.CYAN}Capital:{Style.RESET_ALL}")
        print(f"  Starting: ${result['starting_capital']:.2f}")
        print(f"  Current:  ${result['current_capital']:.2f}")
        print()
        
        roi = result.get('roi', 0)
        roi_color = Fore.GREEN if roi > 0 else Fore.RED
        pnl_color = Fore.GREEN if result.get('total_pnl', 0) >= 0 else Fore.RED
        
        print(f"{Fore.CYAN}Performance:{Style.RESET_ALL}")
        pnl_sign = '+' if result.get('total_pnl', 0) >= 0 else ''
        roi_sign = '+' if roi >= 0 else ''
        print(f"  Total P&L:     {pnl_color}{pnl_sign}${result.get('total_pnl', 0):.2f}{Style.RESET_ALL}")
        print(f"  ROI:           {roi_color}{roi_sign}{roi:.2f}%{Style.RESET_ALL}")
        print(f"  Realized:      ${result.get('realized_pnl', 0):.2f}")
        print(f"  Unrealized:    ${result.get('unrealized_pnl', 0):.2f}")
        print()
        
        print(f"{Fore.CYAN}Trades:{Style.RESET_ALL}")
        print(f"  Total trades:  {result.get('total_trades', 0)}")
        print(f"  Copied:        {Fore.GREEN}{result.get('copied_trades', 0)}{Style.RESET_ALL}")
        print(f"  Skipped:       {Fore.YELLOW}{result.get('skipped_trades', 0)} (below ${MIN_ORDER_SIZE} minimum){Style.RESET_ALL}")
        print()
        
        open_positions = [p for p in result.get('positions', []) if not p.get('closed', False)]
        closed_positions = [p for p in result.get('positions', []) if p.get('closed', False)]
        
        print(f"{Fore.CYAN}Open Positions:{Style.RESET_ALL}")
        print(f"  Count: {len(open_positions)}")
        print()
        
        for i, pos in enumerate(open_positions[:10], 1):
            pnl = pos.get('pnl', 0)
            pnl_str = f"{Fore.GREEN}+${pnl:.2f}{Style.RESET_ALL}" if pnl >= 0 else f"{Fore.RED}-${abs(pnl):.2f}{Style.RESET_ALL}"
            market_label = (pos.get('market', 'Unknown market') or 'Unknown market')[:50]
            print(f"  {i}. {market_label}")
            print(f"     Outcome: {pos.get('outcome', 'Unknown')} | Invested: ${pos.get('invested', 0):.2f} | Value: ${pos.get('current_value', 0):.2f} | P&L: {pnl_str}")
        
        if len(open_positions) > 10:
            print(f"{Fore.YELLOW}  ... and {len(open_positions) - 10} more positions{Style.RESET_ALL}")
        
        if closed_positions:
            print()
            print(f"{Fore.CYAN}Closed Positions:{Style.RESET_ALL}")
            print(f"  Count: {len(closed_positions)}")
            print()
            
            for i, pos in enumerate(closed_positions[:5], 1):
                pnl = pos.get('pnl', 0)
                pnl_str = f"{Fore.GREEN}+${pnl:.2f}{Style.RESET_ALL}" if pnl >= 0 else f"{Fore.RED}-${abs(pnl):.2f}{Style.RESET_ALL}"
                market_label = (pos.get('market', 'Unknown market') or 'Unknown market')[:50]
                print(f"  {i}. {market_label}")
                print(f"     Outcome: {pos.get('outcome', 'Unknown')} | P&L: {pnl_str}")
            
            if len(closed_positions) > 5:
                print(f"{Fore.YELLOW}  ... and {len(closed_positions) - 5} more closed positions{Style.RESET_ALL}")
        
        print()
        print('=' * 80)
        print()
        
        # Save to JSON file
        results_dir = project_root / 'simulation_results'
        results_dir.mkdir(exist_ok=True)
        
        tag = os.getenv('SIM_RESULT_TAG', '').strip()
        if tag:
            tag = '_' + tag.replace(' ', '-').replace('/', '-')
        
        filename = f"old_logic_{trader_address[:10]}_{HISTORY_DAYS}d{tag}_{datetime.now().strftime('%Y-%m-%d')}.json"
        filepath = results_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Results saved to: {filepath}")
        print()
        
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Simulation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(simulate_profitability_old())
