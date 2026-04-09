"""Unit tests for Kill Switch"""

import pytest
import asyncio
from datetime import datetime
from src.risk.kill_switch import (
    KillSwitch,
    KillSwitchConfig,
    KillSwitchReason,
    SystemState
)
from src.risk.drawdown_monitor import DrawdownMonitor
from src.notifications.telegram import TelegramBot


@pytest.fixture
def telegram_bot():
    """Create mock Telegram bot"""
    bot = TelegramBot(
        bot_token="test_token",
        chat_ids=["123456"],
        rate_limit=10
    )
    bot.enable_mock_mode()
    return bot


@pytest.fixture
def kill_switch(telegram_bot):
    """Create kill switch"""
    config = KillSwitchConfig(
        max_daily_drawdown=0.05,
        max_consecutive_losses=5,
        max_api_error_rate=0.20,
        max_price_movement=0.10
    )
    return KillSwitch(config, telegram_bot)


class TestKillSwitch:
    """Test KillSwitch"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, kill_switch):
        """Test kill switch initialization"""
        assert not kill_switch.is_activated
        assert kill_switch.activation_reason is None
        
    @pytest.mark.asyncio
    async def test_daily_drawdown_activation(self, kill_switch):
        """Test activation on daily drawdown"""
        starting_balance = 10000.0
        current_balance = 9400.0  # 6% drawdown
        
        activated = await kill_switch.check_daily_drawdown(
            current_balance, starting_balance
        )
        
        assert activated
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.DAILY_DRAWDOWN
        
    @pytest.mark.asyncio
    async def test_daily_drawdown_not_activated(self, kill_switch):
        """Test no activation when drawdown below threshold"""
        starting_balance = 10000.0
        current_balance = 9600.0  # 4% drawdown
        
        activated = await kill_switch.check_daily_drawdown(
            current_balance, starting_balance
        )
        
        assert not activated
        assert not kill_switch.is_activated
        
    @pytest.mark.asyncio
    async def test_consecutive_losses_activation(self, kill_switch):
        """Test activation on consecutive losses"""
        activated = await kill_switch.check_consecutive_losses(5)
        
        assert activated
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.CONSECUTIVE_LOSSES
        
    @pytest.mark.asyncio
    async def test_consecutive_losses_not_activated(self, kill_switch):
        """Test no activation when losses below threshold"""
        activated = await kill_switch.check_consecutive_losses(4)
        
        assert not activated
        assert not kill_switch.is_activated
        
    @pytest.mark.asyncio
    async def test_api_error_rate_activation(self, kill_switch):
        """Test activation on API error rate"""
        # Record 3 errors
        for _ in range(3):
            kill_switch.record_api_error("Test error")
        
        # Check with 10 total requests (30% error rate)
        activated = await kill_switch.check_api_error_rate(10)
        
        assert activated
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.API_ERROR_RATE
        
    @pytest.mark.asyncio
    async def test_api_error_rate_not_activated(self, kill_switch):
        """Test no activation when error rate below threshold"""
        # Record 1 error
        kill_switch.record_api_error("Test error")
        
        # Check with 10 total requests (10% error rate)
        activated = await kill_switch.check_api_error_rate(10)
        
        assert not activated
        assert not kill_switch.is_activated
        
    @pytest.mark.asyncio
    async def test_price_movement_activation(self, kill_switch):
        """Test activation on abnormal price movement"""
        # Record prices with 15% movement
        kill_switch.record_price(50000.0)
        kill_switch.record_price(57500.0)
        
        activated = await kill_switch.check_price_movement()
        
        assert activated
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.ABNORMAL_PRICE_MOVEMENT
        
    @pytest.mark.asyncio
    async def test_price_movement_not_activated(self, kill_switch):
        """Test no activation when price movement below threshold"""
        # Record prices with 5% movement
        kill_switch.record_price(50000.0)
        kill_switch.record_price(52500.0)
        
        activated = await kill_switch.check_price_movement()
        
        assert not activated
        assert not kill_switch.is_activated
        
    @pytest.mark.asyncio
    async def test_manual_activation(self, kill_switch):
        """Test manual activation"""
        await kill_switch.activate_manual("Test manual activation")
        
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.MANUAL
        
    @pytest.mark.asyncio
    async def test_telegram_alert_sent(self, kill_switch, telegram_bot):
        """Test Telegram alert is sent on activation"""
        await kill_switch.check_consecutive_losses(5)
        
        # Wait for async alert
        await asyncio.sleep(0.1)
        
        messages = telegram_bot.get_sent_messages()
        assert len(messages) == 1
        assert "KILL SWITCH ACTIVATED" in messages[0]
        assert "CONSECUTIVE_LOSSES" in messages[0]
        
    @pytest.mark.asyncio
    async def test_callback_called(self, kill_switch):
        """Test callback is called on activation"""
        callback_called = False
        callback_reason = None
        
        async def on_activated(reason, state):
            nonlocal callback_called, callback_reason
            callback_called = True
            callback_reason = reason
            
        kill_switch.set_callback(on_activated)
        
        await kill_switch.check_consecutive_losses(5)
        
        assert callback_called
        assert callback_reason == KillSwitchReason.CONSECUTIVE_LOSSES
        
    def test_reset_requires_confirmation(self, kill_switch):
        """Test reset requires manual confirmation"""
        with pytest.raises(ValueError):
            kill_switch.reset(manual_confirmation=False)
            
    @pytest.mark.asyncio
    async def test_reset_with_confirmation(self, kill_switch):
        """Test reset with confirmation"""
        # Activate
        await kill_switch.check_consecutive_losses(5)
        assert kill_switch.is_activated
        
        # Reset
        kill_switch.reset(manual_confirmation=True)
        assert not kill_switch.is_activated
        assert kill_switch.activation_reason is None
        
    @pytest.mark.asyncio
    async def test_get_status(self, kill_switch):
        """Test get status"""
        # Before activation
        status = kill_switch.get_status()
        assert not status['activated']
        assert status['reason'] is None
        
        # After activation
        await kill_switch.check_consecutive_losses(5)
        status = kill_switch.get_status()
        assert status['activated']
        assert status['reason'] == 'CONSECUTIVE_LOSSES'
        assert status['activation_time'] is not None


class TestDrawdownMonitor:
    """Test DrawdownMonitor"""
    
    def test_initialization(self):
        """Test monitor initialization"""
        monitor = DrawdownMonitor(10000.0)
        assert monitor.current_balance == 10000.0
        assert monitor.peak_balance == 10000.0
        assert monitor.get_current_drawdown() == 0.0
        
    def test_update_balance_profit(self):
        """Test update balance with profit"""
        monitor = DrawdownMonitor(10000.0)
        monitor.update_balance(11000.0)
        
        assert monitor.current_balance == 11000.0
        assert monitor.peak_balance == 11000.0
        assert monitor.get_current_drawdown() == 0.0
        
    def test_update_balance_loss(self):
        """Test update balance with loss"""
        monitor = DrawdownMonitor(10000.0)
        monitor.update_balance(9000.0)
        
        assert monitor.current_balance == 9000.0
        assert monitor.peak_balance == 10000.0
        assert monitor.get_current_drawdown() == 0.10  # 10%
        
    def test_max_drawdown_tracking(self):
        """Test max drawdown tracking"""
        monitor = DrawdownMonitor(10000.0)
        
        monitor.update_balance(9000.0)  # 10% DD
        monitor.update_balance(9500.0)  # 5% DD
        monitor.update_balance(8500.0)  # 15% DD
        
        assert monitor.max_drawdown == 0.15
        
    def test_daily_drawdown(self):
        """Test daily drawdown calculation"""
        monitor = DrawdownMonitor(10000.0)
        monitor.update_balance(9500.0)
        
        daily_dd = monitor.get_daily_drawdown()
        assert daily_dd == 0.05  # 5%
        
    def test_get_metrics(self):
        """Test get all metrics"""
        monitor = DrawdownMonitor(10000.0)
        monitor.update_balance(9000.0)
        
        metrics = monitor.get_metrics()
        assert metrics.current_drawdown == 0.10
        assert metrics.peak_balance == 10000.0
        assert metrics.current_balance == 9000.0
        assert metrics.underwater_since is not None


class TestTelegramBot:
    """Test TelegramBot"""
    
    @pytest.mark.asyncio
    async def test_send_alert(self):
        """Test sending alert"""
        bot = TelegramBot("test_token", ["123456"])
        bot.enable_mock_mode()
        
        await bot.send_alert("Test message")
        
        messages = bot.get_sent_messages()
        assert len(messages) == 1
        assert messages[0] == "Test message"
        
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting"""
        bot = TelegramBot("test_token", ["123456"], rate_limit=2)
        bot.enable_mock_mode()
        
        # Send 3 messages (limit is 2)
        await bot.send_alert("Message 1")
        await bot.send_alert("Message 2")
        await bot.send_alert("Message 3")  # Should be dropped
        
        messages = bot.get_sent_messages()
        assert len(messages) == 2
        
    @pytest.mark.asyncio
    async def test_critical_bypasses_rate_limit(self):
        """Test critical alerts bypass rate limit"""
        bot = TelegramBot("test_token", ["123456"], rate_limit=1)
        bot.enable_mock_mode()
        
        # Send 2 messages, second is critical
        await bot.send_alert("Message 1")
        await bot.send_alert("Critical message", priority="critical")
        
        messages = bot.get_sent_messages()
        assert len(messages) == 2
