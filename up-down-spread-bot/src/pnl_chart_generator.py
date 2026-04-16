"""
PnL Chart Generator - Creates cumulative PnL charts for all 4 coins
"""
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

def load_trades(log_dir: str, coins: List[str]) -> Dict[str, List[Dict]]:
    """Load all trades from JSONL files for each coin"""
    all_trades = {}
    
    # DEBUG: Write to file too
    debug_file = "/root/4coins_live/logs/chart_debug.log"
    with open(debug_file, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"[CHART DEBUG] {datetime.now()} load_trades called\n")
        f.write(f"[CHART DEBUG] log_dir = {log_dir}\n")
        f.write(f"[CHART DEBUG] coins = {coins}\n")
    
    print(f"[CHART DEBUG] load_trades called")
    print(f"[CHART DEBUG] log_dir = {log_dir}")
    print(f"[CHART DEBUG] coins = {coins}")
    
    for coin in coins:
        trades_file = Path(log_dir) / f"late_v3_{coin}" / "trades.jsonl"
        trades = []
        
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] Looking for: {trades_file}\n")
            f.write(f"[CHART DEBUG] File exists: {trades_file.exists()}\n")
        
        print(f"[CHART DEBUG] Looking for: {trades_file}")
        print(f"[CHART DEBUG] File exists: {trades_file.exists()}")
        
        if trades_file.exists():
            with open(trades_file, 'r') as f:
                for line in f:
                    try:
                        trade = json.loads(line.strip())
                        trades.append(trade)
                    except Exception as e:
                        with open(debug_file, 'a') as df:
                            df.write(f"[CHART DEBUG] Failed to parse line: {e}\n")
                        print(f"[CHART DEBUG] Failed to parse line: {e}")
            
            with open(debug_file, 'a') as f:
                f.write(f"[CHART DEBUG] Loaded {len(trades)} trades from {coin}\n")
            print(f"[CHART DEBUG] Loaded {len(trades)} trades from {coin}")
        else:
            with open(debug_file, 'a') as f:
                f.write(f"[CHART DEBUG] File NOT FOUND: {trades_file}\n")
            print(f"[CHART DEBUG] File NOT FOUND: {trades_file}")
        
        all_trades[coin] = trades
    
    total = sum(len(t) for t in all_trades.values())
    with open(debug_file, 'a') as f:
        f.write(f"[CHART DEBUG] Total trades loaded: {total}\n")
    print(f"[CHART DEBUG] Total trades loaded: {total}")
    
    return all_trades

def generate_pnl_chart(log_dir: str, coins: List[str], output_path: str) -> bool:
    """
    Generate cumulative PnL chart for all coins + combined
    All lines use the same X-axis (unique market close timestamps)
    
    Args:
        log_dir: Path to logs directory
        coins: List of coin names (e.g., ['btc', 'eth', 'sol', 'xrp'])
        output_path: Where to save the chart
    
    Returns:
        True if chart created successfully
    """
    try:
        # Load trades for all coins
        all_trades = load_trades(log_dir, coins)
        
        # Check if we have any trades
        total_trades = sum(len(trades) for trades in all_trades.values())
        if total_trades == 0:
            print("[CHART] No trades found, skipping chart generation")
            return False
        
        # 🔥 CRITICAL: Deduplication! Avoid double counting estimated + real PnL
        # Each trade is written twice:
        # 1. Estimated PnL (WITHOUT "updated" field)
        # 2. Real PnL (WITH "updated": true field)
        # Take only final entries with real PnL!
        trade_map = {}  # {coin_market_slug: trade_data}
        
        debug_file = "/root/4coins_live/logs/chart_debug.log"
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] Starting deduplication...\n")
        
        for coin in coins:
            with open(debug_file, 'a') as f:
                f.write(f"[CHART DEBUG] Processing {len(all_trades[coin])} trades for {coin}\n")
            
            for trade in all_trades[coin]:
                market_slug = trade.get('market_slug', '')
                key = f"{coin}_{market_slug}"
                has_updated = trade.get('updated', False)
                
                # If entry has "updated": true - this is FINAL entry (real PnL)
                # Always replace previous estimated entry with it
                if has_updated:
                    trade_map[key] = {
                        'coin': coin,
                        'close_time': trade.get('close_time', 0),
                        'pnl': trade.get('pnl', 0)
                    }
                # If NO "updated" and such entry doesn't exist - add it
                # (for old entries without dual logging or if real entry didn't arrive)
                elif key not in trade_map:
                    trade_map[key] = {
                        'coin': coin,
                        'close_time': trade.get('close_time', 0),
                        'pnl': trade.get('pnl', 0)
                    }
        
        # Convert to list of unique entries
        all_trades_timed = list(trade_map.values())
        
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] After deduplication: {len(all_trades_timed)} trades\n")
            f.write(f"[CHART DEBUG] trade_map keys sample: {list(trade_map.keys())[:5]}\n")
        
        # Sort by close_time
        all_trades_timed.sort(key=lambda x: x['close_time'])
        
        debug_file = "/root/4coins_live/logs/chart_debug.log"
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] Sorted {len(all_trades_timed)} trades\n")
        
        # Group trades by close_time (same timestamp = same point)
        time_groups = {}
        for trade in all_trades_timed:
            close_time = trade['close_time']
            if close_time not in time_groups:
                time_groups[close_time] = []
            time_groups[close_time].append(trade)
        
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] Grouped into {len(time_groups)} time points\n")
        
        # Create unified timeline
        unique_times = sorted(time_groups.keys())
        
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] unique_times count: {len(unique_times)}\n")
        
        # Calculate cumulative PnL for COMBINED (using grouped timestamps)
        combined_pnl = []
        current_combined = 0
        for time in unique_times:
            # Sum all PnL changes at this timestamp
            time_pnl = sum(t['pnl'] for t in time_groups[time])
            current_combined += time_pnl
            combined_pnl.append(current_combined)
        
        # X-axis for combined (1 to N unique timestamps)
        combined_indices = list(range(1, len(combined_pnl) + 1))
        
        # Calculate cumulative PnL for each coin on the SAME timeline
        # 🔥 FIX: Use DEDUPLICATED trades from trade_map, not original all_trades!
        coin_cumulative = {}
        coin_indices = {}
        
        for coin in coins:
            # Get deduplicated trades for this coin from all_trades_timed
            coin_trades = [t for t in all_trades_timed if t['coin'] == coin]
            if not coin_trades:
                continue
            
            # Sort by close_time
            coin_trades.sort(key=lambda x: x['close_time'])
            
            # Map coin trades to unified timeline
            cumulative = []
            coin_times = []
            current_pnl = 0
            
            for trade in coin_trades:
                current_pnl += trade['pnl']
                close_time = trade['close_time']
                
                # Find position in unified timeline
                try:
                    timeline_index = unique_times.index(close_time) + 1
                    cumulative.append(current_pnl)
                    coin_times.append(timeline_index)
                except ValueError:
                    # Close_time not in unique_times (shouldn't happen but safety check)
                    pass
            
            coin_cumulative[coin] = cumulative
            coin_indices[coin] = coin_times
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Colors for each coin
        colors = {
            'btc': '#F7931A',  # Bitcoin orange
            'eth': '#627EEA',  # Ethereum blue
            'sol': '#9945FF',  # Solana purple
            'xrp': '#23292F',  # XRP black
        }
        
        # Plot combined line first (thicker, as background)
        if combined_pnl:
            combined_color = '#2ecc71' if combined_pnl[-1] >= 0 else '#e74c3c'
            ax.plot(combined_indices, combined_pnl,
                   label=f'COMBINED (${combined_pnl[-1]:+.0f})',
                   color=combined_color,
                   linewidth=4,
                   marker='s',
                   markersize=6,
                   alpha=0.9,
                   zorder=10)
        
        # Plot each coin line (using timeline indices)
        for coin in coins:
            if coin not in coin_cumulative:
                continue
            
            cumulative = coin_cumulative[coin]
            indices = coin_indices[coin]
            
            ax.plot(indices, cumulative, 
                   label=f'{coin.upper()} (${cumulative[-1]:+.0f})',
                   color=colors.get(coin, '#888888'),
                   linewidth=2,
                   marker='o',
                   markersize=4,
                   alpha=0.7,
                   zorder=5)
        
        # Styling
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
        ax.set_xlabel('Market Close Events', fontsize=12, fontweight='bold')
        ax.set_ylabel('Cumulative PnL ($)', fontsize=12, fontweight='bold')
        
        # Set X-axis limits to unified timeline
        ax.set_xlim(0.5, len(unique_times) + 0.5)
        
        # Title with timestamp
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        ax.set_title(f'Meridian — portfolio performance\n{now}', 
                    fontsize=16, fontweight='bold', pad=20)
        
        # Legend
        ax.legend(loc='best', fontsize=11, framealpha=0.95, shadow=True)
        
        # Add stats text at bottom
        # 🔥 FIX: Use deduplicated trades for stats, not original all_trades!
        stats_lines = []
        stats_lines.append(f"Total Markets: {len(all_trades_timed)}  •  Events: {len(unique_times)}")
        
        for coin in coins:
            # Get deduplicated trades for this coin
            coin_trades = [t for t in all_trades_timed if t['coin'] == coin]
            if coin_trades:
                wins = sum(1 for t in coin_trades if t.get('pnl', 0) > 0)
                wr = (wins / len(coin_trades) * 100) if coin_trades else 0
                final_pnl = coin_cumulative.get(coin, [0])[-1] if coin in coin_cumulative else 0
                # Use USD instead of $ to avoid matplotlib LaTeX parsing
                stats_lines.append(f"{coin.upper()}: {len(coin_trades)}m | {final_pnl:+.0f} USD | {wr:.0f}% WR")
        
        stats_text = "  •  ".join(stats_lines)
        
        ax.text(0.5, 0.02, stats_text, 
               transform=ax.transAxes,
               ha='center',
               fontsize=9,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Tight layout and save
        plt.tight_layout()
        
        debug_file = "/root/4coins_live/logs/chart_debug.log"
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] About to save chart to: {output_path}\n")
        
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        with open(debug_file, 'a') as f:
            f.write(f"[CHART DEBUG] Chart saved successfully!\n")
        
        print(f"[CHART] ✓ Generated PnL chart: {output_path}")
        return True
        
    except Exception as e:
        debug_file = "/root/4coins_live/logs/chart_debug.log"
        with open(debug_file, 'a') as f:
            f.write(f"[CHART ERROR] Exception: {str(e)}\n")
            import traceback
            f.write(f"[CHART ERROR] Traceback:\n")
            f.write(traceback.format_exc())
        
        print(f"[CHART] ✗ Error generating chart: {e}")
        import traceback
        traceback.print_exc()
        return False

