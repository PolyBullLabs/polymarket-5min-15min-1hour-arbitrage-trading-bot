#!/usr/bin/env python3
"""
Aggregate trading results

This script scans all result directories and aggregates statistics
across different strategies and traders.
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style

init(autoreset=True)


class StrategyPerformance:
    """Performance metrics for a strategy"""
    def __init__(self, strategy_id: str, history_days: int, multiplier: float):
        self.strategy_id = strategy_id
        self.history_days = history_days
        self.multiplier = multiplier
        self.best_roi = float('-inf')
        self.best_win_rate = 0.0
        self.best_pnl = float('-inf')
        self.avg_roi = 0.0
        self.avg_win_rate = 0.0
        self.traders_analyzed = 0
        self.profitable_traders = 0
        self.files_count = 0
        self.total_roi = 0.0
        self.total_win_rate = 0.0
        self.trader_count = 0
    
    def to_dict(self):
        """Convert to dictionary for JSON output"""
        return {
            'strategyId': self.strategy_id,
            'historyDays': self.history_days,
            'multiplier': self.multiplier,
            'bestROI': self.best_roi,
            'bestWinRate': self.best_win_rate,
            'bestPnL': self.best_pnl,
            'avgROI': self.avg_roi,
            'avgWinRate': self.avg_win_rate,
            'tradersAnalyzed': self.traders_analyzed,
            'profitableTraders': self.profitable_traders,
            'filesCount': self.files_count,
        }


def load_result_files(dirs: List[str]) -> tuple[Dict[str, StrategyPerformance], Dict[str, Dict], int]:
    """Load and process all result files from directories"""
    all_strategies = {}
    all_traders = {}
    total_files = 0
    
    for dir_name in dirs:
        dir_path = project_root / dir_name
        
        if not dir_path.exists():
            continue
        
        files = list(dir_path.glob('*.json'))
        print(f"{Fore.YELLOW}📁 Scanning {dir_name}/: found {len(files)} files{Style.RESET_ALL}")
        
        for file in files:
            total_files += 1
            
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Determine file type and extract data
                config = None
                traders = []
                
                if 'traders' in data and isinstance(data['traders'], list):
                    # Scan results format
                    config = data.get('config', {})
                    traders = data['traders']
                elif 'results' in data and isinstance(data['results'], list):
                    # Analysis results format
                    config = data.get('config', {})
                    traders = data['results']
                elif 'address' in data and 'roi' in data:
                    # Single trader result format
                    config = data.get('config', {})
                    traders = [data]
                else:
                    continue
                
                if not config or not config.get('historyDays'):
                    # Try to infer from filename or use defaults
                    config = config or {}
                    if 'historyDays' not in config:
                        config['historyDays'] = 30  # Default
                    if 'multiplier' not in config:
                        config['multiplier'] = 1.0  # Default
                
                history_days = config.get('historyDays', 30)
                multiplier = config.get('multiplier', 1.0)
                strategy_id = f"{history_days}d_{multiplier}x"
                
                # Initialize strategy if not exists
                if strategy_id not in all_strategies:
                    all_strategies[strategy_id] = StrategyPerformance(
                        strategy_id, history_days, multiplier
                    )
                
                strategy = all_strategies[strategy_id]
                strategy.files_count += 1
                
                # Analyze traders
                for trader in traders:
                    roi = trader.get('roi')
                    if roi is None:
                        continue
                    
                    strategy.trader_count += 1
                    strategy.total_roi += roi
                    strategy.total_win_rate += trader.get('winRate', 0)
                    
                    if roi > strategy.best_roi:
                        strategy.best_roi = roi
                    if trader.get('winRate', 0) > strategy.best_win_rate:
                        strategy.best_win_rate = trader.get('winRate', 0)
                    if trader.get('totalPnl', trader.get('total_pnl', 0)) > strategy.best_pnl:
                        strategy.best_pnl = trader.get('totalPnl', trader.get('total_pnl', 0))
                    if roi > 0:
                        strategy.profitable_traders += 1
                    
                    # Track traders
                    address = trader.get('address', trader.get('traderAddress', ''))
                    if address:
                        if address not in all_traders:
                            all_traders[address] = {
                                'bestROI': roi,
                                'bestStrategy': strategy_id,
                                'timesFound': 1,
                            }
                        else:
                            all_traders[address]['timesFound'] += 1
                            if roi > all_traders[address]['bestROI']:
                                all_traders[address]['bestROI'] = roi
                                all_traders[address]['bestStrategy'] = strategy_id
                
                # Update averages
                if strategy.trader_count > 0:
                    strategy.avg_roi = strategy.total_roi / strategy.trader_count
                    strategy.avg_win_rate = strategy.total_win_rate / strategy.trader_count
                    strategy.traders_analyzed += strategy.trader_count
                    strategy.trader_count = 0  # Reset for next file
                    strategy.total_roi = 0.0
                    strategy.total_win_rate = 0.0
            
            except Exception as e:
                # Ignore parsing errors
                print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Skipped {file.name}: {e}")
    
    return all_strategies, all_traders, total_files


def print_top_strategies(strategies: List[StrategyPerformance]):
    """Print top strategies table"""
    print('=' * 100)
    print(f"{Fore.CYAN}{Style.BRIGHT}  🏆 TOP STRATEGIES BY BEST ROI{Style.RESET_ALL}")
    print('=' * 100)
    print()
    
    print(f"{Style.BRIGHT}  #  | Strategy      | Best ROI  | Best Win% | Best P&L   | Avg ROI   | Profitable | Files{Style.RESET_ALL}")
    print('─' * 100)
    
    for i, strategy in enumerate(strategies[:15], 1):
        roi_color = Fore.GREEN if strategy.best_roi >= 0 else Fore.RED
        roi_sign = '+' if strategy.best_roi >= 0 else ''
        pnl_sign = '+' if strategy.best_pnl >= 0 else ''
        
        print(
            f"  {Fore.YELLOW}{str(i):<2}{Style.RESET_ALL} | "
            f"{Fore.BLUE}{strategy.strategy_id:<13}{Style.RESET_ALL} | "
            f"{roi_color}{roi_sign}{strategy.best_roi:.1f}%{' ' * (9 - len(f'{roi_sign}{strategy.best_roi:.1f}%'))}{Style.RESET_ALL} | "
            f"{Fore.YELLOW}{strategy.best_win_rate:.1f}%{' ' * (9 - len(f'{strategy.best_win_rate:.1f}%'))}{Style.RESET_ALL} | "
            f"{pnl_sign}${strategy.best_pnl:.0f}{' ' * (9 - len(f'{pnl_sign}${strategy.best_pnl:.0f}'))} | "
            f"{strategy.avg_roi:.1f}%{' ' * (9 - len(f'{strategy.avg_roi:.1f}%'))} | "
            f"{strategy.profitable_traders}/{strategy.traders_analyzed}{' ' * (10 - len(f'{strategy.profitable_traders}/{strategy.traders_analyzed}'))} | "
            f"{strategy.files_count}"
        )
    
    print()


def print_top_traders(traders: List[tuple[str, Dict]]):
    """Print top traders table"""
    print('=' * 100)
    print(f"{Fore.CYAN}{Style.BRIGHT}  🎯 TOP TRADERS (found in multiple scans){Style.RESET_ALL}")
    print('=' * 100)
    print()
    
    print(f"{Style.BRIGHT}  #  | Address                                    | Best ROI  | Best Strategy | Found{Style.RESET_ALL}")
    print('─' * 100)
    
    for i, (address, data) in enumerate(traders[:10], 1):
        roi_color = Fore.GREEN if data['bestROI'] >= 0 else Fore.RED
        roi_sign = '+' if data['bestROI'] >= 0 else ''
        
        print(
            f"  {Fore.YELLOW}{str(i):<2}{Style.RESET_ALL} | "
            f"{Fore.BLUE}{address:<42}{Style.RESET_ALL} | "
            f"{roi_color}{roi_sign}{data['bestROI']:.1f}%{' ' * (9 - len(f'{roi_sign}{data['bestROI']:.1f}%'))}{Style.RESET_ALL} | "
            f"{Fore.CYAN}{data['bestStrategy']:<13}{Style.RESET_ALL} | "
            f"{data['timesFound']}"
        )
    
    print()


def print_statistics(strategies: List[StrategyPerformance], traders: Dict, total_files: int):
    """Print aggregate statistics"""
    print('=' * 100)
    print(f"{Fore.CYAN}{Style.BRIGHT}  📈 AGGREGATE STATISTICS{Style.RESET_ALL}")
    print('=' * 100)
    print()
    
    total_traders = sum(s.traders_analyzed for s in strategies)
    total_profitable = sum(s.profitable_traders for s in strategies)
    unique_traders = len(traders)
    profitable_rate = (total_profitable / total_traders * 100) if total_traders > 0 else 0
    
    print(f"  Total files:           {Fore.CYAN}{total_files}{Style.RESET_ALL}")
    print(f"  Total strategies:      {Fore.CYAN}{len(strategies)}{Style.RESET_ALL}")
    print(f"  Total traders:         {Fore.CYAN}{total_traders}{Style.RESET_ALL}")
    print(f"  Unique traders:        {Fore.CYAN}{unique_traders}{Style.RESET_ALL}")
    print(f"  Profitable traders:    {Fore.GREEN}{total_profitable}{Style.RESET_ALL} ({profitable_rate:.1f}%)")
    
    # Best strategy
    if strategies:
        best = strategies[0]
        print()
        print(f"{Fore.GREEN}🌟 BEST STRATEGY:{Style.RESET_ALL}")
        print(f"  ID: {Fore.YELLOW}{best.strategy_id}{Style.RESET_ALL}")
        print(f"  ROI: {Fore.GREEN}+{best.best_roi:.2f}%{Style.RESET_ALL}")
        print(f"  Win Rate: {Fore.YELLOW}{best.best_win_rate:.1f}%{Style.RESET_ALL}")
        print(f"  P&L: {Fore.GREEN}+${best.best_pnl:.2f}{Style.RESET_ALL}")
    
    print()


def save_aggregated_results(strategies: List[StrategyPerformance], traders: List[tuple], total_files: int):
    """Save aggregated results to JSON file"""
    output_dir = project_root / 'strategy_factory_results'
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / 'aggregated_results.json'
    
    total_traders = sum(s.traders_analyzed for s in strategies)
    total_profitable = sum(s.profitable_traders for s in strategies)
    unique_traders = len(traders)
    profitable_rate = (total_profitable / total_traders * 100) if total_traders > 0 else 0
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'totalFiles': total_files,
            'totalStrategies': len(strategies),
            'totalTraders': total_traders,
            'uniqueTraders': unique_traders,
            'profitableTraders': total_profitable,
            'profitableRate': profitable_rate,
        },
        'strategies': [s.to_dict() for s in strategies[:20]],
        'topTraders': [{'address': addr, **data} for addr, data in traders[:20]],
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"{Fore.GREEN}✓ Aggregated results saved: {Fore.CYAN}{output_path}{Style.RESET_ALL}")
    print()


def aggregate_results():
    """Main function to aggregate results"""
    print('=' * 100)
    print(f"{Fore.CYAN}{Style.BRIGHT}  📊 RESULTS AGGREGATOR FOR ALL STRATEGIES{Style.RESET_ALL}")
    print('=' * 100)
    print()
    
    # Result directories to scan
    dirs = [
        'trader_scan_results',
        'trader_analysis_results',
        'top_traders_results',
        'strategy_factory_results',
        'simulation_results',  # Also include simulation results
    ]
    
    # Load and process all files
    all_strategies, all_traders, total_files = load_result_files(dirs)
    
    if not all_strategies:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No results found in any directory")
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Run scans or simulations first")
        return
    
    print(f"{Fore.GREEN}✓ Processed {total_files} files{Style.RESET_ALL}")
    print()
    
    # Sort strategies by best ROI
    strategies = sorted(all_strategies.values(), key=lambda s: s.best_roi, reverse=True)
    
    # Sort traders by best ROI
    top_traders = sorted(all_traders.items(), key=lambda x: x[1]['bestROI'], reverse=True)
    
    # Print results
    print_top_strategies(strategies)
    print_top_traders(top_traders)
    print_statistics(strategies, all_traders, total_files)
    
    # Save aggregated results
    save_aggregated_results(strategies, top_traders, total_files)


if __name__ == '__main__':
    try:
        aggregate_results()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[INFO]{Style.RESET_ALL} Interrupted by user")
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
