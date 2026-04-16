"""
Position management with support for multiple entries per market
"""
import time
import json
import threading
from typing import Dict, List, Optional
from pathlib import Path


# Global dependencies (injected externally)
_order_executor = None
_data_feed = None  # ✅ For access to position_tracker (REAL data!)
_token_ids_cache = {}  # {market_slug: {'UP': token_id, 'DOWN': token_id}}
_market_metadata_cache = {}  # {market_slug: {'condition_id': str, 'neg_risk': bool}}

# Persistent storage for metadata (critical for redeem after restart!)
_METADATA_FILE = Path("logs/market_metadata.json")


def set_order_executor(executor):
    """Inject OrderExecutor for real trading"""
    global _order_executor
    _order_executor = executor
    print("[TRADER] ✓ OrderExecutor injected")


def set_data_feed(data_feed):
    """Inject DataFeed for access to REAL positions"""
    global _data_feed
    _data_feed = data_feed
    print("[TRADER] ✅ DataFeed injected (REAL position tracking)")


def save_market_metadata_to_disk():
    """
    💾 Save metadata to disk (CRITICAL for redeem after restart!)
    
    Metadata includes:
    - token_ids (UP, DOWN) 
    - condition_id (for redeem)
    - neg_risk flag
    
    WITHOUT this redeem after restart is IMPOSSIBLE!
    """
    try:
        _METADATA_FILE.parent.mkdir(exist_ok=True)
        
        # Merge token_ids and metadata into one dict
        combined = {}
        for market_slug in _token_ids_cache:
            combined[market_slug] = {
                'token_ids': _token_ids_cache[market_slug],
                'metadata': _market_metadata_cache.get(market_slug, {})
            }
        
        with open(_METADATA_FILE, 'w') as f:
            json.dump(combined, f, indent=2)
        
        # print(f"[TRADER] 💾 Saved metadata for {len(combined)} markets to disk")
    except Exception as e:
        print(f"[TRADER] ⚠️ Failed to save metadata: {e}")


def load_market_metadata_from_disk():
    """
    📂 Load metadata from disk at startup
    
    This is critical for:
    - Redeeming positions after restart
    - EMERGENCY_SAVE positions (loaded from trades.jsonl)
    """
    global _token_ids_cache, _market_metadata_cache
    
    if not _METADATA_FILE.exists():
        print("[TRADER] ℹ️ No metadata file found (first run or clean start)")
        return
    
    try:
        with open(_METADATA_FILE, 'r') as f:
            combined = json.load(f)
        
        # Restore caches
        for market_slug, data in combined.items():
            if 'token_ids' in data:
                _token_ids_cache[market_slug] = data['token_ids']
            if 'metadata' in data:
                _market_metadata_cache[market_slug] = data['metadata']
        
        print(f"[TRADER] ✅ Loaded metadata for {len(combined)} markets from disk")
    except Exception as e:
        print(f"[TRADER] ⚠️ Failed to load metadata: {e}")


def set_token_ids(market_slug: str, up_token_id: str, down_token_id: str, 
                  condition_id: str = "", neg_risk: bool = True):
    """Cache token IDs and metadata for market + save to disk!"""
    global _token_ids_cache, _market_metadata_cache
    _token_ids_cache[market_slug] = {
        'UP': up_token_id,
        'DOWN': down_token_id
    }
    _market_metadata_cache[market_slug] = {
        'condition_id': condition_id,
        'neg_risk': neg_risk
    }
    
    # 💾 CRITICAL: Save to disk for redeem after restart!
    save_market_metadata_to_disk()


def get_token_ids(market_slug: str) -> dict:
    """Get token IDs for market"""
    return _token_ids_cache.get(market_slug, {})


def get_market_metadata(market_slug: str) -> dict:
    """Get metadata (condition_id, neg_risk) for market"""
    return _market_metadata_cache.get(market_slug, {})


class Trader:
    """Manage trading positions with detailed entry tracking"""
    
    def __init__(self, capital: float, log_dir: str = "logs", config: dict = None):
        self.starting_capital = capital
        self.current_capital = capital
        
        # Config for stop-loss checks
        self.config = config
        
        # Positions: {market_slug: {'UP': {...}, 'DOWN': {...}, 'entries': [...], ...}}
        self.positions = {}
        
        # Closed trades history
        self.closed_trades = []
        
        # Track closed markets to prevent re-entry after early exit
        self.closed_markets = set()  # Markets that were closed (early exit or normal)
        
        # 🛡️ THREAD SAFETY: Lock for async operations
        self.lock = threading.RLock()  # Reentrant lock (avoids deadlock)
        
        # Market statistics tracking
        self.market_max_drawdown = {}  # {market_slug: max_dd_value}
        self.market_entries_count = {}  # {market_slug: count}
        
        # Logging
        self.log_dir = Path(log_dir)
        self.trades_file = self.log_dir / "trades.jsonl"
        self.session_file = self.log_dir / "session.json"
        
        print(f"[TRADER] Initialized with ${capital:,.2f} capital")
        
        # Load previous trades to restore statistics
        self.load_previous_trades()
    
    def load_previous_trades(self):
        """
        Load previous trades from trades.jsonl to restore statistics
        This allows bot to continue from where it left off after restart
        """
        if not self.trades_file.exists():
            print(f"[TRADER] No previous trades file found (this is OK for first run)")
            return
        
        try:
            loaded_count = 0
            corrupted_lines = 0
            
            with open(self.trades_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue  # Skip empty lines
                    
                    try:
                        trade = json.loads(line)
                        
                        # Validate trade has required fields
                        if 'pnl' not in trade or 'market_slug' not in trade:
                            print(f"[WARNING] Trade on line {line_num} missing required fields, skipping")
                            corrupted_lines += 1
                            continue
                        
                        self.closed_trades.append(trade)
                        loaded_count += 1
                        
                    except json.JSONDecodeError as e:
                        print(f"[WARNING] Corrupted JSON on line {line_num}: {e}")
                        corrupted_lines += 1
                        continue
            
            if loaded_count > 0:
                # Recalculate current capital from loaded trades
                total_pnl = sum(t['pnl'] for t in self.closed_trades)
                self.current_capital = self.starting_capital + total_pnl
                
                # Get stats
                wins = sum(1 for t in self.closed_trades if t['pnl'] > 0)
                win_rate = (wins / loaded_count * 100) if loaded_count > 0 else 0
                
                print(f"[TRADER] ✓ Loaded {loaded_count} previous trade(s)")
                print(f"[TRADER]   Cumulative PnL: ${total_pnl:+,.2f}")
                print(f"[TRADER]   Win Rate: {win_rate:.1f}% ({wins}/{loaded_count})")
                print(f"[TRADER]   Current Capital: ${self.current_capital:,.2f}")
                
                if corrupted_lines > 0:
                    print(f"[TRADER] ⚠ Skipped {corrupted_lines} corrupted line(s)")
            else:
                print(f"[TRADER] No valid trades found in file")
                
        except Exception as e:
            print(f"[TRADER] ⚠ Error loading previous trades: {e}")
            print(f"[TRADER] Starting fresh with capital ${self.starting_capital:,.2f}")
            # Reset to fresh state on error
            self.closed_trades = []
            self.current_capital = self.starting_capital
    
    def enter_position_contracts(self, market_slug: str, side: str, price: float, contracts: int,
                                 up_ask: float = None, down_ask: float = None,
                                 winner_ratio: float = 0.0, is_recovery: bool = False,
                                 entry_reason: str = 'normal',
                                 seconds_till_end: int = 0, time_from_start: int = 0) -> bool:
        """
        Enter a position by specifying number of contracts/shares
        🛡️ THREAD-SAFE: can be called from different threads
        
        Args:
            market_slug: Market identifier
            side: 'UP' or 'DOWN'
            price: Entry price
            contracts: Number of contracts/shares to buy
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
        # Skip if contracts is 0 (hedge with no position)
        if contracts == 0:
            return True  # Success, just didn't enter anything
        
        # Note: Market closure check now handled in main.py (market_start_prices)
        # This provides single source of truth and auto-cleanup on market switch
        
        # Calculate position size in USD
        size_usd = contracts * price
        shares = float(contracts)
        
        # Track entry count for ratio calculation
        if not hasattr(self, '_entry_count'):
            self._entry_count = 0
        self._entry_count += 1
        
        # 🔥 FIRST TRY TO BUY (if live mode)
        actual_contracts = shares
        actual_cost = size_usd
        
        if _order_executor and market_slug in _token_ids_cache:
            token_id = _token_ids_cache[market_slug][side]
            ask_price = up_ask if side == 'UP' else down_ask
            
            if token_id and ask_price:
                print(f"[TRADER] ▶ {side:4s} @ ${price:.3f}  {shares:6.1f} contracts = ${size_usd:6.2f}  ({market_slug})")
                
                result = _order_executor.place_buy_order(
                    market_slug=market_slug,
                    token_id=token_id,
                    side=side,
                    contracts=contracts,
                    ask_price=ask_price
                )
                
                if result.success:
                    # ✅ SUCCESS! Using ACTUAL filled amounts
                    actual_contracts = result.filled_size
                    actual_cost = result.total_spent_usd
                    
                    if actual_contracts != contracts:
                        print(f"[TRADER] ⚠ FAK partial fill: {actual_contracts:.2f}/{contracts} contracts")
                    
                    print(f"[TRADER] ✓ Order filled: {actual_contracts:.2f} contracts for ${actual_cost:.2f}")
                    
                elif not result.dry_run:
                    # ❌ FAILED! Don't create position at all!
                    print(f"[TRADER] ❌ Order FAILED for {side}: {result.error} - position NOT created")
                    return False
        else:
            # DRY_RUN or no executor - just print
            print(f"[TRADER] ▶ {side:4s} @ ${price:.3f}  {shares:6.1f} shares = ${size_usd:6.2f}  ({market_slug})")
        
        # NOW create position with ACTUAL values (or paper values if DRY_RUN)
        if market_slug not in self.positions:
            self.positions[market_slug] = {
                'UP': {
                    'entries': [],
                    'total_invested': 0.0,
                    'total_shares': 0.0
                },
                'DOWN': {
                    'entries': [],
                    'total_invested': 0.0,
                    'total_shares': 0.0
                },
                'all_entries': [],
                'start_time': time.time(),
                'status': 'OPEN'
            }
        
        # Create entry with ACTUAL values
        entry = {
            'side': side,
            'price': price,
            'size_usd': actual_cost,
            'shares': actual_contracts,
            'time': time.time(),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'actual_fill': (_order_executor is not None)  # Mark if real order
        }
        
        # Add to position
        pos = self.positions[market_slug]
        pos['all_entries'].append(entry)
        pos[side]['entries'].append(entry)
        pos[side]['total_invested'] += actual_cost
        pos[side]['total_shares'] += actual_contracts
        
        # Update market statistics
        self._update_market_stats(market_slug)
        
        # Detailed logging for backtesting
        if up_ask is not None and down_ask is not None and market_slug in self.positions:
            try:
                self.log_entry_detailed(
                    market_slug=market_slug,
                    side=side,
                    contracts=actual_contracts,  # Log actual
                    price=price,
                    up_ask=up_ask,
                    down_ask=down_ask,
                    winner_ratio=winner_ratio,
                    is_recovery=is_recovery,
                    entry_reason=entry_reason,
                    seconds_till_end=seconds_till_end,
                    time_from_start=time_from_start
                )
            except Exception as e:
                # Don't fail the trade if logging fails
                print(f"[WARNING] Detailed logging failed: {e}")
        
        return True
    
    def enter_position(self, market_slug: str, side: str, price: float, size_pct: float) -> bool:
        """
        Enter a position
        
        Args:
            market_slug: Market identifier
            side: 'UP' or 'DOWN'
            price: Entry price
            size_pct: Position size as % of capital
            
        Returns:
            True if entered successfully
        """
        # Calculate position size
        size_usd = self.current_capital * (size_pct / 100.0)
        shares = size_usd / price if price > 0 else 0
        
        # Create market if doesn't exist
        if market_slug not in self.positions:
            self.positions[market_slug] = {
                'UP': {
                    'entries': [],
                    'total_invested': 0.0,
                    'total_shares': 0.0
                },
                'DOWN': {
                    'entries': [],
                    'total_invested': 0.0,
                    'total_shares': 0.0
                },
                'all_entries': [],
                'start_time': time.time(),
                'status': 'OPEN'
            }
        
        # Create entry
        entry = {
            'side': side,
            'price': price,
            'size_usd': size_usd,
            'shares': shares,
            'time': time.time(),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Add to position
        pos = self.positions[market_slug]
        pos['all_entries'].append(entry)
        pos[side]['entries'].append(entry)
        pos[side]['total_invested'] += size_usd
        pos[side]['total_shares'] += shares
        
        # Update market statistics
        self._update_market_stats(market_slug)
        
        # Calculate current ratio after this entry
        up_shares = pos['UP']['total_shares']
        down_shares = pos['DOWN']['total_shares']
        total_shares = up_shares + down_shares
        
        if total_shares > 0 and self._entry_count % 5 == 1:
            up_ratio = (up_shares / total_shares) * 100
            down_ratio = (down_shares / total_shares) * 100
            print(f"[TRADER] After entry: UP {up_shares:.1f} ({up_ratio:.1f}%) | DOWN {down_shares:.1f} ({down_ratio:.1f}%)")
        
        print(f"[TRADER] ▶ {side:4s} @ ${price:.3f}  {shares:6.1f} shares = ${size_usd:6.2f}  ({market_slug})")
        
        return True
    
    def close_market(self, market_slug: str, winner: str, btc_start: float, btc_final: float) -> Optional[Dict]:
        """
        Close all positions for a market
        
        Args:
            market_slug: Market identifier
            winner: 'UP' or 'DOWN'
            btc_start: Starting BTC price
            btc_final: Final BTC price
            
        Returns:
            Trade result dict
        """
        if market_slug not in self.positions:
            return None
        
        pos = self.positions[market_slug]
        
        # Calculate PnL
        winner_side = pos[winner]
        loser_side = pos['UP' if winner == 'DOWN' else 'DOWN']
        
        # Winner pays $1 per share
        payout = winner_side['total_shares'] * 1.0
        
        # Total cost
        total_cost = pos['UP']['total_invested'] + pos['DOWN']['total_invested']
        
        # PnL
        pnl = payout - total_cost
        roi_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
        
        # Winner ratio
        total_shares = pos['UP']['total_shares'] + pos['DOWN']['total_shares']
        winner_ratio = (winner_side['total_shares'] / total_shares * 100) if total_shares > 0 else 50
        
        # Update capital
        self.current_capital += pnl
        
        # Create trade record
        trade = {
            'market_slug': market_slug,
            'winner': winner,
            'btc_start': btc_start,
            'btc_final': btc_final,
            'pnl': pnl,
            'roi_pct': roi_pct,
            'total_cost': total_cost,
            'payout': payout,
            'winner_ratio': winner_ratio,
            'total_entries': len(pos['all_entries']),
            'up_entries': len(pos['UP']['entries']),
            'down_entries': len(pos['DOWN']['entries']),
            'up_invested': pos['UP']['total_invested'],
            'down_invested': pos['DOWN']['total_invested'],
            'up_shares': pos['UP']['total_shares'],
            'down_shares': pos['DOWN']['total_shares'],
            'duration': time.time() - pos['start_time'],
            'close_time': time.time(),
            'close_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # ═══════════════════════════════════════════════════════════
        # CRITICAL FIX: Log trade FIRST, then delete position!
        # This prevents data loss if _log_trade() fails
        # ═══════════════════════════════════════════════════════════
        
        try:
            # 1. Log trade to disk FIRST (most important!)
            self._log_trade(trade)
            
            # 2. Add to memory (safe even if disk write failed)
            self.closed_trades.append(trade)
            
            # 3. Mark market as closed to prevent re-entry
            self.closed_markets.add(market_slug)
            
            # 4. NOW we can safely delete the position
            del self.positions[market_slug]
            
            # 5. Clean up market stats
            if market_slug in self.market_max_drawdown:
                del self.market_max_drawdown[market_slug]
            if market_slug in self.market_entries_count:
                del self.market_entries_count[market_slug]
                
        except Exception as e:
            # CRITICAL: If logging failed, DO NOT delete position!
            # Position will remain open and can be closed again
            print(f"[TRADER] ⚠️ FAILED TO CLOSE MARKET {market_slug}: {e}")
            print(f"[TRADER] ⚠️ Position kept open for retry!")
            return None
        
        # Print result
        status = "✓" if pnl > 0 else "✗"
        print(f"[TRADER] {status} CLOSED {market_slug}: {pnl:+.2f} ({roi_pct:+.1f}%) | "
              f"{trade['total_entries']} entries, ${total_cost:.0f} invested, {winner_ratio:.1f}% {winner}")
        
        # ═══════════════════════════════════════════════════════════
        # 🔥 CRITICAL: Reset investment tracking for this market!
        # Now we can trade new market without limits!
        # ═══════════════════════════════════════════════════════════
        try:
            if order_executor and hasattr(order_executor, 'safety'):
                order_executor.safety.reset_market(market_slug)
        except Exception as reset_err:
            print(f"[TRADER] ⚠ Failed to reset market tracking: {reset_err}")
        
        return trade
    
    def close_market_early_exit(self, market_slug: str, exit_price: float, exit_reason: str = 'early_exit',
                                up_bid: float = None, down_bid: float = None) -> Optional[Dict]:
        """
        Early exit: close position at current favorite price
        🛡️ THREAD-SAFE: can be called from different threads
        
        Args:
            market_slug: Market identifier
            exit_price: Current favorite price (e.g. 0.52)
            exit_reason: Reason for exit ('stop_loss', 'flip_stop', 'early_exit')
            up_bid: Current UP bid price (for selling UP tokens)
            down_bid: Current DOWN bid price (for selling DOWN tokens)
        
        Returns:
            Trade result dict
        """
        with self.lock:
            # ✅ PROTECTION #1: Check that position exists
            if market_slug not in self.positions:
                return None
            
            # ✅ PROTECTION #2: Check market not closed (another thread could have closed)
            if market_slug in self.closed_markets:
                return None  # Already closed, skip silently
            
            pos = self.positions[market_slug]
            
            # Get contracts
            up_contracts = pos['UP']['total_shares']
            down_contracts = pos['DOWN']['total_shares']
            
            # Determine favorite (who has more contracts)
            if up_contracts > down_contracts:
                # UP is favorite - sell UP at exit_price, DOWN at (1 - exit_price)
                payout = up_contracts * exit_price + down_contracts * (1 - exit_price)
                winner = 'UP'
            else:
                # DOWN is favorite - sell DOWN at exit_price, UP at (1 - exit_price)
                payout = down_contracts * exit_price + up_contracts * (1 - exit_price)
                winner = 'DOWN'
            
            # Total cost
            total_cost = pos['UP']['total_invested'] + pos['DOWN']['total_invested']
            
            # PnL = payout - cost
            pnl = payout - total_cost
            roi_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
            
            # Winner ratio
            total_shares = up_contracts + down_contracts
            winner_ratio = (up_contracts / total_shares * 100) if winner == 'UP' else (down_contracts / total_shares * 100)
            
            # Update capital
            self.current_capital += pnl
            
            # ═══════════════════════════════════════════════════════════
            # 📊 LOG FULL ORDERBOOK before selling (for analysis)
            # ═══════════════════════════════════════════════════════════
            if exit_reason in ['stop_loss', 'flip_stop']:
                try:
                    # Get current ask prices from data_feed
                    up_ask = 0.5
                    down_ask = 0.5
                    if _data_feed:
                        market_state = _data_feed.get_state(self.coin)
                        up_ask = market_state.get('up_ask', 0.5)
                        down_ask = market_state.get('down_ask', 0.5)
                    
                    self._last_orderbook_snapshot = self._capture_orderbook_snapshot(
                        market_slug, exit_reason,
                        up_bid if up_bid else (1 - exit_price),
                        down_bid if down_bid else exit_price,
                        up_ask, down_ask
                    )
                    self._log_exit_orderbook(self._last_orderbook_snapshot)
                except Exception as e:
                    print(f"[TRADER] ⚠ Failed to log orderbook: {e}")
                    self._last_orderbook_snapshot = None
            
            # Create trade record
            trade = {
                'market_slug': market_slug,
                'winner': winner,
                'exit_type': 'early_exit',
                'exit_reason': exit_reason,
                'exit_price': exit_price,
                'pnl': pnl,
                'roi_pct': roi_pct,
                'total_cost': total_cost,
                'payout': payout,
                'winner_ratio': winner_ratio,
                'total_entries': len(pos['all_entries']),
                'up_entries': len(pos['UP']['entries']),
                'down_entries': len(pos['DOWN']['entries']),
                'up_invested': pos['UP']['total_invested'],
                'down_invested': pos['DOWN']['total_invested'],
                'up_shares': up_contracts,
                'down_shares': down_contracts,
                'duration': time.time() - pos['start_time'],
                'close_time': time.time(),
                'close_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # ═══════════════════════════════════════════════════════════
            # CRITICAL FIX: Log trade FIRST, then delete position!
            # This prevents data loss if _log_trade() fails
            # ═══════════════════════════════════════════════════════════
            
            try:
                # 1. Log trade to disk FIRST (most important!)
                self._log_trade(trade)
                
                # 2. Add to memory (safe even if disk write failed)
                self.closed_trades.append(trade)
                
                # 3. Mark market as closed to prevent re-entry
                self.closed_markets.add(market_slug)
                
                # 4. NOW we can safely delete the position
                del self.positions[market_slug]
                
                # 5. Clean up market stats
                if market_slug in self.market_max_drawdown:
                    del self.market_max_drawdown[market_slug]
                if market_slug in self.market_entries_count:
                    del self.market_entries_count[market_slug]
                    
            except Exception as e:
                # CRITICAL: If logging failed, DO NOT delete position!
                # Position will remain open and can be closed again
                print(f"[TRADER] ⚠️ FAILED TO CLOSE MARKET {market_slug}: {e}")
                print(f"[TRADER] ⚠️ Position kept open for retry!")
                return None
            
            # Print result
            status = "🚨" if pnl < 0 else "✓"
            print(f"[TRADER] {status} EARLY EXIT {market_slug} @ ${exit_price:.2f}: {pnl:+.2f} ({roi_pct:+.1f}%) | "
                  f"{trade['total_entries']} entries, ${total_cost:.0f} invested")
            
            # 🔥 REAL SELL (if executor connected)
            # 📊 Collecting real payouts for accurate PnL
            real_payout = 0.0
            real_sells_executed = False
            
            if _order_executor and market_slug in _token_ids_cache:
                token_ids = _token_ids_cache[market_slug]
                
                # Sell both sides (UP and DOWN) using TRACKED contracts
                for side in ['UP', 'DOWN']:
                    token_id = token_ids[side]
                    # Get tracked contract amount
                    side_contracts = up_contracts if side == 'UP' else down_contracts
                    
                    # Skip if no contracts
                    if side_contracts <= 0:
                        continue
                    
                    # Get bid price
                    bid = up_bid if side == 'UP' else down_bid
                    if bid is None:
                        # Fallback
                        bid = exit_price if side == 'UP' else (1 - exit_price)
                    
                    result = _order_executor.sell_position(
                        market_slug=market_slug,
                        token_id=token_id,
                        side=side,
                        contracts=side_contracts,  # TRACKED amount!
                        bid_price=bid
                    )
                    
                    if result.success:
                        # Accumulating REAL payout
                        real_payout += result.total_spent_usd
                        real_sells_executed = True
                    elif not result.dry_run:
                        print(f"[TRADER] ⚠ Failed to sell {side}: {result.error}")
                
                # ═══════════════════════════════════════════════════════════
                # 📊 SLIPPAGE ANALYSIS: Expected vs Actual
                # Compare estimated payout (by best BID) with real
                # ═══════════════════════════════════════════════════════════
                if real_sells_executed and real_payout > 0:
                    # Get orderbook snapshot (was captured BEFORE sell)
                    try:
                        if hasattr(self, '_last_orderbook_snapshot') and self._last_orderbook_snapshot:
                            snapshot = self._last_orderbook_snapshot
                            expected_payout = snapshot.get('expected_sale', {}).get('expected_payout_usd', payout)
                            expected_price = snapshot.get('expected_sale', {}).get('best_bid_price', exit_price)
                            
                            # Calculate slippage
                            slippage_usd = real_payout - expected_payout
                            slippage_pct = (slippage_usd / expected_payout * 100) if expected_payout > 0 else 0
                            
                            actual_avg_price = real_payout / (up_contracts + down_contracts) if (up_contracts + down_contracts) > 0 else 0
                            price_diff = actual_avg_price - expected_price
                            price_diff_pct = (price_diff / expected_price * 100) if expected_price > 0 else 0
                            
                            print(f"\n{'='*80}")
                            print(f"[SLIPPAGE ANALYSIS] {self.coin.upper()} - {exit_reason}")
                            print(f"{'='*80}")
                            print(f"📊 EXPECTED (based on BID at trigger):")
                            print(f"   Best BID price: ${expected_price:.4f}")
                            print(f"   Expected payout: ${expected_payout:.2f}")
                            print(f"   Expected PnL: ${pnl:.2f}")
                            print(f"")
                            print(f"💰 ACTUAL (from API response):")
                            print(f"   Avg fill price: ${actual_avg_price:.4f}")
                            print(f"   Actual payout: ${real_payout:.2f}")
                            print(f"   Actual PnL: ${real_pnl:.2f}")
                            print(f"")
                            print(f"📉 SLIPPAGE:")
                            print(f"   Payout difference: ${slippage_usd:+.2f} ({slippage_pct:+.1f}%)")
                            print(f"   Price difference: ${price_diff:+.4f} ({price_diff_pct:+.1f}%)")
                            
                            if slippage_usd < -1.0:
                                print(f"   ⚠️ NEGATIVE SLIPPAGE > $1 - investigating...")
                            elif abs(slippage_usd) < 0.5:
                                print(f"   ✅ Minimal slippage")
                            
                            print(f"{'='*80}\n")
                            
                            # Add to snapshot for logging
                            snapshot['actual_sale'] = {
                                'actual_payout': real_payout,
                                'actual_avg_price': actual_avg_price,
                                'actual_pnl': real_pnl,
                                'slippage_usd': slippage_usd,
                                'slippage_pct': slippage_pct,
                                'price_diff': price_diff,
                                'price_diff_pct': price_diff_pct
                            }
                            
                            # Overwrite snapshot with actual data
                            self._log_exit_orderbook(snapshot)
                            
                    except Exception as e:
                        print(f"[TRADER] ⚠ Slippage analysis error: {e}")
                
                # ═══════════════════════════════════════════════════════════
                # 📊 UPDATE TRADE RECORD with real data
                # Recalculate PnL based on REAL payout from blockchain
                # ═══════════════════════════════════════════════════════════
                if real_sells_executed and real_payout > 0:
                    # Recalculate PnL with real payout
                    real_pnl = real_payout - total_cost
                    real_roi_pct = (real_pnl / total_cost * 100) if total_cost > 0 else 0
                    
                    # Update trade record (returned and in memory)
                    trade['payout'] = real_payout
                    trade['pnl'] = real_pnl
                    trade['roi_pct'] = real_roi_pct
                    
                    # IMPORTANT: Also update last element in closed_trades
                    # (which was added before sell)
                    if self.closed_trades and self.closed_trades[-1]['market_slug'] == market_slug:
                        self.closed_trades[-1]['payout'] = real_payout
                        self.closed_trades[-1]['pnl'] = real_pnl
                        self.closed_trades[-1]['roi_pct'] = real_roi_pct
                    
                    # Log updated trade with real data
                    # (add second entry with updated=True flag for post-mortem analysis)
                    updated_trade = trade.copy()
                    updated_trade['updated'] = True
                    updated_trade['estimated_pnl'] = pnl
                    updated_trade['estimated_payout'] = payout
                    self._log_trade(updated_trade)
                    
                    # Update capital with real PnL (instead of estimated)
                    self.current_capital = self.current_capital - pnl + real_pnl
                    
                    print(f"[TRADER] 💰 Real payout: ${real_payout:.2f} (estimated: ${payout:.2f})")
                    if abs(real_pnl - pnl) > 0.5:
                        diff = real_pnl - pnl
                        print(f"[TRADER] ⚠️  PnL correction: {diff:+.2f} (real: {real_pnl:+.2f} vs estimated: {pnl:+.2f})")
            
            # ═══════════════════════════════════════════════════════════
            # 🔥 CRITICAL: Reset investment tracking for this market!
            # Now we can trade new market without limits!
            # ═══════════════════════════════════════════════════════════
            try:
                if order_executor and hasattr(order_executor, 'safety'):
                    order_executor.safety.reset_market(market_slug)
            except Exception as reset_err:
                print(f"[TRADER] ⚠ Failed to reset market tracking: {reset_err}")
            
            return trade
    
    def _capture_orderbook_snapshot(self, market_slug: str, exit_reason: str, 
                                    up_bid: float, down_bid: float, up_ask: float, down_ask: float) -> Dict:
        """
        Capture full orderbook snapshot for exit analysis
        
        Returns dict with position + orderbook data
        """
        pos = self.positions.get(market_slug, {})
        
        # Determine which side we're selling
        up_shares = pos.get('UP', {}).get('total_shares', 0)
        down_shares = pos.get('DOWN', {}).get('total_shares', 0)
        
        if up_shares > down_shares:
            our_side = 'UP'
            sell_contracts = up_shares
            sell_bid_price = up_bid
        elif down_shares > 0:
            our_side = 'DOWN'
            sell_contracts = down_shares
            sell_bid_price = down_bid
        else:
            our_side = None
            sell_contracts = 0
            sell_bid_price = 0
        
        total_invested = pos.get('UP', {}).get('total_invested', 0) + pos.get('DOWN', {}).get('total_invested', 0)
        
        # Get full orderbook from data_feed
        up_bids_full = []
        down_bids_full = []
        up_asks_full = []
        down_asks_full = []
        
        if _data_feed:
            market_state = _data_feed.get_state(self.coin)
            up_bids_full = market_state.get('up_bids_full', [])
            down_bids_full = market_state.get('down_bids_full', [])
            up_asks_full = market_state.get('up_asks_full', [])
            down_asks_full = market_state.get('down_asks_full', [])
        
        snapshot = {
            'timestamp': time.time(),
            'datetime': time.strftime('%Y-%m-%d %H:%M:%S'),
            'coin': self.coin,
            'market_slug': market_slug,
            'exit_reason': exit_reason,
            'position': {
                'up_shares': up_shares,
                'down_shares': down_shares,
                'up_invested': pos.get('UP', {}).get('total_invested', 0),
                'down_invested': pos.get('DOWN', {}).get('total_invested', 0),
                'total_invested': total_invested,
                'our_side': our_side
            },
            'orderbook': {
                'UP': {
                    'best_bid': up_bid,
                    'best_ask': up_ask,
                    'spread': up_ask - up_bid if (up_ask and up_bid) else 0,
                    'bids_top5': [{'price': p, 'size': s} for p, s in up_bids_full[:5]],
                    'asks_top1': [{'price': p, 'size': s} for p, s in up_asks_full[:1]]
                },
                'DOWN': {
                    'best_bid': down_bid,
                    'best_ask': down_ask,
                    'spread': down_ask - down_bid if (down_ask and down_bid) else 0,
                    'bids_top5': [{'price': p, 'size': s} for p, s in down_bids_full[:5]],
                    'asks_top1': [{'price': p, 'size': s} for p, s in down_asks_full[:1]]
                }
            },
            'expected_sale': {
                'side': our_side,
                'contracts': sell_contracts,
                'best_bid_price': sell_bid_price,
                'expected_payout_usd': sell_contracts * sell_bid_price if sell_bid_price else 0,
                'invested_usd': total_invested,
                'expected_loss_usd': (sell_contracts * sell_bid_price - total_invested) if sell_bid_price else -total_invested
            }
        }
        
        return snapshot
    
    def _log_exit_orderbook(self, snapshot: Dict):
        """Write orderbook snapshot to log file for analysis"""
        import os
        
        log_dir = f"logs/{self.strategy_name}"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = f"{log_dir}/exit_orderbooks.jsonl"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(snapshot) + '\n')
        
        # Print summary to console
        print(f"\n{'='*80}")
        print(f"[EXIT ORDERBOOK] {snapshot['coin'].upper()} - {snapshot['exit_reason']}")
        print(f"Market: {snapshot['market_slug']}")
        print(f"Our side: {snapshot['position']['our_side']}")
        print(f"Invested: ${snapshot['position']['total_invested']:.2f}")
        print(f"Best bid (sell price): {snapshot['expected_sale']['best_bid_price']:.4f}")
        print(f"Expected payout: ${snapshot['expected_sale']['expected_payout_usd']:.2f}")
        print(f"Expected loss: ${snapshot['expected_sale']['expected_loss_usd']:.2f}")
        print(f"UP: BID={snapshot['orderbook']['UP']['best_bid']:.4f} ASK={snapshot['orderbook']['UP']['best_ask']:.4f} SPREAD={snapshot['orderbook']['UP']['spread']:.4f}")
        print(f"DOWN: BID={snapshot['orderbook']['DOWN']['best_bid']:.4f} ASK={snapshot['orderbook']['DOWN']['best_ask']:.4f} SPREAD={snapshot['orderbook']['DOWN']['spread']:.4f}")
        
        # Print full orderbook of selling side
        our_side = snapshot['position']['our_side']
        if our_side:
            print(f"\n{our_side} Orderbook (we're selling here):")
            ob = snapshot['orderbook'][our_side]
            print(f"  Asks (top 1):")
            for level in ob['asks_top1']:
                print(f"    ${level['price']:.4f} × {level['size']:.2f}")
            print(f"  Bids (top 5):")
            for level in ob['bids_top5']:
                print(f"    ${level['price']:.4f} × {level['size']:.2f}")
        
        print(f"{'='*80}\n")
    
    def get_market_stats(self, market_slug: str, up_current: float = 0.5, down_current: float = 0.5) -> Optional[Dict]:
        """
        Get statistics for a specific market including unrealized PnL
        
        ✅ USES REAL DATA from trader.positions (updated via REST API takingAmount)!
        """
        if market_slug not in self.positions:
            return None
        
        pos = self.positions[market_slug]
        
        total_entries = len(pos['all_entries'])
        
        # ✅ USE REAL DATA from trader.positions (updated via REST API)
        total_invested = pos['UP']['total_invested'] + pos['DOWN']['total_invested']
        up_shares = pos['UP']['total_shares']
        down_shares = pos['DOWN']['total_shares']
        up_invested = pos['UP']['total_invested']
        down_invested = pos['DOWN']['total_invested']
        
        up_avg_price = (pos['UP']['total_invested'] / pos['UP']['total_shares']) if pos['UP']['total_shares'] > 0 else 0
        down_avg_price = (pos['DOWN']['total_invested'] / pos['DOWN']['total_shares']) if pos['DOWN']['total_shares'] > 0 else 0
        
        # Calculate unrealized PnL using current prices
        up_value = pos['UP']['total_shares'] * up_current
        down_value = pos['DOWN']['total_shares'] * down_current
        total_value = up_value + down_value
        unrealized_pnl = total_value - total_invested
        
        up_entries = len(pos['UP']['entries'])
        down_entries = len(pos['DOWN']['entries'])
        
        total_shares = up_shares + down_shares
        up_ratio = (up_shares / total_shares * 100) if total_shares > 0 else 0
        down_ratio = (down_shares / total_shares * 100) if total_shares > 0 else 0
        
        return {
            'total_entries': total_entries,
            'total_invested': total_invested,
            'total_cost': total_invested,  # Alias for compatibility
            'avg_per_entry': total_invested / total_entries if total_entries > 0 else 0,
            'up_entries': up_entries,
            'down_entries': down_entries,
            'up_invested': up_invested,  # ✅ REAL data
            'down_invested': down_invested,  # ✅ REAL data
            'up_shares': up_shares,  # ✅ REAL data
            'down_shares': down_shares,  # ✅ REAL data
            'up_avg_price': up_avg_price,
            'down_avg_price': down_avg_price,
            'up_ratio': up_ratio,
            'down_ratio': down_ratio,
            'unrealized_pnl': unrealized_pnl,  # ✅ REAL PnL from WebSocket!
            'exposure_pct': (total_invested / self.current_capital * 100) if self.current_capital > 0 else 0.0
        }
    
    def get_performance_stats(self) -> Dict:
        """Get overall performance statistics"""
        total_trades = len(self.closed_trades)
        wins = sum(1 for t in self.closed_trades if t['pnl'] > 0)
        losses = total_trades - wins
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = sum(t['pnl'] for t in self.closed_trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        winning_trades = [t for t in self.closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in self.closed_trades if t['pnl'] <= 0]
        
        best_win = max(winning_trades, key=lambda t: t['pnl']) if winning_trades else None
        worst_loss = min(losing_trades, key=lambda t: t['pnl']) if losing_trades else None
        
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        avg_entries = sum(t.get('total_entries', 0) for t in self.closed_trades) / total_trades if total_trades > 0 else 0
        avg_invested = sum(t.get('total_cost', 0) for t in self.closed_trades) / total_trades if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'best_win': best_win,
            'worst_loss': worst_loss,
            'profit_factor': profit_factor,
            'avg_entries': avg_entries,
            'avg_invested': avg_invested
        }
    
    def _update_market_stats(self, market_slug: str):
        """Update market statistics after entry"""
        # Update entries count
        if market_slug not in self.market_entries_count:
            self.market_entries_count[market_slug] = 0
        self.market_entries_count[market_slug] += 1
        
        # Initialize max drawdown if needed
        if market_slug not in self.market_max_drawdown:
            self.market_max_drawdown[market_slug] = 0.0
    
    def update_market_drawdown(self, market_slug: str, unrealized_pnl: float):
        """Update max drawdown for market if current is worse"""
        if market_slug not in self.market_max_drawdown:
            self.market_max_drawdown[market_slug] = 0.0
        
        if unrealized_pnl < self.market_max_drawdown[market_slug]:
            self.market_max_drawdown[market_slug] = unrealized_pnl
    
    def get_market_detailed_stats(self, market_slug: str, up_ask: float = 0.5, down_ask: float = 0.5) -> Optional[Dict]:
        """
        Get detailed statistics for a market
        
        Args:
            market_slug: Market identifier
            up_ask: Current UP ask price
            down_ask: Current DOWN ask price
            
        Returns:
            Dict with detailed stats or None
        """
        if market_slug not in self.positions:
            return None
        
        pos = self.positions[market_slug]
        
        up_shares = pos['UP']['total_shares']
        down_shares = pos['DOWN']['total_shares']
        up_invested = pos['UP']['total_invested']
        down_invested = pos['DOWN']['total_invested']
        total_invested = up_invested + down_invested
        
        # Current value (unrealized)
        current_value = (up_shares * up_ask) + (down_shares * down_ask)
        unrealized_pnl = current_value - total_invested
        unrealized_pct = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0
        
        # ═══════════════════════════════════════════════════════════
        # 🚨 CHECK STOP-LOSS RIGHT HERE (where PnL is calculated!)
        # ═══════════════════════════════════════════════════════════
        stop_loss_triggered = False
        stop_loss_threshold = None
        stop_loss_type = None
        
        # Get coin from market_slug (e.g., "btc-updown-15m-1768060800" -> "btc")
        coin = market_slug.split('-')[0] if '-' in market_slug else ''
        
        # Check if we have config for stop-loss
        if self.config and coin and total_invested > 0:
            sl_config = self.config.get('exit', {}).get('stop_loss', {}).get('per_coin', {}).get(coin, {})
            sl_enabled = sl_config.get('enabled', False)
            sl_type = sl_config.get('type', 'none')
            sl_value = sl_config.get('value', None)
            
            if sl_enabled and sl_value is not None:
                if sl_type == 'fixed':
                    # Fixed dollar amount (e.g., -$10)
                    stop_loss_threshold = sl_value
                    stop_loss_triggered = unrealized_pnl <= stop_loss_threshold
                    stop_loss_type = 'fixed'
                elif sl_type == 'percent':
                    # Percentage of invested capital (e.g., -15%)
                    stop_loss_threshold = total_invested * (sl_value / 100.0)
                    stop_loss_triggered = unrealized_pnl <= stop_loss_threshold
                    stop_loss_type = 'percent'
        
        # ═══════════════════════════════════════════════════════════
        # 🚨 CHECK FLIP-STOP (price reversal protection)
        # ═══════════════════════════════════════════════════════════
        flip_stop_triggered = False
        flip_stop_price = None
        
        if self.config and coin and (up_shares > 0 or down_shares > 0):
            flip_cfg = self.config.get('exit', {}).get('flip_stop', {})
            flip_stop_price = flip_cfg.get('price_threshold', 0.48)
            
            # Determine our side
            our_side = 'UP' if up_shares > down_shares else 'DOWN'
            our_price = up_ask if our_side == 'UP' else down_ask
            
            # Check if our side price dropped too low
            if our_price <= flip_stop_price:
                flip_stop_triggered = True
                print(f"[FLIP-STOP] 🚨 {coin.upper()} {our_side} @ ${our_price:.4f} <= ${flip_stop_price:.4f} TRIGGERED!")
            else:
                # Log warning if price is getting close to flip-stop (within 25%)
                if our_price < flip_stop_price * 1.25:
                    print(f"[FLIP-STOP] ⚠️  {coin.upper()} {our_side} @ ${our_price:.4f} close to ${flip_stop_price:.4f}")
        
        # Update drawdown with current unrealized PnL
        self.update_market_drawdown(market_slug, unrealized_pnl)
        
        # Max drawdown
        max_dd = self.market_max_drawdown.get(market_slug, 0.0)
        max_dd_pct = (max_dd / total_invested * 100) if total_invested > 0 else 0
        
        # Average entry prices
        avg_up_price = up_invested / up_shares if up_shares > 0 else 0
        avg_down_price = down_invested / down_shares if down_shares > 0 else 0
        
        # Entries count
        entries_count = self.market_entries_count.get(market_slug, len(pos['all_entries']))
        
        return {
            'up_shares': up_shares,
            'down_shares': down_shares,
            'up_invested': up_invested,
            'down_invested': down_invested,
            'total_invested': total_invested,
            'unrealized_pnl': unrealized_pnl,
            'unrealized_pct': unrealized_pct,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'avg_up_price': avg_up_price,
            'avg_down_price': avg_down_price,
            'entries_count': entries_count,
            'stop_loss_triggered': stop_loss_triggered,
            'stop_loss_threshold': stop_loss_threshold,
            'stop_loss_type': stop_loss_type,
            'flip_stop_triggered': flip_stop_triggered,
            'flip_stop_price': flip_stop_price
        }
    
    def _log_trade(self, trade: Dict):
        """
        Log trade to file with maximum fault tolerance
        
        CRITICAL: This function MUST succeed or raise exception!
        If it fails silently, we lose trade data!
        """
        try:
            # Ensure directory exists
            self.trades_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file with explicit flush
            with open(self.trades_file, 'a') as f:
                f.write(json.dumps(trade) + '\n')
                f.flush()  # Force write to disk immediately
                
        except PermissionError as e:
            print(f"[TRADER] ⚠️ PERMISSION ERROR logging trade: {e}")
            print(f"[TRADER] ⚠️ Trade data: {trade}")
            print(f"[TRADER] ⚠️ File: {self.trades_file}")
            raise  # Re-raise to prevent position deletion
            
        except OSError as e:
            print(f"[TRADER] ⚠️ DISK ERROR logging trade: {e}")
            print(f"[TRADER] ⚠️ Trade data: {trade}")
            print(f"[TRADER] ⚠️ Check disk space: df -h")
            raise  # Re-raise to prevent position deletion
            
        except Exception as e:
            print(f"[TRADER] ⚠️ UNKNOWN ERROR logging trade: {e}")
            print(f"[TRADER] ⚠️ Trade data: {trade}")
            import traceback
            traceback.print_exc()
            raise  # Re-raise to prevent position deletion
    
    def save_session(self):
        """Save current session state"""
        try:
            session = {
                'starting_capital': self.starting_capital,
                'current_capital': self.current_capital,
                'total_pnl': self.current_capital - self.starting_capital,
                'roi_pct': ((self.current_capital / self.starting_capital) - 1) * 100,
                'open_positions': len(self.positions),
                'closed_trades': len(self.closed_trades),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(self.session_file, 'w') as f:
                json.dump(session, f, indent=2)
                
        except Exception as e:
            print(f"[TRADER] Error saving session: {e}")
    
    def log_entry_detailed(self, market_slug: str, side: str, contracts: int, 
                           price: float, up_ask: float, down_ask: float,
                           winner_ratio: float, is_recovery: bool, 
                           entry_reason: str, seconds_till_end: int,
                           time_from_start: int):
        """
        Log detailed entry for backtesting analysis
        
        Args:
            market_slug: Full market slug
            side: 'UP' or 'DOWN'
            contracts: Number of contracts
            price: Entry price
            up_ask: Current UP ask price
            down_ask: Current DOWN ask price
            winner_ratio: Current winner ratio (0.0-1.0)
            is_recovery: Is this a recovery entry after WR < 40%?
            entry_reason: 'normal' or 'recovery'
            seconds_till_end: Seconds until market end
            time_from_start: Seconds from market start
        """
        import os
        
        # Create detailed logs directory
        detailed_dir = str(self.log_dir).replace('/logs/', '/logs_detailed/')
        Path(detailed_dir).mkdir(parents=True, exist_ok=True)
        
        # Get position data
        if market_slug not in self.positions:
            return
        
        pos = self.positions[market_slug]
        
        # Calculate current metrics
        up_contracts = pos['UP']['total_shares']
        down_contracts = pos['DOWN']['total_shares']
        up_invested = pos['UP']['total_invested']
        down_invested = pos['DOWN']['total_invested']
        total_invested = up_invested + down_invested
        total_contracts = up_contracts + down_contracts
        entries_count = len(pos['all_entries'])
        
        # Calculate CORRECT unrealized PnL based on current market prices
        current_value = (up_contracts * up_ask) + (down_contracts * down_ask)
        unrealized_pnl = current_value - total_invested
        unrealized_pnl_pct = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0
        
        # Update max drawdown with current unrealized PnL BEFORE reading it
        self.update_market_drawdown(market_slug, unrealized_pnl)
        
        # Calculate PnL scenarios if market resolves
        if_up_wins = (up_contracts * 1.0) - total_invested
        if_down_wins = (down_contracts * 1.0) - total_invested
        
        # Average prices
        avg_up_price = (up_invested / up_contracts) if up_contracts > 0 else 0
        avg_down_price = (down_invested / down_contracts) if down_contracts > 0 else 0
        
        # Get max drawdown for this market (after updating it above)
        max_dd = self.market_max_drawdown.get(market_slug, 0.0)
        max_dd_pct = (max_dd / total_invested * 100) if total_invested > 0 else 0
        
        # Build entry data
        entry_data = {
            "timestamp": int(time.time()),
            "market_slug": market_slug,
            "seconds_till_end": seconds_till_end,
            "time_from_start": time_from_start,
            
            "market_prices": {
                "up_ask": round(up_ask, 3),
                "down_ask": round(down_ask, 3),
                "confidence": round(abs(down_ask - up_ask), 3)
            },
            
            "entry": {
                "side": side,
                "contracts": contracts,
                "price": round(price, 3),
                "cost": round(contracts * price, 2)
            },
            
            "position_after": {
                "up_contracts": int(up_contracts),
                "down_contracts": int(down_contracts),
                "up_invested": round(up_invested, 2),
                "down_invested": round(down_invested, 2),
                "total_invested": round(total_invested, 2),
                "total_contracts": int(total_contracts),
                "entries_count": entries_count
            },
            
            "pnl_metrics": {
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                "max_drawdown": round(max_dd, 2),
                "max_drawdown_pct": round(max_dd_pct, 2),
                "if_up_wins": round(if_up_wins, 2),
                "if_down_wins": round(if_down_wins, 2),
                "avg_up_price": round(avg_up_price, 3),
                "avg_down_price": round(avg_down_price, 3)
            },
            
            "strategy_state": {
                "winner_ratio": round(winner_ratio, 3),
                "is_recovery": is_recovery,
                "entry_reason": entry_reason
            }
        }
        
        # Filename based on market slug
        filename = f"{market_slug}_entries.jsonl"
        filepath = os.path.join(detailed_dir, filename)
        
        # Append entry
        with open(filepath, 'a') as f:
            f.write(json.dumps(entry_data) + '\n')


