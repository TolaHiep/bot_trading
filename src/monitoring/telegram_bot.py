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
        self.application.add_handler(CommandHandler("scalp", self._handle_scalp))
        self.application.add_handler(CommandHandler("scalp_v2", self._handle_scalp_v2))
        self.application.add_handler(CommandHandler("wyckoff", self._handle_wyckoff))
        self.application.add_handler(CommandHandler("scalp_pos", self._handle_scalp_positions))
        self.application.add_handler(CommandHandler("scalp_v2_pos", self._handle_scalp_v2_positions))
        self.application.add_handler(CommandHandler("wyckoff_pos", self._handle_wyckoff_positions))
        self.application.add_handler(CommandHandler("all", self._handle_all_bots))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        
        # Start bot
        await self.application.initialize()
        await self.application.start()
        
        # Clear old commands first (to remove any stale commands)
        await self.application.bot.delete_my_commands()
        
        # Set bot commands menu (for / autocomplete)
        from telegram import BotCommand
        commands = [
            BotCommand("start", "Bắt đầu và xem hướng dẫn"),
            BotCommand("all", "Báo cáo tổng hợp cả 3 bot"),
            BotCommand("status", "Dashboard sức khỏe bot"),
            BotCommand("wyckoff", "Báo cáo bot Wyckoff"),
            BotCommand("wyckoff_pos", "Lệnh đang chạy Wyckoff"),
            BotCommand("scalp", "Báo cáo bot Scalping V1"),
            BotCommand("scalp_pos", "Lệnh đang chạy Scalp V1"),
            BotCommand("scalp_v2", "Báo cáo bot Scalping V2"),
            BotCommand("scalp_v2_pos", "Lệnh đang chạy Scalp V2"),
            BotCommand("help", "Hướng dẫn sử dụng chi tiết")
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
            "🤖 <b>Quantitative Trading Bot</b>\n\n"
            "📊 <b>Bot Commands</b>\n"
            "/all • Báo cáo tổng hợp cả 3 bot\n"
            "/wyckoff • Wyckoff strategy (Main)\n"
            "/scalp • Scalping V1 strategy\n"
            "/scalp_v2 • Scalping V2 strategy\n"
            "/status • System health\n"
            "/help • Command guide\n\n"
            "💰 <b>3 Bots Running</b>\n"
            "Each bot has separate $100 wallet\n"
            "Cross margin enabled\n\n"
            "⚡ <b>Notifications</b>\n"
            "Position opened/closed only\n"
            "No spam alerts\n\n"
            "💡 Paper trading • Real-time data",
            parse_mode="HTML"
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
        
        # Try to read from shared metrics file first
        try:
            import json
            import os
            from datetime import datetime
            
            metrics_file = "logs/metrics.json"
            if os.path.exists(metrics_file):
                with open(metrics_file, "r") as f:
                    data = json.load(f)
                
                system = data.get("system", {})
                trading = data.get("trading", {})
                market = data.get("market", {})
                multi_symbol = data.get("multi_symbol", {})
                mode = data.get("mode", "single_symbol")
                
                # Check if data is recent (within last 60 seconds)
                last_update = datetime.fromisoformat(data.get("timestamp"))
                seconds_ago = (datetime.now() - last_update).total_seconds()
                
                if seconds_ago > 60:
                    await update.message.reply_text(
                        f"⚠️ <b>Bot Status</b>\n\n"
                        f"Last update: {seconds_ago:.0f}s ago\n"
                        f"Bot might be offline or restarting",
                        parse_mode="HTML"
                    )
                    return
                
                # Format message
                uptime_hours = system.get("uptime_seconds", 0) / 3600
                
                if mode == "multi_symbol":
                    # Multi-symbol mode status
                    monitored_symbols = multi_symbol.get("monitored_symbols", 0)
                    active_symbols = multi_symbol.get("active_symbols", [])
                    
                    message = (
                        f"📊 <b>System Status</b>\n\n"
                        f"🟢 API • 🟢 DB\n"
                        f"⏱ Uptime: {uptime_hours:.1f}h\n"
                        f"🔄 Updated: {seconds_ago:.0f}s ago\n\n"
                        f"<b>Multi-Symbol Trading</b>\n"
                        f"Monitoring: {monitored_symbols} symbols\n"
                        f"Balance: <code>${trading.get('current_balance', 0):.2f}</code>\n"
                        f"Equity: <code>${trading.get('equity', 0):.2f}</code>\n"
                        f"Open: {trading.get('open_positions', 0)} positions\n"
                    )
                    
                    if active_symbols:
                        symbols_preview = ", ".join(active_symbols[:5])
                        if len(active_symbols) > 5:
                            symbols_preview += f" +{len(active_symbols)-5}"
                        message += f"\n<code>{symbols_preview}</code>"
                else:
                    # Single-symbol mode status
                    message = (
                        f"📊 <b>System Status</b>\n\n"
                        f"🟢 API • 🟢 DB\n"
                        f"⏱ Uptime: {uptime_hours:.1f}h\n"
                        f"🔄 Updated: {seconds_ago:.0f}s ago\n\n"
                        f"<b>Single-Symbol Trading</b>\n"
                        f"Symbol: <b>{market.get('symbol', 'N/A')}</b>\n"
                        f"Balance: <code>${trading.get('current_balance', 0):.2f}</code>\n"
                        f"Equity: <code>${trading.get('equity', 0):.2f}</code>\n"
                        f"Open: {trading.get('open_positions', 0)} positions\n"
                    )
                
                await update.message.reply_text(message, parse_mode="HTML")
                return
        except Exception as e:
            logger.error(f"Error reading metrics file: {e}")
        
        # Fallback to old method
        status = self.metrics_collector.get_system_status()
        
        if status.get("status") == "unknown":
            await update.message.reply_text("⚠️ System status unknown - trading bot might not be running")
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
        
        # Try to read from shared metrics file first
        try:
            import json
            import os
            
            metrics_file = "logs/metrics.json"
            if os.path.exists(metrics_file):
                with open(metrics_file, "r") as f:
                    data = json.load(f)
                
                trading = data.get("trading", {})
                mode = data.get("mode", "single_symbol")
                positions_data = data.get("positions", [])
                
                open_positions = trading.get('open_positions', 0)
                
                if open_positions == 0:
                    await update.message.reply_text("📊 <b>Open Positions</b>\n\nNo positions open", parse_mode="HTML")
                    return
                
                # Format message
                message = (
                    f"📊 <b>Open Positions</b> ({open_positions})\n"
                    f"Unrealized: <code>{trading.get('unrealized_pnl', 0):+.2f} USDT</code>\n\n"
                )
                
                # Show individual positions if available
                if positions_data:
                    for pos in positions_data[:10]:  # Limit to 10 positions
                        symbol = pos.get('symbol', 'N/A')
                        side = pos.get('side', 'N/A')
                        quantity = pos.get('quantity', 0)
                        entry_price = pos.get('entry_price', 0)
                        current_price = pos.get('current_price', entry_price)
                        unrealized_pnl = pos.get('unrealized_pnl', 0)
                        
                        pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                        pnl_pct = (unrealized_pnl / (entry_price * quantity)) * 100 if (entry_price * quantity) > 0 else 0
                        
                        message += (
                            f"{pnl_emoji} <b>{symbol}</b> {side} × {quantity:.6f}\n"
                            f"Entry: <code>${entry_price:.2f}</code> • Now: <code>${current_price:.2f}</code>\n"
                            f"P&L: <code>{unrealized_pnl:+.2f}</code> ({pnl_pct:+.2f}%)\n\n"
                        )
                    
                    if len(positions_data) > 10:
                        message += f"<i>+{len(positions_data)-10} more positions</i>\n\n"
                
                message += (
                    f"<b>Account</b>\n"
                    f"Balance: <code>${trading.get('current_balance', 0):.2f}</code>\n"
                    f"Equity: <code>${trading.get('equity', 0):.2f}</code>"
                )
                
                await update.message.reply_text(message, parse_mode="HTML")
                return
        except Exception as e:
            logger.error(f"Error reading metrics file: {e}")
        
        # Fallback to old method
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
        
        # Try to read from shared metrics file first
        try:
            import json
            import os
            
            metrics_file = "logs/metrics.json"
            if os.path.exists(metrics_file):
                with open(metrics_file, "r") as f:
                    data = json.load(f)
                
                trading = data.get("trading", {})
                
                # Format message
                total_pnl = trading.get('total_pnl', 0)
                realized_pnl = trading.get('realized_pnl', 0)
                unrealized_pnl = trading.get('unrealized_pnl', 0)
                
                total_pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
                realized_pnl_emoji = "🟢" if realized_pnl >= 0 else "🔴"
                unrealized_pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                
                total_return = (total_pnl / trading.get('initial_balance', 100)) * 100
                
                message = (
                    f"💰 <b>Performance</b>\n\n"
                    f"{total_pnl_emoji} Total: <code>{total_pnl:+.2f} USDT</code>\n"
                    f"Realized: <code>{realized_pnl:+.2f}</code>\n"
                    f"Unrealized: <code>{unrealized_pnl:+.2f}</code>\n\n"
                    f"<b>Statistics</b>\n"
                    f"Return: <code>{total_return:+.2f}%</code>\n"
                    f"Win Rate: <code>{trading.get('win_rate', 0):.1f}%</code>\n"
                    f"Trades: {trading.get('total_trades', 0)} "
                    f"({trading.get('winning_trades', 0)}W/{trading.get('losing_trades', 0)}L)"
                )
                
                await update.message.reply_text(message, parse_mode="HTML")
                return
        except Exception as e:
            logger.error(f"Error reading metrics file: {e}")
        
        # Fallback to old method
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
    
    async def _handle_scalp(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /scalp command - Show scalping V1 bot statistics"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            import json
            import os
            
            # Read metrics from scalp specific file
            metrics_file = "logs/metrics_scalp.json"
            if not os.path.exists(metrics_file):
                await update.message.reply_text(
                    "⚡ <b>Scalping V1 Strategy</b>\n\n"
                    "Status: 🔴 Not Running\n"
                    "<i>Bot chưa được khởi động</i>",
                    parse_mode="HTML"
                )
                return
            
            with open(metrics_file, "r") as f:
                data = json.load(f)
            
            account = data.get("account", {})
            stats = data.get("stats", {})
            config = data.get("config", {})
            
            # Account info
            balance = account.get("balance", 0)
            equity = account.get("equity", 0)
            realized_pnl = account.get("realized_pnl", 0)
            unrealized_pnl = account.get("unrealized_pnl", 0)
            total_pnl = realized_pnl + unrealized_pnl
            
            # Stats
            total_trades = stats.get("total_trades", 0)
            winning = stats.get("winning_trades", 0)
            losing = stats.get("losing_trades", 0)
            win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
            open_positions = stats.get("open_positions", 0)
            
            # Emojis
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            status_emoji = "🟢" if equity > 5 else "🔴"
            
            message = (
                f"⚡ <b>Scalping V1 Strategy</b>\n\n"
                f"Status: {status_emoji} Active • 1m timeframe\n"
                f"Risk: {config.get('risk_per_trade', 0.05)*100}% • "
                f"Leverage: {config.get('leverage', 20)}x\n\n"
                f"<b>Account (Cross Margin)</b>\n"
                f"Balance: <code>${balance:.2f}</code>\n"
                f"Equity: <code>${equity:.2f}</code>\n"
                f"{pnl_emoji} Total P&L: <code>{total_pnl:+.2f}</code>\n"
                f"Realized: <code>{realized_pnl:+.2f}</code> • "
                f"Unrealized: <code>{unrealized_pnl:+.2f}</code>\n\n"
                f"<b>Performance</b>\n"
                f"Trades: {total_trades} ({winning}W/{losing}L)\n"
                f"Win Rate: <code>{win_rate:.1f}%</code>\n"
                f"Open: {open_positions} positions"
            )
            
            await update.message.reply_text(message, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in /scalp command: {e}")
            await update.message.reply_text(f"⚠️ Lỗi: {e}")
    
    async def _handle_scalp_v2(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /scalp_v2 command - Show scalping V2 bot statistics"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            import json
            import os
            
            # Read metrics from scalp_v2 specific file
            metrics_file = "logs/metrics_scalp_v2.json"
            if not os.path.exists(metrics_file):
                await update.message.reply_text(
                    "⚡ <b>Scalping V2 Strategy</b>\n\n"
                    "Status: 🔴 Not Running\n"
                    "<i>Bot chưa được khởi động</i>",
                    parse_mode="HTML"
                )
                return
            
            with open(metrics_file, "r") as f:
                data = json.load(f)
            
            account = data.get("account", {})
            stats = data.get("stats", {})
            config = data.get("config", {})
            
            # Account info
            balance = account.get("balance", 0)
            equity = account.get("equity", 0)
            realized_pnl = account.get("realized_pnl", 0)
            unrealized_pnl = account.get("unrealized_pnl", 0)
            total_pnl = realized_pnl + unrealized_pnl
            
            # Stats
            total_trades = stats.get("total_trades", 0)
            winning = stats.get("winning_trades", 0)
            losing = stats.get("losing_trades", 0)
            win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
            open_positions = stats.get("open_positions", 0)
            
            # Emojis
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            status_emoji = "🟢" if equity > 5 else "🔴"
            
            message = (
                f"⚡ <b>Scalping V2 Strategy</b>\n\n"
                f"Status: {status_emoji} Active • 1m timeframe\n"
                f"Risk: {config.get('risk_per_trade', 0.025)*100}% • "
                f"Leverage: {config.get('leverage', 12)}x\n"
                f"TP: {config.get('tp1_pct', 0.004)*100}%/{config.get('tp2_pct', 0.008)*100}% • "
                f"SL: {config.get('sl_method', 'atr')}\n\n"
                f"<b>Account (Cross Margin)</b>\n"
                f"Balance: <code>${balance:.2f}</code>\n"
                f"Equity: <code>${equity:.2f}</code>\n"
                f"{pnl_emoji} Total P&L: <code>{total_pnl:+.2f}</code>\n"
                f"Realized: <code>{realized_pnl:+.2f}</code> • "
                f"Unrealized: <code>{unrealized_pnl:+.2f}</code>\n\n"
                f"<b>Performance</b>\n"
                f"Trades: {total_trades} ({winning}W/{losing}L)\n"
                f"Win Rate: <code>{win_rate:.1f}%</code>\n"
                f"Open: {open_positions} positions"
            )
            
            await update.message.reply_text(message, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in /scalp_v2 command: {e}")
            await update.message.reply_text(f"⚠️ Lỗi: {e}")
    
    async def _handle_wyckoff(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /wyckoff command - Show main strategy (Wyckoff) statistics"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            import json
            import os
            
            # Read metrics from wyckoff specific file
            metrics_file = "logs/metrics_wyckoff.json"
            if not os.path.exists(metrics_file):
                await update.message.reply_text(
                    "📊 <b>Wyckoff Strategy</b>\n\n"
                    "Status: 🔴 Not Running\n"
                    "<i>Bot chưa được khởi động</i>",
                    parse_mode="HTML"
                )
                return
            
            with open(metrics_file, "r") as f:
                data = json.load(f)
            
            account = data.get("account", {})
            stats = data.get("stats", {})
            config = data.get("config", {})
            
            # Account info
            balance = account.get("balance", 0)
            equity = account.get("equity", 0)
            realized_pnl = account.get("realized_pnl", 0)
            unrealized_pnl = account.get("unrealized_pnl", 0)
            total_pnl = realized_pnl + unrealized_pnl
            
            # Stats
            total_trades = stats.get("total_trades", 0)
            winning = stats.get("winning_trades", 0)
            losing = stats.get("losing_trades", 0)
            win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
            open_positions = stats.get("open_positions", 0)
            monitored_symbols = stats.get("monitored_symbols", 0)
            
            # Emojis
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            status_emoji = "🟢" if equity > 5 else "🔴"
            
            mode = config.get("mode", "multi_symbol")
            mode_text = "Multi-Symbol" if mode == "multi_symbol" else "Single-Symbol"
            
            message = (
                f"📊 <b>Wyckoff Strategy</b> (Main)\n\n"
                f"Status: {status_emoji} Active • {mode_text}\n"
                f"Timeframes: 5m, 15m, 1h\n"
                f"Monitoring: {monitored_symbols} symbols\n\n"
                f"<b>Account (Cross Margin)</b>\n"
                f"Balance: <code>${balance:.2f}</code>\n"
                f"Equity: <code>${equity:.2f}</code>\n"
                f"{pnl_emoji} Total P&L: <code>{total_pnl:+.2f}</code>\n"
                f"Realized: <code>{realized_pnl:+.2f}</code> • "
                f"Unrealized: <code>{unrealized_pnl:+.2f}</code>\n\n"
                f"<b>Performance</b>\n"
                f"Trades: {total_trades} ({winning}W/{losing}L)\n"
                f"Win Rate: <code>{win_rate:.1f}%</code>\n"
                f"Open: {open_positions} positions"
            )
            
            await update.message.reply_text(message, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in /wyckoff command: {e}")
            await update.message.reply_text(f"⚠️ Lỗi: {e}")
    
    async def _handle_scalp_positions(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /scalp_pos command - Show Scalp V1 open positions"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            import json
            import os
            
            # Read positions from scalp specific file
            metrics_file = "logs/metrics_scalp_positions.json"
            if not os.path.exists(metrics_file):
                await update.message.reply_text(
                    "⚡ <b>Scalp V1 Positions</b>\n\n"
                    "No open positions",
                    parse_mode="HTML"
                )
                return
            
            with open(metrics_file, "r") as f:
                data = json.load(f)
            
            positions = data.get("positions", [])
            account = data.get("account", {})
            
            if not positions:
                await update.message.reply_text(
                    "⚡ <b>Scalp V1 Positions</b>\n\n"
                    "No open positions",
                    parse_mode="HTML"
                )
                return
            
            # Build message
            message = f"⚡ <b>Scalp V1 Open Positions</b> ({len(positions)})\n\n"
            
            for pos in positions[:10]:  # Limit to 10
                symbol = pos.get("symbol", "N/A")
                side = pos.get("side", "N/A")
                entry_price = pos.get("entry_price", 0)
                current_price = pos.get("current_price", entry_price)
                quantity = pos.get("quantity", 0)
                unrealized_pnl = pos.get("unrealized_pnl", 0)
                
                pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                pnl_pct = (unrealized_pnl / (entry_price * quantity)) * 100 if (entry_price * quantity) > 0 else 0
                
                message += (
                    f"{pnl_emoji} <b>{symbol}</b> {side}\n"
                    f"Entry: <code>${entry_price:.4f}</code> • Now: <code>${current_price:.4f}</code>\n"
                    f"Qty: {quantity:.6f} • P&L: <code>{unrealized_pnl:+.2f}</code> ({pnl_pct:+.2f}%)\n\n"
                )
            
            if len(positions) > 10:
                message += f"<i>+{len(positions)-10} more positions</i>\n\n"
            
            message += (
                f"<b>Account</b>\n"
                f"Balance: <code>${account.get('balance', 0):.2f}</code>\n"
                f"Equity: <code>${account.get('equity', 0):.2f}</code>\n"
                f"Unrealized: <code>{account.get('unrealized_pnl', 0):+.2f}</code>"
            )
            
            await update.message.reply_text(message, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in /scalp_pos command: {e}")
            await update.message.reply_text(f"⚠️ Lỗi: {e}")
    
    async def _handle_scalp_v2_positions(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /scalp_v2_pos command - Show Scalp V2 open positions"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            import json
            import os
            
            # Read positions from scalp_v2 specific file
            metrics_file = "logs/metrics_scalp_v2_positions.json"
            if not os.path.exists(metrics_file):
                await update.message.reply_text(
                    "⚡ <b>Scalp V2 Positions</b>\n\n"
                    "No open positions",
                    parse_mode="HTML"
                )
                return
            
            with open(metrics_file, "r") as f:
                data = json.load(f)
            
            positions = data.get("positions", [])
            account = data.get("account", {})
            targets = data.get("targets", {})
            
            if not positions:
                await update.message.reply_text(
                    "⚡ <b>Scalp V2 Positions</b>\n\n"
                    "No open positions",
                    parse_mode="HTML"
                )
                return
            
            # Build message
            message = f"⚡ <b>Scalp V2 Open Positions</b> ({len(positions)})\n\n"
            
            for pos in positions[:10]:  # Limit to 10
                symbol = pos.get("symbol", "N/A")
                side = pos.get("side", "N/A")
                entry_price = pos.get("entry_price", 0)
                current_price = pos.get("current_price", entry_price)
                quantity = pos.get("quantity", 0)
                unrealized_pnl = pos.get("unrealized_pnl", 0)
                
                # Get targets for this symbol
                target = targets.get(symbol, {})
                sl = target.get("stop_loss", 0)
                tp1 = target.get("take_profit1", 0)
                tp2 = target.get("take_profit2", 0)
                
                pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                pnl_pct = (unrealized_pnl / (entry_price * quantity)) * 100 if (entry_price * quantity) > 0 else 0
                
                message += (
                    f"{pnl_emoji} <b>{symbol}</b> {side}\n"
                    f"Entry: <code>${entry_price:.4f}</code> • Now: <code>${current_price:.4f}</code>\n"
                    f"Qty: {quantity:.6f} • P&L: <code>{unrealized_pnl:+.2f}</code> ({pnl_pct:+.2f}%)\n"
                )
                
                if sl > 0:
                    message += f"SL: <code>${sl:.4f}</code> • TP1: <code>${tp1:.4f}</code> • TP2: <code>${tp2:.4f}</code>\n"
                
                message += "\n"
            
            if len(positions) > 10:
                message += f"<i>+{len(positions)-10} more positions</i>\n\n"
            
            message += (
                f"<b>Account</b>\n"
                f"Balance: <code>${account.get('balance', 0):.2f}</code>\n"
                f"Equity: <code>${account.get('equity', 0):.2f}</code>\n"
                f"Unrealized: <code>{account.get('unrealized_pnl', 0):+.2f}</code>"
            )
            
            await update.message.reply_text(message, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in /scalp_v2_pos command: {e}")
            await update.message.reply_text(f"⚠️ Lỗi: {e}")
    
    async def _handle_wyckoff_positions(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /wyckoff_pos command - Show Wyckoff open positions"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            import json
            import os
            
            # Read positions from wyckoff specific file
            metrics_file = "logs/metrics_wyckoff_positions.json"
            if not os.path.exists(metrics_file):
                await update.message.reply_text(
                    "📊 <b>Wyckoff Positions</b>\n\n"
                    "No open positions",
                    parse_mode="HTML"
                )
                return
            
            with open(metrics_file, "r") as f:
                data = json.load(f)
            
            positions = data.get("positions", [])
            account = data.get("account", {})
            
            if not positions:
                await update.message.reply_text(
                    "📊 <b>Wyckoff Positions</b>\n\n"
                    "No open positions",
                    parse_mode="HTML"
                )
                return
            
            # Build message
            message = f"📊 <b>Wyckoff Open Positions</b> ({len(positions)})\n\n"
            
            for pos in positions[:10]:  # Limit to 10
                symbol = pos.get("symbol", "N/A")
                side = pos.get("side", "N/A")
                entry_price = pos.get("entry_price", 0)
                current_price = pos.get("current_price", entry_price)
                quantity = pos.get("quantity", 0)
                unrealized_pnl = pos.get("unrealized_pnl", 0)
                
                pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                pnl_pct = (unrealized_pnl / (entry_price * quantity)) * 100 if (entry_price * quantity) > 0 else 0
                
                message += (
                    f"{pnl_emoji} <b>{symbol}</b> {side}\n"
                    f"Entry: <code>${entry_price:.4f}</code> • Now: <code>${current_price:.4f}</code>\n"
                    f"Qty: {quantity:.6f} • P&L: <code>{unrealized_pnl:+.2f}</code> ({pnl_pct:+.2f}%)\n\n"
                )
            
            if len(positions) > 10:
                message += f"<i>+{len(positions)-10} more positions</i>\n\n"
            
            message += (
                f"<b>Account</b>\n"
                f"Balance: <code>${account.get('balance', 0):.2f}</code>\n"
                f"Equity: <code>${account.get('equity', 0):.2f}</code>\n"
                f"Unrealized: <code>{account.get('unrealized_pnl', 0):+.2f}</code>"
            )
            
            await update.message.reply_text(message, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in /wyckoff_pos command: {e}")
            await update.message.reply_text(f"⚠️ Lỗi: {e}")
    
    async def _handle_all_bots(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /all command - Show summary of all 3 bots"""
        chat_id = update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            await update.message.reply_text("❌ Unauthorized")
            return
        
        try:
            import json
            import os
            
            # Read all bot metrics
            wyckoff_file = "logs/metrics_wyckoff.json"
            scalp_file = "logs/metrics_scalp.json"
            scalp_v2_file = "logs/metrics_scalp_v2.json"
            
            bots_data = []
            
            # Wyckoff
            if os.path.exists(wyckoff_file):
                with open(wyckoff_file, "r") as f:
                    wyckoff_data = json.load(f)
                    bots_data.append(("📊 Wyckoff", wyckoff_data))
            
            # Scalp V1
            if os.path.exists(scalp_file):
                with open(scalp_file, "r") as f:
                    scalp_data = json.load(f)
                    bots_data.append(("⚡ Scalp V1", scalp_data))
            
            # Scalp V2
            if os.path.exists(scalp_v2_file):
                with open(scalp_v2_file, "r") as f:
                    scalp_v2_data = json.load(f)
                    bots_data.append(("⚡ Scalp V2", scalp_v2_data))
            
            if not bots_data:
                await update.message.reply_text(
                    "⚠️ <b>All Bots Summary</b>\n\n"
                    "No bot data available",
                    parse_mode="HTML"
                )
                return
            
            # Build summary message
            message = "🤖 <b>All Bots Summary</b>\n\n"
            
            total_equity = 0
            total_pnl = 0
            total_trades = 0
            total_positions = 0
            
            for bot_name, data in bots_data:
                account = data.get("account", {})
                stats = data.get("stats", {})
                
                balance = account.get("balance", 0)
                equity = account.get("equity", 0)
                realized_pnl = account.get("realized_pnl", 0)
                unrealized_pnl = account.get("unrealized_pnl", 0)
                bot_total_pnl = realized_pnl + unrealized_pnl
                
                trades = stats.get("total_trades", 0)
                winning = stats.get("winning_trades", 0)
                losing = stats.get("losing_trades", 0)
                win_rate = (winning / trades * 100) if trades > 0 else 0
                open_pos = stats.get("open_positions", 0)
                
                # Accumulate totals
                total_equity += equity
                total_pnl += bot_total_pnl
                total_trades += trades
                total_positions += open_pos
                
                # Status emoji
                status_emoji = "🟢" if equity > 5 else "🔴"
                pnl_emoji = "🟢" if bot_total_pnl >= 0 else "🔴"
                
                message += (
                    f"{bot_name} {status_emoji}\n"
                    f"Equity: <code>${equity:.2f}</code> • "
                    f"{pnl_emoji} P&L: <code>{bot_total_pnl:+.2f}</code>\n"
                    f"Trades: {trades} ({winning}W/{losing}L • {win_rate:.0f}%) • "
                    f"Open: {open_pos}\n\n"
                )
            
            # Overall summary
            total_pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            total_return = (total_pnl / 300) * 100  # 3 bots × $100
            
            message += (
                f"<b>Portfolio Total</b>\n"
                f"Total Equity: <code>${total_equity:.2f}</code>\n"
                f"{total_pnl_emoji} Total P&L: <code>{total_pnl:+.2f}</code> ({total_return:+.2f}%)\n"
                f"Total Trades: {total_trades}\n"
                f"Open Positions: {total_positions}\n\n"
                f"<i>Initial: $300 (3 × $100)</i>"
            )
            
            await update.message.reply_text(message, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Error in /all command: {e}")
            await update.message.reply_text(f"⚠️ Lỗi: {e}")
    
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
            "🤖 <b>Command Guide</b>\n\n"
            "<b>Bot Reports</b>\n"
            "/all • Báo cáo tổng hợp cả 3 bot\n"
            "/wyckoff • Wyckoff strategy report\n"
            "/wyckoff_pos • Wyckoff open positions\n"
            "/scalp • Scalping V1 report\n"
            "/scalp_pos • Scalp V1 open positions\n"
            "/scalp_v2 • Scalping V2 report\n"
            "/scalp_v2_pos • Scalp V2 open positions\n"
            "/status • System health\n\n"
            "<b>Position Details</b>\n"
            "Each position shows:\n"
            "• Entry & Current price\n"
            "• Quantity & P&L\n"
            "• SL/TP targets (Scalp V2)\n\n"
            "<b>3 Independent Bots</b>\n"
            "💰 Wyckoff: $100 wallet\n"
            "⚡ Scalp V1: $100 wallet\n"
            "⚡ Scalp V2: $100 wallet\n\n"
            "<b>Auto-Reset</b>\n"
            "If equity < $5: Auto-reset to $100\n\n"
            "💡 Paper trading • Real-time data"
        )
        
        await update.message.reply_text(message, parse_mode="HTML")
    
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
