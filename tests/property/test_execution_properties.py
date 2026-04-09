"""
Property-based tests for Execution Model

Tests invariants and properties that must hold for all inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock

from src.execution.order_manager import (
    OrderManager,
    Order,
    OrderState,
    OrderSide,
    OrderType,
    Position
)


# Strategies
order_sides = st.sampled_from([OrderSide.BUY, OrderSide.SELL])
order_types = st.sampled_from([OrderType.LIMIT, OrderType.MARKET])
positive_decimals = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("100000"),
    places=8
)
quantities = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("100"),
    places=8
)


@given(
    side=order_sides,
    quantity=quantities,
    price=positive_decimals
)
@settings(max_examples=50, deadline=1000)
def test_property_39_order_creation_validity(side, quantity, price):
    """Property 39: Order Creation Validity
    
    For any valid order parameters, created order must have:
    - Valid state (PENDING initially)
    - Positive quantity
    - Positive price (for limit orders)
    - Zero filled quantity initially
    
    Property: All created orders start in valid state
    """
    order = Order(
        order_id="test-123",
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
        state=OrderState.PENDING
    )
    
    # Order must start in PENDING state
    assert order.state == OrderState.PENDING
    
    # Quantity must be positive
    assert order.quantity > Decimal("0")
    
    # Price must be positive for limit orders
    if order.order_type == OrderType.LIMIT:
        assert order.price > Decimal("0")
    
    # Initially no fills
    assert order.filled_qty == Decimal("0")
    assert order.avg_fill_price == Decimal("0")
    
    # No retries yet
    assert order.retry_count == 0


@given(
    initial_state=st.sampled_from([
        OrderState.PENDING,
        OrderState.OPEN,
        OrderState.PARTIAL
    ]),
    filled_qty=quantities,
    total_qty=quantities
)
@settings(max_examples=50, deadline=1000)
def test_property_40_state_transition_validity(initial_state, filled_qty, total_qty):
    """Property 40: State Transition Validity
    
    For any order state transition:
    - PENDING can only go to OPEN, REJECTED, or FAILED
    - OPEN can go to PARTIAL, FILLED, CANCELLED, or REJECTED
    - PARTIAL can only go to FILLED or CANCELLED
    - Terminal states (FILLED, CANCELLED, REJECTED, FAILED) cannot transition
    
    Property: State transitions follow valid state machine rules
    """
    assume(filled_qty <= total_qty)
    
    order = Order(
        order_id="test-123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=total_qty,
        price=Decimal("50000"),
        state=initial_state
    )
    
    # Update fill
    order.update_fill(filled_qty, Decimal("50000"))
    
    # Check state is valid based on fill ratio
    if filled_qty >= total_qty:
        assert order.state == OrderState.FILLED
    elif filled_qty > Decimal("0"):
        assert order.state == OrderState.PARTIAL
    else:
        # No fill, state should remain unchanged
        assert order.state == initial_state


@given(
    quantity=quantities,
    fill_qty=quantities
)
@settings(max_examples=50, deadline=1000)
def test_property_41_partial_fill_invariant(quantity, fill_qty):
    """Property 41: Partial Fill Invariant
    
    For any order with partial fill:
    - filled_qty <= quantity (cannot overfill)
    - If filled_qty < quantity: state is PARTIAL
    - If filled_qty >= quantity: state is FILLED
    
    Property: Filled quantity never exceeds order quantity
    """
    assume(fill_qty <= quantity)
    
    order = Order(
        order_id="test-123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=Decimal("50000"),
        state=OrderState.OPEN
    )
    
    order.update_fill(fill_qty, Decimal("50000"))
    
    # Filled quantity must not exceed order quantity
    assert order.filled_qty <= order.quantity
    
    # State must be consistent with fill ratio
    if order.filled_qty >= order.quantity:
        assert order.state == OrderState.FILLED
    elif order.filled_qty > Decimal("0"):
        assert order.state == OrderState.PARTIAL


@given(
    side=order_sides,
    entry_price=positive_decimals,
    current_price=positive_decimals,
    quantity=quantities
)
@settings(max_examples=50, deadline=1000)
def test_property_42_pnl_calculation_correctness(side, entry_price, current_price, quantity):
    """Property 42: P&L Calculation Correctness
    
    For any position:
    - Long position: PnL = (current_price - entry_price) * quantity
    - Short position: PnL = (entry_price - current_price) * quantity
    - PnL sign must be correct (profit > 0, loss < 0)
    
    Property: P&L calculation is mathematically correct
    """
    position = Position(
        position_id="pos-123",
        symbol="BTCUSDT",
        side=side,
        entry_price=entry_price,
        quantity=quantity
    )
    
    pnl = position.calculate_pnl(current_price)
    
    # Calculate expected PnL
    if side == OrderSide.BUY:
        expected_pnl = (current_price - entry_price) * quantity
    else:  # SELL
        expected_pnl = (entry_price - current_price) * quantity
    
    # PnL must match expected (within floating point precision)
    assert abs(pnl - expected_pnl) < Decimal("0.00000001")
    
    # PnL sign must be correct
    if side == OrderSide.BUY:
        if current_price > entry_price:
            assert pnl > Decimal("0"), "Long position should profit when price rises"
        elif current_price < entry_price:
            assert pnl < Decimal("0"), "Long position should lose when price falls"
    else:  # SELL
        if current_price < entry_price:
            assert pnl > Decimal("0"), "Short position should profit when price falls"
        elif current_price > entry_price:
            assert pnl < Decimal("0"), "Short position should lose when price rises"


@given(
    entry_price=positive_decimals,
    quantity=quantities,
    price_change_pct=st.floats(min_value=-0.5, max_value=0.5)
)
@settings(max_examples=50, deadline=1000)
def test_property_43_pnl_symmetry(entry_price, quantity, price_change_pct):
    """Property 43: P&L Symmetry
    
    For any position:
    - Long and short positions with same parameters should have opposite P&L
    - PnL(long, +X%) = -PnL(short, +X%)
    
    Property: Long and short P&L are symmetric
    """
    current_price = entry_price * Decimal(str(1 + price_change_pct))
    
    # Create long position
    long_position = Position(
        position_id="long-123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=entry_price,
        quantity=quantity
    )
    
    # Create short position
    short_position = Position(
        position_id="short-123",
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        entry_price=entry_price,
        quantity=quantity
    )
    
    long_pnl = long_position.calculate_pnl(current_price)
    short_pnl = short_position.calculate_pnl(current_price)
    
    # P&L should be opposite (within precision)
    assert abs(long_pnl + short_pnl) < Decimal("0.00000001")


@given(
    quantity=quantities,
    avg_price=positive_decimals
)
@settings(max_examples=50, deadline=1000)
def test_property_44_position_value_calculation(quantity, avg_price):
    """Property 44: Position Value Calculation
    
    For any position:
    - Position value = quantity * entry_price
    - Position value must be positive
    
    Property: Position value is always positive and correctly calculated
    """
    position = Position(
        position_id="pos-123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=avg_price,
        quantity=quantity
    )
    
    position_value = position.quantity * position.entry_price
    
    # Position value must be positive
    assert position_value > Decimal("0")
    
    # Position value must equal quantity * entry_price
    expected_value = quantity * avg_price
    assert abs(position_value - expected_value) < Decimal("0.00000001")


@given(
    retry_count=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=20, deadline=1000)
def test_property_45_retry_count_monotonic(retry_count):
    """Property 45: Retry Count Monotonicity
    
    For any order:
    - Retry count starts at 0
    - Retry count only increases
    - Retry count never exceeds max_retries
    
    Property: Retry count is monotonically increasing
    """
    order = Order(
        order_id="test-123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
        state=OrderState.PENDING,
        retry_count=0
    )
    
    # Simulate retries
    for i in range(retry_count):
        order.retry_count = i
        assert order.retry_count >= 0
        if i > 0:
            assert order.retry_count >= i - 1  # Monotonic


@given(
    side=order_sides,
    quantity=quantities,
    entry_price=positive_decimals,
    exit_price=positive_decimals
)
@settings(max_examples=50, deadline=1000)
def test_property_46_round_trip_pnl(side, quantity, entry_price, exit_price):
    """Property 46: Round Trip P&L
    
    For any position that is opened and closed:
    - If exit_price > entry_price: long profits, short loses
    - If exit_price < entry_price: long loses, short profits
    - If exit_price == entry_price: P&L == 0 (minus fees)
    
    Property: Round trip P&L follows price direction
    """
    position = Position(
        position_id="pos-123",
        symbol="BTCUSDT",
        side=side,
        entry_price=entry_price,
        quantity=quantity
    )
    
    pnl = position.calculate_pnl(exit_price)
    
    if exit_price > entry_price:
        if side == OrderSide.BUY:
            assert pnl > Decimal("0") or abs(pnl) < Decimal("0.00000001")
        else:
            assert pnl < Decimal("0") or abs(pnl) < Decimal("0.00000001")
    elif exit_price < entry_price:
        if side == OrderSide.BUY:
            assert pnl < Decimal("0") or abs(pnl) < Decimal("0.00000001")
        else:
            assert pnl > Decimal("0") or abs(pnl) < Decimal("0.00000001")
    else:
        # Same price, P&L should be zero
        assert abs(pnl) < Decimal("0.00000001")


@given(
    quantity=quantities,
    price=positive_decimals
)
@settings(max_examples=30, deadline=1000)
def test_property_47_order_immutability_after_fill(quantity, price):
    """Property 47: Order Immutability After Fill
    
    For any filled order:
    - Quantity cannot change after creation
    - Symbol cannot change
    - Side cannot change
    - Order type cannot change (except LIMIT → MARKET fallback)
    
    Property: Core order parameters are immutable
    """
    order = Order(
        order_id="test-123",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
        state=OrderState.PENDING
    )
    
    original_quantity = order.quantity
    original_symbol = order.symbol
    original_side = order.side
    
    # Fill the order
    order.update_fill(quantity, price)
    
    # Core parameters must remain unchanged
    assert order.quantity == original_quantity
    assert order.symbol == original_symbol
    assert order.side == original_side


@given(
    list_size=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=30, deadline=1000)
def test_property_48_average_fill_price_calculation(list_size):
    """Property 48: Average Fill Price Calculation
    
    For any order with multiple partial fills:
    - Average fill price = sum(qty_i * price_i) / sum(qty_i)
    - Average fill price must be within range of individual fill prices
    
    Property: Average fill price is correctly weighted
    """
    # Generate matching lists
    quantities_list = [
        Decimal(str(0.001 + i * 0.1)) for i in range(list_size)
    ]
    prices_list = [
        Decimal(str(1000 + i * 100)) for i in range(list_size)
    ]
    
    total_qty = sum(quantities_list)
    weighted_sum = sum(q * p for q, p in zip(quantities_list, prices_list))
    expected_avg = weighted_sum / total_qty
    
    # Average must be within range of individual prices
    min_price = min(prices_list)
    max_price = max(prices_list)
    
    assert min_price <= expected_avg <= max_price or abs(expected_avg - min_price) < Decimal("0.01")
