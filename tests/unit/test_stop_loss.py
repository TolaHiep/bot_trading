"""Unit tests for Stop-Loss Engine"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.risk.stop_loss import (
    StopLossEngine,
    StopLossMode,
    StopLossConfig,
    Position,
    PositionSide
)


class MockRESTClient:
    """Mock REST client"""
    
    def __init__(self):
        self.orders = {}
        self.order_counter = 1000
        
    async def place_order(self, **kwargs):
        """Mock place order"""
        order_id = f"ORDER_{self.order_counter}"
        self.order_counter += 1
        self.orders[order_id] = kwargs
        return {'orderId': order_id}
        
    async def cancel_order(self, symbol, order_id):
        """Mock cancel order"""
        if order_id in self.orders:
            del self.orders[order_id]
        return {'orderId': order_id}


@pytest.fixture
def mock_rest_client():
    """Create mock REST client"""
    return MockRESTClient()


@pytest.fixture
def fixed_config():
    """Create fixed % config"""
    return StopLossConfig(
        mode=StopLossMode.FIXED_PERCENT,
        initial_stop_pct=0.02,
        breakeven_profit_pct=0.01,
        trailing_activation_pct=0.02,
        trailing_distance_pct=0.01
    )


@pytest.fixture
def trailing_config():
    """Create trailing config"""
    return StopLossConfig(
        mode=StopLossMode.TRAILING,
        initial_stop_pct=0.02,
        breakeven_profit_pct=0.01,
        trailing_activation_pct=0.02,
        trailing_distance_pct=0.01
    )


@pytest.fixture
def atr_config():
    """Create ATR config"""
    return StopLossConfig(
        mode=StopLossMode.ATR_BASED,
        atr_multiplier=2.0,
        atr_adjustment_threshold=0.20
    )


class TestStopLossEngine:
    """Test StopLossEngine"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_rest_client, fixed_config):
        """Test engine initialization"""
        engine = StopLossEngine(
            rest_client=mock_rest_client,
            config=fixed_config,
            monitor_interval=1.0
        )
        
        assert engine.rest_client == mock_rest_client
        assert engine.config == fixed_config
        assert engine.monitor_interval == 1.0
        assert len(engine.positions) == 0
        
    @pytest.mark.asyncio
    async def test_add_long_position_fixed(self, mock_rest_client, fixed_config):
        """Test adding long position with fixed stop"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Check position
        assert position.symbol == "BTCUSDT"
        assert position.side == PositionSide.LONG
        assert position.entry_price == 50000.0
        assert position.quantity == 0.1
        
        # Check stop-loss (2% below entry)
        expected_stop = 50000.0 * 0.98
        assert abs(position.stop_loss_price - expected_stop) < 0.01
        
        # Check order placed
        assert position.stop_loss_order_id is not None
        assert position.stop_loss_order_id in mock_rest_client.orders
        
    @pytest.mark.asyncio
    async def test_add_short_position_fixed(self, mock_rest_client, fixed_config):
        """Test adding short position with fixed stop"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Check stop-loss (2% above entry)
        expected_stop = 50000.0 * 1.02
        assert abs(position.stop_loss_price - expected_stop) < 0.01
        
    @pytest.mark.asyncio
    async def test_add_position_atr_based(self, mock_rest_client, atr_config):
        """Test adding position with ATR-based stop"""
        engine = StopLossEngine(mock_rest_client, atr_config)
        
        atr = 500.0  # ATR = 500
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0,
            atr=atr
        )
        
        # Check stop-loss (entry - 2*ATR)
        expected_stop = 50000.0 - (2.0 * 500.0)
        assert abs(position.stop_loss_price - expected_stop) < 0.01
        
    @pytest.mark.asyncio
    async def test_move_to_breakeven_long(self, mock_rest_client, fixed_config):
        """Test moving stop to breakeven for long position"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        initial_stop = position.stop_loss_price
        
        # Price moves up 1% (triggers breakeven)
        await engine.update_position("BTCUSDT", 50500.0)
        
        # Check stop moved to breakeven
        position = engine.get_position("BTCUSDT")
        assert position.breakeven_moved
        assert position.stop_loss_price == 50000.0
        assert position.stop_loss_price > initial_stop
        
    @pytest.mark.asyncio
    async def test_move_to_breakeven_short(self, mock_rest_client, fixed_config):
        """Test moving stop to breakeven for short position"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        initial_stop = position.stop_loss_price
        
        # Price moves down 1% (triggers breakeven)
        await engine.update_position("BTCUSDT", 49500.0)
        
        # Check stop moved to breakeven
        position = engine.get_position("BTCUSDT")
        assert position.breakeven_moved
        assert position.stop_loss_price == 50000.0
        assert position.stop_loss_price < initial_stop
        
    @pytest.mark.asyncio
    async def test_trailing_stop_activation(self, mock_rest_client, trailing_config):
        """Test trailing stop activation"""
        engine = StopLossEngine(mock_rest_client, trailing_config)
        
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Price moves up 2% (triggers trailing)
        await engine.update_position("BTCUSDT", 51000.0)
        
        # Check trailing activated
        position = engine.get_position("BTCUSDT")
        assert position.trailing_activated
        assert position.highest_price == 51000.0
        
        # Check stop-loss updated (1% below highest)
        expected_stop = 51000.0 * 0.99
        assert abs(position.stop_loss_price - expected_stop) < 0.01
        
    @pytest.mark.asyncio
    async def test_trailing_stop_follows_price(self, mock_rest_client, trailing_config):
        """Test trailing stop follows price upward"""
        engine = StopLossEngine(mock_rest_client, trailing_config)
        
        await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Activate trailing at 51000
        await engine.update_position("BTCUSDT", 51000.0)
        position = engine.get_position("BTCUSDT")
        stop_at_51k = position.stop_loss_price
        
        # Price moves to 52000
        await engine.update_position("BTCUSDT", 52000.0)
        position = engine.get_position("BTCUSDT")
        stop_at_52k = position.stop_loss_price
        
        # Stop should have moved up
        assert stop_at_52k > stop_at_51k
        assert position.highest_price == 52000.0
        
    @pytest.mark.asyncio
    async def test_trailing_stop_does_not_move_down(self, mock_rest_client, trailing_config):
        """Test trailing stop doesn't move down"""
        engine = StopLossEngine(mock_rest_client, trailing_config)
        
        await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Activate trailing at 51000
        await engine.update_position("BTCUSDT", 51000.0)
        position = engine.get_position("BTCUSDT")
        stop_at_51k = position.stop_loss_price
        
        # Price drops to 50500
        await engine.update_position("BTCUSDT", 50500.0)
        position = engine.get_position("BTCUSDT")
        
        # Stop should NOT have moved
        assert position.stop_loss_price == stop_at_51k
        
    @pytest.mark.asyncio
    async def test_atr_adjustment(self, mock_rest_client, atr_config):
        """Test ATR-based stop adjustment"""
        engine = StopLossEngine(mock_rest_client, atr_config)
        
        # Initial ATR = 500
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0,
            atr=500.0
        )
        
        initial_stop = position.stop_loss_price
        
        # ATR increases by 25% (triggers adjustment)
        new_atr = 625.0
        await engine.update_position("BTCUSDT", 50000.0, atr=new_atr)
        
        # Stop should have been adjusted
        position = engine.get_position("BTCUSDT")
        assert position.stop_loss_price != initial_stop
        
    @pytest.mark.asyncio
    async def test_stop_loss_triggered_long(self, mock_rest_client, fixed_config):
        """Test stop-loss triggered for long position"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Price drops below stop-loss
        await engine.update_position("BTCUSDT", 48900.0)
        
        # Check if triggered
        triggered = await engine.check_stop_loss_triggered("BTCUSDT")
        assert triggered
        
    @pytest.mark.asyncio
    async def test_stop_loss_triggered_short(self, mock_rest_client, fixed_config):
        """Test stop-loss triggered for short position"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.SHORT,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Price rises above stop-loss
        await engine.update_position("BTCUSDT", 51100.0)
        
        # Check if triggered
        triggered = await engine.check_stop_loss_triggered("BTCUSDT")
        assert triggered
        
    @pytest.mark.asyncio
    async def test_emergency_close_callback(self, mock_rest_client, fixed_config):
        """Test emergency close callback"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        # Set up callback
        emergency_called = False
        emergency_position = None
        emergency_loss = None
        
        async def on_emergency(position, loss):
            nonlocal emergency_called, emergency_position, emergency_loss
            emergency_called = True
            emergency_position = position
            emergency_loss = loss
            
        engine.set_callbacks(on_emergency_close=on_emergency)
        
        # Add position without stop-loss order
        position = await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        # Remove order ID to simulate missing stop-loss
        position.stop_loss_order_id = None
        
        # Trigger stop-loss
        await engine.update_position("BTCUSDT", 48900.0)
        await engine.check_stop_loss_triggered("BTCUSDT")
        
        # Wait a bit for async callback
        await asyncio.sleep(0.1)
        
        # Check callback was called
        assert emergency_called
        assert emergency_position.symbol == "BTCUSDT"
        assert emergency_loss > 0
        
    @pytest.mark.asyncio
    async def test_remove_position(self, mock_rest_client, fixed_config):
        """Test removing position"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        assert "BTCUSDT" in engine.positions
        
        await engine.remove_position("BTCUSDT")
        
        assert "BTCUSDT" not in engine.positions
        
    @pytest.mark.asyncio
    async def test_get_all_positions(self, mock_rest_client, fixed_config):
        """Test getting all positions"""
        engine = StopLossEngine(mock_rest_client, fixed_config)
        
        await engine.add_position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            entry_price=50000.0,
            quantity=0.1,
            current_price=50000.0
        )
        
        await engine.add_position(
            symbol="ETHUSDT",
            side=PositionSide.SHORT,
            entry_price=3000.0,
            quantity=1.0,
            current_price=3000.0
        )
        
        positions = engine.get_all_positions()
        assert len(positions) == 2
        assert "BTCUSDT" in positions
        assert "ETHUSDT" in positions
