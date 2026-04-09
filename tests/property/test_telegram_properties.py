"""
Property-Based Tests for Telegram Bot

Tests correctness properties for Telegram alerts and commands.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck
from unittest.mock import Mock, AsyncMock, patch

from src.monitoring.telegram_bot import TelegramBot, AlertRateLimiter
from src.monitoring.metrics_collector import MetricsCollector


# Strategies
@st.composite
def chat_id_strategy(draw, allowed_ids=[123456, 789012]):
    """Generate chat IDs (some authorized, some not)"""
    # 70% chance of authorized ID, 30% unauthorized
    is_authorized = draw(st.integers(min_value=0, max_value=9)) < 7
    
    if is_authorized:
        return draw(st.sampled_from(allowed_ids))
    else:
        # Generate unauthorized ID
        unauthorized = draw(st.integers(min_value=100000, max_value=999999))
        assume(unauthorized not in allowed_ids)
        return unauthorized


@st.composite
def alert_message_strategy(draw):
    """Generate alert messages"""
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    symbol = draw(st.sampled_from(symbols))
    
    message_types = [
        f"Order FILLED {symbol}",
        f"Order PENDING {symbol}",
        f"Order CANCELLED {symbol}",
        f"Order REJECTED {symbol}",
        f"Kill Switch Activated - {symbol}"
    ]
    
    return draw(st.sampled_from(message_types))


class TestTelegramBotProperties:
    """Property-based tests for Telegram Bot"""
    
    @given(
        chat_id=chat_id_strategy(),
        command=st.sampled_from(["/status", "/positions", "/pnl"])
    )
    @settings(
        max_examples=30,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @pytest.mark.asyncio
    async def test_property_59_telegram_command_response(
        self,
        chat_id,
        command
    ):
        """
        Property 59: Telegram Command Response
        
        For any valid Telegram command (/status, /positions, /pnl) from an 
        authenticated user, the bot should respond with the requested information.
        
        Validates: Requirements 16.9, 16.10, 16.11
        """
        # Arrange
        allowed_chat_ids = [123456, 789012]
        collector = MetricsCollector()
        
        # Add some test data
        collector.update_system_metrics(
            api_status="healthy",
            db_status="healthy",
            last_tick_time=datetime.now(),
            error_rate=Decimal("1.0"),
            uptime_seconds=3600,
            total_requests=1000,
            failed_requests=10
        )
        
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
        
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=allowed_chat_ids,
            metrics_collector=collector
        )
        
        # Mock Update and Context
        update = Mock()
        update.effective_chat.id = chat_id
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        
        # Act
        if command == "/status":
            await bot._handle_status(update, context)
        elif command == "/positions":
            await bot._handle_positions(update, context)
        elif command == "/pnl":
            await bot._handle_pnl(update, context)
        
        # Assert
        if chat_id in allowed_chat_ids:
            # Property 59.1: Authorized user should receive response
            assert update.message.reply_text.called, \
                f"Bot should respond to {command} from authorized user"
            
            # Property 59.2: Response should contain relevant information
            call_args = update.message.reply_text.call_args
            response_text = call_args[0][0] if call_args else ""
            
            if command == "/status":
                assert "System" in response_text or "API" in response_text, \
                    "/status response should contain system information"
            elif command == "/positions":
                assert "Position" in response_text or "Balance" in response_text, \
                    "/positions response should contain position information"
            elif command == "/pnl":
                assert "P&L" in response_text or "PnL" in response_text, \
                    "/pnl response should contain P&L information"
        else:
            # Property 60: Unauthorized user should be rejected
            # (tested in property 60 test)
            pass
    
    @given(
        chat_id=st.integers(min_value=100000, max_value=999999),
        command=st.sampled_from(["/status", "/positions", "/pnl", "/help"])
    )
    @settings(
        max_examples=30,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @pytest.mark.asyncio
    async def test_property_60_telegram_authentication(
        self,
        chat_id,
        command
    ):
        """
        Property 60: Telegram Authentication
        
        For any Telegram command received, if the chat_id is not in the 
        allowed list, the command should be rejected and no sensitive 
        information should be sent.
        
        Validates: Requirements 16.12
        """
        # Arrange
        allowed_chat_ids = [123456, 789012]
        
        # Ensure chat_id is not in allowed list
        assume(chat_id not in allowed_chat_ids)
        
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=allowed_chat_ids,
            metrics_collector=collector
        )
        
        # Mock Update and Context
        update = Mock()
        update.effective_chat.id = chat_id
        update.message.reply_text = AsyncMock()
        
        context = Mock()
        
        # Act
        if command == "/status":
            await bot._handle_status(update, context)
        elif command == "/positions":
            await bot._handle_positions(update, context)
        elif command == "/pnl":
            await bot._handle_pnl(update, context)
        elif command == "/help":
            await bot._handle_help(update, context)
        
        # Assert
        # Property 60.1: Unauthorized user should receive rejection
        assert update.message.reply_text.called, \
            "Bot should respond to unauthorized user"
        
        # Property 60.2: Response should indicate unauthorized
        call_args = update.message.reply_text.call_args
        response_text = call_args[0][0] if call_args else ""
        
        assert "Unauthorized" in response_text or "❌" in response_text, \
            "Response should indicate unauthorized access"
        
        # Property 60.3: No sensitive information should be leaked
        sensitive_keywords = ["Balance", "P&L", "position", "equity", "API"]
        for keyword in sensitive_keywords:
            if keyword in response_text:
                # If sensitive keyword found, it should only be in rejection message
                assert "Unauthorized" in response_text, \
                    f"Sensitive information '{keyword}' should not be sent to unauthorized user"
    
    @given(
        num_alerts=st.integers(min_value=1, max_value=20)
    )
    @settings(
        max_examples=20,
        deadline=3000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @pytest.mark.asyncio
    async def test_property_61_alert_rate_limiting(
        self,
        num_alerts
    ):
        """
        Property 61: Alert Rate Limiting
        
        For any 1-hour window, the total number of Telegram alerts sent 
        should not exceed 10 (excluding critical alerts).
        
        Validates: Requirements 16.14
        """
        # Arrange
        max_alerts = 10
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector,
            max_alerts_per_hour=max_alerts
        )
        
        # Mock application
        bot.application = Mock()
        bot.application.bot = AsyncMock()
        
        # Act - Send multiple alerts
        successful_alerts = 0
        failed_alerts = 0
        
        for i in range(num_alerts):
            result = await bot.send_alert(f"Test alert {i}", priority="normal")
            if result:
                successful_alerts += 1
            else:
                failed_alerts += 1
        
        # Assert
        # Property 61.1: Should not exceed max_alerts
        assert successful_alerts <= max_alerts, \
            f"Should not send more than {max_alerts} alerts per hour"
        
        # Property 61.2: Alerts after limit should be rejected
        if num_alerts > max_alerts:
            assert failed_alerts > 0, \
                "Alerts beyond limit should be rejected"
            assert failed_alerts == num_alerts - max_alerts, \
                f"Expected {num_alerts - max_alerts} rejected alerts, got {failed_alerts}"
        
        # Property 61.3: Rate limiter should track correctly
        status = bot.get_rate_limit_status()
        assert status["alerts_sent"] == successful_alerts, \
            "Rate limiter should track sent alerts correctly"
        assert status["remaining_quota"] == max(0, max_alerts - successful_alerts), \
            "Remaining quota should be calculated correctly"
    
    @given(
        num_critical_alerts=st.integers(min_value=1, max_value=5)
    )
    @settings(
        max_examples=10,
        deadline=3000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @pytest.mark.asyncio
    async def test_property_61_critical_alerts_bypass_rate_limit(
        self,
        num_critical_alerts
    ):
        """
        Property 61 (Extended): Critical Alerts Bypass Rate Limit
        
        Critical alerts (e.g., kill switch) should bypass rate limiting.
        """
        # Arrange
        max_alerts = 2
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector,
            max_alerts_per_hour=max_alerts
        )
        
        # Mock application
        bot.application = Mock()
        bot.application.bot = AsyncMock()
        
        # Act - Fill up normal alert quota
        await bot.send_alert("Normal alert 1", priority="normal")
        await bot.send_alert("Normal alert 2", priority="normal")
        
        # Normal alert should be rejected
        result_normal = await bot.send_alert("Normal alert 3", priority="normal")
        assert result_normal is False, "Normal alert should be rate limited"
        
        # Critical alerts should still go through
        critical_results = []
        for i in range(num_critical_alerts):
            result = await bot.send_alert(
                f"Critical alert {i}",
                priority="critical"
            )
            critical_results.append(result)
        
        # Assert
        # Property 61.4: All critical alerts should succeed
        assert all(critical_results), \
            "All critical alerts should bypass rate limit"
        
        # Property 61.5: Critical alerts should not count toward quota
        status = bot.get_rate_limit_status()
        assert status["alerts_sent"] == max_alerts, \
            "Critical alerts should not count toward rate limit"
    
    @given(
        symbol=st.sampled_from(["BTCUSDT", "ETHUSDT", "BNBUSDT"]),
        side=st.sampled_from(["BUY", "SELL"]),
        quantity=st.decimals(min_value=0.01, max_value=10, places=4),
        price=st.decimals(min_value=1000, max_value=100000, places=2),
        state=st.sampled_from(["PENDING", "FILLED", "CANCELLED", "REJECTED"])
    )
    @settings(
        max_examples=30,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @pytest.mark.asyncio
    async def test_property_62_alert_message_completeness(
        self,
        symbol,
        side,
        quantity,
        price,
        state
    ):
        """
        Property 62: Alert Message Completeness
        
        For any Telegram alert sent, the message should include both a 
        timestamp and the relevant symbol.
        
        Validates: Requirements 16.15
        """
        # Arrange
        collector = MetricsCollector()
        bot = TelegramBot(
            bot_token="test_token",
            allowed_chat_ids=[123456],
            metrics_collector=collector
        )
        
        # Mock application
        bot.application = Mock()
        bot.application.bot = AsyncMock()
        
        # Act - Send order alert
        result = await bot.send_order_alert(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            state=state
        )
        
        # Assert
        assert result is True, "Alert should be sent successfully"
        
        # Get the message that was sent
        assert bot.application.bot.send_message.called, \
            "send_message should be called"
        
        call_args = bot.application.bot.send_message.call_args
        message_text = call_args[1]["text"] if call_args else ""
        
        # Property 62.1: Message must include timestamp
        # Format: [YYYY-MM-DD HH:MM:SS]
        assert "[" in message_text and "]" in message_text, \
            "Alert message must include timestamp in brackets"
        
        # Extract timestamp part
        timestamp_part = message_text.split("]")[0] + "]"
        assert len(timestamp_part) > 10, \
            "Timestamp should be properly formatted"
        
        # Property 62.2: Message must include symbol
        assert symbol in message_text, \
            f"Alert message must include symbol {symbol}"
        
        # Property 62.3: Message must include order state
        assert state in message_text, \
            f"Alert message must include order state {state}"
        
        # Property 62.4: Message must include side
        assert side in message_text, \
            f"Alert message must include order side {side}"
        
        # Property 62.5: Message must include quantity
        assert str(quantity) in message_text, \
            f"Alert message must include quantity {quantity}"
        
        # Property 62.6: Message must include price
        price_str = f"${price:,.2f}"
        assert str(price) in message_text or price_str in message_text, \
            f"Alert message must include price {price}"


class TestAlertRateLimiterProperties:
    """Property-based tests for AlertRateLimiter"""
    
    @given(
        max_alerts=st.integers(min_value=1, max_value=20),
        num_attempts=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=30, deadline=1000)
    def test_property_61_rate_limiter_enforcement(
        self,
        max_alerts,
        num_attempts
    ):
        """
        Property 61: Rate Limiter Enforcement
        
        The rate limiter should never allow more than max_alerts in a window.
        """
        # Arrange
        limiter = AlertRateLimiter(max_alerts=max_alerts, window_seconds=3600)
        
        # Act
        allowed_count = 0
        for i in range(num_attempts):
            if limiter.can_send_alert():
                limiter.record_alert()
                allowed_count += 1
        
        # Assert
        # Property 61.6: Should not exceed max_alerts
        assert allowed_count <= max_alerts, \
            f"Rate limiter allowed {allowed_count} alerts, max is {max_alerts}"
        
        # Property 61.7: Should allow exactly max_alerts if attempts >= max_alerts
        if num_attempts >= max_alerts:
            assert allowed_count == max_alerts, \
                f"Rate limiter should allow exactly {max_alerts} alerts"
        else:
            assert allowed_count == num_attempts, \
                f"Rate limiter should allow all {num_attempts} alerts when under limit"
        
        # Property 61.8: Remaining quota should be correct
        remaining = limiter.get_remaining_quota()
        assert remaining == max_alerts - allowed_count, \
            f"Remaining quota should be {max_alerts - allowed_count}, got {remaining}"
