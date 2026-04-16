#!/usr/bin/env python3
"""
Telegram Notifier

Sends notifications and charts to Telegram.

Features:
- Async message sending
- Rate limiting
- Equity curve chart generation
- Message queue with retry
"""

import asyncio
import io
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from queue import Queue, Empty
from threading import Thread

import aiohttp

logger = logging.getLogger("btc_live.telegram")


class TelegramNotifier:
    """
    Async Telegram notification sender.
    
    Features:
    - Non-blocking message sending
    - Rate limiting (5 msg/sec max)
    - Image/chart sending
    - Graceful error handling
    """
    
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        rate_limit: float = 5.0,
        enabled: bool = True
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.rate_limit = rate_limit
        self.min_interval = 1.0 / rate_limit
        self.enabled = enabled and bool(bot_token and chat_id)
        
        self._last_send_time = 0.0
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Stats
        self.messages_sent = 0
        self.errors_count = 0
        
        if not self.enabled:
            logger.warning("Telegram notifications disabled")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def _rate_limit(self):
        """Apply rate limiting."""
        import time
        now = time.time()
        elapsed = now - self._last_send_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self._last_send_time = time.time()
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML"
    ) -> bool:
        """
        Send a text message.
        
        Args:
            text: Message text
            parse_mode: "HTML" or "Markdown"
        
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, would send: {text[:50]}...")
            return True
        
        await self._rate_limit()
        
        try:
            session = await self._get_session()
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    self.messages_sent += 1
                    logger.debug(f"Telegram sent: {text[:50]}...")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Telegram error {resp.status}: {error}")
                    self.errors_count += 1
                    return False
                    
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            self.errors_count += 1
            return False
    
    async def send_photo(
        self,
        photo: bytes,
        caption: str = ""
    ) -> bool:
        """
        Send a photo.
        
        Args:
            photo: Photo bytes
            caption: Optional caption
        
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return True
        
        await self._rate_limit()
        
        try:
            session = await self._get_session()
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            
            data = aiohttp.FormData()
            data.add_field('chat_id', self.chat_id)
            data.add_field('photo', photo, filename='chart.png')
            if caption:
                data.add_field('caption', caption)
            
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.messages_sent += 1
                    logger.debug("Telegram photo sent")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Telegram photo error {resp.status}: {error}")
                    self.errors_count += 1
                    return False
                    
        except Exception as e:
            logger.error(f"Telegram photo error: {e}")
            self.errors_count += 1
            return False
    
    async def notify_entry(
        self,
        side: str,
        price: float,
        contracts: int,
        cost: float,
        retries: int,
        interval_minutes: int = 15,
        simulation: bool = False,
    ):
        """Send entry notification."""
        mode = "🎮 <b>[SIMULATION]</b>\n" if simulation else ""
        text = (
            f"{mode}"
            f"🟢 <b>ENTRY</b>\n"
            f"📊 BTC {interval_minutes}min - {side}\n"
            f"💰 ${cost:.2f} @ {price:.2f}\n"
            f"📦 {contracts} contracts\n"
            f"🔄 {retries} retries"
        )
        await self.send_message(text)
    
    async def notify_hedge(
        self,
        contracts: int,
        price: float,
        cost: float
    ):
        """Send hedge notification."""
        text = (
            f"🛡 <b>HEDGE</b>\n"
            f"📦 {contracts} contracts @ ${price:.3f}\n"
            f"💰 Cost: ${cost:.2f}\n"
            f"✅ Position protected"
        )
        await self.send_message(text)
    
    async def notify_market_end(
        self,
        winner: str,
        pnl: float,
        total_pnl: float,
        win_rate: float
    ):
        """Send market end notification."""
        emoji = "🎯" if pnl > 0 else "❌"
        pnl_sign = "+" if pnl > 0 else ""
        
        text = (
            f"🏁 <b>MARKET RESOLVED</b>\n"
            f"{emoji} Winner: <b>{winner}</b>\n"
            f"💵 P&L: {pnl_sign}${pnl:.2f}\n"
            f"📈 Total: ${total_pnl:.2f}\n"
            f"📊 Win rate: {win_rate:.1%}"
        )
        await self.send_message(text)
    
    async def send_equity_chart(
        self,
        equity_curve: List[float],
        title: str = "Equity Curve"
    ):
        """
        Generate and send equity curve chart.
        
        Args:
            equity_curve: List of equity values
            title: Chart title
        """
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Plot equity curve
            ax.plot(equity_curve, linewidth=2, color='#2196F3')
            ax.fill_between(
                range(len(equity_curve)),
                equity_curve,
                alpha=0.3,
                color='#2196F3'
            )
            
            # Styling
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel('Trade #', fontsize=12)
            ax.set_ylabel('Equity ($)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            
            # Add current value annotation
            if equity_curve:
                final_value = equity_curve[-1]
                ax.annotate(
                    f'${final_value:.2f}',
                    xy=(len(equity_curve)-1, final_value),
                    fontsize=11,
                    fontweight='bold'
                )
            
            plt.tight_layout()
            
            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            plt.close(fig)
            
            # Send
            caption = f"📊 {title}\nTrades: {len(equity_curve)-1} | Final: ${equity_curve[-1]:.2f}"
            await self.send_photo(buf.getvalue(), caption)
            
        except ImportError:
            logger.warning("matplotlib not available for charts")
        except Exception as e:
            logger.error(f"Chart generation error: {e}")
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def get_stats(self) -> Dict:
        """Get notifier statistics."""
        return {
            "enabled": self.enabled,
            "messages_sent": self.messages_sent,
            "errors_count": self.errors_count
        }
