"""
Unit tests for Backtesting Engine
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from src.backtest.engine import (
    EventEngine,
    BacktestRunner,
    KlineEvent,
    TradeEvent,
    SignalEvent,
    OrderEvent,
    FillEvent
)


class TestEventEngine:
    """Test EventEngine"""
    
    @pytest.mark.asyncio
    async def test_event_engine_initialization(self):
        """Test EventEngine initializes correctly"""
        engine = EventEngine()
        
        assert engine.event_queue is not None
        assert engine.handlers == {}
        assert engine.is_running is False
        assert engine.events_processed == 0
    
    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test handler registration"""
        engine = EventEngine()
        
        async def test_handler(event):
            pass
        
        engine.register_handler("kline", test_handler)
        
        assert "kline" in engine.handlers
        assert len(engine.handlers["kline"]) == 1
    
    @pytest.mark.asyncio
    async def test_emit_event(self):
        """Test event emission"""
        engine = EventEngine()
        
        event = KlineEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            timeframe="1m",
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50050"),
            volume=Decimal("10")
        )
        
        await engine.emit(event)
        
        assert engine.event_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_process_events(self):
        """Test event processing"""
        engine = EventEngine()
        
        events_received = []
        
        async def test_handler(event):
            events_received.append(event)
        
        engine.register_handler("kline", test_handler)
        
        # Start event processor
        processor_task = asyncio.create_task(engine.process_events())
        
        # Emit event
        event = KlineEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            timeframe="1m",
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50050"),
            volume=Decimal("10")
        )
        
        await engine.emit(event)
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Stop engine
        await engine.stop()
        processor_task.cancel()
        
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
        
        assert len(events_received) == 1
        assert events_received[0].symbol == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test engine statistics"""
        engine = EventEngine()
        
        async def test_handler(event):
            pass
        
        engine.register_handler("kline", test_handler)
        engine.register_handler("trade", test_handler)
        
        stats = engine.get_stats()
        
        assert stats["events_processed"] == 0
        assert stats["handlers_registered"] == 2
        assert stats["queue_size"] == 0


class TestBacktestRunner:
    """Test BacktestRunner"""
    
    def test_backtest_runner_initialization(self):
        """Test BacktestRunner initializes correctly"""
        initial_balance = Decimal("10000")
        runner = BacktestRunner(initial_balance)
        
        assert runner.initial_balance == initial_balance
        assert runner.current_balance == initial_balance
        assert runner.commission_rate == Decimal("0.0006")
        assert runner.positions == {}
        assert runner.trades == []
        assert runner.equity_curve == []
    
    def test_register_handlers(self):
        """Test handler registration"""
        runner = BacktestRunner(Decimal("10000"))
        runner.register_handlers()
        
        assert "kline" in runner.event_engine.handlers
        assert "signal" in runner.event_engine.handlers
        assert "order" in runner.event_engine.handlers
        assert "fill" in runner.event_engine.handlers
    
    @pytest.mark.asyncio
    async def test_handle_kline(self):
        """Test kline event handling"""
        runner = BacktestRunner(Decimal("10000"))
        
        event = KlineEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            timeframe="1m",
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50050"),
            volume=Decimal("10")
        )
        
        await runner._handle_kline(event)
        
        assert runner.candles_processed == 1
        assert len(runner.equity_curve) == 1
    
    @pytest.mark.asyncio
    async def test_handle_fill(self):
        """Test fill event handling"""
        runner = BacktestRunner(Decimal("10000"))
        
        event = FillEvent(
            timestamp=datetime.now(),
            order_id="TEST_1",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.1"),
            fill_price=Decimal("50000"),
            commission=Decimal("3"),
            slippage=Decimal("0.0005")
        )
        
        initial_balance = runner.current_balance
        
        await runner._handle_fill(event)
        
        assert len(runner.trades) == 1
        assert runner.current_balance < initial_balance
    
    def test_export_trades_csv(self, tmp_path):
        """Test CSV export"""
        runner = BacktestRunner(Decimal("10000"))
        
        # Add sample trade
        runner.trades.append({
            "timestamp": datetime.now().isoformat(),
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": 0.1,
            "price": 50000.0,
            "commission": 3.0,
            "slippage": 0.0005
        })
        
        csv_file = tmp_path / "trades.csv"
        runner.export_trades_csv(str(csv_file))
        
        assert csv_file.exists()


class TestEvents:
    """Test Event classes"""
    
    def test_kline_event(self):
        """Test KlineEvent creation"""
        event = KlineEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            timeframe="1m",
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50050"),
            volume=Decimal("10")
        )
        
        assert event.event_type == "kline"
        assert event.symbol == "BTCUSDT"
        assert event.timeframe == "1m"
    
    def test_trade_event(self):
        """Test TradeEvent creation"""
        event = TradeEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            side="BUY"
        )
        
        assert event.event_type == "trade"
        assert event.symbol == "BTCUSDT"
        assert event.side == "BUY"
    
    def test_signal_event(self):
        """Test SignalEvent creation"""
        event = SignalEvent(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            signal_type="BUY",
            confidence=75,
            reason="Wyckoff MARKUP + positive delta"
        )
        
        assert event.event_type == "signal"
        assert event.signal_type == "BUY"
        assert event.confidence == 75
    
    def test_order_event(self):
        """Test OrderEvent creation"""
        event = OrderEvent(
            timestamp=datetime.now(),
            order_id="TEST_1",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            order_type="LIMIT"
        )
        
        assert event.event_type == "order"
        assert event.order_id == "TEST_1"
        assert event.order_type == "LIMIT"
    
    def test_fill_event(self):
        """Test FillEvent creation"""
        event = FillEvent(
            timestamp=datetime.now(),
            order_id="TEST_1",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.1"),
            fill_price=Decimal("50000"),
            commission=Decimal("3"),
            slippage=Decimal("0.0005")
        )
        
        assert event.event_type == "fill"
        assert event.fill_price == Decimal("50000")
        assert event.commission == Decimal("3")
