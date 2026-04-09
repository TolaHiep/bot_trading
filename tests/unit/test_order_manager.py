"""
Unit tests for Order Manager
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.execution.order_manager import (
    OrderManager,
    Order,
    OrderState,
    OrderSide,
    OrderType,
    Position
)


@pytest.fixture
def mock_rest_client():
    """Mock Bybit REST client"""
    client = AsyncMock()
    return client


@pytest.fixture
def order_manager(mock_rest_client):
    """Create OrderManager instance"""
    return OrderManager(mock_rest_client, max_retries=2, limit_timeout=5)


class TestOrderStateTransitions:
    """Test order state machine transitions"""
    
    def test_order_creation(self):
        """Test order is created in PENDING state"""
        order = Order(
            order_id="test-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            state=OrderState.PENDING
        )
        
        assert order.state == OrderState.PENDING
        assert order.filled_qty == Decimal("0")
        assert order.retry_count == 0
    
    def test_state_transition_pending_to_open(self):
        """Test PENDING → OPEN transition"""
        order = Order(
            order_id="test-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            state=OrderState.PENDING
        )
        
        order.update_state(OrderState.OPEN)
        assert order.state == OrderState.OPEN
    
    def test_state_transition_open_to_partial(self):
        """Test OPEN → PARTIAL transition"""
        order = Order(
            order_id="test-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000"),
            state=OrderState.OPEN
        )
        
        order.update_fill(Decimal("0.5"), Decimal("50000"))
        assert order.state == OrderState.PARTIAL
        assert order.filled_qty == Decimal("0.5")
    
    def test_state_transition_partial_to_filled(self):
        """Test PARTIAL → FILLED transition"""
        order = Order(
            order_id="test-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000"),
            state=OrderState.PARTIAL,
            filled_qty=Decimal("0.5")
        )
        
        order.update_fill(Decimal("1.0"), Decimal("50000"))
        assert order.state == OrderState.FILLED
        assert order.filled_qty == Decimal("1.0")
    
    def test_state_transition_to_rejected(self):
        """Test transition to REJECTED with reason"""
        order = Order(
            order_id="test-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            state=OrderState.PENDING
        )
        
        order.update_state(OrderState.REJECTED, "Insufficient balance")
        assert order.state == OrderState.REJECTED
        assert order.reject_reason == "Insufficient balance"


class TestOrderPlacement:
    """Test order placement functionality"""
    
    @pytest.mark.asyncio
    async def test_place_limit_order_success(self, order_manager, mock_rest_client):
        """Test successful limit order placement"""
        mock_rest_client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "exchange-123"}
        }
        
        order_id = await order_manager.place_limit_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=Decimal("0.1"),
            price=Decimal("50000")
        )
        
        assert order_id == "exchange-123"
        mock_rest_client.place_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_place_limit_order_failure(self, order_manager, mock_rest_client):
        """Test failed limit order placement"""
        mock_rest_client.place_order.return_value = {
            "retCode": 10001,
            "retMsg": "Insufficient balance"
        }
        
        order_id = await order_manager.place_limit_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=Decimal("0.1"),
            price=Decimal("50000")
        )
        
        assert order_id is None
    
    @pytest.mark.asyncio
    async def test_place_market_order_success(self, order_manager, mock_rest_client):
        """Test successful market order placement"""
        mock_rest_client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "exchange-456"}
        }
        
        order_id = await order_manager.place_market_order(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            qty=Decimal("0.1")
        )
        
        assert order_id == "exchange-456"
        mock_rest_client.place_order.assert_called_once()


class TestOrderCancellation:
    """Test order cancellation"""
    
    @pytest.mark.asyncio
    async def test_cancel_order_success(self, order_manager, mock_rest_client):
        """Test successful order cancellation"""
        mock_rest_client.cancel_order.return_value = {
            "retCode": 0,
            "result": {}
        }
        
        result = await order_manager.cancel_order("exchange-123")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_cancel_order_failure(self, order_manager, mock_rest_client):
        """Test failed order cancellation"""
        mock_rest_client.cancel_order.return_value = {
            "retCode": 10001,
            "retMsg": "Order not found"
        }
        
        result = await order_manager.cancel_order("exchange-123")
        assert result is False


class TestOrderVerification:
    """Test order execution verification"""
    
    @pytest.mark.asyncio
    async def test_verify_filled_order(self, order_manager, mock_rest_client):
        """Test verification of filled order"""
        mock_rest_client.get_order_history.return_value = {
            "retCode": 0,
            "result": {
                "list": [{
                    "orderId": "exchange-123",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "qty": "0.1",
                    "price": "50000",
                    "orderStatus": "Filled",
                    "cumExecQty": "0.1",
                    "avgPrice": "50000"
                }]
            }
        }
        
        order = await order_manager.verify_execution("exchange-123")
        
        assert order is not None
        assert order.state == OrderState.FILLED
        assert order.filled_qty == Decimal("0.1")
        assert order.avg_fill_price == Decimal("50000")
    
    @pytest.mark.asyncio
    async def test_verify_partial_order(self, order_manager, mock_rest_client):
        """Test verification of partially filled order"""
        mock_rest_client.get_order_history.return_value = {
            "retCode": 0,
            "result": {
                "list": [{
                    "orderId": "exchange-123",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "qty": "1.0",
                    "price": "50000",
                    "orderStatus": "PartiallyFilled",
                    "cumExecQty": "0.5",
                    "avgPrice": "50000"
                }]
            }
        }
        
        order = await order_manager.verify_execution("exchange-123")
        
        assert order is not None
        assert order.state == OrderState.PARTIAL
        assert order.filled_qty == Decimal("0.5")


class TestWaitForFill:
    """Test wait for fill functionality"""
    
    @pytest.mark.asyncio
    async def test_wait_for_fill_success(self, order_manager, mock_rest_client):
        """Test successful wait for fill"""
        mock_rest_client.get_order_history.return_value = {
            "retCode": 0,
            "result": {
                "list": [{
                    "orderId": "exchange-123",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "qty": "0.1",
                    "price": "50000",
                    "orderStatus": "Filled",
                    "cumExecQty": "0.1",
                    "avgPrice": "50000"
                }]
            }
        }
        
        filled = await order_manager.wait_for_fill("exchange-123", timeout=2)
        assert filled is True
    
    @pytest.mark.asyncio
    async def test_wait_for_fill_timeout(self, order_manager, mock_rest_client):
        """Test wait for fill timeout"""
        mock_rest_client.get_order_history.return_value = {
            "retCode": 0,
            "result": {
                "list": [{
                    "orderId": "exchange-123",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "qty": "0.1",
                    "price": "50000",
                    "orderStatus": "New",
                    "cumExecQty": "0",
                    "avgPrice": "0"
                }]
            }
        }
        
        filled = await order_manager.wait_for_fill("exchange-123", timeout=1)
        assert filled is False


class TestPositionCreation:
    """Test position creation from orders"""
    
    def test_create_position_from_buy_order(self, order_manager):
        """Test position creation from buy order"""
        order = Order(
            order_id="test-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            state=OrderState.FILLED,
            filled_qty=Decimal("0.1"),
            avg_fill_price=Decimal("50000")
        )
        
        position = order_manager._create_position(order)
        
        assert position.symbol == "BTCUSDT"
        assert position.side == OrderSide.BUY
        assert position.quantity == Decimal("0.1")
        assert position.entry_price == Decimal("50000")
    
    def test_create_position_from_sell_order(self, order_manager):
        """Test position creation from sell order"""
        order = Order(
            order_id="test-123",
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("1.0"),
            price=None,
            state=OrderState.FILLED,
            filled_qty=Decimal("1.0"),
            avg_fill_price=Decimal("3000")
        )
        
        position = order_manager._create_position(order)
        
        assert position.symbol == "ETHUSDT"
        assert position.side == OrderSide.SELL
        assert position.quantity == Decimal("1.0")
        assert position.entry_price == Decimal("3000")


class TestPnLCalculation:
    """Test P&L calculation"""
    
    def test_pnl_calculation_long_profit(self):
        """Test P&L calculation for profitable long position"""
        position = Position(
            position_id="pos-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1")
        )
        
        pnl = position.calculate_pnl(Decimal("51000"))
        assert pnl == Decimal("100")  # (51000 - 50000) * 0.1
    
    def test_pnl_calculation_long_loss(self):
        """Test P&L calculation for losing long position"""
        position = Position(
            position_id="pos-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1")
        )
        
        pnl = position.calculate_pnl(Decimal("49000"))
        assert pnl == Decimal("-100")  # (49000 - 50000) * 0.1
    
    def test_pnl_calculation_short_profit(self):
        """Test P&L calculation for profitable short position"""
        position = Position(
            position_id="pos-123",
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1")
        )
        
        pnl = position.calculate_pnl(Decimal("49000"))
        assert pnl == Decimal("100")  # (50000 - 49000) * 0.1
    
    def test_pnl_calculation_short_loss(self):
        """Test P&L calculation for losing short position"""
        position = Position(
            position_id="pos-123",
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1")
        )
        
        pnl = position.calculate_pnl(Decimal("51000"))
        assert pnl == Decimal("-100")  # (50000 - 51000) * 0.1


class TestOrderTracking:
    """Test order tracking functionality"""
    
    @pytest.mark.asyncio
    async def test_track_pending_order(self, order_manager, mock_rest_client):
        """Test tracking of pending order"""
        mock_rest_client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "exchange-123"}
        }
        mock_rest_client.get_order_history.return_value = {
            "retCode": 0,
            "result": {
                "list": [{
                    "orderId": "exchange-123",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Limit",
                    "qty": "0.1",
                    "price": "50000",
                    "orderStatus": "New",
                    "cumExecQty": "0",
                    "avgPrice": "0"
                }]
            }
        }
        
        # Start execution (will timeout)
        task = asyncio.create_task(
            order_manager.execute_signal(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                quantity=Decimal("0.1"),
                limit_price=Decimal("50000")
            )
        )
        
        # Give it time to place order
        await asyncio.sleep(0.1)
        
        # Check pending orders
        assert len(order_manager.pending_orders) > 0
        
        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    def test_get_order_status(self, order_manager):
        """Test getting order status"""
        order = Order(
            order_id="test-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            state=OrderState.OPEN
        )
        
        order_manager.pending_orders["test-123"] = order
        
        status = order_manager.get_order_status("test-123")
        assert status == OrderState.OPEN
    
    def test_get_position(self, order_manager):
        """Test getting position by ID"""
        position = Position(
            position_id="pos-123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1")
        )
        
        order_manager.positions["pos-123"] = position
        
        retrieved = order_manager.get_position("pos-123")
        assert retrieved == position
    
    def test_get_all_positions(self, order_manager):
        """Test getting all positions"""
        pos1 = Position(
            position_id="pos-1",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.1")
        )
        pos2 = Position(
            position_id="pos-2",
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            entry_price=Decimal("3000"),
            quantity=Decimal("1.0")
        )
        
        order_manager.positions["pos-1"] = pos1
        order_manager.positions["pos-2"] = pos2
        
        all_positions = order_manager.get_all_positions()
        assert len(all_positions) == 2
        assert pos1 in all_positions
        assert pos2 in all_positions
