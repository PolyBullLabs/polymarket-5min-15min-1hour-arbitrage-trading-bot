#!/usr/bin/env python3
"""
Compare simulation results

This script loads simulation results and compares them side-by-side
to identify the best strategies and traders.
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from colorama import init, Fore, Style

init(autoreset=True)


def load_simulation_results() -> List[Dict[str, Any]]:
    """Load all simulation result files"""
    results_dir = project_root / 'simulation_results'
    
    if not results_dir.exists():
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} simulation_results directory not found")
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Run simulations first")
        return []
    
    files = list(results_dir.glob('*.json'))
    
    if not files:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No result files found in simulation_results/")
        return []
    
    results = []
    
    for file in files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Add filename and filepath for reference
                data['_filename'] = file.name
                data['_filepath'] = str(file)
                results.append(data)
        except Exception as e:
            print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Skipped {file.name} (invalid JSON: {e})")
    
    return results


def get_result_name(result: Dict[str, Any]) -> str:
    """Extract a readable name from result"""
    # Try to get name from config tag
    if 'config' in result and result['config'].get('tag'):
        tag = result['config']['tag']
        multiplier = result['config'].get('multiplier', 1.0)
        days = result['config'].get('history_days', 30)
        return f"{tag}_m{multiplier}x_{days}d"
    
    # Try to extract from filename
    filename = result.get('_filename', '')
    if filename:
        # Remove extension and common prefixes
        name = filename.replace('.json', '')
        return name
    
    # Fallback
    address = result.get('address', 'unknown')[:10]
    return f"sim_{address}"


def group_by_trader(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group results by trader address"""
    grouped = {}
    
    for result in results:
        trader = result.get('address', 'unknown').lower()
        if trader not in grouped:
            grouped[trader] = []
        grouped[trader].append(result)
    
    return grouped


def print_comparison_table(results: List[Dict[str, Any]]):
    """Print comparison table grouped by trader"""
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  SIMULATION RESULTS COMPARISON{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    print(f"{Fore.YELLOW}Total results found: {len(results)}")
    print()
    
    grouped = group_by_trader(results)
    
    for trader, trader_results in grouped.items():
        trader_display = f"{trader[:10]}...{trader[-8:]}" if len(trader) > 18 else trader
        print(f"{Fore.BLUE}{Style.BRIGHT}▶ Trader: {trader_display}{Style.RESET_ALL}")
        print('─' * 80)
        print()
        
        # Sort by ROI descending
        sorted_results = sorted(trader_results, key=lambda r: r.get('roi', 0), reverse=True)
        
        # Print table header
        print(f"{Style.BRIGHT}{'Name':<30} | {'ROI':<12} | {'P&L':<14} | {'Trades':<12} | {'Positions':<10}{Style.RESET_ALL}")
        print('─' * 80)
        
        for result in sorted_results:
            name = get_result_name(result)[:30]
            roi = result.get('roi', 0)
            total_pnl = result.get('total_pnl', 0)
            copied = result.get('copied_trades', 0)
            total = result.get('total_trades', 0)
            
            # Count open positions
            positions = result.get('positions', [])
            open_positions = sum(1 for p in positions if not p.get('closed', False))
            
            roi_str = f"{Fore.GREEN}+{roi:.2f}%{Style.RESET_ALL}" if roi >= 0 else f"{Fore.RED}{roi:.2f}%{Style.RESET_ALL}"
            pnl_str = f"{Fore.GREEN}+${total_pnl:.2f}{Style.RESET_ALL}" if total_pnl >= 0 else f"{Fore.RED}-${abs(total_pnl):.2f}{Style.RESET_ALL}"
            trades_str = f"{copied}/{total}"
            
            print(f"{name:<30} | {roi_str:<20} | {pnl_str:<22} | {trades_str:<12} | {open_positions:<10}")
        
        print()
    
    print('=' * 80)
    print()


def print_best_results(results: List[Dict[str, Any]], limit: int = 5):
    """Print top performing configurations"""
    print(f"{Fore.GREEN}{Style.BRIGHT}🏆 TOP {limit} BEST PERFORMING CONFIGURATIONS{Style.RESET_ALL}")
    print()
    
    sorted_results = sorted(results, key=lambda r: r.get('roi', 0), reverse=True)[:limit]
    
    medals = ['🥇', '🥈', '🥉']
    
    for i, result in enumerate(sorted_results, 1):
        rank = i
        medal = medals[i - 1] if i <= 3 else f"{rank}."
        
        name = get_result_name(result)
        trader = result.get('address', 'unknown')
        roi = result.get('roi', 0)
        total_pnl = result.get('total_pnl', 0)
        copied = result.get('copied_trades', 0)
        skipped = result.get('skipped_trades', 0)
        starting = result.get('starting_capital', 0)
        current = result.get('current_capital', 0)
        
        print(f"{Style.BRIGHT}{medal} {name}{Style.RESET_ALL}")
        print(f"   Trader: {Fore.BLUE}{trader[:10]}...{Style.RESET_ALL}")
        
        roi_color = Fore.GREEN if roi >= 0 else Fore.RED
        roi_sign = '+' if roi >= 0 else ''
        print(f"   ROI: {roi_color}{roi_sign}{roi:.2f}%{Style.RESET_ALL}")
        
        pnl_color = Fore.GREEN if total_pnl >= 0 else Fore.RED
        pnl_sign = '+' if total_pnl >= 0 else ''
        print(f"   P&L: {pnl_color}{pnl_sign}${total_pnl:.2f}{Style.RESET_ALL}")
        
        print(f"   Trades: {Fore.GREEN}{copied}{Style.RESET_ALL} copied, {Fore.YELLOW}{skipped}{Style.RESET_ALL} skipped")
        print(f"   Capital: ${starting:.2f} → ${current:.2f}")
        print()


def print_worst_results(results: List[Dict[str, Any]], limit: int = 3):
    """Print worst performing configurations"""
    print(f"{Fore.RED}{Style.BRIGHT}⚠️  WORST {limit} PERFORMING CONFIGURATIONS{Style.RESET_ALL}")
    print()
    
    sorted_results = sorted(results, key=lambda r: r.get('roi', 0))[:limit]
    
    for i, result in enumerate(sorted_results, 1):
        name = get_result_name(result)
        trader = result.get('address', 'unknown')
        roi = result.get('roi', 0)
        total_pnl = result.get('total_pnl', 0)
        copied = result.get('copied_trades', 0)
        skipped = result.get('skipped_trades', 0)
        
        print(f"{Style.BRIGHT}{i}. {name}{Style.RESET_ALL}")
        print(f"   Trader: {Fore.BLUE}{trader[:10]}...{Style.RESET_ALL}")
        
        roi_color = Fore.GREEN if roi >= 0 else Fore.RED
        roi_sign = '+' if roi >= 0 else ''
        print(f"   ROI: {roi_color}{roi_sign}{roi:.2f}%{Style.RESET_ALL}")
        
        pnl_color = Fore.GREEN if total_pnl >= 0 else Fore.RED
        pnl_sign = '+' if total_pnl >= 0 else ''
        print(f"   P&L: {pnl_color}{pnl_sign}${total_pnl:.2f}{Style.RESET_ALL}")
        
        print(f"   Trades: {Fore.GREEN}{copied}{Style.RESET_ALL} copied, {Fore.YELLOW}{skipped}{Style.RESET_ALL} skipped")
        print()


def print_statistics(results: List[Dict[str, Any]]):
    """Print aggregate statistics"""
    print(f"{Fore.CYAN}{Style.BRIGHT}📈 AGGREGATE STATISTICS{Style.RESET_ALL}")
    print()
    
    if not results:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No results to analyze")
        return
    
    avg_roi = sum(r.get('roi', 0) for r in results) / len(results)
    avg_pnl = sum(r.get('total_pnl', 0) for r in results) / len(results)
    total_copied = sum(r.get('copied_trades', 0) for r in results)
    total_skipped = sum(r.get('skipped_trades', 0) for r in results)
    positive = sum(1 for r in results if r.get('roi', 0) > 0)
    negative = sum(1 for r in results if r.get('roi', 0) < 0)
    
    print(f"Total simulations: {Fore.YELLOW}{len(results)}{Style.RESET_ALL}")
    
    positive_pct = (positive / len(results)) * 100 if results else 0
    negative_pct = (negative / len(results)) * 100 if results else 0
    
    print(f"Profitable: {Fore.GREEN}{positive}{Style.RESET_ALL} ({positive_pct:.1f}%)")
    print(f"Unprofitable: {Fore.RED}{negative}{Style.RESET_ALL} ({negative_pct:.1f}%)")
    print()
    
    avg_roi_color = Fore.GREEN if avg_roi >= 0 else Fore.RED
    avg_roi_sign = '+' if avg_roi >= 0 else ''
    print(f"Average ROI: {avg_roi_color}{avg_roi_sign}{avg_roi:.2f}%{Style.RESET_ALL}")
    
    avg_pnl_color = Fore.GREEN if avg_pnl >= 0 else Fore.RED
    avg_pnl_sign = '+' if avg_pnl >= 0 else ''
    print(f"Average P&L: {avg_pnl_color}{avg_pnl_sign}${avg_pnl:.2f}{Style.RESET_ALL}")
    print()
    
    print(f"Total trades copied: {Fore.CYAN}{total_copied}{Style.RESET_ALL}")
    print(f"Total trades skipped: {Fore.YELLOW}{total_skipped}{Style.RESET_ALL}")
    print()


def print_detailed_result(result: Dict[str, Any]):
    """Print detailed information for a single result"""
    print('=' * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  📋 DETAILED RESULT{Style.RESET_ALL}")
    print('=' * 80)
    print()
    
    name = get_result_name(result)
    trader = result.get('address', 'unknown')
    config = result.get('config', {})
    
    print(f"{Style.BRIGHT}Configuration:{Style.RESET_ALL}")
    print(f"  Name: {Fore.YELLOW}{name}{Style.RESET_ALL}")
    print(f"  Trader: {Fore.BLUE}{trader}{Style.RESET_ALL}")
    
    if config:
        print(f"  History Days: {config.get('history_days', 'N/A')}")
        print(f"  Multiplier: {config.get('multiplier', 'N/A')}x")
        print(f"  Min Order Size: ${config.get('min_order_size', 'N/A')}")
        if config.get('tag'):
            print(f"  Tag: {config.get('tag')}")
    
    print()
    
    starting = result.get('starting_capital', 0)
    current = result.get('current_capital', 0)
    invested = result.get('total_invested', 0)
    value = result.get('current_value', 0)
    
    print(f"{Style.BRIGHT}Capital:{Style.RESET_ALL}")
    print(f"  Starting: {Fore.CYAN}${starting:.2f}{Style.RESET_ALL}")
    print(f"  Current:  {Fore.CYAN}${current:.2f}{Style.RESET_ALL}")
    print(f"  Invested: {Fore.CYAN}${invested:.2f}{Style.RESET_ALL}")
    print(f"  Value:    {Fore.CYAN}${value:.2f}{Style.RESET_ALL}")
    print()
    
    total_pnl = result.get('total_pnl', 0)
    roi = result.get('roi', 0)
    realized = result.get('realized_pnl', 0)
    unrealized = result.get('unrealized_pnl', 0)
    
    print(f"{Style.BRIGHT}Performance:{Style.RESET_ALL}")
    pnl_color = Fore.GREEN if total_pnl >= 0 else Fore.RED
    pnl_sign = '+' if total_pnl >= 0 else ''
    print(f"  Total P&L:     {pnl_color}{pnl_sign}${total_pnl:.2f}{Style.RESET_ALL}")
    
    roi_color = Fore.GREEN if roi >= 0 else Fore.RED
    roi_sign = '+' if roi >= 0 else ''
    print(f"  ROI:           {roi_color}{roi_sign}{roi:.2f}%{Style.RESET_ALL}")
    
    print(f"  Realized:      ${realized:.2f}")
    print(f"  Unrealized:    ${unrealized:.2f}")
    print()
    
    total = result.get('total_trades', 0)
    copied = result.get('copied_trades', 0)
    skipped = result.get('skipped_trades', 0)
    copy_rate = (copied / total * 100) if total > 0 else 0
    
    print(f"{Style.BRIGHT}Trading Activity:{Style.RESET_ALL}")
    print(f"  Total trades:    {Fore.CYAN}{total}{Style.RESET_ALL}")
    print(f"  Copied:          {Fore.GREEN}{copied}{Style.RESET_ALL}")
    print(f"  Skipped:         {Fore.YELLOW}{skipped}{Style.RESET_ALL}")
    print(f"  Copy rate:       {copy_rate:.1f}%")
    print()
    
    positions = result.get('positions', [])
    open_positions = [p for p in positions if not p.get('closed', False)]
    closed_positions = [p for p in positions if p.get('closed', False)]
    
    print(f"{Style.BRIGHT}Positions:{Style.RESET_ALL}")
    print(f"  Open:   {Fore.CYAN}{len(open_positions)}{Style.RESET_ALL}")
    print(f"  Closed: {Fore.YELLOW}{len(closed_positions)}{Style.RESET_ALL}")
    print()
    
    if result.get('_filepath'):
        print(f"{Style.BRIGHT}File:{Style.RESET_ALL} {result['_filepath']}")
        print()


def print_help():
    """Print usage help"""
    print(f"{Fore.CYAN}Simulation Results Comparison - Usage{Style.RESET_ALL}")
    print()
    print("Commands:")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.compare_results{Style.RESET_ALL}              # Show all results")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.compare_results best [N]{Style.RESET_ALL}     # Show top N results (default: 10)")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.compare_results worst [N]{Style.RESET_ALL}    # Show worst N results (default: 5)")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.compare_results stats{Style.RESET_ALL}        # Show aggregate statistics")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.compare_results detail <name>{Style.RESET_ALL} # Show detailed info for a result")
    print()
    print("Examples:")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.compare_results best 5{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}python -m src.scripts.simulation.compare_results detail std_m2p0{Style.RESET_ALL}")
    print()


def compare_results():
    """Main function to compare results"""
    args = sys.argv[1:]
    results = load_simulation_results()
    
    if not results:
        print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} No simulation results to compare.")
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Run simulations first with:")
        print(f"  {Fore.YELLOW}python -m src.scripts.simulation.run_simulations{Style.RESET_ALL}")
        print()
        return
    
    command = args[0].lower() if args else 'all'
    
    if command == 'all':
        print_comparison_table(results)
        print_best_results(results, 5)
        print_worst_results(results, 3)
        print_statistics(results)
    
    elif command == 'best':
        limit = int(args[1]) if len(args) > 1 else 10
        print_best_results(results, limit)
    
    elif command == 'worst':
        limit = int(args[1]) if len(args) > 1 else 5
        print_worst_results(results, limit)
    
    elif command == 'stats':
        print_statistics(results)
    
    elif command == 'detail':
        if len(args) < 2:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please provide a result name to view details")
            print(f"{Fore.YELLOW}Usage: python -m src.scripts.simulation.compare_results detail <name>{Style.RESET_ALL}")
            return
        
        search_name = args[1]
        found = None
        
        for result in results:
            name = get_result_name(result)
            if search_name.lower() in name.lower():
                found = result
                break
        
        if not found:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No result found matching: {search_name}")
            return
        
        print_detailed_result(found)
    
    elif command in ['help', '--help', '-h']:
        print_help()
    
    else:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Unknown command: {command}")
        print()
        print_help()


if __name__ == '__main__':
    try:
        compare_results()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[INFO]{Style.RESET_ALL} Interrupted by user")
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
