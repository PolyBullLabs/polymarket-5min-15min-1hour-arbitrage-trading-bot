#!/usr/bin/env python3
"""
Hedge Manager (GTD)

Places a passive GTD limit order on the opposite leg immediately after entry.
The order sits on the book and fills automatically when price reaches hedge_price.

No trigger monitoring needed — the CLOB handles execution.
Order auto-cancels when the market resolves.

Features:
- GTD limit order on opposite token
- Exact contract count matching main position
- Duplicate protection via hedge_order_placed flag
- Fill tracking via WebSocket user channel
- Telegram notifications for placement and fills
"""

import asyncio
import logging
import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("btc_live.hedge")

# Separate logger for detailed hedge tracking
hedge_logger = logging.getLogger("btc_live.hedges")
hedge_logger.setLevel(logging.DEBUG)


@dataclass
class HedgeConfig:
    """Configuration for hedging."""
    enabled: bool = True
    hedge_price: float = 0.02
    order_type: str = "GTD"
    max_retries: int = 3
    retry_delay_ms: int = 1000
    simulation_mode: bool = False


@dataclass
class HedgeResult:
    """Result of hedge order placement."""
    success: bool
    order_id: str = ""
    contracts: int = 0
    price: float = 0.0
    attempts: int = 0
    error: str = ""


@dataclass
class HedgePosition:
    """Tracks hedge state for a position."""
    opposite_token_id: str
    contracts: int
    hedge_order_placed: bool = False
    hedge_order_id: str = ""
    hedge_contracts_filled: int = 0
    hedged: bool = False  # True when fully filled


class HedgeManager:
    """
    Manages position hedging via GTD limit orders.
    
    After entry is confirmed, places a GTD BUY order on the opposite token
    at hedge_price (e.g. $0.02). The order sits passively on the book.
    
    When our side reaches ~$0.98, the opposite side drops to ~$0.02
    and our hedge order fills automatically — locking in profit.
    """
    
    def __init__(self, order_executor: Any, config: HedgeConfig):
        self.executor = order_executor
        self.config = config
        self._position: Optional[HedgePosition] = None
        
        # Stats
        self.hedges_placed = 0
        self.hedges_filled = 0
    
    def set_position(self, opposite_token_id: str, contracts: int):
        """
        Set the position to hedge (called after entry is confirmed).
        
        Args:
            opposite_token_id: Token ID of the opposite leg
            contracts: Exact number of contracts from main entry
        """
        self._position = HedgePosition(
            opposite_token_id=opposite_token_id,
            contracts=contracts
        )
        
        hedge_logger.info("=" * 50)
        hedge_logger.info("HEDGE POSITION SET")
        hedge_logger.info(f"  Opposite Token: {opposite_token_id[:30]}...")
        hedge_logger.info(f"  Contracts: {contracts}")
        hedge_logger.info(f"  Hedge Price: ${self.config.hedge_price}")
        hedge_logger.info(f"  Hedge Cost: ${contracts * self.config.hedge_price:.2f}")
        hedge_logger.info(f"  Enabled: {self.config.enabled}")
        hedge_logger.info(f"  Simulation: {self.config.simulation_mode}")
        hedge_logger.info("=" * 50)
        
        logger.info(
            f"Hedge position set: {contracts} contracts, "
            f"will hedge @ ${self.config.hedge_price}"
        )
    
    async def place_gtd_hedge(self) -> HedgeResult:
        """
        Place GTD hedge order on the opposite token.
        
        Called once after entry is confirmed. Retries up to max_retries
        only if API explicitly rejects (success=False).
        
        CRITICAL: Only places ONE order. Flag hedge_order_placed prevents duplicates.
        
        Returns:
            HedgeResult with placement details
        """
        if not self.config.enabled:
            return HedgeResult(success=False, error="Hedge disabled")
        
        if not self._position:
            return HedgeResult(success=False, error="No position set")
        
        pos = self._position
        
        # DUPLICATE PROTECTION
        if pos.hedge_order_placed:
            hedge_logger.warning("HEDGE ALREADY PLACED - skipping")
            return HedgeResult(
                success=True,
                order_id=pos.hedge_order_id,
                contracts=pos.contracts,
                price=self.config.hedge_price,
                error="Already placed"
            )

        if self.config.simulation_mode:
            hedge_logger.info("=" * 60)
            hedge_logger.info("SIMULATION: GTD hedge (no order sent)")
            oid = "SIM-HEDGE"
            pos.hedge_order_placed = True
            pos.hedge_order_id = oid
            self.hedges_placed += 1
            hedge_logger.info(f"  Order ID: {oid}")
            hedge_logger.info("=" * 60)
            logger.info(f"Simulation hedge: {pos.contracts} @ ${self.config.hedge_price}")
            return HedgeResult(
                success=True,
                order_id=oid,
                contracts=pos.contracts,
                price=self.config.hedge_price,
                attempts=1,
            )
        
        hedge_logger.info("=" * 60)
        hedge_logger.info("PLACING GTD HEDGE ORDER")
        hedge_logger.info(f"  Token: {pos.opposite_token_id[:30]}...")
        hedge_logger.info(f"  Size: {pos.contracts} contracts")
        hedge_logger.info(f"  Price: ${self.config.hedge_price}")
        hedge_logger.info(f"  Cost: ${pos.contracts * self.config.hedge_price:.2f}")
        hedge_logger.info(f"  Type: GTD")
        hedge_logger.info(f"  Max Retries: {self.config.max_retries}")
        hedge_logger.info("-" * 40)
        
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY
        
        last_error = ""
        expiration = str(int(time.time()) + 3600)  # 1 hour, market resolves before this
        
        for attempt in range(1, self.config.max_retries + 1):
            hedge_logger.info(f"ATTEMPT {attempt}/{self.config.max_retries}")
            
            try:
                # Create signed order
                signed_order = await asyncio.to_thread(
                    self.executor._client.create_order,
                    OrderArgs(
                        price=self.config.hedge_price,
                        size=pos.contracts,
                        side=BUY,
                        token_id=pos.opposite_token_id,
                        expiration=expiration
                    )
                )
                
                # Post as GTD
                response = await asyncio.to_thread(
                    self.executor._client.post_order,
                    signed_order,
                    OrderType.GTD
                )
                
                # Parse response
                if isinstance(response, dict):
                    success = response.get("success", False)
                    order_id = response.get("orderID", "")
                    status = response.get("status", "")
                    error_msg = response.get("errorMsg", "")
                else:
                    success = getattr(response, 'success', False)
                    order_id = getattr(response, 'orderID', "")
                    status = getattr(response, 'status', "")
                    error_msg = getattr(response, 'errorMsg', "")
                
                hedge_logger.info(f"  Response: success={success}, status={status}, orderID={order_id[:30] if order_id else 'N/A'}")
                
                if success and order_id:
                    # ORDER PLACED SUCCESSFULLY
                    pos.hedge_order_placed = True
                    pos.hedge_order_id = order_id
                    self.hedges_placed += 1
                    
                    hedge_logger.info(f"  ✅ GTD HEDGE ORDER PLACED")
                    hedge_logger.info(f"  Order ID: {order_id}")
                    hedge_logger.info(f"  Status: {status}")
                    
                    logger.info(f"GTD hedge placed: {pos.contracts} @ ${self.config.hedge_price}, ID: {order_id[:20]}...")
                    
                    return HedgeResult(
                        success=True,
                        order_id=order_id,
                        contracts=pos.contracts,
                        price=self.config.hedge_price,
                        attempts=attempt
                    )
                else:
                    # API explicitly rejected — can retry
                    last_error = error_msg or "Order rejected"
                    hedge_logger.warning(f"  ❌ Rejected: {last_error}")
                    logger.warning(f"Hedge attempt {attempt} rejected: {last_error}")
                    
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay_ms / 1000)
                    
            except Exception as e:
                last_error = str(e)
                hedge_logger.error(f"  ❌ Exception: {last_error}")
                logger.error(f"Hedge attempt {attempt} error: {last_error}")
                
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay_ms / 1000)
        
        # All attempts failed
        hedge_logger.error(f"HEDGE FAILED after {self.config.max_retries} attempts: {last_error}")
        logger.error(f"Hedge failed: {last_error}")
        
        return HedgeResult(
            success=False,
            attempts=self.config.max_retries,
            error=last_error
        )
    
    def on_hedge_fill(self, size: int, price: float):
        """
        Called when WebSocket reports a fill on our hedge order.
        
        Args:
            size: Number of contracts filled
            price: Fill price
        """
        if not self._position:
            return
        
        pos = self._position
        pos.hedge_contracts_filled += size
        
        hedge_logger.info(f"HEDGE FILL: +{size} contracts @ ${price:.4f}")
        hedge_logger.info(f"  Total filled: {pos.hedge_contracts_filled}/{pos.contracts}")
        
        if pos.hedge_contracts_filled >= pos.contracts:
            pos.hedged = True
            self.hedges_filled += 1
            hedge_logger.info(f"  ✅ FULLY HEDGED")
            logger.info(f"Position fully hedged: {pos.hedge_contracts_filled} contracts")
        else:
            logger.info(f"Hedge partial fill: {pos.hedge_contracts_filled}/{pos.contracts}")
    
    @property
    def hedge_order_id(self) -> Optional[str]:
        """Get the current hedge order ID."""
        if self._position and self._position.hedge_order_id:
            return self._position.hedge_order_id
        return None
    
    @property
    def is_hedged(self) -> bool:
        """Check if position is fully hedged."""
        return self._position.hedged if self._position else False
    
    @property
    def hedge_order_placed(self) -> bool:
        """Check if hedge order has been placed."""
        return self._position.hedge_order_placed if self._position else False
    
    def clear(self):
        """Clear hedge state (called on market change)."""
        self._position = None
    
    def get_stats(self) -> Dict:
        """Get hedge statistics."""
        pos = self._position
        return {
            "hedges_placed": self.hedges_placed,
            "hedges_filled": self.hedges_filled,
            "current_order_id": pos.hedge_order_id if pos else "",
            "current_filled": pos.hedge_contracts_filled if pos else 0,
            "current_total": pos.contracts if pos else 0,
            "is_hedged": pos.hedged if pos else False,
        }
