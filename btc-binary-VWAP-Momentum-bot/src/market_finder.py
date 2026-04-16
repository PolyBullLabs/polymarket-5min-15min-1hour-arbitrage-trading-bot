#!/usr/bin/env python3
"""
Market Finder

Searches for active BTC 5- or 15-minute up/down markets on Polymarket.
Features:
- Async HTTP with retry logic
- Caching to reduce API calls
- Automatic market lifecycle detection
- Robust error handling
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

import aiohttp

logger = logging.getLogger("btc_live.market_finder")

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

def _btc_slug_pattern(interval_minutes: int) -> re.Pattern:
    return re.compile(rf"btc-updown-{int(interval_minutes)}m-(\d+)")


@dataclass
class Market:
    """Represents a BTC up/down interval market (5m or 15m slug)."""
    
    id: str
    slug: str
    question: str
    condition_id: str
    
    # Token IDs
    up_token_id: str
    down_token_id: str
    
    # Timing
    start_time: datetime
    end_time: datetime
    
    # State
    active: bool = True
    closed: bool = False
    accepting_orders: bool = True
    
    # Prices (updated from WebSocket)
    up_price: float = 0.5
    down_price: float = 0.5
    best_bid: float = 0.0
    best_ask: float = 0.0
    
    # Metadata
    volume: float = 0.0
    liquidity: float = 0.0
    
    def time_remaining_seconds(self) -> float:
        """Get seconds until market ends."""
        now = datetime.now(timezone.utc)
        delta = self.end_time - now
        return max(0, delta.total_seconds())
    
    def time_elapsed_seconds(self) -> float:
        """Get seconds since market started."""
        now = datetime.now(timezone.utc)
        delta = now - self.start_time
        return max(0, delta.total_seconds())
    
    def minutes_remaining(self) -> float:
        """Get minutes until market ends."""
        return self.time_remaining_seconds() / 60
    
    def minutes_elapsed(self) -> float:
        """Get minutes since market started."""
        return self.time_elapsed_seconds() / 60
    
    def is_tradeable(self) -> bool:
        """Check if market is currently tradeable."""
        return (
            self.active and 
            not self.closed and 
            self.accepting_orders and
            self.time_remaining_seconds() > 0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "slug": self.slug,
            "question": self.question,
            "condition_id": self.condition_id,
            "up_token_id": self.up_token_id,
            "down_token_id": self.down_token_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "active": self.active,
            "closed": self.closed,
            "up_price": self.up_price,
            "down_price": self.down_price,
        }


class MarketFinder:
    """
    Finds and tracks BTC up/down markets for a chosen interval (5 or 15 minutes).
    
    Features:
    - Async HTTP requests with exponential backoff
    - Market caching
    - Automatic refresh
    - Error recovery
    """
    
    def __init__(
        self,
        refresh_interval: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        interval_minutes: int = 15,
    ):
        self.refresh_interval = refresh_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.interval_minutes = int(interval_minutes) if int(interval_minutes) in (5, 15) else 15
        self._slug_pattern = _btc_slug_pattern(self.interval_minutes)
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._current_market: Optional[Market] = None
        self._market_history: List[str] = []  # List of processed market slugs
        self._last_refresh: Optional[datetime] = None
        self._running = False
        
        # Callbacks
        self._on_new_market_callbacks: List[callable] = []
        self._on_market_end_callbacks: List[callable] = []
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def _request_with_retry(
        self,
        url: str,
        params: Optional[Dict] = None,
        method: str = "GET"
    ) -> Optional[Dict]:
        """
        Make HTTP request with retry logic.
        
        Args:
            url: Request URL
            params: Query parameters
            method: HTTP method
        
        Returns:
            JSON response or None on failure
        """
        session = await self._get_session()
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                async with session.request(method, url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        # Rate limited - wait longer
                        wait_time = self.retry_delay * (2 ** attempt) * 2
                        logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    elif resp.status >= 500:
                        # Server error - retry
                        logger.warning(f"Server error {resp.status}, retrying...")
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                        continue
                    else:
                        logger.error(f"HTTP {resp.status}: {await resp.text()}")
                        return None
                        
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.max_retries})")
                last_error = "timeout"
            except aiohttp.ClientError as e:
                logger.warning(f"Client error: {e} (attempt {attempt + 1}/{self.max_retries})")
                last_error = str(e)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                last_error = str(e)
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"Request failed after {self.max_retries} attempts: {last_error}")
        return None
    
    def _parse_market(self, data: Dict) -> Optional[Market]:
        """
        Parse market data from Gamma API response.
        
        Args:
            data: Raw market data from API
        
        Returns:
            Market object or None if parsing fails
        """
        try:
            slug = data.get("slug", "")
            
            # Check if it's a BTC up/down market for our interval
            match = self._slug_pattern.match(slug)
            if not match:
                return None
            
            # Parse token IDs
            clob_token_ids = data.get("clobTokenIds", "[]")
            if isinstance(clob_token_ids, str):
                clob_token_ids = json.loads(clob_token_ids)
            
            if len(clob_token_ids) < 2:
                logger.warning(f"Market {slug} has insufficient token IDs")
                return None
            
            # Parse outcomes to match tokens
            outcomes = data.get("outcomes", "[]")
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            
            # Determine Up/Down token indices
            up_idx, down_idx = 0, 1
            for i, outcome in enumerate(outcomes):
                if outcome.lower() == "up":
                    up_idx = i
                elif outcome.lower() == "down":
                    down_idx = i
            
            # Parse times
            end_date_str = data.get("endDate", "")
            start_time_str = data.get("eventStartTime") or data.get("startDate", "")
            
            if not end_date_str:
                logger.warning(f"Market {slug} has no end date")
                return None
            
            # Parse ISO dates
            end_time = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            else:
                start_time = end_time - timedelta(minutes=self.interval_minutes)
            
            # Parse prices
            outcome_prices = data.get("outcomePrices", "[]")
            if isinstance(outcome_prices, str):
                outcome_prices = json.loads(outcome_prices)
            
            up_price = float(outcome_prices[up_idx]) if len(outcome_prices) > up_idx else 0.5
            down_price = float(outcome_prices[down_idx]) if len(outcome_prices) > down_idx else 0.5
            
            return Market(
                id=data.get("id", ""),
                slug=slug,
                question=data.get("question", ""),
                condition_id=data.get("conditionId", ""),
                up_token_id=clob_token_ids[up_idx],
                down_token_id=clob_token_ids[down_idx],
                start_time=start_time,
                end_time=end_time,
                active=data.get("active", True),
                closed=data.get("closed", False),
                accepting_orders=data.get("acceptingOrders", True),
                up_price=up_price,
                down_price=down_price,
                best_bid=float(data.get("bestBid", 0) or 0),
                best_ask=float(data.get("bestAsk", 0) or 0),
                volume=float(data.get("volume", 0) or 0),
                liquidity=float(data.get("liquidity", 0) or 0),
            )
            
        except Exception as e:
            logger.error(f"Error parsing market: {e}")
            return None
    
    async def find_active_market(self) -> Optional[Market]:
        """
        Find the currently active BTC up/down market for this finder’s interval.
        
        Returns:
            Active Market or None if not found
        """
        slug_part = f"btc-updown-{self.interval_minutes}m"
        logger.debug("Searching for active %s market...", slug_part)
        
        # Search Gamma API
        url = f"{GAMMA_API}/markets"
        params = {
            "slug_contains": slug_part,
            "active": "true",
            "closed": "false",
            "limit": 10,
            "order": "endDate",
            "ascending": "true"
        }
        
        data = await self._request_with_retry(url, params)
        
        if not data:
            logger.warning("No response from Gamma API")
            return None
        
        # Handle both list and single object responses
        markets_list = data if isinstance(data, list) else [data]
        
        now = datetime.now(timezone.utc)
        best_market: Optional[Market] = None
        
        for market_data in markets_list:
            market = self._parse_market(market_data)
            
            if market is None:
                continue
            
            # Skip already processed markets
            if market.slug in self._market_history:
                continue
            
            # Check if market is currently tradeable
            if not market.is_tradeable():
                continue
            
            # Check if market has started
            if market.start_time > now:
                continue
            
            # Prefer market with most time remaining
            if best_market is None or market.time_remaining_seconds() > best_market.time_remaining_seconds():
                best_market = market
        
        if best_market:
            logger.info(
                f"Found active market: {best_market.slug} "
                f"({best_market.minutes_remaining():.1f} min remaining)"
            )
        
        return best_market
    
    async def refresh(self) -> Optional[Market]:
        """
        Refresh market status.
        
        Checks if current market is still active, or finds a new one.
        
        Returns:
            Current active market or None
        """
        self._last_refresh = datetime.now(timezone.utc)
        
        # Check if current market has ended
        if self._current_market:
            if self._current_market.time_remaining_seconds() <= 0:
                logger.info(f"Market {self._current_market.slug} has ended")
                
                # Mark as processed
                self._market_history.append(self._current_market.slug)
                
                # Trigger callbacks
                for callback in self._on_market_end_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(self._current_market)
                        else:
                            callback(self._current_market)
                    except Exception as e:
                        logger.error(f"Market end callback error: {e}")
                
                self._current_market = None
        
        # Find new market if needed
        if self._current_market is None:
            new_market = await self.find_active_market()
            
            if new_market:
                self._current_market = new_market
                
                # Trigger callbacks
                for callback in self._on_new_market_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(new_market)
                        else:
                            callback(new_market)
                    except Exception as e:
                        logger.error(f"New market callback error: {e}")
        
        return self._current_market
    
    def on_new_market(self, callback: callable):
        """Register callback for new market discovery."""
        self._on_new_market_callbacks.append(callback)
    
    def on_market_end(self, callback: callable):
        """Register callback for market end."""
        self._on_market_end_callbacks.append(callback)
    
    @property
    def current_market(self) -> Optional[Market]:
        """Get current market."""
        return self._current_market
    
    async def run_loop(self):
        """
        Main loop - continuously searches for markets.
        """
        self._running = True
        logger.info("Market finder started")
        
        while self._running:
            try:
                await self.refresh()
                
                # Adjust sleep based on market state
                if self._current_market:
                    remaining = self._current_market.time_remaining_seconds()
                    
                    if remaining < 60:
                        # Market ending soon - check frequently
                        await asyncio.sleep(5)
                    elif remaining < 300:
                        # Less than 5 min - moderate frequency
                        await asyncio.sleep(15)
                    else:
                        await asyncio.sleep(self.refresh_interval)
                else:
                    # No active market - search more frequently
                    await asyncio.sleep(10)
                    
            except asyncio.CancelledError:
                logger.info("Market finder cancelled")
                break
            except Exception as e:
                logger.error(f"Market finder error: {e}")
                await asyncio.sleep(self.retry_delay)
        
        # Cleanup
        if self._session and not self._session.closed:
            await self._session.close()
        
        logger.info("Market finder stopped")
    
    def stop(self):
        """Stop the market finder."""
        self._running = False
    
    async def close(self):
        """Close resources."""
        self.stop()
        if self._session and not self._session.closed:
            await self._session.close()
