"""
Meridian — terminal dashboard (late_v3 × BTC, ETH, SOL, XRP).
"""
import time
from typing import Dict
from multi_trader import MultiTrader


class DashboardMultiAB:
    """Multi-market dashboard - grouped by strategies"""
    
    def __init__(self, width: int = 160, coins: list = None, config: dict = None):
        self.width = width
        self.start_time = time.time()
        self.coins = coins or ['btc', 'eth', 'sol', 'xrp']
        self.events_log = []  # Last N events for display
        self.max_events = 10
        self.config = config or {}
    
    def add_event(self, message: str, event_type: str = 'info'):
        """Add event to log (ONLY critical errors displayed in terminal)"""
        # FILTER: Show only errors in terminal
        if event_type not in ['error']:
            return  # Ignore everything except errors
        
        timestamp = time.strftime('%H:%M:%S')
        
        # Shorten message for terminal display
        if len(message) > 70:
            message = message[:67] + "..."
        
        emoji = '✗'  # Only for errors
        
        event = f"[{timestamp}] {emoji} {message}"
        self.events_log.append(event)
        
        # Keep only last N events
        if len(self.events_log) > self.max_events:
            self.events_log = self.events_log[-self.max_events:]
    
    def render(self, multi_trader: MultiTrader, strategies: Dict, data_feed, wallet_balance: float = None, pending_markets: Dict = None):
        """Render dashboard"""
        # Clear screen
        print('\033[2J\033[H', end='')
        
        # Build display
        lines = self._build_display(multi_trader, strategies, data_feed, wallet_balance, pending_markets)
        print(lines, end='', flush=True)
    
    def _build_display(self, multi_trader: MultiTrader, strategies: Dict, data_feed, wallet_balance: float = None, pending_markets: Dict = None) -> str:
        """Build display string"""
        output = []
        
        # Get market states for all coins
        market_states = {}
        for coin in self.coins:
            market_states[coin] = data_feed.get_state(coin)
        
        # Runtime
        runtime = time.time() - self.start_time
        runtime_str = self._format_time(runtime)
        
        # Header - all coins use orderbook data
        header = f"⏱ {runtime_str} │ BTC │ ETH │ SOL │ XRP (Polymarket orderbooks)"
        
        output.append("=" * self.width)
        output.append(header.center(self.width))
        output.append("=" * self.width)
        output.append("")
        
        # Strategy base names
        strategy_bases = [
            ('late_v3', 'LATE V3')
        ]
        
        # Display each strategy (grouped by base)
        for base_name, display_name in strategy_bases:
            output.append(f"┌─ {display_name.upper()} {'─' * (self.width - len(display_name) - 5)}┐")
            
            # Calculate total for this strategy (all coins)
            traders = {}
            stats = {}
            for coin in self.coins:
                trader_name = f"{base_name}_{coin}"
                if trader_name in multi_trader.traders:
                    traders[coin] = multi_trader.traders[trader_name]
                    stats[coin] = traders[coin].get_performance_stats()
            
            if not traders:
                output.append(f"│ ERROR: No traders found for strategy")
                output.append(f"└{'─' * (self.width - 2)}┘")
                output.append("")
                continue
            
            # Strategy totals
            total_capital = sum(t.current_capital for t in traders.values())
            starting_capital = sum(t.starting_capital for t in traders.values())
            total_pnl = total_capital - starting_capital
            
            # Calculate ROI correctly - use wallet_balance if available, otherwise use starting_capital
            # ROI = PnL / Initial Investment * 100
            if wallet_balance and wallet_balance > 0:
                # Use real wallet balance to calculate initial investment
                initial_balance = wallet_balance - total_pnl
                total_roi = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0
            elif starting_capital > 0:
                # Fallback to starting_capital if available
                total_roi = (total_pnl / starting_capital * 100)
            else:
                # Last resort: calculate from current capital
                total_roi = (total_pnl / total_capital * 100) if total_capital > total_pnl and total_capital > 0 else 0
            total_trades = sum(s['total_trades'] for s in stats.values())
            total_wins = sum(s['wins'] for s in stats.values())
            total_losses = sum(s['losses'] for s in stats.values())
            total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
            
            # Color code total PnL
            pnl_color = '\033[92m' if total_pnl >= 0 else '\033[91m'
            pnl_reset = '\033[0m'
            pnl_sign = "+" if total_pnl >= 0 else ""
            
            # Strategy summary line (unified balance)
            balance_display = f"${wallet_balance:,.2f}" if wallet_balance else f"${total_capital:,.0f}"
            output.append(f"│ Balance: {balance_display} │ PnL: {pnl_color}{pnl_sign}${total_pnl:,.0f}({pnl_sign}{total_roi:.1f}%){pnl_reset} │ "
                         f"Trades: {total_trades} │ W/L: {total_wins}/{total_losses} │ WR: {total_wr:.1f}%")
            output.append(f"│")
            
            # Display each coin market
            for coin in self.coins:
                if coin in traders:
                    trader_name = f"{base_name}_{coin}"
                    self._add_market_info(output, coin.upper(), market_states[coin], trader_name, 
                                         traders[coin], strategies.get(trader_name), multi_trader)
            
            output.append(f"└{'─' * (self.width - 2)}┘")
            output.append("")
        
        # Recent activity (compact)
        output.append("📈 Recent Trades:")
        
        all_closed = []
        for name, trader in multi_trader.traders.items():
            for trade in trader.closed_trades[-1:]:
                trade['strategy'] = name
                all_closed.append(trade)
        
        all_closed.sort(key=lambda x: x.get('close_time', 0), reverse=True)
        
        for trade in all_closed[:4]:
            strategy = trade['strategy']
            # Extract coin from strategy name (last part)
            coin = strategy.split('_')[-1].upper()
            # Extract base name (everything except coin)
            base = '_'.join(strategy.split('_')[:-1]).replace('late_v3', 'LV3')
            market = trade['market_slug'].split('-')[-1]
            pnl = trade['pnl']
            pnl_sign = "+" if pnl >= 0 else ""
            pnl_color = '\033[92m' if pnl >= 0 else '\033[91m'
            pnl_reset = '\033[0m'
            
            activity = f"  [{base:>3}/{coin:>3}] {market}: {pnl_color}{pnl_sign}${pnl:>5,.0f}{pnl_reset}"
            output.append(activity)
        
        if not all_closed:
            output.append("  (None)")
        
        output.append("")
        
        # Pending markets
        if pending_markets:
            import time as time_module
            output.append("⏳ Pending:")
            
            for market_slug_pending, info in pending_markets.items():
                elapsed = (time_module.time() - info['first_attempt']) / 60
                next_retry = (info['next_retry'] - time_module.time()) / 60
                
                # Extract coin from market slug
                coin = market_slug_pending.split('-')[0].upper()
                market_short = market_slug_pending.split('-')[-1]
                
                if next_retry > 0:
                    status = f"~{next_retry:.0f}m (#{info['attempts']})"
                else:
                    status = f"checking... (#{info['attempts'] + 1})"
                
                output.append(f"  • {coin}/{market_short}: {status}")
            
            output.append("")
        
        # Events log (ONLY critical errors, if any)
        if self.events_log:
            output.append("🚨 Critical Errors:")
            for event in self.events_log[-10:]:  # Last 10
                output.append(f"  {event}")
            output.append("")
        
        # Add keyboard controls footer
        output.append("─" * self.width)
        output.append("🎹 Keyboard: [M] Manual Redeem All  │  [Ctrl+C] Stop Trading".center(self.width))
        
        return '\n'.join(output)
    
    def _add_market_info(self, output, coin_label, market_state, trader_name, trader, strategy, multi_trader):
        """Add market information block for a specific coin"""
        market_slug = market_state['market_slug']
        seconds_left = market_state['seconds_till_end']
        up_ask = market_state.get('up_ask') or 0.0
        down_ask = market_state.get('down_ask') or 0.0
        confidence = market_state.get('confidence', 0.0)
        
        # Time left
        time_left_str = self._format_time(seconds_left) if seconds_left > 0 else "ENDED"
        market_short = market_slug.split('-')[-1] if market_slug else "N/A"
        
        # MM Favorite (higher price = favorite)
        mm_favorite = 'UP' if up_ask > down_ask else 'DOWN'
        fav_arrow = '↑' if mm_favorite == 'UP' else '↓'
        
        # Color code confidence
        conf_color = '\033[92m' if confidence >= 0.2 else '\033[93m'
        conf_reset = '\033[0m'
        
        # Strategy stats
        stats = trader.get_performance_stats()
        pnl = trader.current_capital - trader.starting_capital
        pnl_sign = "+" if pnl >= 0 else ""
        pnl_color = '\033[92m' if pnl >= 0 else '\033[91m'
        pnl_reset = '\033[0m'
        
        # WR Stop Loss stats
        wr_stopped = 0
        recoveries = 0
        if strategy:
            strategy_stats = strategy.get_stats()
            wr_stopped = strategy_stats['skip_breakdown'].get('wr_stop_loss', 0)
            recoveries = strategy_stats.get('wr_recoveries', 0)
        
        # Trading status indicator
        coin_lower = coin_label.lower()
        trading_enabled = self.config.get('trading', {}).get(coin_lower, {}).get('enabled', True)
        trading_status = "📈" if trading_enabled else "👁️"
        
        # Market header
        output.append(f"│ {trading_status} 【{coin_label}】 {market_short} │ ⏰ {time_left_str} │ "
                     f"UP:{up_ask:.3f} DN:{down_ask:.3f} {fav_arrow}{mm_favorite} │ "
                     f"Conf:{conf_color}{confidence:.3f}{conf_reset}")
        
        # Stats line (no Cap - unified balance in header)
        output.append(f"│   PnL: {pnl_color}{pnl_sign}${pnl:,.0f}{pnl_reset} │ "
                     f"Trades: {stats['total_trades']} │ W/L: {stats['wins']}/{stats['losses']} │ "
                     f"WR: {stats['win_rate']:.1f}% │ St:{wr_stopped} Rc:{recoveries}")
        
        # Current position
        pos = multi_trader.get_current_positions(trader_name, market_slug)
        
        if pos and (pos['up_shares'] > 0 or pos['down_shares'] > 0):
            # Get detailed stats
            detailed_stats = trader.get_market_detailed_stats(market_slug, up_ask, down_ask)
            
            if detailed_stats:
                up_shares = detailed_stats['up_shares']
                down_shares = detailed_stats['down_shares']
                up_invested = detailed_stats['up_invested']
                down_invested = detailed_stats['down_invested']
                total_invested = detailed_stats['total_invested']
                unrealized_pnl = detailed_stats['unrealized_pnl']
                unrealized_pct = detailed_stats['unrealized_pct']
                max_dd = detailed_stats['max_drawdown']
                max_dd_pct = detailed_stats['max_drawdown_pct']
                entries_count = detailed_stats['entries_count']
                
                # Calculate PnL scenarios
                if_up_wins = (up_shares * 1.0) - total_invested
                if_down_wins = (down_shares * 1.0) - total_invested
                
                # Determine our bet
                total_shares = up_shares + down_shares
                our_pct = (up_shares / total_shares * 100) if total_shares > 0 else 50
                our_favorite = 'UP' if up_shares > down_shares else 'DOWN'
                
                # Status
                is_right = (our_favorite == mm_favorite)
                overall_status = '\033[92m✓\033[0m' if is_right else '\033[91m✗\033[0m'
                
                # Color code unrealized PnL
                unreal_color = '\033[92m' if unrealized_pnl >= 0 else '\033[91m'
                unreal_reset = '\033[0m'
                
                # Position details (compact 3-line format)
                output.append(f"│   Pos: UP:{int(up_shares)}×{up_ask:.3f}=${up_invested:.0f} │ "
                             f"DN:{int(down_shares)}×{down_ask:.3f}=${down_invested:.0f} │ "
                             f"Total:${total_invested:.0f} │ Entries:{entries_count}")
                output.append(f"│   Now: {unreal_color}{unrealized_pnl:+.0f}({unrealized_pct:+.0f}%){unreal_reset} │ "
                             f"MaxDD:{max_dd:.0f}({max_dd_pct:.0f}%) │ "
                             f"If↑:{if_up_wins:+.0f} If↓:{if_down_wins:+.0f}")
                output.append(f"│   Bet: {our_favorite}({our_pct:.0f}%) vs MM:{mm_favorite} {overall_status}")
        else:
            output.append(f"│   Position: None")
        
        output.append(f"│")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS"""
        seconds = int(seconds)
        if seconds >= 3600:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:02d}:{secs:02d}"
