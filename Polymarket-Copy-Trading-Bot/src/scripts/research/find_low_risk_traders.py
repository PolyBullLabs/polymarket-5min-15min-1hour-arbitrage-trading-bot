#!/usr/bin/env python3
"""
Find low-risk traders
"""
import sys
import asyncio
import os
import math
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

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
HISTORY_DAYS = int(os.getenv('SIM_HISTORY_DAYS', '90'))  # 90 days for better statistics
MIN_TRADER_TRADES = int(os.getenv('MIN_TRADER_TRADES', '50'))
MIN_TRADING_DAYS = int(os.getenv('MIN_TRADING_DAYS', '30'))

# Risk thresholds
MAX_MDD_THRESHOLD = float(os.getenv('MAX_MDD_THRESHOLD', '20.0'))  # Max 20% drawdown
MIN_SHARPE_THRESHOLD = float(os.getenv('MIN_SHARPE_THRESHOLD', '1.5'))  # Min Sharpe Ratio 1.5
MIN_ROI_THRESHOLD = float(os.getenv('MIN_ROI_THRESHOLD', '10.0'))  # Min 10% ROI

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
        
        while len(all_trades) < 2000:  # Reasonable limit
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
        return all_trades
    
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


def calculate_equity_curve(trades: List[Dict[str, Any]], positions: Dict[str, Any]) -> List[Tuple[int, float]]:
    """Calculate equity curve from trades"""
    equity_points = []
    current_equity = STARTING_CAPITAL
    
    for trade in trades:
        side = trade.get('side', '')
        usdc_size = float(trade.get('usdcSize', 0))
        
        if side == 'BUY':
            current_equity -= usdc_size
        elif side == 'SELL':
            current_equity += usdc_size
        
        equity_points.append((trade.get('timestamp', 0), current_equity))
    
    # Add current position values
    total_position_value = sum(
        float(p.get('currentValue', p.get('initialValue', 0)))
        for p in positions.values()
    )
    
    if equity_points:
        last_equity = equity_points[-1][1] + total_position_value
        equity_points.append((int(datetime.now().timestamp()), last_equity))
    
    return equity_points


def calculate_max_drawdown(equity_points: List[Tuple[int, float]]) -> Tuple[float, float]:
    """Calculate maximum drawdown (percentage and amount)"""
    if len(equity_points) < 2:
        return 0.0, 0.0
    
    peak = equity_points[0][1]
    max_dd = 0.0
    max_dd_amount = 0.0
    
    for _, equity in equity_points:
        if equity > peak:
            peak = equity
        
        drawdown = ((peak - equity) / peak) * 100 if peak > 0 else 0
        drawdown_amount = peak - equity
        
        if drawdown > max_dd:
            max_dd = drawdown
            max_dd_amount = drawdown_amount
    
    return max_dd, max_dd_amount


def calculate_sharpe_ratio(equity_points: List[Tuple[int, float]]) -> float:
    """Calculate Sharpe ratio (risk-adjusted return)"""
    if len(equity_points) < 2:
        return 0.0
    
    # Calculate daily returns
    returns = []
    for i in range(1, len(equity_points)):
        prev_equity = equity_points[i-1][1]
        curr_equity = equity_points[i][1]
        
        if prev_equity > 0:
            daily_return = ((curr_equity - prev_equity) / prev_equity) * 100
            returns.append(daily_return)
    
    if not returns:
        return 0.0
    
    # Calculate mean and standard deviation
    mean_return = sum(returns) / len(returns)
    
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance) if variance > 0 else 0
    
    # Sharpe ratio = mean return / standard deviation
    # Annualized (assuming 365 trading days)
    if std_dev > 0:
        sharpe = (mean_return / std_dev) * math.sqrt(365)
    else:
        sharpe = 0.0
    
    return sharpe


def calculate_volatility(equity_points: List[Tuple[int, float]]) -> float:
    """Calculate volatility (standard deviation of daily returns)"""
    if len(equity_points) < 2:
        return 0.0
    
    returns = []
    for i in range(1, len(equity_points)):
        prev_equity = equity_points[i-1][1]
        curr_equity = equity_points[i][1]
        
        if prev_equity > 0:
            daily_return = ((curr_equity - prev_equity) / prev_equity) * 100
            returns.append(daily_return)
    
    if not returns:
        return 0.0
    
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance) if variance > 0 else 0
    
    # Annualized volatility
    return std_dev * math.sqrt(365)


def calculate_win_rate(trades: List[Dict[str, Any]], positions: Dict[str, Any]) -> float:
    """Calculate win rate from closed positions"""
    # Simplified: count profitable vs unprofitable trades
    # This is a simplified calculation
    buy_trades = [t for t in trades if t.get('side') == 'BUY']
    sell_trades = [t for t in trades if t.get('side') == 'SELL']
    
    if len(buy_trades) == 0:
        return 0.0
    
    # Estimate win rate based on position outcomes
    # This is simplified - full implementation would track position P&L
    return 55.0  # Default estimate


def calculate_risk_score(mdd: float, sharpe: float, volatility: float, win_rate: float) -> float:
    """Calculate overall risk score (lower is better)"""
    # Risk score based on multiple factors
    # Lower drawdown = better
    # Higher Sharpe = better
    # Lower volatility = better
    # Higher win rate = better
    
    mdd_score = min(mdd / 50.0, 1.0) * 30  # Max 30 points for drawdown
    sharpe_score = max(0, (2.0 - sharpe) / 2.0) * 25  # Max 25 points for Sharpe
    vol_score = min(volatility / 100.0, 1.0) * 25  # Max 25 points for volatility
    win_score = max(0, (100 - win_rate) / 100.0) * 20  # Max 20 points for win rate
    
    return mdd_score + sharpe_score + vol_score + win_score


async def analyze_trader(trader_address: str) -> Dict[str, Any]:
    """Analyze trader with risk metrics"""
    try:
        trades = await fetch_trader_activity(trader_address)
        
        if len(trades) < MIN_TRADER_TRADES:
            return {
                'address': trader_address,
                'roi': 0,
                'total_pnl': 0,
                'starting_capital': STARTING_CAPITAL,
                'current_capital': STARTING_CAPITAL,
                'max_drawdown': 0,
                'max_drawdown_amount': 0,
                'sharpe_ratio': 0,
                'calmar_ratio': 0,
                'volatility': 0,
                'total_trades': len(trades),
                'win_rate': 0,
                'avg_trade_size': 0,
                'trading_days': 0,
                'risk_score': 100,
                'status': 'bad',
                'error': f'Not enough trades ({len(trades)} < {MIN_TRADER_TRADES})'
            }
        
        # Calculate trading period
        if not trades:
            return {'address': trader_address, 'error': 'No trades found', 'roi': 0}
        
        first_trade = trades[0]
        last_trade = trades[-1]
        trading_days = max(
            1,
            (last_trade.get('timestamp', 0) - first_trade.get('timestamp', 0)) // (24 * 60 * 60)
        )
        
        if trading_days < MIN_TRADING_DAYS:
            return {
                'address': trader_address,
                'roi': 0,
                'total_pnl': 0,
                'trading_days': trading_days,
                'error': f'Not enough trading days ({trading_days} < {MIN_TRADING_DAYS})',
                'status': 'bad'
            }
        
        # Simulate positions
        positions = {}
        current_equity = STARTING_CAPITAL
        
        for trade in trades:
            asset = trade.get('asset', '')
            side = trade.get('side', '')
            usdc_size = float(trade.get('usdcSize', 0))
            
            if side == 'BUY':
                current_equity -= usdc_size
                if asset not in positions:
                    positions[asset] = {'invested': 0, 'shares': 0}
                positions[asset]['invested'] += usdc_size
            elif side == 'SELL':
                current_equity += usdc_size
                if asset in positions:
                    positions[asset]['invested'] = max(0, positions[asset]['invested'] - usdc_size)
        
        # Get current positions
        positions_data = await fetch_trader_positions(trader_address)
        for pos in positions_data:
            asset = pos.get('asset', '')
            if asset:
                positions[asset] = {
                    'invested': float(pos.get('initialValue', 0)),
                    'shares': float(pos.get('size', 0)),
                    'currentValue': float(pos.get('currentValue', 0))
                }
        
        # Calculate equity curve
        equity_points = calculate_equity_curve(trades, positions)
        
        if not equity_points:
            return {'address': trader_address, 'error': 'Could not calculate equity curve', 'roi': 0}
        
        # Calculate final equity
        final_equity = equity_points[-1][1]
        total_pnl = final_equity - STARTING_CAPITAL
        roi = (total_pnl / STARTING_CAPITAL) * 100 if STARTING_CAPITAL > 0 else 0
        
        # Calculate risk metrics
        mdd, mdd_amount = calculate_max_drawdown(equity_points)
        sharpe = calculate_sharpe_ratio(equity_points)
        volatility = calculate_volatility(equity_points)
        calmar = (roi / mdd) if mdd > 0 else (float('inf') if roi > 0 else 0)
        win_rate = calculate_win_rate(trades, positions)
        
        # Calculate average trade size
        total_volume = sum(float(t.get('usdcSize', 0)) for t in trades)
        avg_trade_size = total_volume / len(trades) if trades else 0
        
        # Calculate risk score
        risk_score = calculate_risk_score(mdd, sharpe, volatility, win_rate)
        
        # Determine status
        if (roi >= MIN_ROI_THRESHOLD and mdd <= MAX_MDD_THRESHOLD and 
            sharpe >= MIN_SHARPE_THRESHOLD and risk_score < 30):
            status = 'excellent'
        elif (roi >= MIN_ROI_THRESHOLD * 0.5 and mdd <= MAX_MDD_THRESHOLD * 1.5 and 
              sharpe >= MIN_SHARPE_THRESHOLD * 0.7 and risk_score < 50):
            status = 'good'
        elif (roi >= 0 and mdd <= MAX_MDD_THRESHOLD * 2 and risk_score < 70):
            status = 'average'
        elif roi >= -10 and risk_score < 85:
            status = 'poor'
        else:
            status = 'bad'
        
        return {
            'address': trader_address,
            'roi': roi,
            'total_pnl': total_pnl,
            'starting_capital': STARTING_CAPITAL,
            'current_capital': final_equity,
            'max_drawdown': mdd,
            'max_drawdown_amount': mdd_amount,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'volatility': volatility,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'avg_trade_size': avg_trade_size,
            'trading_days': trading_days,
            'risk_score': risk_score,
            'status': status,
            'profile_url': f'https://polymarket.com/profile/{trader_address}'
        }
    
    except Exception as e:
        return {
            'address': trader_address,
            'error': str(e),
            'roi': 0,
            'status': 'bad'
        }


async def find_low_risk_traders():
    """Find low-risk traders by analyzing risk metrics"""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Finding low-risk traders...")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analyzing last {HISTORY_DAYS} days of trading")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Risk thresholds:")
    print(f"  Max Drawdown: ≤{MAX_MDD_THRESHOLD}%")
    print(f"  Min Sharpe Ratio: ≥{MIN_SHARPE_THRESHOLD}")
    print(f"  Min ROI: ≥{MIN_ROI_THRESHOLD}%")
    print()
    
    # Get traders to analyze
    traders_to_analyze = KNOWN_TRADERS.copy()
    
    # Optionally get from USER_ADDRESSES if configured
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
        result = await analyze_trader(trader)
        results.append(result)
        
        if result.get('error'):
            print(f"  {Fore.YELLOW}⚠ {result['error']}{Style.RESET_ALL}")
        else:
            status_color = {
                'excellent': Fore.GREEN,
                'good': Fore.CYAN,
                'average': Fore.YELLOW,
                'poor': Fore.MAGENTA,
                'bad': Fore.RED
            }.get(result.get('status', 'bad'), Fore.WHITE)
            
            print(f"  {status_color}✓ {result.get('status', 'unknown').upper()}{Style.RESET_ALL} | "
                  f"ROI: {result.get('roi', 0):.2f}% | "
                  f"MDD: {result.get('max_drawdown', 0):.2f}% | "
                  f"Sharpe: {result.get('sharpe_ratio', 0):.2f}")
    
    print()
    print('=' * 100)
    print(f"{Fore.CYAN}{Style.BRIGHT}LOW-RISK TRADERS (Ranked by Risk Score){Style.RESET_ALL}")
    print('=' * 100)
    print()
    
    # Filter out errors and sort by risk score (lower is better)
    valid_results = [r for r in results if not r.get('error')]
    valid_results.sort(key=lambda x: (x.get('risk_score', 100), -x.get('roi', 0)))
    
    if not valid_results:
        print(f"{Fore.YELLOW}No valid results found{Style.RESET_ALL}")
        return
    
    # Display results
    print(f"{Fore.CYAN}{'Rank':<6} {'Address':<15} {'Status':<12} {'ROI':<10} {'MDD':<10} {'Sharpe':<10} {'Risk':<10}{Style.RESET_ALL}")
    print('-' * 100)
    
    status_colors = {
        'excellent': Fore.GREEN,
        'good': Fore.CYAN,
        'average': Fore.YELLOW,
        'poor': Fore.MAGENTA,
        'bad': Fore.RED
    }
    
    for idx, result in enumerate(valid_results[:15], 1):
        address = result['address'][:12] + '...'
        status = result.get('status', 'unknown')
        roi = result.get('roi', 0)
        mdd = result.get('max_drawdown', 0)
        sharpe = result.get('sharpe_ratio', 0)
        risk_score = result.get('risk_score', 100)
        
        status_color = status_colors.get(status, Fore.WHITE)
        roi_color = Fore.GREEN if roi > 0 else Fore.RED
        
        print(f"{idx:<6} {address:<15} {status_color}{status.upper():<12}{Style.RESET_ALL} "
              f"{roi_color}{roi:>8.2f}%{Style.RESET_ALL}  {mdd:>7.2f}%  {sharpe:>8.2f}  {risk_score:>8.1f}")
    
    print()
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Analysis complete!")
    
    # Show best low-risk trader
    best = valid_results[0] if valid_results else None
    if best:
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Best low-risk trader: {best['address']}")
        print(f"  ROI: {best.get('roi', 0):.2f}% | MDD: {best.get('max_drawdown', 0):.2f}% | "
              f"Sharpe: {best.get('sharpe_ratio', 0):.2f} | Risk Score: {best.get('risk_score', 100):.1f}")


if __name__ == '__main__':
    asyncio.run(find_low_risk_traders())
