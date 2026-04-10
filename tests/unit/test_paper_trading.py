"""
Unit tests for Paper Trading
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime

from src.execution.paper_trader import PaperTrader, SimulatedAccount
from src.execution.order_manager import OrderSide
from src.execution.cost_filter import Orderbook, OrderbookLevel
from src.execution.mode_switcher import ModeSwitcher, SafeModeSwitcher, TradingMode
from src.risk.position_manager import PositionManager


@pytest.fixture
def sample_orderbook():
    """Create sample orderbook"""
    return Orderbook(
        symbol="BTCUSDT",
        bids=[
            OrderbookLevel(price=Decimal("50000"), quantity=Decimal("10.0")),
            OrderbookLevel(price=Decimal("49990"), quantity=Decimal("20.0")),
        ],
        asks=[
            OrderbookLevel(price=Decimal("50010"), quantity=Decimal("10.0")),
            OrderbookLevel(price=Decimal("50020"), quantity=Decimal("20.0")),
        ],
        timestamp=1234567890.0
    )


class TestPaperTrader:
    """Test Paper Trader functionality"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test paper trader initialization"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        assert trader.account.initial_balance == Decimal("10000")
        assert trader.account.current_balance == Decimal("10000")
        assert trader.account.total_trades == 0
        assert len(trader.positions) == 0
    
    @pytest.mark.asyncio
    async def test_execute_buy_signal(self, sample_orderbook):
        """Test executing buy signal"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Test signal"
        )
        
        assert position is not None
        assert position.symbol == "BTCUSDT"
        assert position.side == OrderSide.BUY
        assert position.quantity == Decimal("0.1")
        assert trader.account.total_trades == 1
        assert len(trader.positions) == 1
    
    @pytest.mark.asyncio
    async def test_execute_sell_signal(self, sample_orderbook):
        """Test executing sell signal"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Test signal"
        )
        
        assert position is not None
        assert position.side == OrderSide.SELL
    
    @pytest.mark.asyncio
    async def test_insufficient_balance(self, sample_orderbook):
        """Test rejection due to insufficient balance"""
        trader = PaperTrader(initial_balance=Decimal("100"))
        
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("10.0"),  # Too large
            orderbook=sample_orderbook,
            reason="Test signal"
        )
        
        assert position is None
        assert trader.account.total_trades == 0
    
    @pytest.mark.asyncio
    async def test_close_position(self, sample_orderbook):
        """Test closing position"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # Open position
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Entry"
        )
        
        assert position is not None
        position_id = position.position_id
        
        # Close position
        pnl = await trader.close_position(
            position_id=position_id,
            orderbook=sample_orderbook,
            reason="Exit"
        )
        
        assert pnl is not None
        assert len(trader.positions) == 0
        assert trader.account.realized_pnl != Decimal("0")
    
    @pytest.mark.asyncio
    async def test_winning_trade(self, sample_orderbook):
        """Test winning trade tracking"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # Open position
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Entry"
        )
        
        # Create orderbook with higher price
        exit_orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("51000"), quantity=Decimal("10.0")),
            ],
            asks=[
                OrderbookLevel(price=Decimal("51010"), quantity=Decimal("10.0")),
            ],
            timestamp=1234567890.0
        )
        
        # Close position at profit
        pnl = await trader.close_position(
            position_id=position.position_id,
            orderbook=exit_orderbook,
            reason="Take profit"
        )
        
        assert pnl > Decimal("0")
        assert trader.account.winning_trades == 1
        assert trader.account.losing_trades == 0
    
    @pytest.mark.asyncio
    async def test_losing_trade(self, sample_orderbook):
        """Test losing trade tracking"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # Open position
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Entry"
        )
        
        # Create orderbook with lower price
        exit_orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("49000"), quantity=Decimal("10.0")),
            ],
            asks=[
                OrderbookLevel(price=Decimal("49010"), quantity=Decimal("10.0")),
            ],
            timestamp=1234567890.0
        )
        
        # Close position at loss
        pnl = await trader.close_position(
            position_id=position.position_id,
            orderbook=exit_orderbook,
            reason="Stop loss"
        )
        
        assert pnl < Decimal("0")
        assert trader.account.winning_trades == 0
        assert trader.account.losing_trades == 1
    
    def test_get_account_summary(self):
        """Test account summary"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        summary = trader.get_account_summary()
        
        assert summary["initial_balance"] == 10000.0
        assert summary["current_balance"] == 10000.0
        assert summary["total_trades"] == 0
        assert summary["win_rate"] == 0
    
    def test_get_trade_history(self):
        """Test trade history retrieval"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        history = trader.get_trade_history()
        
        assert isinstance(history, list)
        assert len(history) == 0
    
    def test_reset(self):
        """Test paper trader reset"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        trader.account.current_balance = Decimal("5000")
        trader.account.total_trades = 10
        
        trader.reset()
        
        assert trader.account.current_balance == Decimal("10000")
        assert trader.account.total_trades == 0
        assert len(trader.positions) == 0
    
    @pytest.mark.asyncio
    async def test_has_open_position(self, sample_orderbook):
        """Test checking for open position by symbol"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # No position initially
        assert not trader.has_open_position("BTCUSDT")
        
        # Open position
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Test"
        )
        
        # Position exists
        assert trader.has_open_position("BTCUSDT")
        assert not trader.has_open_position("ETHUSDT")
    
    @pytest.mark.asyncio
    async def test_get_position_by_symbol(self, sample_orderbook):
        """Test getting position by symbol"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # No position initially
        assert trader.get_position_by_symbol("BTCUSDT") is None
        
        # Open position
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Test"
        )
        
        # Get position
        retrieved = trader.get_position_by_symbol("BTCUSDT")
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"
        assert retrieved.position_id == position.position_id
    
    @pytest.mark.asyncio
    async def test_get_all_positions(self, sample_orderbook):
        """Test getting all positions"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # No positions initially
        assert len(trader.get_all_positions()) == 0
        
        # Open first position
        await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Test"
        )
        
        # Open second position (different symbol)
        eth_orderbook = Orderbook(
            symbol="ETHUSDT",
            bids=[OrderbookLevel(price=Decimal("3000"), quantity=Decimal("10.0"))],
            asks=[OrderbookLevel(price=Decimal("3001"), quantity=Decimal("10.0"))],
            timestamp=1234567890.0
        )
        await trader.execute_signal(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("1.0"),
            orderbook=eth_orderbook,
            reason="Test"
        )
        
        # Get all positions
        positions = trader.get_all_positions()
        assert len(positions) == 2
        symbols = {pos.symbol for pos in positions}
        assert symbols == {"BTCUSDT", "ETHUSDT"}
    
    @pytest.mark.asyncio
    async def test_close_position_by_symbol(self, sample_orderbook):
        """Test closing position by symbol"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # Open position
        await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Entry"
        )
        
        # Close by symbol
        pnl = await trader.close_position_by_symbol(
            symbol="BTCUSDT",
            orderbook=sample_orderbook,
            reason="Exit"
        )
        
        assert pnl is not None
        assert not trader.has_open_position("BTCUSDT")
        assert len(trader.positions) == 0
    
    @pytest.mark.asyncio
    async def test_close_position_by_symbol_not_found(self, sample_orderbook):
        """Test closing position by symbol when not found"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # Try to close non-existent position
        pnl = await trader.close_position_by_symbol(
            symbol="BTCUSDT",
            orderbook=sample_orderbook,
            reason="Exit"
        )
        
        assert pnl is None
    
    @pytest.mark.asyncio
    async def test_prevent_multiple_positions_same_symbol(self, sample_orderbook):
        """Test prevention of multiple positions on same symbol"""
        trader = PaperTrader(initial_balance=Decimal("10000"))
        
        # Open first position
        position1 = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="First"
        )
        
        assert position1 is not None
        
        # Try to open second position on same symbol
        position2 = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            orderbook=sample_orderbook,
            reason="Second"
        )
        
        assert position2 is None
        assert len(trader.positions) == 1


class TestModeSwitcher:
    """Test Mode Switcher functionality"""
    
    def test_initialization_paper_mode(self):
        """Test initialization in paper mode"""
        switcher = ModeSwitcher()
        
        assert switcher.current_mode == TradingMode.PAPER
        assert switcher.is_paper_mode
        assert not switcher.is_live_mode
    
    def test_initialization_live_mode(self):
        """Test initialization in live mode"""
        switcher = ModeSwitcher(initial_mode=TradingMode.LIVE)
        
        assert switcher.current_mode == TradingMode.LIVE
        assert switcher.is_live_mode
        assert not switcher.is_paper_mode
    
    def test_request_live_mode(self):
        """Test requesting live mode"""
        switcher = ModeSwitcher()
        
        token = switcher.request_live_mode()
        
        assert token != ""
        assert len(token) == 32  # 16 bytes hex = 32 chars
        assert switcher.current_mode == TradingMode.PAPER  # Not activated yet
    
    def test_activate_live_mode_success(self):
        """Test successful live mode activation"""
        switcher = ModeSwitcher()
        
        token = switcher.request_live_mode()
        result = switcher.activate_live_mode(
            confirmation_token=token,
            explicit_confirmation=True
        )
        
        assert result is True
        assert switcher.is_live_mode
    
    def test_activate_live_mode_no_confirmation(self):
        """Test live mode activation without explicit confirmation"""
        switcher = ModeSwitcher()
        
        token = switcher.request_live_mode()
        
        with pytest.raises(ValueError, match="explicit_confirmation must be True"):
            switcher.activate_live_mode(
                confirmation_token=token,
                explicit_confirmation=False
            )
    
    def test_activate_live_mode_invalid_token(self):
        """Test live mode activation with invalid token"""
        switcher = ModeSwitcher()
        
        switcher.request_live_mode()
        
        with pytest.raises(ValueError, match="Invalid confirmation token"):
            switcher.activate_live_mode(
                confirmation_token="invalid_token",
                explicit_confirmation=True
            )
    
    def test_activate_live_mode_no_request(self):
        """Test live mode activation without request"""
        switcher = ModeSwitcher()
        
        with pytest.raises(ValueError, match="No confirmation token found"):
            switcher.activate_live_mode(
                confirmation_token="any_token",
                explicit_confirmation=True
            )
    
    def test_switch_to_paper_mode(self):
        """Test switching to paper mode"""
        switcher = ModeSwitcher(initial_mode=TradingMode.LIVE)
        
        result = switcher.switch_to_paper_mode()
        
        assert result is True
        assert switcher.is_paper_mode
    
    def test_switch_to_paper_mode_already_paper(self):
        """Test switching to paper mode when already in paper"""
        switcher = ModeSwitcher()
        
        result = switcher.switch_to_paper_mode()
        
        assert result is False
        assert switcher.is_paper_mode
    
    def test_get_mode_info(self):
        """Test getting mode information"""
        switcher = ModeSwitcher()
        
        info = switcher.get_mode_info()
        
        assert info["current_mode"] == "PAPER"
        assert info["is_paper"] is True
        assert info["is_live"] is False
        assert info["has_pending_confirmation"] is False


class TestSafeModeSwitcher:
    """Test Safe Mode Switcher functionality"""
    
    def test_activate_live_mode_without_env_var(self):
        """Test live mode activation without environment variable"""
        switcher = SafeModeSwitcher(require_env_var=True)
        
        token = switcher.request_live_mode()
        
        with pytest.raises(ValueError, match="Live trading not enabled"):
            switcher.activate_live_mode(
                confirmation_token=token,
                explicit_confirmation=True
            )
    
    def test_activate_live_mode_with_env_var(self, monkeypatch):
        """Test live mode activation with environment variable"""
        monkeypatch.setenv("ENABLE_LIVE_TRADING", "true")
        
        switcher = SafeModeSwitcher(require_env_var=True)
        
        token = switcher.request_live_mode()
        result = switcher.activate_live_mode(
            confirmation_token=token,
            explicit_confirmation=True
        )
        
        assert result is True
        assert switcher.is_live_mode
    
    def test_activate_live_mode_no_env_check(self):
        """Test live mode activation without env var check"""
        switcher = SafeModeSwitcher(require_env_var=False)
        
        token = switcher.request_live_mode()
        result = switcher.activate_live_mode(
            confirmation_token=token,
            explicit_confirmation=True
        )
        
        assert result is True
        assert switcher.is_live_mode


class TestPaperTraderWithPositionManager:
    """Test PaperTrader integration with PositionManager"""
    
    @pytest.mark.asyncio
    async def test_position_manager_integration(self, sample_orderbook):
        """Test PaperTrader with PositionManager for capital allocation"""
        initial_balance = Decimal("10000")
        position_manager = PositionManager(
            initial_equity=initial_balance,
            max_position_pct=Decimal("0.05"),  # 5% per position
            max_exposure_pct=Decimal("0.80")   # 80% total exposure
        )
        trader = PaperTrader(
            initial_balance=initial_balance,
            position_manager=position_manager
        )
        
        # Open position - should succeed
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.009"),  # Small position (0.009 * 50010 = 450.09 < 500)
            orderbook=sample_orderbook,
            reason="Test"
        )
        
        assert position is not None
        assert position_manager.get_position_count() == 1
        assert "BTCUSDT" in position_manager.get_positions_by_symbol()
    
    @pytest.mark.asyncio
    async def test_position_manager_rejects_duplicate_symbol(self, sample_orderbook):
        """Test PositionManager rejects duplicate symbol positions"""
        initial_balance = Decimal("10000")
        position_manager = PositionManager(
            initial_equity=initial_balance,
            max_position_pct=Decimal("0.05"),
            max_exposure_pct=Decimal("0.80")
        )
        trader = PaperTrader(
            initial_balance=initial_balance,
            position_manager=position_manager
        )
        
        # Open first position
        position1 = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.009"),
            orderbook=sample_orderbook,
            reason="First"
        )
        
        assert position1 is not None
        
        # Try to open second position on same symbol - should be rejected
        position2 = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.009"),
            orderbook=sample_orderbook,
            reason="Second"
        )
        
        assert position2 is None
        assert position_manager.get_position_count() == 1
    
    @pytest.mark.asyncio
    async def test_position_manager_enforces_position_limit(self, sample_orderbook):
        """Test PositionManager enforces per-position size limit"""
        initial_balance = Decimal("10000")
        position_manager = PositionManager(
            initial_equity=initial_balance,
            max_position_pct=Decimal("0.05"),  # 5% = $500 max per position
            max_exposure_pct=Decimal("0.80")
        )
        trader = PaperTrader(
            initial_balance=initial_balance,
            position_manager=position_manager
        )
        
        # Try to open position larger than 5% of equity
        # Position value = 0.02 * 50010 = 1000.2 > 500 (5% of 10000)
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.02"),  # Too large
            orderbook=sample_orderbook,
            reason="Test"
        )
        
        assert position is None
        assert position_manager.get_position_count() == 0
    
    @pytest.mark.asyncio
    async def test_position_manager_close_removes_position(self, sample_orderbook):
        """Test closing position removes it from PositionManager"""
        initial_balance = Decimal("10000")
        position_manager = PositionManager(
            initial_equity=initial_balance,
            max_position_pct=Decimal("0.05"),
            max_exposure_pct=Decimal("0.80")
        )
        trader = PaperTrader(
            initial_balance=initial_balance,
            position_manager=position_manager
        )
        
        # Open position
        position = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.009"),
            orderbook=sample_orderbook,
            reason="Entry"
        )
        
        assert position is not None
        assert position_manager.get_position_count() == 1
        
        # Close position
        pnl = await trader.close_position(
            position_id=position.position_id,
            orderbook=sample_orderbook,
            reason="Exit"
        )
        
        assert pnl is not None
        assert position_manager.get_position_count() == 0
        assert "BTCUSDT" not in position_manager.get_positions_by_symbol()
    
    @pytest.mark.asyncio
    async def test_position_manager_multiple_symbols(self, sample_orderbook):
        """Test PositionManager with multiple symbols"""
        initial_balance = Decimal("10000")
        position_manager = PositionManager(
            initial_equity=initial_balance,
            max_position_pct=Decimal("0.05"),
            max_exposure_pct=Decimal("0.80")
        )
        trader = PaperTrader(
            initial_balance=initial_balance,
            position_manager=position_manager
        )
        
        # Open first position
        position1 = await trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.009"),
            orderbook=sample_orderbook,
            reason="Test"
        )
        
        # Open second position (different symbol)
        eth_orderbook = Orderbook(
            symbol="ETHUSDT",
            bids=[OrderbookLevel(price=Decimal("3000"), quantity=Decimal("10.0"))],
            asks=[OrderbookLevel(price=Decimal("3001"), quantity=Decimal("10.0"))],
            timestamp=1234567890.0
        )
        position2 = await trader.execute_signal(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.15"),  # Small position
            orderbook=eth_orderbook,
            reason="Test"
        )
        
        assert position1 is not None
        assert position2 is not None
        assert position_manager.get_position_count() == 2
        assert "BTCUSDT" in position_manager.get_positions_by_symbol()
        assert "ETHUSDT" in position_manager.get_positions_by_symbol()
