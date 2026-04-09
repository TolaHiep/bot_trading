"""
Unit tests for Monitoring module
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.monitoring.metrics_collector import (
    MetricsCollector,
    SystemMetrics,
    TradingMetrics,
    SignalMetrics
)
from src.monitoring.telegram_bot import TelegramBot, AlertRateLimiter


class TestMetricsCollector:
    """Test MetricsCollector functionality"""
    
    def test_initialization(self):
        """Test metrics collector initialization"""
        collector = MetricsCollector(max_signals=50)
        
        assert collector.max_signals == 50
        assert collector.system_metrics is None
        assert collector.trading_metrics is None
        assert len(collector.recent_signals) == 0
        assert len(collector.equity_history) == 0
    
    def test_update_system_metrics(self):
        """Test updating system metrics"""
        collector = MetricsCollector()
        
        collector.update_system_metrics(
            api_status="healthy",
            db_status="healthy",
            last_tick_time=datetime.now(),
            error_rate=Decimal("1.5"),
            uptime_seconds=3600,
            total_requests=1000,
            failed_requests=15
        )
        
        assert collector.system_metrics is not None
        assert collector.system_metrics.api_status == "healthy"
        assert collector.system_metrics.db_status == "healthy"
        assert collector.system_metrics.error_rate == Decimal("1.5")
        assert collector.system_metrics.uptime_seconds == 3600
    
    def test_update_trading_metrics(self):
        """Test updating trading metrics"""
        collector = MetricsCollector()
        
        collector.update_trading_metrics(
            current_balance=Decimal("10500"),
            initial_balance=Decimal("10000"),
            equity=Decimal("10500"),
            total_pnl=Decimal("500"),
            realized_pnl=Decimal("500"),
            unrealized_pnl=Decimal("0"),
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            open_positions=0
        )
        
        assert collector.trading_metrics is not None
        assert collector.trading_metrics.current_balance == Decimal("10500")
        assert collector.trading_metrics.total_pnl == Decimal("500")
        assert collector.trading_metrics.win_rate == Decimal("70.0")
        assert len(collector.equity_history) == 1
    
    def test_add_signal(self):
        """Test adding signal"""
        collector = MetricsCollector()
        
        collector.add_signal(
            symbol="BTCUSDT",
            signal_type="BUY",
            confidence=75,
            wyckoff_phase="MARKUP",
            order_flow_delta=Decimal("150.5")
        )
        
        assert len(collector.recent_signals) == 1
        signal = collector.recent_signals[0]
        assert signal.symbol == "BTCUSDT"
        assert signal.signal_type == "BUY"
        assert signal.confidence == 75
    
    def test_signal_max_limit(self):
        """Test signal max limit"""
        collector = MetricsCollector(max_signals=5)
        
        # Add 10 signals
        for i in range(10):
            collector.add_signal(
                symbol="BTCUSDT",
                signal_type="BUY",
                confidence=70,
                wyckoff_phase="MARKUP",
                order_flow_delta=Decimal("100")
            )
        
        # Should only keep last 5
        assert len(collector.recent_signals) == 5
    
    def test_log_error(self):
        """Test error logging"""
        collector = MetricsCollector()
        
        collector.log_error("API_ERROR", "Connection timeout")
        
        assert len(collector.error_log) == 1
        error = collector.error_log[0]
        assert error["type"] == "API_ERROR"
        assert error["message"] == "Connection timeout"
    
    def test_get_system_status(self):
        """Test getting system status"""
        collector = MetricsCollector()
        
        # No data
        status = collector.get_system_status()
        assert status["status"] == "unknown"
        
        # With data
        collector.update_system_metrics(
            api_status="healthy",
            db_status="healthy",
            last_tick_time=datetime.now(),
            error_rate=Decimal("2.0"),
            uptime_seconds=7200,
            total_requests=5000,
            failed_requests=100
        )
        
        status = collector.get_system_status()
        assert status["status"] == "healthy"
        assert status["api_status"] == "healthy"
        assert status["error_rate"] == 2.0
    
    def test_get_trading_summary(self):
        """Test getting trading summary"""
        collector = MetricsCollector()
        
        # No data
        summary = collector.get_trading_summary()
        assert summary["status"] == "no_data"
        
        # With data
        collector.update_trading_metrics(
            current_balance=Decimal("11000"),
            initial_balance=Decimal("10000"),
            equity=Decimal("11000"),
            total_pnl=Decimal("1000"),
            realized_pnl=Decimal("1000"),
            unrealized_pnl=Decimal("0"),
            total_trades=20,
            winning_trades=15,
            losing_trades=5,
            open_positions=0
        )
        
        summary = collector.get_trading_summary()
        assert summary["current_balance"] == 11000.0
        assert summary["total_return"] == 10.0
        assert summary["win_rate"] == 75.0
    
    def test_get_recent_signals(self):
        """Test getting recent signals"""
        collector = MetricsCollector()
        
        # Add signals
        for i in range(5):
            collector.add_signal(
                symbol="BTCUSDT",
                signal_type="BUY",
                confidence=70 + i,
                wyckoff_phase="MARKUP",
                order_flow_delta=Decimal("100")
            )
        
        # Get last 3
        signals = collector.get_recent_signals(limit=3)
        assert len(signals) == 3
        assert signals[0]["confidence"] == 72  # 3rd signal
    
    def test_get_equity_curve(self):
        """Test getting equity curve"""
        collector = MetricsCollector()
        
        # Add equity points
        for i in range(5):
            collector.update_trading_metrics(
                current_balance=Decimal("10000") + Decimal(i * 100),
                initial_balance=Decimal("10000"),
                equity=Decimal("10000") + Decimal(i * 100),
                total_pnl=Decimal(i * 100),
                realized_pnl=Decimal(i * 100),
                unrealized_pnl=Decimal("0"),
                total_trades=i,
                winning_trades=i,
                losing_trades=0,
                open_positions=0
            )
        
        curve = collector.get_equity_curve(days=30)
        assert len(curve) == 5


class TestSystemMetrics:
    """Test SystemMetrics dataclass"""
    
    def test_is_healthy(self):
        """Test is_healthy property"""
        # Healthy system
        metrics = SystemMetrics(
            api_status="healthy",
            db_status="healthy",
            last_tick_time=datetime.now(),
            error_rate=Decimal("2.0"),
            uptime_seconds=3600,
            total_requests=1000,
            failed_requests=20
        )
        
        assert metrics.is_healthy is True
        
        # Degraded system (high error rate)
        metrics.error_rate = Decimal("10.0")
        assert metrics.is_healthy is False
        
        # Degraded system (API down)
        metrics.error_rate = Decimal("2.0")
        metrics.api_status = "down"
        assert metrics.is_healthy is False


class TestTradingMetrics:
    """Test TradingMetrics dataclass"""
    
    def test_win_rate(self):
        """Test win rate calculation"""
        metrics = TradingMetrics(
            current_balance=Decimal("10500"),
            initial_balance=Decimal("10000"),
            equity=Decimal("10500"),
            total_pnl=Decimal("500"),
            realized_pnl=Decimal("500"),
            unrealized_pnl=Decimal("0"),
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            open_positions=0
        )
        
        assert metrics.win_rate == Decimal("70.0")
        
        # No trades
        metrics.total_trades = 0
        assert metrics.win_rate == Decimal("0")
    
    def test_total_return(self):
        """Test total return calculation"""
        metrics = TradingMetrics(
            current_balance=Decimal("11000"),
            initial_balance=Decimal("10000"),
            equity=Decimal("11000"),
            total_pnl=Decimal("1000"),
            realized_pnl=Decimal("1000"),
            unrealized_pnl=Decimal("0"),
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            open_positions=0
        )
        
        assert metrics.total_return == Decimal("10.0")


class TestAlertRateLimiter:
    """Test AlertRateLimiter functionality"""
    
    def test_initialization(self):
        """Test rate limiter initialization"""
        limiter = AlertRateLimiter(max_alerts=10, window_seconds=3600)
        
        assert limiter.max_alerts == 10
        assert limiter.window_seconds == 3600
        assert len(limiter.alert_timestamps) == 0
    
    def test_can_send_alert(self):
        """Test can send alert check"""
        limiter = AlertRateLimiter(max_alerts=3, window_seconds=60)
        
        # Should allow first 3 alerts
        assert limiter.can_send_alert() is True
        limiter.record_alert()
        
        assert limiter.can_send_alert() is True
        limiter.record_alert()
        
        assert limiter.can_send_alert() is True
        limiter.record_alert()
        
        # Should block 4th alert
        assert limiter.can_send_alert() is False
    
    def test_get_remaining_quota(self):
        """Test getting remaining quota"""
        limiter = AlertRateLimiter(max_alerts=5, window_seconds=60)
        
        assert limiter.get_remaining_quota() == 5
        
        limiter.record_alert()
        assert limiter.get_remaining_quota() == 4
        
        limiter.record_alert()
        assert limiter.get_remaining_quota() == 3


class TestTelegramBot:
    """Test TelegramBot functionality"""
    
    def test_initialization(self):
        """Test Telegram bot initialization"""
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456, 789012],
            metrics_collector=collector,
            max_alerts_per_hour=10
        )
        
        assert bot.bot_token == "test_token"
        assert len(bot.allowed_chat_ids) == 2
        assert 123456 in bot.allowed_chat_ids
        assert bot.rate_limiter.max_alerts == 10
    
    def test_is_authorized(self):
        """Test authorization check"""
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector
        )
        
        assert bot._is_authorized(123456) is True
        assert bot._is_authorized(999999) is False
    
    @pytest.mark.asyncio
    async def test_send_alert_rate_limited(self):
        """Test alert rate limiting"""
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector,
            max_alerts_per_hour=2
        )
        
        # Mock application
        bot.application = Mock()
        bot.application.bot = AsyncMock()
        
        # First 2 alerts should succeed
        result1 = await bot.send_alert("Test alert 1")
        assert result1 is True
        
        result2 = await bot.send_alert("Test alert 2")
        assert result2 is True
        
        # 3rd alert should be rate limited
        result3 = await bot.send_alert("Test alert 3")
        assert result3 is False
    
    @pytest.mark.asyncio
    async def test_send_alert_critical_bypasses_rate_limit(self):
        """Test critical alerts bypass rate limit"""
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector,
            max_alerts_per_hour=1
        )
        
        # Mock application
        bot.application = Mock()
        bot.application.bot = AsyncMock()
        
        # Normal alert
        result1 = await bot.send_alert("Normal alert")
        assert result1 is True
        
        # Critical alert should bypass rate limit
        result2 = await bot.send_alert("Critical alert", priority="critical")
        assert result2 is True
    
    @pytest.mark.asyncio
    async def test_send_order_alert(self):
        """Test sending order alert"""
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector
        )
        
        # Mock application
        bot.application = Mock()
        bot.application.bot = AsyncMock()
        
        result = await bot.send_order_alert(
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            state="FILLED"
        )
        
        assert result is True
        assert bot.application.bot.send_message.called
    
    @pytest.mark.asyncio
    async def test_send_kill_switch_alert(self):
        """Test sending kill switch alert"""
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector
        )
        
        # Mock application
        bot.application = Mock()
        bot.application.bot = AsyncMock()
        
        result = await bot.send_kill_switch_alert("Daily drawdown > 5%")
        
        assert result is True
        assert bot.application.bot.send_message.called
    
    def test_get_rate_limit_status(self):
        """Test getting rate limit status"""
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector,
            max_alerts_per_hour=10
        )
        
        status = bot.get_rate_limit_status()
        
        assert status["max_alerts"] == 10
        assert status["window_seconds"] == 3600
        assert status["remaining_quota"] == 10
        assert status["alerts_sent"] == 0
