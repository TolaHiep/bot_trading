"""Tests for MultiSymbolManager"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from src.core.multi_symbol_manager import MultiSymbolManager
from src.alpha.signal_engine import SignalGenerator, TradingSignal, SignalType
from src.connectors.bybit_ws import WebSocketManager
from src.execution.paper_trader import PaperTrader
from src.execution.cost_filter import Orderbook


@pytest.fixture
def mock_ws_manager():
    """Create mock WebSocket manager"""
    ws_manager = MagicMock(spec=WebSocketManager)
    ws_manager.subscribe_batch = AsyncMock()
    ws_manager.unsubscribe_batch = AsyncMock()
    ws_manager.register_callback = MagicMock()
    return ws_manager


@pytest.fixture
def mock_paper_trader():
    """Create mock paper trader"""
    paper_trader = MagicMock(spec=PaperTrader)
    paper_trader.has_open_position = MagicMock(return_value=False)
    paper_trader.execute_signal = AsyncMock()
    paper_trader.account = MagicMock()
    paper_trader.account.current_balance = Decimal("10000")
    return paper_trader


@pytest.fixture
def manager(mock_ws_manager, mock_paper_trader):
    """Create MultiSymbolManager instance"""
    return MultiSymbolManager(
        ws_manager=mock_ws_manager,
        paper_trader=mock_paper_trader
    )


@pytest.mark.asyncio
async def test_init_registers_callbacks(mock_ws_manager, mock_paper_trader):
    """Test that initialization registers WebSocket callbacks"""
    manager = MultiSymbolManager(
        ws_manager=mock_ws_manager,
        paper_trader=mock_paper_trader
    )
    
    # Verify callbacks registered
    assert mock_ws_manager.register_callback.call_count == 3
    
    # Check callback topics
    call_args = [call[0][0] for call in mock_ws_manager.register_callback.call_args_list]
    assert "kline" in call_args
    assert "publicTrade" in call_args
    assert "orderbook" in call_args


@pytest.mark.asyncio
async def test_add_symbol_creates_engine_and_subscribes(manager, mock_ws_manager):
    """Test adding a symbol creates signal engine and subscribes to channels"""
    symbol = "BTCUSDT"
    
    with patch('src.core.multi_symbol_manager.SignalGenerator') as mock_signal_gen:
        mock_engine = MagicMock()
        mock_signal_gen.return_value = mock_engine
        
        await manager.add_symbol(symbol)
        
        # Verify signal engine created
        assert symbol in manager.signal_engines
        assert manager.signal_engines[symbol] == mock_engine
        
        # Verify subscriptions
        mock_ws_manager.subscribe_batch.assert_called_once()
        subscriptions = mock_ws_manager.subscribe_batch.call_args[0][0]
        
        # Should subscribe to 5 channels
        assert len(subscriptions) == 5
        assert ("kline.1", symbol) in subscriptions
        assert ("kline.5", symbol) in subscriptions
        assert ("kline.15", symbol) in subscriptions
        assert ("publicTrade", symbol) in subscriptions
        assert ("orderbook.20", symbol) in subscriptions


@pytest.mark.asyncio
async def test_remove_symbol_destroys_engine_and_unsubscribes(manager, mock_ws_manager):
    """Test removing a symbol destroys signal engine and unsubscribes"""
    symbol = "BTCUSDT"
    
    # Add symbol first
    with patch('src.core.multi_symbol_manager.SignalGenerator'):
        await manager.add_symbol(symbol)
    
    # Add some market data
    manager.current_prices[symbol] = 50000.0
    manager.current_orderbooks[symbol] = MagicMock()
    
    # Remove symbol
    await manager.remove_symbol(symbol)
    
    # Verify signal engine removed
    assert symbol not in manager.signal_engines
    
    # Verify market data cleaned up
    assert symbol not in manager.current_prices
    assert symbol not in manager.current_orderbooks
    
    # Verify unsubscriptions
    mock_ws_manager.unsubscribe_batch.assert_called_once()
    subscriptions = mock_ws_manager.unsubscribe_batch.call_args[0][0]
    assert len(subscriptions) == 5


@pytest.mark.asyncio
async def test_get_active_symbols(manager):
    """Test getting list of active symbols"""
    # Initially empty
    assert manager.get_active_symbols() == []
    
    # Add symbols
    with patch('src.core.multi_symbol_manager.SignalGenerator'):
        await manager.add_symbol("BTCUSDT")
        await manager.add_symbol("ETHUSDT")
    
    # Verify list
    active = manager.get_active_symbols()
    assert len(active) == 2
    assert "BTCUSDT" in active
    assert "ETHUSDT" in active


@pytest.mark.asyncio
async def test_get_signal_engine(manager):
    """Test getting signal engine for a symbol"""
    symbol = "BTCUSDT"
    
    # Initially None
    assert manager.get_signal_engine(symbol) is None
    
    # Add symbol
    with patch('src.core.multi_symbol_manager.SignalGenerator') as mock_signal_gen:
        mock_engine = MagicMock()
        mock_signal_gen.return_value = mock_engine
        
        await manager.add_symbol(symbol)
        
        # Verify engine returned
        assert manager.get_signal_engine(symbol) == mock_engine


@pytest.mark.asyncio
async def test_on_kline_routes_to_engine(manager):
    """Test kline message routing to signal engine"""
    symbol = "BTCUSDT"
    
    # Add symbol with mock engine
    mock_engine = MagicMock()
    mock_engine.add_kline = MagicMock(return_value=None)
    manager.signal_engines[symbol] = mock_engine
    
    # Create kline message
    message = {
        "topic": "kline.15.BTCUSDT",
        "data": [{
            "timestamp": 1234567890,
            "open": "50000",
            "high": "51000",
            "low": "49000",
            "close": "50500",
            "volume": "100"
        }]
    }
    
    await manager.on_kline(message)
    
    # Verify engine called
    mock_engine.add_kline.assert_called_once()
    call_args = mock_engine.add_kline.call_args
    assert call_args[1]["timeframe"] == "15m"
    assert call_args[1]["close"] == 50500.0
    
    # Verify price updated
    assert manager.current_prices[symbol] == 50500.0


@pytest.mark.asyncio
async def test_on_trade_routes_to_engine(manager):
    """Test trade message routing to signal engine"""
    symbol = "BTCUSDT"
    
    # Add symbol with mock engine
    mock_engine = MagicMock()
    mock_engine.add_trade = MagicMock()
    manager.signal_engines[symbol] = mock_engine
    
    # Create trade message
    message = {
        "topic": "publicTrade.BTCUSDT",
        "data": [{
            "T": 1234567890,
            "p": "50000",
            "v": "1.5",
            "S": "Buy"
        }]
    }
    
    await manager.on_trade(message)
    
    # Verify engine called for all timeframes
    assert mock_engine.add_trade.call_count == 3  # 1m, 5m, 15m


@pytest.mark.asyncio
async def test_on_orderbook_stores_data(manager):
    """Test orderbook message storage"""
    symbol = "BTCUSDT"
    
    # Create orderbook message
    message = {
        "topic": "orderbook.20.BTCUSDT",
        "data": {
            "b": [["50000", "1.0"], ["49900", "2.0"]],
            "a": [["50100", "1.5"], ["50200", "2.5"]],
            "ts": 1234567890
        }
    }
    
    await manager.on_orderbook(message)
    
    # Verify orderbook stored
    assert symbol in manager.current_orderbooks
    orderbook = manager.current_orderbooks[symbol]
    assert orderbook.symbol == symbol
    assert len(orderbook.bids) == 2
    assert len(orderbook.asks) == 2
    assert orderbook.timestamp == 1234567890
