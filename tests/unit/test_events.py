"""
Unit tests for event types.

Tests event creation, field validation, and type correctness.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from src.core.events import (
    Event,
    MarketDataEvent,
    SignalGeneratedEvent,
    SignalType,
    OrderPlacedEvent,
    OrderFilledEvent,
    OrderSide,
    OrderState,
    PositionOpenedEvent,
    PositionClosedEvent,
    KillSwitchActivatedEvent,
    SystemHealthEvent,
)


def test_base_event_creation():
    """Test creating a base Event."""
    event = Event()
    
    assert event.timestamp is not None
    assert isinstance(event.timestamp, datetime)
    assert event.event_id is not None
    assert len(event.event_id) > 0
    assert event.event_type == "Event"


def test_base_event_unique_ids():
    """Test that each event gets a unique ID."""
    event1 = Event()
    event2 = Event()
    
    assert event1.event_id != event2.event_id


def test_market_data_event_kline():
    """Test creating a MarketDataEvent for kline data."""
    event = MarketDataEvent(
        symbol="BTCUSDT",
        timeframe="1m",
        data_type="kline",
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=100.5
    )
    
    assert event.event_type == "MarketDataEvent"
    assert event.symbol == "BTCUSDT"
    assert event.timeframe == "1m"
    assert event.data_type == "kline"
    assert event.open == 50000.0
    assert event.high == 50100.0
    assert event.low == 49900.0
    assert event.close == 50050.0
    assert event.volume == 100.5


def test_market_data_event_trade():
    """Test creating a MarketDataEvent for trade data."""
    event = MarketDataEvent(
        symbol="BTCUSDT",
        timeframe="",
        data_type="trade",
        price=50000.0,
        quantity=0.5,
        side="BUY"
    )
    
    assert event.event_type == "MarketDataEvent"
    assert event.data_type == "trade"
    assert event.price == 50000.0
    assert event.quantity == 0.5
    assert event.side == "BUY"


def test_signal_generated_event():
    """Test creating a SignalGeneratedEvent."""
    event = SignalGeneratedEvent(
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        confidence=75.5,
        price=50000.0,
        reason="Strong bullish momentum",
        wyckoff_phase="Markup",
        delta=1500.0,
        breakout_direction="UP",
        volume_ratio=2.5,
        trend_aligned=True,
        momentum_score=0.85
    )
    
    assert event.event_type == "SignalGeneratedEvent"
    assert event.symbol == "BTCUSDT"
    assert event.signal_type == SignalType.BUY
    assert event.confidence == 75.5
    assert event.price == 50000.0
    assert event.reason == "Strong bullish momentum"
    assert event.wyckoff_phase == "Markup"
    assert event.delta == 1500.0
    assert event.breakout_direction == "UP"
    assert event.volume_ratio == 2.5
    assert event.trend_aligned is True
    assert event.momentum_score == 0.85


def test_signal_type_enum():
    """Test SignalType enum values."""
    assert SignalType.BUY.value == "BUY"
    assert SignalType.SELL.value == "SELL"
    assert SignalType.NEUTRAL.value == "NEUTRAL"


def test_order_placed_event():
    """Test creating an OrderPlacedEvent."""
    event = OrderPlacedEvent(
        order_id="order_123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("50000.00"),
        order_type="LIMIT",
        state=OrderState.PENDING
    )
    
    assert event.event_type == "OrderPlacedEvent"
    assert event.order_id == "order_123"
    assert event.symbol == "BTCUSDT"
    assert event.side == OrderSide.BUY
    assert event.quantity == Decimal("0.1")
    assert event.price == Decimal("50000.00")
    assert event.order_type == "LIMIT"
    assert event.state == OrderState.PENDING


def test_order_side_enum():
    """Test OrderSide enum values."""
    assert OrderSide.BUY.value == "BUY"
    assert OrderSide.SELL.value == "SELL"


def test_order_state_enum():
    """Test OrderState enum values."""
    assert OrderState.PENDING.value == "PENDING"
    assert OrderState.OPEN.value == "OPEN"
    assert OrderState.FILLED.value == "FILLED"
    assert OrderState.CANCELLED.value == "CANCELLED"
    assert OrderState.REJECTED.value == "REJECTED"


def test_order_filled_event():
    """Test creating an OrderFilledEvent."""
    event = OrderFilledEvent(
        order_id="order_123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        filled_qty=Decimal("0.1"),
        avg_fill_price=Decimal("50050.00"),
        commission=Decimal("3.003"),
        exchange_order_id="exch_456"
    )
    
    assert event.event_type == "OrderFilledEvent"
    assert event.order_id == "order_123"
    assert event.symbol == "BTCUSDT"
    assert event.side == OrderSide.BUY
    assert event.filled_qty == Decimal("0.1")
    assert event.avg_fill_price == Decimal("50050.00")
    assert event.commission == Decimal("3.003")
    assert event.exchange_order_id == "exch_456"


def test_position_opened_event():
    """Test creating a PositionOpenedEvent."""
    event = PositionOpenedEvent(
        position_id="pos_123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=Decimal("50000.00"),
        quantity=Decimal("0.1"),
        stop_loss=Decimal("49000.00"),
        trailing_stop=Decimal("49500.00")
    )
    
    assert event.event_type == "PositionOpenedEvent"
    assert event.position_id == "pos_123"
    assert event.symbol == "BTCUSDT"
    assert event.side == OrderSide.BUY
    assert event.entry_price == Decimal("50000.00")
    assert event.quantity == Decimal("0.1")
    assert event.stop_loss == Decimal("49000.00")
    assert event.trailing_stop == Decimal("49500.00")


def test_position_closed_event():
    """Test creating a PositionClosedEvent."""
    event = PositionClosedEvent(
        position_id="pos_123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=Decimal("50000.00"),
        exit_price=Decimal("51000.00"),
        quantity=Decimal("0.1"),
        realized_pnl=Decimal("100.00"),
        commission=Decimal("6.00"),
        exit_reason="Take profit"
    )
    
    assert event.event_type == "PositionClosedEvent"
    assert event.position_id == "pos_123"
    assert event.symbol == "BTCUSDT"
    assert event.side == OrderSide.BUY
    assert event.entry_price == Decimal("50000.00")
    assert event.exit_price == Decimal("51000.00")
    assert event.quantity == Decimal("0.1")
    assert event.realized_pnl == Decimal("100.00")
    assert event.commission == Decimal("6.00")
    assert event.exit_reason == "Take profit"


def test_kill_switch_activated_event():
    """Test creating a KillSwitchActivatedEvent."""
    event = KillSwitchActivatedEvent(
        reason="Daily drawdown exceeded",
        daily_drawdown=0.06,
        consecutive_losses=5,
        api_error_rate=0.15,
        price_volatility=0.12
    )
    
    assert event.event_type == "KillSwitchActivatedEvent"
    assert event.reason == "Daily drawdown exceeded"
    assert event.daily_drawdown == 0.06
    assert event.consecutive_losses == 5
    assert event.api_error_rate == 0.15
    assert event.price_volatility == 0.12


def test_kill_switch_activated_event_minimal():
    """Test creating a KillSwitchActivatedEvent with only reason."""
    event = KillSwitchActivatedEvent(reason="Manual activation")
    
    assert event.event_type == "KillSwitchActivatedEvent"
    assert event.reason == "Manual activation"
    assert event.daily_drawdown is None
    assert event.consecutive_losses is None
    assert event.api_error_rate is None
    assert event.price_volatility is None


def test_system_health_event():
    """Test creating a SystemHealthEvent."""
    event = SystemHealthEvent(
        uptime_seconds=3600,
        signals_processed=150,
        orders_placed=25,
        errors_count=3,
        error_rate=0.02,
        memory_usage_mb=256.5,
        cpu_usage_pct=45.2
    )
    
    assert event.event_type == "SystemHealthEvent"
    assert event.uptime_seconds == 3600
    assert event.signals_processed == 150
    assert event.orders_placed == 25
    assert event.errors_count == 3
    assert event.error_rate == 0.02
    assert event.memory_usage_mb == 256.5
    assert event.cpu_usage_pct == 45.2


def test_event_default_values():
    """Test that events have sensible default values."""
    event = MarketDataEvent()
    
    assert event.symbol == ""
    assert event.timeframe == ""
    assert event.data_type == ""
    assert event.open is None
    assert event.high is None
    assert event.low is None
    assert event.close is None
    assert event.volume is None


def test_signal_generated_event_default_values():
    """Test SignalGeneratedEvent default values."""
    event = SignalGeneratedEvent()
    
    assert event.symbol == ""
    assert event.signal_type == SignalType.NEUTRAL
    assert event.confidence == 0.0
    assert event.price == 0.0
    assert event.reason == ""
    assert event.wyckoff_phase == ""
    assert event.delta == 0.0
    assert event.breakout_direction is None
    assert event.volume_ratio == 0.0
    assert event.trend_aligned is False
    assert event.momentum_score == 0.0


def test_order_placed_event_default_values():
    """Test OrderPlacedEvent default values."""
    event = OrderPlacedEvent()
    
    assert event.order_id == ""
    assert event.symbol == ""
    assert event.side == OrderSide.BUY
    assert event.quantity == Decimal("0")
    assert event.price is None
    assert event.order_type == "LIMIT"
    assert event.state == OrderState.PENDING


def test_system_health_event_default_values():
    """Test SystemHealthEvent default values."""
    event = SystemHealthEvent()
    
    assert event.uptime_seconds == 0
    assert event.signals_processed == 0
    assert event.orders_placed == 0
    assert event.errors_count == 0
    assert event.error_rate == 0.0
    assert event.memory_usage_mb == 0.0
    assert event.cpu_usage_pct == 0.0
