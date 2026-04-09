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
