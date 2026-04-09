"""
Telegram Bot - Alert system và command interface

Gửi alerts và xử lý commands từ user.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Callable
from collections import deque
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from .metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class AlertRateLimiter:
    """Rate limiter for alerts"""
    
    def __init__(self, max_alerts: int = 10, window_seconds: int = 3600):
        """
        Initialize rate limiter
        
        Args:
            max_alerts: Maximum alerts per window (default: 10)
            window_seconds: Time window in seconds (default: 3600 = 1 hour)
        """
        self.max_alerts = max_alerts
        self.window_seconds = window_seconds
        self.alert_timestamps: deque = deque(maxlen=max_alerts)
    
    def can_send_alert(self) -> bool:
        """Check if can send alert"""
        now = datetime.now()
        
        # Remove old timestamps outside window
        while self.alert_timestamps and \
              (now - self.alert_timestamps[0]).total_seconds() > self.window_seconds:
            self.alert_timestamps.popleft()
        
        # Check if under limit
        return len(self.alert_timestamps) < self.max_alerts
    
    def record_alert(self) -> None:
        """Record alert sent"""
        self.alert_timestamps.append(datetime.now())
    
    def get_remaining_quota(self) -> int:
        """Get remaining alert quota"""
        now = datetime.now()
        
        # Remove old timestamps
        while self.alert_timestamps and \
              (now - self.alert_timestamps[0]).total_seconds() > self.window_seconds:
            self.alert_timestamps.popleft()
        
        return self.max_alerts - len(self.alert_timestamps)


class TelegramBot:
    """
    Telegram Bot for Alerts and Commands
    
    Features:
    - Send trade alerts (order states: pending, filled, cancelled, rejected)
    - Rate limit alerts to 10/hour
    - Respond to /status command (system status)
    - Respond to /positions command (open positions)
    - Respond to /pnl command (P&L summary)
    - Authenticate users by chat_id
    """
    
    def __init__(
        self,
        bot_token: str,
        allowed_chat_ids: List[int],
        metrics_collector: MetricsCollector,
        max_alerts_per_hour: int = 10
    ):
        """
        Initialize Telegram Bot
        
        Args:
            bot_token: Telegram bot token from BotFather
            allowed_chat_ids: List of allowed chat IDs
            metrics_collector: MetricsCollector instance
            max_alerts_per_hour: Maximum alerts per hour (default: 10)
        """
        self.bot_token = bot_token
        self.allowed_chat_ids = set(allowed_chat_ids)
        self.metrics_collector = metrics_collector
        
        # Rate limiter
        self.rate_limiter = AlertRateLimiter(
            max_alerts=max_alerts_per_hour,
            window_seconds=3600
        )
        
        # Application
        self.application: Optional[Application] = None
        
        logger.info(
            f"TelegramBot initialized with {len(allowed_chat_ids)} allowed chat IDs"
        )
    
    async def start(self) -> None:
        """Start Telegram bot"""
        # Create application
        self.application = Application.builder().token(self.bot_token).build()
        
        # Register command handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("status", self._handle_status))
        self.application.add_handler(CommandHandler("positions", self._handle_positions))
        self.application.add_handler(CommandHandler("pnl", self._handle_pnl))
        self.application.add_handler(CommandHandler("start_trading", self._handle_start_trading))
        self.application.add_handler(CommandHandler("stop_trading", self._handle_stop_trading))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        
        # Start bot
        await self.application.initialize()
        await self.application.start()
        
        # Set bot commands menu (for / autocomplete)
        from telegram import BotCommand
        commands = [
            BotCommand("start", "Start bot and show welcome message"),
            BotCommand("status", "System status and health"),
            BotCommand("positions", "Open positions and unrealized P&L"),
            BotCommand("pnl", "P&L summary and performance"),
            BotCommand("start_trading", "Start paper trading bot"),
            BotCommand("stop_trading", "Stop trading bot"),
            BotCommand("help", "Show help message")
        ]
        await self.application.bot.set_my_commands(commands)
        
        await self.application.updater.start_polling()
        
        logger.info("Telegram bot started with commands menu")
    
    async def stop(self) -> None:
        """Stop Telegram bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        logger.info("Telegram bot stopped")
    
    def _is_authorized(self, chat_id: int) -> bool:
        """Check if chat_id is authorized"""
        return chat_id in self.allowed_chat_ids
    
    async def _handle_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text(
                "❌ Unauthorized. Your chat ID is not in the allowed list.\n"
                f"Your chat ID: {chat_id}"
            )
            logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
            return
        
        await update.message.reply_text(
            "🤖 Trading Bot Active\n\n"
            "Available commands:\n"
            "/status - System status and health\n"
            "/positions - Open positions\n"
            "/pnl - P&L summary\n"
            "/start_trading - Start paper trading\n"
            "/stop_trading - Stop trading\n"
            "/help - Show this help message"
        )
    
    async def _handle_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /status command"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        # Get system status
        status = self.metrics_collector.get_system_status()
        
        if status.get("status") == "unknown":
            await update.message.reply_text("⚠️ System status unknown")
            return
        
        # Format message
        status_emoji = "✅" if status["status"] == "healthy" else "⚠️"
        api_emoji = "🟢" if status["api_status"] == "healthy" else "🔴"
        db_emoji = "🟢" if status["db_status"] == "healthy" else "🔴"
        
        message = (
            f"{status_emoji} *System Status*\n\n"
            f"{api_emoji} API: {status['api_status']}\n"
            f"{db_emoji} Database: {status['db_status']}\n"
            f"📊 Error Rate: {status['error_rate']:.2f}%\n"
            f"⏱ Uptime: {status['uptime_hours']:.1f} hours\n"
            f"📈 Total Requests: {status['total_requests']:,}\n"
            f"❌ Failed Requests: {status['failed_requests']:,}\n"
        )
        
        if status["last_tick"]:
            last_tick = datetime.fromisoformat(status["last_tick"])
            seconds_ago = (datetime.now() - last_tick).total_seconds()
            message += f"🕐 Last Tick: {seconds_ago:.0f}s ago\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    async def _handle_positions(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /positions command"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        # Get trading metrics
        metrics = self.metrics_collector.get_trading_summary()
        
        if metrics.get("status") == "no_data":
            await update.message.reply_text("📊 No trading data available")
            return
        
        # Format message
        message = (
            f"📊 *Open Positions*\n\n"
            f"Count: {metrics['open_positions']}\n"
            f"Unrealized P&L: ${metrics['unrealized_pnl']:,.2f}\n\n"
            f"💰 *Account*\n"
            f"Balance: ${metrics['current_balance']:,.2f}\n"
            f"Equity: ${metrics['equity']:,.2f}\n"
            f"Total P&L: ${metrics['total_pnl']:,.2f}\n"
        )
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    async def _handle_pnl(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /pnl command"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        # Get trading metrics
        metrics = self.metrics_collector.get_trading_summary()
        
        if metrics.get("status") == "no_data":
            await update.message.reply_text("📊 No trading data available")
            return
        
        # Format message
        total_pnl_emoji = "🟢" if metrics['total_pnl'] >= 0 else "🔴"
        realized_pnl_emoji = "🟢" if metrics['realized_pnl'] >= 0 else "🔴"
        unrealized_pnl_emoji = "🟢" if metrics['unrealized_pnl'] >= 0 else "🔴"
        
        message = (
            f"💰 *P&L Summary*\n\n"
            f"{total_pnl_emoji} Total P&L: ${metrics['total_pnl']:,.2f}\n"
            f"{realized_pnl_emoji} Realized: ${metrics['realized_pnl']:,.2f}\n"
            f"{unrealized_pnl_emoji} Unrealized: ${metrics['unrealized_pnl']:,.2f}\n\n"
            f"📈 *Performance*\n"
            f"Total Return: {metrics['total_return']:.2f}%\n"
            f"Win Rate: {metrics['win_rate']:.1f}%\n"
            f"Total Trades: {metrics['total_trades']}\n"
            f"Winning: {metrics['winning_trades']} | Losing: {metrics['losing_trades']}\n"
        )
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    async def _handle_help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /help command"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        message = (
            "🤖 *Trading Bot Commands*\n\n"
            "/status - System status and connection health\n"
            "/positions - Open positions and unrealized P&L\n"
            "/pnl - Daily, weekly, and total P&L\n"
            "/start_trading - Start paper trading bot\n"
            "/stop_trading - Stop trading bot\n"
            "/help - Show this help message\n\n"
            "📢 *Alerts*\n"
            "You will receive alerts for:\n"
            "• Order pending\n"
            "• Order filled\n"
            "• Order cancelled\n"
            "• Order rejected\n"
            "• Kill switch activation\n\n"
            "⚠️ Alerts are rate-limited to 10 per hour"
        )
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    async def _handle_start_trading(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start_trading command"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        await update.message.reply_text(
            "🚀 *Starting Paper Trading Bot*\n\n"
            "Please wait...",
            parse_mode="Markdown"
        )
        
        try:
            import subprocess
            # Start trading bot in background
            result = subprocess.run(
                ["docker", "compose", "exec", "-d", "trading_bot", 
                 "python", "scripts/run_paper_trading.py"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                await update.message.reply_text(
                    "✅ *Trading Bot Started*\n\n"
                    "Mode: Paper Trading\n"
                    "Status: Running\n\n"
                    "📊 Check dashboard: http://localhost:8501\n"
                    "📱 You will receive trade alerts here",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"❌ *Failed to start trading bot*\n\n"
                    f"Error: {result.stderr}",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error starting trading bot: {e}")
            await update.message.reply_text(
                f"❌ *Error*\n\n{str(e)}",
                parse_mode="Markdown"
            )
    
    async def _handle_stop_trading(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /stop_trading command"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        await update.message.reply_text(
            "🛑 *Stopping Trading Bot*\n\n"
            "Please wait...",
            parse_mode="Markdown"
        )
        
        try:
            import subprocess
            # Stop trading bot
            result = subprocess.run(
                ["docker", "compose", "exec", "trading_bot", 
                 "pkill", "-f", "run_paper_trading.py"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            await update.message.reply_text(
                "✅ *Trading Bot Stopped*\n\n"
                "All positions closed (paper trading)\n"
                "No real money affected",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error stopping trading bot: {e}")
            await update.message.reply_text(
                f"❌ *Error*\n\n{str(e)}",
                parse_mode="Markdown"
            )
    
    async def send_alert(
        self,
        message: str,
        priority: str = "normal"
    ) -> bool:
        """
        Send alert to all allowed chat IDs
        
        Args:
            message: Alert message
            priority: Alert priority ("normal", "high", "critical")
        
        Returns:
            True if sent successfully, False if rate limited
        """
        # Check rate limit (skip for critical alerts)
        if priority != "critical" and not self.rate_limiter.can_send_alert():
            logger.warning(
                f"Alert rate limit exceeded. Remaining quota: "
                f"{self.rate_limiter.get_remaining_quota()}"
            )
            return False
        
        # Format message with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Send to all allowed chat IDs
        if not self.application:
            logger.error("Telegram bot not started")
            return False
        
        success = True
        for chat_id in self.allowed_chat_ids:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=formatted_message,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send alert to {chat_id}: {e}")
                success = False
        
        # Record alert
        if priority != "critical":
            self.rate_limiter.record_alert()
        
        logger.info(f"Alert sent: {message} (priority: {priority})")
        return success
    
    async def send_order_alert(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        state: str
    ) -> bool:
        """
        Send order state alert
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            price: Order price
            state: Order state (PENDING, FILLED, CANCELLED, REJECTED)
        
        Returns:
            True if sent successfully
        """
        # Emoji based on state
        state_emojis = {
            "PENDING": "⏳",
            "FILLED": "✅",
            "CANCELLED": "❌",
            "REJECTED": "🚫"
        }
        
        emoji = state_emojis.get(state, "📝")
        
        message = (
            f"{emoji} *Order {state}*\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Quantity: {quantity}\n"
            f"Price: ${price:,.2f}"
        )
        
        # Determine priority
        priority = "high" if state in ["FILLED", "REJECTED"] else "normal"
        
        return await self.send_alert(message, priority=priority)
    
    async def send_kill_switch_alert(self, reason: str) -> bool:
        """
        Send kill switch activation alert
        
        Args:
            reason: Activation reason
        
        Returns:
            True if sent successfully
        """
        message = (
            f"🚨 *KILL SWITCH ACTIVATED* 🚨\n\n"
            f"Reason: {reason}\n"
            f"All trading stopped.\n"
            f"Manual reset required."
        )
        
        return await self.send_alert(message, priority="critical")
    
    def get_rate_limit_status(self) -> Dict:
        """Get rate limit status"""
        return {
            "max_alerts": self.rate_limiter.max_alerts,
            "window_seconds": self.rate_limiter.window_seconds,
            "remaining_quota": self.rate_limiter.get_remaining_quota(),
            "alerts_sent": len(self.rate_limiter.alert_timestamps)
        }



if __name__ == "__main__":
    """Run Telegram bot standalone"""
    import os
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Get configuration from environment
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_ids_str = os.getenv('TELEGRAM_CHAT_IDS', '')
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment")
        exit(1)
    
    if not chat_ids_str:
        logger.error("TELEGRAM_CHAT_IDS not found in environment")
        exit(1)
    
    # Parse chat IDs
    try:
        chat_ids = [int(id.strip()) for id in chat_ids_str.split(',') if id.strip()]
    except ValueError:
        logger.error("Invalid TELEGRAM_CHAT_IDS format. Use comma-separated integers.")
        exit(1)
    
    if not chat_ids:
        logger.error("No valid chat IDs found")
        exit(1)
    
    logger.info(f"Starting Telegram bot with {len(chat_ids)} allowed chat IDs")
    
    # Create metrics collector (mock for standalone)
    metrics_collector = MetricsCollector()
    
    # Create and start bot
    bot = TelegramBot(
        bot_token=bot_token,
        allowed_chat_ids=chat_ids,
        metrics_collector=metrics_collector
    )
    
    async def run():
        try:
            await bot.start()
            logger.info("Telegram bot is running. Press Ctrl+C to stop.")
            # Keep running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await bot.stop()
    
    asyncio.run(run())
