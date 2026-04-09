"""Telegram Bot for Alerts

Sends trading alerts via Telegram.
"""

import logging
import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for sending alerts"""
    
    def __init__(
        self,
        bot_token: str,
        chat_ids: List[str],
        rate_limit: int = 10,  # messages per hour
        rate_window: int = 3600  # seconds
    ):
        """Initialize Telegram bot
        
        Args:
            bot_token: Telegram bot token
            chat_ids: List of authorized chat IDs
            rate_limit: Maximum messages per window
            rate_window: Time window in seconds
        """
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.rate_limit = rate_limit
        self.rate_window = rate_window
        
        # Rate limiting
        self._message_times: deque = deque()
        
        # Mock mode for testing
        self._mock_mode = False
        self._sent_messages: List[str] = []
        
    def enable_mock_mode(self):
        """Enable mock mode for testing"""
        self._mock_mode = True
        
    async def send_alert(self, message: str, priority: str = "normal"):
        """Send alert message
        
        Args:
            message: Alert message
            priority: Priority level (normal, high, critical)
        """
        # Check rate limit (except for critical alerts)
        if priority != "critical" and not self._check_rate_limit():
            logger.warning(f"Rate limit exceeded, dropping message: {message[:50]}...")
            return
        
        # Record message time
        self._message_times.append(datetime.now())
        
        # Mock mode
        if self._mock_mode:
            self._sent_messages.append(message)
            logger.info(f"[MOCK] Telegram alert: {message}")
            return
        
        # Send to all chat IDs
        for chat_id in self.chat_ids:
            try:
                await self._send_message(chat_id, message)
                logger.info(f"Telegram alert sent to {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
                
    async def _send_message(self, chat_id: str, message: str):
        """Send message via Telegram API
        
        Args:
            chat_id: Chat ID
            message: Message text
        """
        # In real implementation, use python-telegram-bot library
        # For now, just simulate
        await asyncio.sleep(0.1)  # Simulate API call
        
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows sending
        
        Returns:
            True if can send
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.rate_window)
        
        # Remove old messages
        while self._message_times and self._message_times[0] < cutoff:
            self._message_times.popleft()
        
        # Check limit
        return len(self._message_times) < self.rate_limit
        
    def get_sent_messages(self) -> List[str]:
        """Get sent messages (mock mode only)"""
        return self._sent_messages.copy()
        
    def clear_sent_messages(self):
        """Clear sent messages (mock mode only)"""
        self._sent_messages.clear()
