#!/usr/bin/env python3
"""
Scan traders from markets
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
MIN_TRADER_TRADES = int(os.getenv('MIN_TRADER_TRADES', '50'))
MAX_TRADES_LIMIT = int(os.getenv('SIM_MAX_TRADES', '2000'))
MAX_TRADERS_TO_ANALYZE = int(os.getenv('MAX_TRADERS_TO_ANALYZE', '50'))


async def fetch_markets_from_traders(limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch markets from known traders' activity"""
    try:
        known_traders = [
            '0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b',
            '0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292',
            '0xa4b366ad22fc0d06f1e934ff468e8922431a87b8',
        ]
        
        markets_map = {}
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Getting markets from traders' activity...")
        
        for i, trader in enumerate(known_traders, 1):
            try:
                activity_url = f'https://data-api.polymarket.com/activity?user={trader}&type=TRADE&limit=100'
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
                
                print(f"  Trader {i}/{len(known_traders)}: Found {len(markets_map)} unique markets...")
            except Exception:
                continue
        
        return list(markets_map.values())[:limit]
    
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch markets: {e}")
        return []


async def extract_traders_from_market(market: Dict[str, Any]) -> Set[str]:
    """Extract trader addresses from a single market"""
    traders = set()
    asset = market.get('conditionId') or market.get('id')
    
    if not asset:
        return traders
    
    try:
        # Get activity for this market/asset
        activity_url = f'https://data-api.polymarket.com/activity?asset={asset}&type=TRADE&limit=100'
        activities = await fetch_data_async(activity_url)
        
        if isinstance(activities, list):
            for activity in activities:
                user = activity.get('user') or activity.get('owner')
                if user:
                    traders.add(user.lower())
    
    except Exception:
        pass
    
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


async def analyze_trader_activity(trader_address: str) -> Dict[str, Any]:
    """Analyze trader's activity patterns"""
    try:
        trades = await fetch_trader_activity(trader_address)
        
        if len(trades) < MIN_TRADER_TRADES:
            return {
                'address': trader_address,
                'total_trades': len(trades),
                'total_volume': 0,
                'avg_trade_size': 0,
                'unique_markets': 0,
                'last_activity': 0,
                'error': f'Not enough trades ({len(trades)} < {MIN_TRADER_TRADES})'
            }
        
        # Calculate activity metrics
        total_volume = sum(float(t.get('usdcSize', 0)) for t in trades)
        avg_trade_size = total_volume / len(trades) if trades else 0
        
        # Get unique markets
        unique_markets = set()
        for trade in trades:
            asset = trade.get('asset') or trade.get('conditionId')
            if asset:
                unique_markets.add(asset)
        
        # Get last activity timestamp
        last_activity = max((t.get('timestamp', 0) for t in trades), default=0)
        
        # Count buy vs sell
        buy_count = sum(1 for t in trades if t.get('side') == 'BUY')
        sell_count = sum(1 for t in trades if t.get('side') == 'SELL')
        
        return {
            'address': trader_address,
            'total_trades': len(trades),
            'total_volume': total_volume,
            'avg_trade_size': avg_trade_size,
            'unique_markets': len(unique_markets),
            'buy_count': buy_count,
            'sell_count': sell_count,
            'last_activity': last_activity,
            'last_activity_date': datetime.fromtimestamp(last_activity).strftime('%Y-%m-%d') if last_activity else 'Unknown',
            'profile_url': f'https://polymarket.com/profile/{trader_address}'
        }
    
    except Exception as e:
        return {
            'address': trader_address,
            'error': str(e),
            'total_trades': 0
        }


async def scan_traders_from_markets():
    """Scan traders from active markets"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Scanning traders from markets...")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analyzing last {HISTORY_DAYS} days of activity")
    print()
    
    # Step 1: Fetch markets
    print(f"{Fore.CYAN}[STEP 1]{Style.RESET_ALL} Fetching active markets...")
    markets = await fetch_markets_from_traders(limit=20)
    
    if not markets:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No markets found")
        return
    
    print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Found {len(markets)} markets")
    print()
    
    # Step 2: Extract traders from markets
    print(f"{Fore.CYAN}[STEP 2]{Style.RESET_ALL} Extracting traders from market activity...")
    all_traders = set()
    
    for i, market in enumerate(markets[:15], 1):  # Limit to 15 markets for performance
        market_name = market.get('slug', market.get('question', 'Unknown'))
        print(f"  Market {i}/{min(15, len(markets))}: {market_name[:40]}...", end=' ', flush=True)
        
        traders = await extract_traders_from_market(market)
        all_traders.update(traders)
        
        print(f"Found {len(traders)} traders (Total: {len(all_traders)})")
    
    if not all_traders:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No traders found in markets")
        return
    
    trader_list = list(all_traders)[:MAX_TRADERS_TO_ANALYZE]
    print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Found {len(trader_list)} unique traders to analyze")
    print()
    
    # Step 3: Analyze trader activity
    print(f"{Fore.CYAN}[STEP 3]{Style.RESET_ALL} Analyzing trader activity patterns...")
    print()
    
    results = []
    for i, trader in enumerate(trader_list, 1):
        print(f"{Fore.CYAN}[{i}/{len(trader_list)}]{Style.RESET_ALL} Analyzing {trader[:10]}...", end=' ', flush=True)
        result = await analyze_trader_activity(trader)
        results.append(result)
        
        if result.get('error'):
            print(f"{Fore.YELLOW}⚠ {result['error']}{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}✓{Style.RESET_ALL} Trades: {result.get('total_trades', 0)} | "
                  f"Volume: ${result.get('total_volume', 0):.2f} | "
                  f"Markets: {result.get('unique_markets', 0)}")
    
    print()
    print('=' * 100)
    print(f"{Fore.CYAN}{Style.BRIGHT}TRADERS FROM MARKET SCAN{Style.RESET_ALL}")
    print('=' * 100)
    print()
    
    # Filter out errors and sort by total volume
    valid_results = [r for r in results if not r.get('error')]
    valid_results.sort(key=lambda x: x.get('total_volume', 0), reverse=True)
    
    if not valid_results:
        print(f"{Fore.YELLOW}No valid results found{Style.RESET_ALL}")
        return
    
    # Display results
    print(f"{Fore.CYAN}{'Rank':<6} {'Address':<15} {'Trades':<10} {'Volume':<15} {'Avg Size':<12} {'Markets':<10} {'Last Activity':<15}{Style.RESET_ALL}")
    print('-' * 100)
    
    for idx, result in enumerate(valid_results[:20], 1):
        address = result['address'][:12] + '...'
        trades = result.get('total_trades', 0)
        volume = result.get('total_volume', 0)
        avg_size = result.get('avg_trade_size', 0)
        markets_count = result.get('unique_markets', 0)
        last_date = result.get('last_activity_date', 'Unknown')
        
        print(f"{idx:<6} {address:<15} {trades:>8}  ${volume:>12.2f}  ${avg_size:>10.2f}  {markets_count:>8}  {last_date:<15}")
    
    print()
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analysis complete!")
    
    # Show most active trader
    if valid_results:
        top = valid_results[0]
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Most active trader: {top['address']}")
        print(f"  Total Trades: {top.get('total_trades', 0)} | "
              f"Total Volume: ${top.get('total_volume', 0):.2f} | "
              f"Markets: {top.get('unique_markets', 0)}")
        print(f"  Profile: {top.get('profile_url', 'N/A')}")


if __name__ == '__main__':
    asyncio.run(scan_traders_from_markets())
