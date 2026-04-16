"""
Safety Guard - Protection layer for real money trading
"""
import time
import json
from pathlib import Path
from typing import Dict, Tuple


class SafetyGuard:
    """Protection against accidental real money trading"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Read from config (NO FALLBACKS - must be explicit!)
        safety_config = config.get("safety")
        if not safety_config:
            raise ValueError("❌ CRITICAL: 'safety' section missing in config.json!")
        
        # Check required parameters
        if "dry_run" not in safety_config:
            raise ValueError("❌ CRITICAL: 'dry_run' not set in config.json!")
        if "max_order_size_usd" not in safety_config:
            raise ValueError("❌ CRITICAL: 'max_order_size_usd' not set in config.json!")
        if "max_total_investment" not in safety_config:
            raise ValueError("❌ CRITICAL: 'max_total_investment' not set in config.json!")
        
        self.dry_run = safety_config["dry_run"]
        self.max_order_size_usd = safety_config["max_order_size_usd"]
        self.max_orders_per_minute = safety_config.get("max_orders_per_minute", 100)  # OK fallback
        self.max_total_investment = safety_config["max_total_investment"]
        
        # Tracking
        self.orders_history = []
        self.invested_per_market = {}  # {market_slug: invested_usd} - PER MARKET!
        self.emergency_stop = False
        
        # Logging
        self.safety_log = Path("logs/safety.log")
        self.safety_log.parent.mkdir(exist_ok=True)
        
        self._log_init()
    
    def _log_init(self):
        """Log initialization"""
        mode = "🟢 DRY_RUN (SAFE)" if self.dry_run else "🔴 LIVE TRADING (REAL MONEY)"
        msg = f"\n{'='*80}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] SafetyGuard Initialized\n"
        msg += f"Mode: {mode}\n"
        msg += f"Max order size: ${self.max_order_size_usd}\n"
        msg += f"Max orders/min: {self.max_orders_per_minute}\n"
        msg += f"Max total investment: ${self.max_total_investment}\n"
        msg += f"{'='*80}\n"
        
        with open(self.safety_log, 'a', encoding='utf-8') as f:
            f.write(msg)
        
        print(msg)
    
    def check_order_allowed(self, side: str, contracts: int, price: float, 
                           market_slug: str) -> Tuple[bool, str]:
        """
        Check if order is allowed
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Emergency stop
        if self.emergency_stop:
            return False, "EMERGENCY_STOP_ACTIVE"
        
        # DRY_RUN - block all real orders
        if self.dry_run:
            return False, "DRY_RUN_MODE"
        
        # Order size
        order_size_usd = contracts * price
        if order_size_usd > self.max_order_size_usd:
            return False, f"ORDER_TOO_LARGE (${order_size_usd:.2f} > ${self.max_order_size_usd})"
        
        # Rate limiting
        recent_orders = [o for o in self.orders_history 
                        if time.time() - o['timestamp'] < 60]
        if len(recent_orders) >= self.max_orders_per_minute:
            return False, f"RATE_LIMIT ({len(recent_orders)}/{self.max_orders_per_minute} per min)"
        
        # Total investment PER THIS MARKET (resets on market change!)
        current_market_invested = self.invested_per_market.get(market_slug, 0.0)
        
        if current_market_invested + order_size_usd > self.max_total_investment:
            return False, f"INVESTMENT_LIMIT for {market_slug} (${current_market_invested:.2f} + ${order_size_usd:.2f} > ${self.max_total_investment})"
        
        return True, "OK"
    
    def record_order(self, side: str, contracts: float, price: float, 
                    market_slug: str, order_id: str = None):
        """Record executed order"""
        order_size_usd = contracts * price
        
        order = {
            'timestamp': time.time(),
            'market_slug': market_slug,
            'side': side,
            'contracts': contracts,
            'price': price,
            'size_usd': order_size_usd,
            'order_id': order_id,
            'dry_run': self.dry_run
        }
        
        self.orders_history.append(order)
        
        # Accumulate for THIS MARKET (not globally!)
        if market_slug not in self.invested_per_market:
            self.invested_per_market[market_slug] = 0.0
        
        self.invested_per_market[market_slug] += order_size_usd
        
        # Write to log
        with open(self.safety_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(order) + '\n')
    
    def reset_market(self, market_slug: str):
        """
        Reset investment tracking for closed market
        
        Called after redeem or market close.
        This allows trading new markets without limits from previous ones!
        """
        if market_slug in self.invested_per_market:
            invested_amount = self.invested_per_market[market_slug]
            del self.invested_per_market[market_slug]
            print(f"[SAFETY] ♻️ Investment tracking reset for {market_slug} (was ${invested_amount:.2f})")
            
            # Write to log
            with open(self.safety_log, 'a', encoding='utf-8') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] RESET_MARKET: {market_slug} (${invested_amount:.2f})\n")
    
    def get_market_investment(self, market_slug: str) -> float:
        """Get current investment in market"""
        return self.invested_per_market.get(market_slug, 0.0)
    
    def get_total_investment_all_markets(self) -> float:
        """Get total investment across all active markets (for info)"""
        return sum(self.invested_per_market.values())
    
    def activate_emergency_stop(self, reason: str):
        """Activate emergency stop"""
        self.emergency_stop = True
        msg = f"\n🚨 EMERGENCY STOP ACTIVATED: {reason}\n"
        print(msg)
        
        with open(self.safety_log, 'a', encoding='utf-8') as f:
            f.write(msg)
