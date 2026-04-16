"""
Position Tracker - SINGLE source of truth for positions!

Updated ONLY from WebSocket User Channel events.
No guesses or calculations - only real data from Polymarket API.
"""

import time
from typing import Dict, Optional, List
from dataclasses import dataclass
from threading import Lock


@dataclass
class TradeInfo:
    """Information about confirmed trade"""
    trade_id: str
    side: str  # BUY/SELL
    contracts: float
    price: float
    usd_amount: float
    timestamp: float
    status: str  # MATCHED/MINED/CONFIRMED


class PositionTracker:
    """
    SINGLE source of truth for positions!
    
    Updated ONLY from WebSocket User Channel:
    - ORDER events (size_matched = real amount)
    - TRADE events (on-chain confirmation)
    
    NO GUESSES! ONLY REAL DATA!
    """
    
    def __init__(self):
        self.positions = {}
        # Structure:
        # {
        #   'market_slug': {
        #     'UP': {
      #       'contracts': 120.5,    # REAL amount
      #       'invested': 85.32,     # REAL investment amount
      #       'trades': [TradeInfo]  # All trades
        #     },
        #     'DOWN': {...}
        #   }
        # }
        
        self.pending_orders = {}  # order_id -> order data
        self.confirmed_trades = {}  # trade_id -> TradeInfo
        
        self.asset_to_market = {}  # asset_id -> (market_slug, side_name)
        self.lock = Lock()
        
        print("[TRACKER] ✅ Position Tracker initialized - REAL DATA ONLY!")
    
    def register_market(self, market_slug: str, up_token_id: str, down_token_id: str):
        """
        Register market and its tokens
        
        Required for mapping asset_id -> market_slug
        """
        with self.lock:
            self.asset_to_market[up_token_id] = (market_slug, 'UP')
            self.asset_to_market[down_token_id] = (market_slug, 'DOWN')
            
            if market_slug not in self.positions:
                self.positions[market_slug] = {
                    'UP': {'contracts': 0.0, 'invested': 0.0, 'trades': []},
                    'DOWN': {'contracts': 0.0, 'invested': 0.0, 'trades': []}
                }
            
            print(f"[TRACKER] 📋 Registered market: {market_slug}")
    
    def on_order_event(self, order_data: dict):
        """
        Process ORDER event from WebSocket
        
        Types:
        - PLACEMENT: order placed
        - UPDATE: order matched (partially or fully)
        - CANCELLATION: order cancelled
        """
        try:
            order_type = order_data.get('type')
            order_id = order_data.get('id')
            
            if order_type == 'PLACEMENT':
                # Save pending order
                with self.lock:
                    self.pending_orders[order_id] = order_data
                print(f"[TRACKER] 📝 Order placed: {order_id[:16]}...")
            
            elif order_type == 'UPDATE':
                # ✅ ORDER MATCHED! UPDATING POSITION WITH REAL DATA!
                size_matched = float(order_data.get('size_matched', 0))
                original_size = float(order_data.get('original_size', 0))
                asset_id = order_data.get('asset_id')
                side = order_data.get('side')  # BUY/SELL
                price = float(order_data.get('price', 0))
                
                # Find market by asset_id
                market_info = self.asset_to_market.get(asset_id)
                if not market_info:
                    print(f"[TRACKER] ⚠ Unknown asset_id: {asset_id}")
                    return
                
                market_slug, side_name = market_info
                
                with self.lock:
                    # Ensure market is initialized
                    if market_slug not in self.positions:
                        self.positions[market_slug] = {
                            'UP': {'contracts': 0.0, 'invested': 0.0, 'trades': []},
                            'DOWN': {'contracts': 0.0, 'invested': 0.0, 'trades': []}
                        }
                    
                    pos = self.positions[market_slug][side_name]
                    
                    if side == 'BUY':
                        # ✅ BUY - add to position
                        pos['contracts'] += size_matched
                        pos['invested'] += (size_matched * price)
                        
                        print(f"[TRACKER] ✅ BUY {side_name}: +{size_matched:.2f} @ ${price:.4f}")
                        print(f"          Position now: {pos['contracts']:.2f} contracts, ${pos['invested']:.2f} invested")
                    
                    elif side == 'SELL':
                        # ✅ SELL - remove from position
                        pos['contracts'] -= size_matched
                        # DON'T touch invested on sell (for PnL calculation)
                        
                        received_usd = size_matched * price
                        print(f"[TRACKER] ✅ SELL {side_name}: -{size_matched:.2f} @ ${price:.4f} = ${received_usd:.2f}")
                        print(f"          Position now: {pos['contracts']:.2f} contracts")
            
            elif order_type == 'CANCELLATION':
                # Order cancelled
                with self.lock:
                    if order_id in self.pending_orders:
                        del self.pending_orders[order_id]
                print(f"[TRACKER] ❌ Order cancelled: {order_id[:16]}...")
        
        except Exception as e:
            print(f"[TRACKER] ⚠ Error processing order event: {e}")
    
    def on_trade_event(self, trade_data: dict):
        """
        Process TRADE event from WebSocket
        
        Status progression:
        - MATCHED: trade matched
        - MINED: transaction in blockchain
        - CONFIRMED: transaction confirmed (FINAL!)
        - RETRYING/FAILED: errors
        """
        try:
            trade_id = trade_data.get('id')
            status = trade_data.get('status')
            size = float(trade_data.get('size', 0))
            price = float(trade_data.get('price', 0))
            side = trade_data.get('side')  # BUY/SELL
            asset_id = trade_data.get('asset_id')
            
            if status == 'MATCHED':
                print(f"[TRACKER] 🔄 Trade matched: {trade_id[:16]}... ({side} {size:.2f})")
            
            elif status == 'MINED':
                print(f"[TRACKER] ⛏️  Trade mined: {trade_id[:16]}...")
            
            elif status == 'CONFIRMED':
                # ✅ TRADE CONFIRMED ON-CHAIN!
                market_info = self.asset_to_market.get(asset_id)
                if market_info:
                    market_slug, side_name = market_info
                    
                    trade_info = TradeInfo(
                        trade_id=trade_id,
                        side=side,
                        contracts=size,
                        price=price,
                        usd_amount=size * price,
                        timestamp=time.time(),
                        status=status
                    )
                    
                    with self.lock:
                        self.confirmed_trades[trade_id] = trade_info
                        
                        # Add to position trades history
                        if market_slug in self.positions:
                            self.positions[market_slug][side_name]['trades'].append(trade_info)
                    
                    print(f"[TRACKER] ✅ Trade CONFIRMED: {trade_id[:16]}...")
                    print(f"          {side} {size:.2f} @ ${price:.4f} = ${size * price:.2f}")
            
            elif status in ['RETRYING', 'FAILED']:
                print(f"[TRACKER] ⚠️  Trade {status}: {trade_id[:16]}...")
        
        except Exception as e:
            print(f"[TRACKER] ⚠ Error processing trade event: {e}")
    
    def get_position(self, market_slug: str, side: str) -> Dict:
        """
        Get REAL position from WebSocket tracking
        
        Returns:
        {
            'contracts': 120.5,   # EXACT amount
            'invested': 85.32,    # EXACT investment amount
            'avg_price': 0.71,    # Average entry price
            'trades_count': 10    # Number of trades
        }
        """
        with self.lock:
            if market_slug not in self.positions:
                return {
                    'contracts': 0.0,
                    'invested': 0.0,
                    'avg_price': 0.0,
                    'trades_count': 0
                }
            
            pos = self.positions[market_slug].get(side, {'contracts': 0.0, 'invested': 0.0, 'trades': []})
            contracts = pos['contracts']
            invested = pos['invested']
            avg_price = invested / contracts if contracts > 0 else 0.0
            
            return {
                'contracts': contracts,
                'invested': invested,
                'avg_price': avg_price,
                'trades_count': len(pos['trades'])
            }
    
    def get_total_position(self, market_slug: str) -> Dict:
        """
        Get total position by market (both sides)
        """
        with self.lock:
            if market_slug not in self.positions:
                return {
                    'up_contracts': 0.0,
                    'down_contracts': 0.0,
                    'up_invested': 0.0,
                    'down_invested': 0.0,
                    'total_invested': 0.0,
                    'total_contracts': 0.0
                }
            
            up = self.positions[market_slug]['UP']
            down = self.positions[market_slug]['DOWN']
            
            return {
                'up_contracts': up['contracts'],
                'down_contracts': down['contracts'],
                'up_invested': up['invested'],
                'down_invested': down['invested'],
                'total_invested': up['invested'] + down['invested'],
                'total_contracts': up['contracts'] + down['contracts']
            }
    
    def calculate_pnl(self, market_slug: str, up_price: float, down_price: float) -> Dict:
        """
        Calculate REAL unrealized PnL based on REAL positions
        
        Returns:
        {
            'unrealized_pnl': -5.32,
            'unrealized_pnl_pct': -5.87,
            'current_value': 85.18,
            'total_invested': 90.50
        }
        """
        with self.lock:
            if market_slug not in self.positions:
                return {
                    'unrealized_pnl': 0.0,
                    'unrealized_pnl_pct': 0.0,
                    'current_value': 0.0,
                    'total_invested': 0.0
                }
            
            up = self.positions[market_slug]['UP']
            down = self.positions[market_slug]['DOWN']
            
            # Current position value
            up_value = up['contracts'] * up_price
            down_value = down['contracts'] * down_price
            current_value = up_value + down_value
            
            # Total invested
            total_invested = up['invested'] + down['invested']
            
            # PnL
            unrealized_pnl = current_value - total_invested
            unrealized_pnl_pct = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0.0
            
            return {
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': unrealized_pnl_pct,
                'current_value': current_value,
                'total_invested': total_invested
            }
    
    def has_position(self, market_slug: str) -> bool:
        """Check if there is an open position"""
        with self.lock:
            if market_slug not in self.positions:
                return False
            
            up_contracts = self.positions[market_slug]['UP']['contracts']
            down_contracts = self.positions[market_slug]['DOWN']['contracts']
            
            return up_contracts > 0.01 or down_contracts > 0.01
    
    def clear_position(self, market_slug: str):
        """Clear position (after market close)"""
        with self.lock:
            if market_slug in self.positions:
                print(f"[TRACKER] 🧹 Clearing position for {market_slug}")
                del self.positions[market_slug]
    
    def get_all_positions(self) -> Dict:
        """Get all open positions"""
        with self.lock:
            return {
                slug: self.get_total_position(slug)
                for slug in self.positions.keys()
                if self.has_position(slug)
            }
