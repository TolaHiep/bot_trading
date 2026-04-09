"""
Property-Based Tests for Paper Trading

Tests correctness properties for paper trading simulation.
"""

import pytest
import asyncio
from decimal import Decimal
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck

from src.execution.paper_trader import PaperTrader
from src.execution.order_manager import OrderSide
from src.execution.cost_filter import Orderbook, OrderbookLevel


# Strategies
@st.composite
def orderbook_strategy(draw):
    """Generate valid orderbook"""
    symbol = draw(st.sampled_from(["BTCUSDT", "ETHUSDT"]))
    
    # Generate base price
    base_price = draw(st.decimals(
        min_value=1000,
        max_value=100000,
        places=2
    ))
    
    # Generate bids (below base price)
    num_bids = draw(st.integers(min_value=2, max_value=5))
    bids = []
    for i in range(num_bids):
        price = base_price - Decimal(str(i * 10))
        quantity = draw(st.decimals(min_value=1, max_value=100, places=4))
        bids.append(OrderbookLevel(price=price, quantity=quantity))
    
    # Generate asks (above base price)
    num_asks = draw(st.integers(min_value=2, max_value=5))
    asks = []
    for i in range(num_asks):
        price = base_price + Decimal(str((i + 1) * 10))
        quantity = draw(st.decimals(min_value=1, max_value=100, places=4))
        asks.append(OrderbookLevel(price=price, quantity=quantity))
    
    return Orderbook(
        symbol=symbol,
        bids=bids,
        asks=asks,
        timestamp=1234567890.0
    )


@st.composite
def trade_params_strategy(draw):
    """Generate valid trade parameters"""
    side = draw(st.sampled_from([OrderSide.BUY, OrderSide.SELL]))
    quantity = draw(st.decimals(min_value=0.01, max_value=10, places=4))
    
    return {
        "side": side,
        "quantity": quantity
    }


class TestPaperTradingProperties:
    """Property-based tests for Paper Trading"""
    
    @given(
        initial_balance=st.decimals(min_value=1000, max_value=100000, places=2),
        orderbook=orderbook_strategy(),
        trade_params=trade_params_strategy()
    )
    @settings(
        max_examples=50,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_57_paper_trading_slippage_and_commission(
        self,
        initial_balance,
        orderbook,
        trade_params
    ):
        """
        Property 57: Paper Trading Slippage and Commission
        
        For any simulated trade in Paper Trading mode, realistic slippage 
        and commission should be applied to match live trading conditions.
        
        Validates: Requirements 14.4
        """
        # Arrange
        commission_rate = Decimal("0.0006")  # Bybit taker fee
        trader = PaperTrader(
            initial_balance=initial_balance,
            commission_rate=commission_rate
        )
        
        side = trade_params["side"]
        quantity = trade_params["quantity"]
        
        # Calculate expected costs
        if side == OrderSide.BUY:
            expected_price = orderbook.asks[0].price
        else:
            expected_price = orderbook.bids[0].price
        
        position_value = expected_price * quantity
        expected_commission = position_value * commission_rate
        
        # Assume sufficient balance
        assume(position_value + expected_commission <= initial_balance)
        
        # Act
        position = await trader.execute_signal(
            symbol=orderbook.symbol,
            side=side,
            quantity=quantity,
            orderbook=orderbook,
            reason="Property test"
        )
        
        # Assert - if trade executed, verify costs were applied
        if position is not None:
            # Check that trade was recorded
            assert len(trader.trade_history) == 1
            trade = trader.trade_history[0]
            
            # Property 57.1: Commission must be applied
            assert trade.commission > Decimal("0"), \
                "Commission must be applied to paper trades"
            
            # Property 57.2: Commission should match expected rate
            assert abs(trade.commission - expected_commission) / expected_commission < Decimal("0.01"), \
                f"Commission {trade.commission} should match expected {expected_commission}"
            
            # Property 57.3: Slippage must be calculated
            assert trade.slippage >= Decimal("0"), \
                "Slippage must be calculated for paper trades"
            
            # Property 57.4: Balance must be reduced by position value + commission
            expected_balance = initial_balance - position_value - trade.commission
            assert abs(trader.account.current_balance - expected_balance) < Decimal("0.01"), \
                f"Balance {trader.account.current_balance} should be {expected_balance}"
            
            # Property 57.5: Entry price should reflect slippage
            # For BUY: entry price >= best ask (slippage increases price)
            # For SELL: entry price <= best bid (slippage decreases price)
            if side == OrderSide.BUY:
                assert position.entry_price >= orderbook.asks[0].price, \
                    "Buy entry price should include slippage (>= best ask)"
            else:
                assert position.entry_price <= orderbook.bids[0].price, \
                    "Sell entry price should include slippage (<= best bid)"
    
    @given(
        initial_balance=st.decimals(min_value=5000, max_value=50000, places=2),
        orderbook=orderbook_strategy(),
        trade_params=trade_params_strategy()
    )
    @settings(
        max_examples=50,
        deadline=2000,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_58_paper_trading_logging(
        self,
        initial_balance,
        orderbook,
        trade_params
    ):
        """
        Property 58: Paper Trading Logging
        
        For any trade executed in Paper Trading mode, the trade should be 
        logged with complete details for later analysis.
        
        Validates: Requirements 14.7
        """
        # Arrange
        trader = PaperTrader(initial_balance=initial_balance)
        
        side = trade_params["side"]
        quantity = trade_params["quantity"]
        
        # Calculate position value
        if side == OrderSide.BUY:
            price = orderbook.asks[0].price
        else:
            price = orderbook.bids[0].price
        
        position_value = price * quantity
        commission = position_value * trader.commission_rate
        
        # Assume sufficient balance
        assume(position_value + commission <= initial_balance)
        
        # Act
        position = await trader.execute_signal(
            symbol=orderbook.symbol,
            side=side,
            quantity=quantity,
            orderbook=orderbook,
            reason="Test entry reason"
        )
        
        # Assert - if trade executed, verify logging
        if position is not None:
            # Property 58.1: Trade must be logged
            assert len(trader.trade_history) == 1, \
                "Trade must be logged in trade history"
            
            trade = trader.trade_history[0]
            
            # Property 58.2: Trade ID must be present
            assert trade.trade_id is not None and trade.trade_id != "", \
                "Trade must have a unique ID"
            
            # Property 58.3: Timestamp must be recorded
            assert trade.timestamp is not None, \
                "Trade must have a timestamp"
            
            # Property 58.4: Symbol must be logged
            assert trade.symbol == orderbook.symbol, \
                f"Trade symbol {trade.symbol} must match orderbook {orderbook.symbol}"
            
            # Property 58.5: Side must be logged
            assert trade.side == side, \
                f"Trade side {trade.side} must match order side {side}"
            
            # Property 58.6: Entry price must be logged
            assert trade.entry_price > Decimal("0"), \
                "Trade must have a valid entry price"
            
            # Property 58.7: Quantity must be logged
            assert trade.quantity == quantity, \
                f"Trade quantity {trade.quantity} must match order quantity {quantity}"
            
            # Property 58.8: Commission must be logged
            assert trade.commission > Decimal("0"), \
                "Trade must have commission logged"
            
            # Property 58.9: Slippage must be logged
            assert trade.slippage >= Decimal("0"), \
                "Trade must have slippage logged"
            
            # Property 58.10: Status must be logged
            assert trade.status in ["OPEN", "CLOSED"], \
                f"Trade status {trade.status} must be valid"
            
            # Property 58.11: Entry reason must be logged
            assert trade.entry_reason == "Test entry reason", \
                f"Trade entry reason must be logged: {trade.entry_reason}"
            
            # Property 58.12: Trade history can be exported
            history = trader.get_trade_history()
            assert len(history) == 1, \
                "Trade history must be exportable"
            
            # Property 58.13: Exported trade contains all fields
            exported_trade = history[0]
            required_fields = [
                "trade_id", "timestamp", "symbol", "side",
                "entry_price", "quantity", "commission", "slippage",
                "status", "entry_reason"
            ]
            for field in required_fields:
                assert field in exported_trade, \
                    f"Exported trade must contain field: {field}"
    
    @given(
        initial_balance=st.decimals(min_value=5000, max_value=50000, places=2),
        orderbook=orderbook_strategy(),
        trade_params=trade_params_strategy()
    )
    @settings(
        max_examples=30,
        deadline=3000,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    @pytest.mark.asyncio
    async def test_property_58_closed_trade_logging(
        self,
        initial_balance,
        orderbook,
        trade_params
    ):
        """
        Property 58 (Extended): Closed Trade Logging
        
        When a position is closed, the trade log should be updated with 
        exit details including exit price, P&L, and exit reason.
        """
        # Arrange
        trader = PaperTrader(initial_balance=initial_balance)
        
        side = trade_params["side"]
        quantity = trade_params["quantity"]
        
        # Calculate position value
        if side == OrderSide.BUY:
            price = orderbook.asks[0].price
        else:
            price = orderbook.bids[0].price
        
        position_value = price * quantity
        commission = position_value * trader.commission_rate
        
        # Assume sufficient balance
        assume(position_value + commission <= initial_balance)
        
        # Act - Open position
        position = await trader.execute_signal(
            symbol=orderbook.symbol,
            side=side,
            quantity=quantity,
            orderbook=orderbook,
            reason="Entry reason"
        )
        
        if position is None:
            return  # Trade rejected, skip test
        
        # Act - Close position
        pnl = await trader.close_position(
            position_id=position.position_id,
            orderbook=orderbook,
            reason="Exit reason"
        )
        
        # Assert
        assert pnl is not None, "Position should be closed successfully"
        
        # Property 58.14: Trade status updated to CLOSED
        trade = trader.trade_history[0]
        assert trade.status == "CLOSED", \
            f"Trade status should be CLOSED, got {trade.status}"
        
        # Property 58.15: Exit price must be logged
        assert trade.exit_price is not None, \
            "Exit price must be logged"
        assert trade.exit_price > Decimal("0"), \
            "Exit price must be positive"
        
        # Property 58.16: P&L must be logged
        assert trade.pnl is not None, \
            "P&L must be logged"
        
        # Property 58.17: Exit reason must be logged
        assert trade.exit_reason == "Exit reason", \
            f"Exit reason must be logged: {trade.exit_reason}"
        
        # Property 58.18: Account statistics updated
        assert trader.account.realized_pnl != Decimal("0"), \
            "Realized P&L should be updated"
        
        total_trades = trader.account.winning_trades + trader.account.losing_trades
        assert total_trades == 1, \
            "Trade should be counted as winning or losing"
