#!/usr/bin/env python3
"""
Fetch and cache historical trade data for traders

This script fetches historical trades from Polymarket API and caches them
for use in simulations and analysis.
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
HISTORY_DAYS = int(os.getenv('HISTORY_DAYS', '30'))
MAX_TRADES_PER_TRADER = int(os.getenv('HISTORY_MAX_TRADES', '20000'))
BATCH_SIZE = min(int(os.getenv('HISTORY_BATCH_SIZE', '100')), 1000)
MAX_PARALLEL = min(int(os.getenv('HISTORY_MAX_PARALLEL', '4')), 10)


def parse_user_addresses() -> List[str]:
    """Parse user addresses from environment"""
    addresses = []
    
    if hasattr(ENV, 'USER_ADDRESSES') and ENV.USER_ADDRESSES:
        if isinstance(ENV.USER_ADDRESSES, list):
            addresses = [addr.lower().strip() for addr in ENV.USER_ADDRESSES if addr.strip()]
        elif isinstance(ENV.USER_ADDRESSES, str):
            addresses = [addr.lower().strip() for addr in ENV.USER_ADDRESSES.split(',') if addr.strip()]
    
    return addresses


async def fetch_batch(address: str, offset: int, limit: int) -> List[Dict[str, Any]]:
    """Fetch a batch of trades for a trader"""
    try:
        url = f'https://data-api.polymarket.com/activity?user={address}&type=TRADE&limit={limit}&offset={offset}'
        trades = await fetch_data_async(url)
        return trades if isinstance(trades, list) else []
    except Exception as e:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Failed to fetch batch (offset={offset}): {e}")
        return []


async def fetch_trades_for_trader(address: str) -> List[Dict[str, Any]]:
    """Fetch all trades for a trader within the history window"""
    short_addr = f"{address[:6]}...{address[-4]}"
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Loading history for {short_addr} (last {HISTORY_DAYS} days)")
    
    since_timestamp = int((datetime.now() - timedelta(days=HISTORY_DAYS)).timestamp())
    
    offset = 0
    all_trades = []
    has_more = True
    
    while has_more and len(all_trades) < MAX_TRADES_PER_TRADER:
        batch_limit = min(BATCH_SIZE, MAX_TRADES_PER_TRADER - len(all_trades))
        batch = await fetch_batch(address, offset, batch_limit)
        
        if not batch:
            has_more = False
            break
        
        # Filter by timestamp
        filtered = [t for t in batch if t.get('timestamp', 0) >= since_timestamp]
        all_trades.extend(filtered)
        
        # Check if we should continue
        if len(batch) < batch_limit or len(filtered) < len(batch):
            has_more = False
        
        offset += batch_limit
        
        # Rate limiting: sleep every few batches
        if len(all_trades) % (BATCH_SIZE * MAX_PARALLEL) == 0:
            await asyncio.sleep(0.15)  # 150ms delay
        
        # Progress indicator
        if len(all_trades) % 500 == 0:
            print(f"  {Fore.YELLOW}Progress: {len(all_trades)} trades fetched...{Style.RESET_ALL}")
    
    # Sort by timestamp
    all_trades.sort(key=lambda x: x.get('timestamp', 0))
    
    print(f"{Fore.GREEN}✓ Fetched {len(all_trades)} trades{Style.RESET_ALL}")
    return all_trades


def save_trades_to_cache(address: str, trades: List[Dict[str, Any]]):
    """Save trades to cache file"""
    cache_dir = project_root / 'trader_data_cache'
    cache_dir.mkdir(exist_ok=True)
    
    today = datetime.now().strftime('%Y-%m-%d')
    cache_file = cache_dir / f"{address}_{HISTORY_DAYS}d_{today}.json"
    
    payload = {
        'name': f"trader_{address[:6]}_{HISTORY_DAYS}d_{today}",
        'traderAddress': address,
        'fetchedAt': datetime.now().isoformat(),
        'period': f"{HISTORY_DAYS}_days",
        'historyDays': HISTORY_DAYS,
        'totalTrades': len(trades),
        'trades': trades,
    }
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    
    print(f"{Fore.GREEN}💾 Saved to {cache_file}{Style.RESET_ALL}")


def check_cache(address: str) -> Optional[Path]:
    """Check if cached data exists for today"""
    cache_dir = project_root / 'trader_data_cache'
    if not cache_dir.exists():
        return None
    
    today = datetime.now().strftime('%Y-%m-%d')
    cache_file = cache_dir / f"{address}_{HISTORY_DAYS}d_{today}.json"
    
    if cache_file.exists():
        return cache_file
    
    return None


def load_cached_trades(cache_file: Path) -> Optional[List[Dict[str, Any]]]:
    """Load trades from cache file"""
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('trades', [])
    except Exception:
        return None


def chunk_list(lst: List[Any], size: int) -> List[List[Any]]:
    """Split list into chunks of specified size"""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


async def fetch_trader_with_cache(address: str, force_refresh: bool = False):
    """Fetch trades for a trader, using cache if available"""
    cache_file = check_cache(address)
    
    if not force_refresh and cache_file:
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Found cached data for {address[:10]}...")
        cached_trades = load_cached_trades(cache_file)
        if cached_trades is not None:
            print(f"{Fore.GREEN}✓ Using cached data: {len(cached_trades)} trades{Style.RESET_ALL}")
            return cached_trades
    
    # Fetch fresh data
    trades = await fetch_trades_for_trader(address)
    if trades:
        save_trades_to_cache(address, trades)
    return trades


async def fetch_historical_trades():
    """Main function to fetch historical trades"""
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  📥 HISTORICAL TRADES FETCHER{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    # Get configuration
    user_addresses = parse_user_addresses()
    
    if not user_addresses:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No traders configured")
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Set USER_ADDRESSES in .env file")
        return
    
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Configuration:")
    print(f"  Traders: {len(user_addresses)}")
    print(f"  History Days: {HISTORY_DAYS}")
    print(f"  Max Trades per Trader: {MAX_TRADES_PER_TRADER}")
    print(f"  Batch Size: {BATCH_SIZE}")
    print(f"  Max Parallel: {MAX_PARALLEL}")
    print()
    
    # Check for force refresh flag
    force_refresh = os.getenv('FORCE_REFRESH', '').lower() in ('true', '1', 'yes')
    if force_refresh:
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Force refresh enabled - ignoring cache")
        print()
    
    # Process traders in parallel chunks
    address_chunks = chunk_list(user_addresses, MAX_PARALLEL)
    
    total_trades = 0
    
    for chunk_idx, chunk in enumerate(address_chunks, 1):
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Processing chunk {chunk_idx}/{len(address_chunks)} ({len(chunk)} traders)")
        print()
        
        # Fetch all traders in chunk in parallel
        tasks = [fetch_trader_with_cache(addr, force_refresh) for addr in chunk]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (address, result) in enumerate(zip(chunk, results)):
            if isinstance(result, Exception):
                print(f"{Fore.RED}✗ Error fetching {address[:10]}...: {result}{Style.RESET_ALL}")
            elif isinstance(result, list):
                total_trades += len(result)
        
        print()
        
        # Small delay between chunks to avoid rate limiting
        if chunk_idx < len(address_chunks):
            await asyncio.sleep(0.5)
    
    print('=' * 80)
    print(f"{Fore.GREEN}{Style.BRIGHT}  ✅ FETCH COMPLETED{Style.RESET_ALL}")
    print('=' * 80)
    print()
    print(f"{Fore.CYAN}Total trades fetched: {total_trades}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Cache directory: {project_root / 'trader_data_cache'}{Style.RESET_ALL}")
    print()


if __name__ == '__main__':
    try:
        asyncio.run(fetch_historical_trades())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[INFO]{Style.RESET_ALL} Interrupted by user")
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Partial data may have been cached")
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to fetch historical trades: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
