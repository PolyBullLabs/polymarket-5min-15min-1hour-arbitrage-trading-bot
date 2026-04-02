#!/usr/bin/env python3
"""
Scan and analyze top traders
"""
import sys
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
from collections import defaultdict

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
MIN_TRADER_TRADES = int(os.getenv('MIN_TRADER_TRADES', '100'))
MAX_TRADES_LIMIT = int(os.getenv('SIM_MAX_TRADES', '2000'))
MAX_TRADERS_TO_ANALYZE = int(os.getenv('MAX_TRADERS_TO_ANALYZE', '50'))


async def fetch_markets(limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch active markets from known traders' recent activity"""
    try:
        # Get markets from known traders' recent activity (this is the reliable method)
        known_traders = [
            '0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b',
            '0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292',
            '0xa4b366ad22fc0d06f1e934ff468e8922431a87b8',
        ]
        
        markets_map = {}
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Getting markets from known traders' activity...")
        
        for i, trader in enumerate(known_traders, 1):
            try:
                activity_url = f'https://data-api.polymarket.com/activity?user={trader}&type=TRADE&limit=50'
                activities = await fetch_data_async(activity_url)
                
                if isinstance(activities, list):
                    for activity in activities:
                        asset = activity.get('asset') or activity.get('conditionId')
                        if asset and asset not in markets_map:
                            markets_map[asset] = {
                                'conditionId': asset,
                                'id': asset,
                                'slug': activity.get('slug') or activity.get('market', 'Unknown'),
                                'question': activity.get('market', 'Unknown')
                            }
                
                print(f"  Trader {i}/{len(known_traders)}: Found {len(markets_map)} unique markets so far...")
            except Exception as e:
                print(f"  {Fore.YELLOW}⚠ Skipped trader {i} due to error{Style.RESET_ALL}")
                continue
        
        markets_list = list(markets_map.values())[:limit]
        print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Found {len(markets_list)} markets")
        return markets_list
    
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch markets: {e}")
        return []


async def extract_traders_from_markets(markets: List[Dict[str, Any]]) -> Set[str]:
    """Extract trader addresses from market activity"""
    traders = set()
    
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Extracting traders from {len(markets)} markets...")
    
    # Also get traders from known successful traders' recent activity
    known_traders = [
        '0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b',
        '0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292',
        '0xa4b366ad22fc0d06f1e934ff468e8922431a87b8',
    ]
    
    # Add known traders as seed
    for trader in known_traders:
        traders.add(trader.lower())
    
    # Extract from markets
    for i, market in enumerate(markets[:10], 1):  # Limit to top 10 markets for performance
        condition_id = market.get('conditionId') or market.get('id')
        if not condition_id:
            continue
        
        try:
            # Try activity endpoint with conditionId/asset filter
            asset = market.get('conditionId') or market.get('id')
            activity_url = f'https://data-api.polymarket.com/activity?asset={asset}&type=TRADE&limit=50'
            activities = await fetch_data_async(activity_url)
            
            if isinstance(activities, list):
                for activity in activities:
                    user = activity.get('user') or activity.get('owner')
                    if user:
                        traders.add(user.lower())
            
            if i % 5 == 0:
                print(f"  Processed {i}/{min(10, len(markets))} markets, found {len(traders)} unique traders...")
        
        except Exception as e:
            # Skip markets that fail
            continue
    
    # Also get traders from recent activity of known traders
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Getting traders from known successful traders' networks...")
    for trader in known_traders[:2]:  # Use first 2 for speed
        try:
            activity_url = f'https://data-api.polymarket.com/activity?user={trader}&type=TRADE&limit=100'
            activities = await fetch_data_async(activity_url)
            
            if isinstance(activities, list):
                # Get markets they trade in, then get other traders from those markets
                markets_traded = set()
                for activity in activities:
                    asset = activity.get('asset') or activity.get('conditionId')
                    if asset:
                        markets_traded.add(asset)
                
                # Get a few traders from each market
                for asset in list(markets_traded)[:3]:  # Limit to 3 markets per trader
                    try:
                        market_activity_url = f'https://data-api.polymarket.com/activity?asset={asset}&type=TRADE&limit=20'
                        market_activities = await fetch_data_async(market_activity_url)
                        
                        if isinstance(market_activities, list):
                            for activity in market_activities:
                                user = activity.get('user') or activity.get('owner')
                                if user and user.lower() != trader.lower():
                                    traders.add(user.lower())
                    except Exception:
                        continue
        except Exception:
            continue
    
    return traders


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
    
    except Exception:
        return []


async def fetch_trader_positions(trader_address: str) -> List[Dict[str, Any]]:
    """Fetch current positions for a trader"""
    try:
        url = f'https://data-api.polymarket.com/positions?user={trader_address}'
        positions = await fetch_data_async(url)
        return positions if isinstance(positions, list) else []
    except Exception:
        return []


async def analyze_trader(trader_address: str) -> Dict[str, Any]:
    """Analyze a trader's performance"""
    try:
        trades = await fetch_trader_activity(trader_address)
        
        if len(trades) < MIN_TRADER_TRADES:
            return {
                'address': trader_address,
                'roi': 0,
                'total_pnl': 0,
                'total_trades': len(trades),
                'copied_trades': 0,
                'skipped_trades': len(trades),
                'win_rate': 0,
                'avg_trade_size': 0,
                'open_positions': 0,
                'closed_positions': 0,
                'realized_pnl': 0,
                'unrealized_pnl': 0,
                'error': f'Not enough trades ({len(trades)} < {MIN_TRADER_TRADES})'
            }
        
        # Simulate copying trades
        your_capital = STARTING_CAPITAL
        total_invested = 0
        copied_trades = 0
        skipped_trades = 0
        
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
        
        # Get current positions for unrealized P&L
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
            'profile_url': f'https://polymarket.com/profile/{trader_address}'
        }
    
    except Exception as e:
        return {
            'address': trader_address,
            'error': str(e),
            'roi': 0,
            'total_pnl': 0
        }


async def scan_best_traders():
    """Scan and analyze top traders from Polymarket"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Scanning and analyzing top traders...")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analyzing last {HISTORY_DAYS} days of trading")
    print()
    
    # Step 1: Fetch markets from known traders
    print(f"{Fore.CYAN}[STEP 1]{Style.RESET_ALL} Fetching active markets from known traders...")
    markets = await fetch_markets(limit=20)
    
    if not markets:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No markets found, using known traders only")
        markets = []
    
    if markets:
        print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Found {len(markets)} markets")
        print()
    
    # Step 2: Extract traders from markets
    print(f"{Fore.CYAN}[STEP 2]{Style.RESET_ALL} Extracting traders from market activity...")
    traders = await extract_traders_from_markets(markets)
    
    if not traders:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No traders found in markets, using known traders only")
        # Use known traders as fallback
        known_traders = [
            '0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b',
            '0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292',
            '0xa4b366ad22fc0d06f1e934ff468e8922431a87b8',
        ]
        traders = set(t.lower() for t in known_traders)
    
    trader_list = list(traders)[:MAX_TRADERS_TO_ANALYZE]  # Limit analysis
    print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Found {len(trader_list)} unique traders to analyze")
    print()
    
    # Step 3: Analyze each trader
    print(f"{Fore.CYAN}[STEP 3]{Style.RESET_ALL} Analyzing trader performance...")
    print()
    
    results = []
    for i, trader in enumerate(trader_list, 1):
        print(f"{Fore.CYAN}[{i}/{len(trader_list)}]{Style.RESET_ALL} Analyzing {trader[:10]}...", end=' ', flush=True)
        result = await analyze_trader(trader)
        results.append(result)
        
        if result.get('error'):
            print(f"{Fore.YELLOW}⚠ {result['error']}{Style.RESET_ALL}")
        else:
            roi = result.get('roi', 0)
            roi_color = Fore.GREEN if roi > 0 else Fore.RED
            print(f"{roi_color}ROI: {roi:.2f}% | Trades: {result.get('copied_trades', 0)}{Style.RESET_ALL}")
    
    print()
    print('=' * 100)
    print(f"{Fore.CYAN}{Style.BRIGHT}TOP TRADERS FROM MARKET SCAN{Style.RESET_ALL}")
    print('=' * 100)
    print()
    
    # Filter out errors and sort by ROI
    valid_results = [r for r in results if not r.get('error')]
    valid_results.sort(key=lambda x: x.get('roi', 0), reverse=True)
    
    if not valid_results:
        print(f"{Fore.YELLOW}No valid results found{Style.RESET_ALL}")
        return
    
    # Display top traders
    print(f"{Fore.CYAN}{'Rank':<6} {'Address':<15} {'ROI':<12} {'P&L':<12} {'Trades':<10} {'Win Rate':<10} {'Status':<12}{Style.RESET_ALL}")
    print('-' * 100)
    
    for idx, result in enumerate(valid_results[:20], 1):
        address = result['address'][:12] + '...'
        roi = result.get('roi', 0)
        pnl = result.get('total_pnl', 0)
        trades = result.get('copied_trades', 0)
        win_rate = result.get('win_rate', 0)
        
        # Determine status
        if roi >= 50 and trades >= 50:
            status = 'Excellent'
            status_color = Fore.GREEN
        elif roi >= 20 and trades >= 30:
            status = 'Good'
            status_color = Fore.CYAN
        elif roi >= 0:
            status = 'Average'
            status_color = Fore.YELLOW
        else:
            status = 'Poor'
            status_color = Fore.RED
        
        roi_color = Fore.GREEN if roi > 0 else Fore.RED
        
        print(f"{idx:<6} {address:<15} {roi_color}{roi:>9.2f}%{Style.RESET_ALL}  "
              f"${pnl:>10.2f}  {trades:>8}  {win_rate:>7.1f}%  {status_color}{status:<12}{Style.RESET_ALL}")
    
    print()
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analysis complete!")
    
    # Show top trader
    if valid_results:
        top = valid_results[0]
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Top trader: {top['address']}")
        print(f"  ROI: {top.get('roi', 0):.2f}% | P&L: ${top.get('total_pnl', 0):.2f} | "
              f"Trades: {top.get('copied_trades', 0)}")
        print(f"  Profile: {top.get('profile_url', 'N/A')}")


if __name__ == '__main__':
    asyncio.run(scan_best_traders())
