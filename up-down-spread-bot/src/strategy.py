"""
Meridian — late-window entry strategy (Late Entry V3 / late_v3).
Time-based sizing; supports 5m and 15m Polymarket windows (see data_sources.polymarket.market_interval_sec).
"""
import time
from typing import Optional, Dict


class LateEntryStrategy:
    """Late-window entry: trade the favorite side in the final minutes of the window."""
    
    def __init__(self, config: Dict):
        # Read ALL params from config (NO HARDCODED VALUES!)
        strategy_cfg = config.get('strategy', {})
        pm = config.get("data_sources", {}).get("polymarket", {})
        self.market_interval_sec = int(pm.get("market_interval_sec", 900))
        if self.market_interval_sec <= 0:
            self.market_interval_sec = 900
        
        # Default entry window: ~last 4 min of 15m, ~last 2 min of 5m (override in config)
        default_entry = 240 if self.market_interval_sec >= 900 else min(120, self.market_interval_sec - 10)
        raw_ew = int(strategy_cfg.get("entry_window_sec", default_entry))
        # If config still has 15m-style values (e.g. 240) on a 5m market, use default_entry
        if self.market_interval_sec < 900 and raw_ew > self.market_interval_sec * 0.5:
            raw_ew = default_entry
        self.entry_window = min(raw_ew, max(10, self.market_interval_sec - 5))
        self.entry_freq = strategy_cfg.get('entry_frequency_sec', 7)
        self.min_confidence = strategy_cfg.get('min_confidence', 0.30)
        self.max_spread = strategy_cfg.get('max_spread', 1.05)
        self.price_max = strategy_cfg.get('price_max', 0.93)
        
        # Sizing (contracts) - time-based FROM CONFIG!
        sizing_cfg = strategy_cfg.get('sizing', {})
        self.size_above_180 = sizing_cfg.get('above_180_sec', 8)
        self.size_above_120 = sizing_cfg.get('above_120_sec', 10)
        self.size_below_120 = sizing_cfg.get('below_120_sec', 12)
        # Scale 180s/120s thresholds for shorter windows (e.g. 5m → 60s/40s)
        scale = self.market_interval_sec / 900.0
        self.sizing_t1 = max(15, int(180 * scale))
        self.sizing_t2 = max(10, int(120 * scale))
        
        # Max investment per market
        self.max_investment = strategy_cfg.get('max_investment_per_market', 300)
        
        # Flip-stop price (price reversal protection)
        exit_cfg = config.get('exit', {})
        flip_cfg = exit_cfg.get('flip_stop', {})
        self.flip_stop_price = flip_cfg.get('price_threshold', 0.48)
        
        # Track last entry per market
        self.last_entry = {}
        self.last_favorite = {}
    
    def should_enter(self, state: Dict, position: Optional[Dict] = None) -> Optional[Dict]:
        """
        Check if should enter (Late Entry V3 logic)
        
        Args:
            state: Market state with keys:
                - market_slug: str
                - seconds_till_end: int
                - up_ask: float
                - down_ask: float
            position: Optional position stats
        
        Returns:
            Signal dict or None
        """
        market = state['market_slug']
        time_left = state['seconds_till_end']
        up_ask = state['up_ask']
        down_ask = state['down_ask']
        
        # TIME: only inside configured late window
        if time_left > self.entry_window or time_left <= 0:
            return None
        
        # FREQUENCY
        now = time.time()
        if market in self.last_entry and now - self.last_entry[market] < self.entry_freq:
            return None
        
        # SPREAD
        spread = up_ask + down_ask
        if spread > self.max_spread or spread <= 0:
            return None
        
        # CONFIDENCE
        confidence = abs(up_ask - down_ask)
        if confidence < self.min_confidence:
            return None
        
        # FAVORITE
        favorite = 'UP' if up_ask > down_ask else 'DOWN'
        fav_price = up_ask if favorite == 'UP' else down_ask
        
        # PRICE MAX
        if fav_price > self.price_max:
            return None
        
        # INVESTMENT LIMIT
        if position:
            total_cost = position.get('total_cost', 0)
            if total_cost >= self.max_investment:
                return None
        
        # RISK CHECKS - stop-loss removed, only flip-stop via main.py
        # Flip-stop logic in main.py (check: our_price <= strategy.flip_stop_price)
        
        # ENTRY (sizing thresholds scale with market length: 15m → 180/120s, 5m → 60/40s)
        size = (
            self.size_above_180
            if time_left > self.sizing_t1
            else (self.size_above_120 if time_left > self.sizing_t2 else self.size_below_120)
        )
        
        self.last_entry[market] = now
        self.last_favorite[market] = favorite
        
        return {
            'favored': {
                'side': favorite,
                'price': fav_price,
                'contracts': size,
            },
            'hedge': {
                'side': 'DOWN' if favorite == 'UP' else 'UP',
                'price': down_ask if favorite == 'UP' else up_ask,
                'contracts': 0,
            },
            'confidence': confidence,
            'is_recovery': False,
            'entry_reason': f'late_entry_{time_left}s',
            'winner_ratio': 0.0
        }
    
    def get_stats(self) -> Dict:
        """Get strategy statistics (for dashboard compatibility)"""
        return {
            'generated': 0,
            'skipped': 0,
            'total': 0,
            'skip_breakdown': {},
            'gen_pct': 0,
            'skip_pct': 0,
            'wr_recoveries': 0
        }
    
    def reset_market(self, market_slug: str):
        """Reset tracking for a market"""
        if market_slug in self.last_entry:
            del self.last_entry[market_slug]
        if market_slug in self.last_favorite:
            del self.last_favorite[market_slug]
