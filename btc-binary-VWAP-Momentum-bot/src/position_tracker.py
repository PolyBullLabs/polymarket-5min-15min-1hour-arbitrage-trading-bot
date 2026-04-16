#!/usr/bin/env python3
"""
Position Tracker

Tracks all positions and calculates P&L.

Features:
- Trade history logging
- P&L calculation
- Win/loss statistics
- Equity curve tracking
- Persistent state
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger("btc_live.tracker")


@dataclass
class Trade:
    """Represents a completed trade."""
    id: str
    market_slug: str
    side: str  # "UP" or "DOWN"
    
    # Entry
    entry_price: float
    entry_contracts: int
    entry_cost: float
    entry_time: datetime
    
    # Hedge (optional)
    hedged: bool = False
    hedge_contracts: int = 0
    hedge_price: float = 0.0
    hedge_cost: float = 0.0
    
    # Exit
    winner: str = ""  # "UP" or "DOWN"
    exit_time: Optional[datetime] = None
    
    # P&L
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "market_slug": self.market_slug,
            "side": self.side,
            "entry_price": self.entry_price,
            "entry_contracts": self.entry_contracts,
            "entry_cost": self.entry_cost,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "hedged": self.hedged,
            "hedge_contracts": self.hedge_contracts,
            "hedge_price": self.hedge_price,
            "hedge_cost": self.hedge_cost,
            "winner": self.winner,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Trade":
        entry_time = data.get("entry_time")
        if entry_time and isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        
        exit_time = data.get("exit_time")
        if exit_time and isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time)
        
        return cls(
            id=data.get("id", ""),
            market_slug=data.get("market_slug", ""),
            side=data.get("side", ""),
            entry_price=data.get("entry_price", 0),
            entry_contracts=data.get("entry_contracts", 0),
            entry_cost=data.get("entry_cost", 0),
            entry_time=entry_time or datetime.now(),
            hedged=data.get("hedged", False),
            hedge_contracts=data.get("hedge_contracts", 0),
            hedge_price=data.get("hedge_price", 0),
            hedge_cost=data.get("hedge_cost", 0),
            winner=data.get("winner", ""),
            exit_time=exit_time,
            pnl=data.get("pnl", 0),
            pnl_pct=data.get("pnl_pct", 0)
        )


@dataclass
class Stats:
    """Trading statistics."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class PositionTracker:
    """
    Tracks positions and calculates P&L.
    
    Features:
    - Active position tracking
    - Trade history with JSONL persistence
    - P&L calculations
    - Win/loss statistics
    - Equity curve for charting
    """
    
    def __init__(
        self,
        trades_file: str = "logs/trades.jsonl",
        state_file: str = "logs/state.json"
    ):
        self.trades_file = Path(trades_file)
        self.state_file = Path(state_file)
        
        # Ensure directories exist
        self.trades_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Current state
        self._active_trade: Optional[Trade] = None
        self._trades: List[Trade] = []
        self._equity_curve: List[float] = [0.0]
        
        # Stats
        self._stats = Stats()
        
        # Load existing state
        self._load_state()
    
    def _load_state(self):
        """Load state from files."""
        # Load trades history
        if self.trades_file.exists():
            try:
                with open(self.trades_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            trade = Trade.from_dict(data)
                            self._trades.append(trade)
                
                logger.info(f"Loaded {len(self._trades)} trades from history")
            except Exception as e:
                logger.error(f"Error loading trades: {e}")
        
        # Load state
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                # Restore active trade
                if state.get("active_trade"):
                    self._active_trade = Trade.from_dict(state["active_trade"])
                
                # Restore equity curve
                self._equity_curve = state.get("equity_curve", [0.0])
                
                # Restore stats
                stats_data = state.get("stats", {})
                self._stats = Stats(**stats_data)
                
                logger.info("State restored")
            except Exception as e:
                logger.error(f"Error loading state: {e}")
        
        # Recalculate stats from trades
        self._recalculate_stats()
    
    def _save_state(self):
        """Save current state to file."""
        try:
            state = {
                "active_trade": self._active_trade.to_dict() if self._active_trade else None,
                "equity_curve": self._equity_curve[-100:],  # Keep last 100 points
                "stats": self._stats.to_dict(),
                "last_update": datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def _append_trade(self, trade: Trade):
        """Append trade to history file."""
        try:
            with open(self.trades_file, 'a') as f:
                f.write(json.dumps(trade.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Error appending trade: {e}")
    
    def _recalculate_stats(self):
        """Recalculate statistics from trade history."""
        if not self._trades:
            return
        
        completed = [t for t in self._trades if t.winner]
        
        wins = [t for t in completed if t.pnl > 0]
        losses = [t for t in completed if t.pnl <= 0]
        
        self._stats.total_trades = len(completed)
        self._stats.wins = len(wins)
        self._stats.losses = len(losses)
        self._stats.total_pnl = sum(t.pnl for t in completed)
        
        if self._stats.total_trades > 0:
            self._stats.win_rate = self._stats.wins / self._stats.total_trades
        
        if wins:
            self._stats.avg_win = sum(t.pnl for t in wins) / len(wins)
        
        if losses:
            self._stats.avg_loss = abs(sum(t.pnl for t in losses) / len(losses))
        
        # Profit factor
        total_wins = sum(t.pnl for t in wins)
        total_losses = abs(sum(t.pnl for t in losses))
        if total_losses > 0:
            self._stats.profit_factor = total_wins / total_losses
        
        # Max drawdown
        equity = 0
        peak = 0
        max_dd = 0
        for t in completed:
            equity += t.pnl
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
        self._stats.max_drawdown = max_dd
        
        # Rebuild equity curve
        self._equity_curve = [0.0]
        equity = 0
        for t in completed:
            equity += t.pnl
            self._equity_curve.append(equity)
    
    def open_trade(
        self,
        trade_id: str,
        market_slug: str,
        side: str,
        entry_price: float,
        entry_contracts: int,
        entry_cost: float
    ):
        """
        Open a new trade.
        
        Args:
            trade_id: Unique trade identifier
            market_slug: Market slug
            side: "UP" or "DOWN"
            entry_price: Average entry price
            entry_contracts: Number of contracts
            entry_cost: Total entry cost
        """
        self._active_trade = Trade(
            id=trade_id,
            market_slug=market_slug,
            side=side,
            entry_price=entry_price,
            entry_contracts=entry_contracts,
            entry_cost=entry_cost,
            entry_time=datetime.now()
        )
        
        logger.info(
            f"Trade opened: {side} {entry_contracts} @ {entry_price:.2f} "
            f"(cost: ${entry_cost:.2f})"
        )
        
        self._save_state()
    
    def update_hedge(
        self,
        hedge_contracts: int,
        hedge_price: float,
        hedge_cost: float
    ):
        """Update trade with hedge information."""
        if not self._active_trade:
            logger.warning("No active trade to update hedge")
            return
        
        self._active_trade.hedged = True
        self._active_trade.hedge_contracts = hedge_contracts
        self._active_trade.hedge_price = hedge_price
        self._active_trade.hedge_cost = hedge_cost
        
        logger.info(
            f"Hedge added: {hedge_contracts} @ {hedge_price:.3f} "
            f"(cost: ${hedge_cost:.2f})"
        )
        
        self._save_state()
    
    def close_trade(self, winner: str):
        """
        Close the active trade with result.
        
        Args:
            winner: Winning side ("UP" or "DOWN")
        """
        if not self._active_trade:
            logger.warning("No active trade to close")
            return
        
        trade = self._active_trade
        trade.winner = winner
        trade.exit_time = datetime.now()
        
        # Calculate P&L
        if trade.hedged:
            # Hedged trade - profit is locked
            # If our side won: we get entry_contracts * 1.0
            # If our side lost: hedge pays out
            if trade.side == winner:
                # Win - collect main position
                payout = trade.entry_contracts * 1.0
                cost = trade.entry_cost + trade.hedge_cost
                trade.pnl = payout - cost
            else:
                # Lose - hedge pays out
                hedge_payout = trade.hedge_contracts * 1.0
                cost = trade.entry_cost + trade.hedge_cost
                trade.pnl = hedge_payout - cost
        else:
            # Unhedged trade
            if trade.side == winner:
                # Win - collect full payout
                payout = trade.entry_contracts * 1.0
                trade.pnl = payout - trade.entry_cost
            else:
                # Lose - lose entry cost
                trade.pnl = -trade.entry_cost
        
        # Calculate percentage
        total_cost = trade.entry_cost + trade.hedge_cost
        if total_cost > 0:
            trade.pnl_pct = (trade.pnl / total_cost) * 100
        
        # Add to history
        self._trades.append(trade)
        self._append_trade(trade)
        
        # Update equity curve
        self._equity_curve.append(self._equity_curve[-1] + trade.pnl)
        
        # Recalculate stats
        self._recalculate_stats()
        
        # Clear active trade
        self._active_trade = None
        
        logger.info(
            f"Trade closed: {winner} won, P&L: ${trade.pnl:.2f} ({trade.pnl_pct:.1f}%)"
        )
        
        self._save_state()
        
        return trade
    
    @property
    def active_trade(self) -> Optional[Trade]:
        return self._active_trade
    
    @property
    def trades(self) -> List[Trade]:
        return self._trades
    
    @property
    def stats(self) -> Stats:
        return self._stats
    
    @property
    def equity_curve(self) -> List[float]:
        return self._equity_curve
    
    @property
    def total_pnl(self) -> float:
        return self._stats.total_pnl
    
    @property
    def win_rate(self) -> float:
        return self._stats.win_rate
    
    def get_summary(self) -> Dict:
        """Get trading summary."""
        return {
            "total_trades": self._stats.total_trades,
            "wins": self._stats.wins,
            "losses": self._stats.losses,
            "win_rate": f"{self._stats.win_rate:.1%}",
            "total_pnl": f"${self._stats.total_pnl:.2f}",
            "avg_win": f"${self._stats.avg_win:.2f}",
            "avg_loss": f"${self._stats.avg_loss:.2f}",
            "profit_factor": f"{self._stats.profit_factor:.2f}",
            "max_drawdown": f"${self._stats.max_drawdown:.2f}",
            "active_trade": self._active_trade is not None
        }
