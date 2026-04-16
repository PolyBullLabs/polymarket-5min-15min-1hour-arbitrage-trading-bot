"""
Multi-Trader Manager
Manages 4 isolated Trader instances (2 strategies × 2 coins) with complete separation
"""
from typing import Dict, Optional
from pathlib import Path
from trader import Trader


class MultiTrader:
    """Manage multiple isolated trading strategies"""
    
    def __init__(self, capital_per_strategy: float = 10000, strategy_names: list = None, config: dict = None):
        """
        Initialize isolated traders
        
        Args:
            capital_per_strategy: Starting capital for each strategy
            strategy_names: List of strategy names (if None, use default 6)
            config: Configuration dict (for stop-loss checks)
        """
        self.capital_per_strategy = capital_per_strategy
        self.config = config
        
        # Use provided strategy names or default 6
        if strategy_names is None:
            strategy_names = [
                'v1_current',
                'v11_extreme',
                'v9_sqrt',
                'v10_hedge_reduction',
                'v12_balanced',
                'v8_high_base'
            ]
        
        self.traders = {}
        # Get project root (parent of src directory)
        project_root = Path(__file__).parent.parent
        
        for name in strategy_names:
            log_dir = project_root / "logs" / name
            log_dir.mkdir(parents=True, exist_ok=True)
            self.traders[name] = Trader(capital=capital_per_strategy, log_dir=str(log_dir), config=config)
            print(f"[MULTI-TRADER] Initialized {name} with ${capital_per_strategy:,.0f}")
        
        print(f"[MULTI-TRADER] Total portfolio: ${len(self.traders) * capital_per_strategy:,.0f}")
    
    def enter_position(self, strategy_name: str, market_slug: str, side: str, 
                      price: float, contracts: int,
                      up_ask: float = None, down_ask: float = None,
                      winner_ratio: float = 0.0, is_recovery: bool = False,
                      entry_reason: str = 'normal',
                      seconds_till_end: int = 0, time_from_start: int = 0) -> bool:
        """
        Enter position for specific strategy (isolated)
        
        Args:
            strategy_name: Which strategy's trader to use
            market_slug: Market identifier
            side: 'UP' or 'DOWN'
            price: Entry price
            contracts: Number of contracts
            up_ask: Current UP ask price (for detailed logging)
            down_ask: Current DOWN ask price (for detailed logging)
            winner_ratio: Current winner ratio (for detailed logging)
            is_recovery: Is this a recovery entry? (for detailed logging)
            entry_reason: Reason for entry (for detailed logging)
            seconds_till_end: Seconds until market end (for detailed logging)
            time_from_start: Seconds from market start (for detailed logging)
            
        Returns:
            True if entered successfully
        """
        if strategy_name not in self.traders:
            print(f"[ERROR] Unknown strategy: {strategy_name}")
            return False
        
        try:
            trader = self.traders[strategy_name]
            return trader.enter_position_contracts(
                market_slug=market_slug,
                side=side,
                price=price,
                contracts=contracts,
                up_ask=up_ask,
                down_ask=down_ask,
                winner_ratio=winner_ratio,
                is_recovery=is_recovery,
                entry_reason=entry_reason,
                seconds_till_end=seconds_till_end,
                time_from_start=time_from_start
            )
        except Exception as e:
            print(f"[ERROR] {strategy_name} entry failed: {e}")
            return False
    
    def close_market(self, strategy_name: str, market_slug: str, 
                     winner: str, btc_start: float, btc_final: float) -> Optional[Dict]:
        """
        Close market for specific strategy (isolated)
        
        Args:
            strategy_name: Which strategy's trader to use
            market_slug: Market identifier
            winner: 'UP' or 'DOWN'
            btc_start: Starting BTC price
            btc_final: Final BTC price
            
        Returns:
            Trade result dict or None
        """
        if strategy_name not in self.traders:
            print(f"[ERROR] Unknown strategy: {strategy_name}")
            return None
        
        try:
            trader = self.traders[strategy_name]
            return trader.close_market(
                market_slug=market_slug,
                winner=winner,
                btc_start=btc_start,
                btc_final=btc_final
            )
        except Exception as e:
            print(f"[ERROR] {strategy_name} close failed: {e}")
            return None
    
    def close_market_early_exit(self, strategy_name: str, market_slug: str, 
                                exit_price: float, exit_reason: str = 'early_exit',
                                up_bid: float = None, down_bid: float = None) -> Optional[Dict]:
        """
        Close market with early exit for specific strategy
        
        Args:
            strategy_name: Which strategy's trader to use
            market_slug: Market identifier
            exit_price: Current favorite price
            exit_reason: Reason for exit ('stop_loss', 'flip_stop', 'early_exit')
            up_bid: Current UP bid price (for selling)
            down_bid: Current DOWN bid price (for selling)
        
        Returns:
            Trade result dict or None
        """
        if strategy_name not in self.traders:
            print(f"[ERROR] Unknown strategy: {strategy_name}")
            return None
        
        try:
            trader = self.traders[strategy_name]
            return trader.close_market_early_exit(
                market_slug=market_slug,
                exit_price=exit_price,
                exit_reason=exit_reason,
                up_bid=up_bid,
                down_bid=down_bid
            )
        except Exception as e:
            print(f"[ERROR] {strategy_name} early exit failed: {e}")
            return None
    
    def get_trader(self, strategy_name: str) -> Optional[Trader]:
        """Get specific trader instance"""
        return self.traders.get(strategy_name)
    
    def get_all_traders(self) -> Dict[str, Trader]:
        """Get all trader instances"""
        return self.traders
    
    def get_portfolio_stats(self) -> Dict:
        """Get aggregate portfolio statistics"""
        total_capital = 0
        total_pnl = 0
        total_trades = 0
        total_wins = 0
        total_losses = 0
        
        strategy_stats = {}
        
        for name, trader in self.traders.items():
            stats = trader.get_performance_stats()
            
            total_capital += trader.current_capital
            pnl = trader.current_capital - trader.starting_capital
            total_pnl += pnl
            total_trades += stats['total_trades']
            total_wins += stats['wins']
            total_losses += stats['losses']
            
            strategy_stats[name] = {
                'capital': trader.current_capital,
                'pnl': pnl,
                'stats': stats
            }
        
        total_starting = len(self.traders) * self.capital_per_strategy
        portfolio_roi = (total_pnl / total_starting * 100) if total_starting > 0 else 0
        
        return {
            'total_capital': total_capital,
            'total_pnl': total_pnl,
            'total_trades': total_trades,
            'total_wins': total_wins,
            'total_losses': total_losses,
            'portfolio_roi': portfolio_roi,
            'strategy_stats': strategy_stats,
            'num_strategies': len(self.traders)
        }
    
    def get_market_stats(self, strategy_name: str, market_slug: str, up_current: float = 0.5, down_current: float = 0.5) -> Optional[Dict]:
        """
        Get market statistics for specific strategy
        
        Args:
            strategy_name: Which strategy's trader to use
            market_slug: Market identifier
            up_current: Current UP ask price for unrealized PnL
            down_current: Current DOWN ask price for unrealized PnL
            
        Returns:
            Market stats dict or None if no position
        """
        if strategy_name not in self.traders:
            return None
        
        trader = self.traders[strategy_name]
        return trader.get_market_stats(market_slug, up_current, down_current)
    
    def get_current_positions(self, strategy_name: str, market_slug: str) -> Optional[Dict]:
        """Get current positions for specific strategy and market"""
        if strategy_name not in self.traders:
            return None
        
        trader = self.traders[strategy_name]
        if market_slug not in trader.positions:
            return None
        
        pos = trader.positions[market_slug]
        return {
            'up_shares': pos['UP']['total_shares'],
            'down_shares': pos['DOWN']['total_shares'],
            'up_invested': pos['UP']['total_invested'],
            'down_invested': pos['DOWN']['total_invested'],
            'num_entries': len(pos['all_entries'])
        }
    
    def get_session_stats(self, strategy_name: str, markets_skipped: int = 0) -> Dict:
        """
        Get session statistics for a strategy/coin
        
        Args:
            strategy_name: Strategy identifier (e.g. 'late_v3_btc')
            markets_skipped: Number of skipped markets (tracked externally)
        
        Returns:
            Dict with session statistics
        """
        if strategy_name not in self.traders:
            return {
                'markets_played': 0,
                'markets_skipped': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'stop_losses': 0,
                'flip_stops': 0,
            }
        
        trader = self.traders[strategy_name]
        stats = trader.get_performance_stats()
        
        # Count exit types
        stop_losses = sum(1 for t in trader.closed_trades 
                         if t.get('exit_reason') == 'stop_loss')
        flip_stops = sum(1 for t in trader.closed_trades 
                        if t.get('exit_reason') == 'flip_stop')
        
        return {
            'markets_played': stats['total_trades'],
            'markets_skipped': markets_skipped,
            'wins': stats['wins'],
            'losses': stats['losses'],
            'win_rate': stats['win_rate'],
            'total_pnl': trader.current_capital - trader.starting_capital,
            'stop_losses': stop_losses,
            'flip_stops': flip_stops,
        }


