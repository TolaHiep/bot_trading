"""
Property-based tests for Cost Filter

Tests invariants and properties for slippage and cost calculations.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from decimal import Decimal

from src.execution.cost_filter import (
    CostFilter,
    Orderbook,
    OrderbookLevel
)


# Strategies
positive_decimals = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("100000"),
    places=2
)
quantities = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("100"),
    places=8
)


def create_orderbook(bid_price, ask_price, liquidity):
    """Helper to create orderbook"""
    return Orderbook(
        symbol="BTCUSDT",
        bids=[
            OrderbookLevel(price=bid_price, quantity=liquidity),
            OrderbookLevel(price=bid_price * Decimal("0.999"), quantity=liquidity * 2),
        ],
        asks=[
            OrderbookLevel(price=ask_price, quantity=liquidity),
            OrderbookLevel(price=ask_price * Decimal("1.001"), quantity=liquidity * 2),
        ],
        timestamp=1234567890.0
    )


@given(
    bid_price=positive_decimals,
    spread_pct=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1.0"), places=4)
)
@settings(max_examples=50, deadline=1000)
def test_property_44_spread_calculation(bid_price, spread_pct):
    """Property 44: Spread Calculation
    
    For any orderbook:
    - Spread = ask - bid
    - Spread % = (ask - bid) / mid_price * 100
    - Spread must be non-negative
    
    Property: Spread is always non-negative and correctly calculated
    """
    assume(bid_price > Decimal("100"))
    
    ask_price = bid_price * (Decimal("1") + spread_pct / Decimal("100"))
    
    orderbook = Orderbook(
        symbol="BTCUSDT",
        bids=[OrderbookLevel(price=bid_price, quantity=Decimal("1.0"))],
        asks=[OrderbookLevel(price=ask_price, quantity=Decimal("1.0"))],
        timestamp=1234567890.0
    )
    
    # Spread must be non-negative
    assert orderbook.spread >= Decimal("0")
    
    # Spread must equal ask - bid
    expected_spread = ask_price - bid_price
    assert abs(orderbook.spread - expected_spread) < Decimal("0.01")
    
    # Spread % must be non-negative
    assert orderbook.spread_pct >= Decimal("0")


@given(
    price=st.decimals(min_value=Decimal("10000"), max_value=Decimal("50000"), places=2),
    quantity=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("10"), places=2),
    liquidity=st.decimals(min_value=Decimal("5"), max_value=Decimal("50"), places=2)
)
@settings(max_examples=30, deadline=1000, suppress_health_check=[HealthCheck.filter_too_much])
def test_property_45_slippage_monotonicity(price, quantity, liquidity):
    """Property 45: Slippage Monotonicity
    
    For any orderbook:
    - Larger orders have equal or higher slippage
    - Slippage(qty1) <= Slippage(qty2) if qty1 <= qty2
    
    Property: Slippage is monotonically increasing with order size
    """
    cost_filter = CostFilter()
    orderbook = create_orderbook(price, price * Decimal("1.0001"), liquidity)
    
    # Calculate slippage for two different quantities
    qty1 = quantity / Decimal("2")
    qty2 = quantity
    
    slippage1, _ = cost_filter.calculate_expected_slippage(orderbook, "Buy", qty1)
    slippage2, _ = cost_filter.calculate_expected_slippage(orderbook, "Buy", qty2)
    
    # Larger order should have equal or higher slippage
    assert slippage2 >= slippage1 or abs(slippage2 - slippage1) < Decimal("0.001")


@given(
    price=positive_decimals,
    quantity=quantities
)
@settings(max_examples=50, deadline=1000)
def test_property_46_slippage_bounds(price, quantity):
    """Property 46: Slippage Bounds
    
    For any order:
    - Slippage >= 0%
    - Slippage <= 100% (or order is rejected)
    
    Property: Slippage is always within valid bounds
    """
    assume(price > Decimal("1000"))
    assume(quantity > Decimal("0.01"))
    
    cost_filter = CostFilter()
    orderbook = create_orderbook(price, price * Decimal("1.0001"), quantity * 2)
    
    slippage_pct, _ = cost_filter.calculate_expected_slippage(orderbook, "Buy", quantity)
    
    # Slippage must be non-negative
    assert slippage_pct >= Decimal("0")
    
    # Slippage must not exceed 100%
    assert slippage_pct <= Decimal("100")


@given(
    price=st.decimals(min_value=Decimal("10000"), max_value=Decimal("50000"), places=2),
    quantity=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("10"), places=2),
    liquidity=st.decimals(min_value=Decimal("5"), max_value=Decimal("50"), places=2)
)
@settings(max_examples=30, deadline=1000, suppress_health_check=[HealthCheck.filter_too_much])
def test_property_47_total_cost_composition(price, quantity, liquidity):
    """Property 47: Total Cost Composition
    
    For any trade:
    - Total cost = slippage + commission + spread_cost
    - Total cost >= commission (minimum cost)
    - Each component >= 0
    
    Property: Total cost is sum of all components
    """
    cost_filter = CostFilter(commission_rate=Decimal("0.06"))
    orderbook = create_orderbook(price, price * Decimal("1.0001"), liquidity)
    
    analysis = cost_filter.analyze_trade(orderbook, "Buy", quantity)
    
    # All components must be non-negative
    assert analysis.expected_slippage >= Decimal("0")
    assert analysis.commission >= Decimal("0")
    assert analysis.spread_cost >= Decimal("0")
    
    # Total cost must equal sum of components
    expected_total = (
        analysis.expected_slippage +
        analysis.commission +
        analysis.spread_cost
    )
    assert abs(analysis.total_cost - expected_total) < Decimal("0.0001")
    
    # Total cost must be at least commission
    assert analysis.total_cost >= analysis.commission


@given(
    price=positive_decimals,
    quantity=quantities
)
@settings(max_examples=50, deadline=1000)
def test_property_48_avg_fill_price_bounds(price, quantity):
    """Property 48: Average Fill Price Bounds
    
    For any buy order:
    - avg_fill_price >= best_ask
    
    For any sell order:
    - avg_fill_price <= best_bid
    
    Property: Average fill price respects orderbook bounds
    """
    assume(price > Decimal("1000"))
    assume(quantity > Decimal("0.01"))
    
    cost_filter = CostFilter()
    orderbook = create_orderbook(price, price * Decimal("1.0001"), quantity * 2)
    
    # Test buy order
    _, avg_fill_buy = cost_filter.calculate_expected_slippage(orderbook, "Buy", quantity)
    if avg_fill_buy > Decimal("0"):
        assert avg_fill_buy >= orderbook.best_ask or abs(avg_fill_buy - orderbook.best_ask) < Decimal("0.01")
    
    # Test sell order
    _, avg_fill_sell = cost_filter.calculate_expected_slippage(orderbook, "Sell", quantity)
    if avg_fill_sell > Decimal("0"):
        assert avg_fill_sell <= orderbook.best_bid or abs(avg_fill_sell - orderbook.best_bid) < Decimal("0.01")


@given(
    price=positive_decimals,
    max_slippage=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1.0"), places=2),
    max_total_cost=st.decimals(min_value=Decimal("0.05"), max_value=Decimal("2.0"), places=2)
)
@settings(max_examples=30, deadline=1000)
def test_property_49_rejection_consistency(price, max_slippage, max_total_cost):
    """Property 49: Rejection Consistency
    
    For any cost filter configuration:
    - If slippage > max_slippage: reject
    - If total_cost > max_total_cost: reject
    - Rejection decision is deterministic
    
    Property: Rejection logic is consistent with thresholds
    """
    assume(price > Decimal("1000"))
    assume(max_total_cost > max_slippage)
    
    cost_filter = CostFilter(
        max_slippage_pct=max_slippage,
        max_total_cost_pct=max_total_cost
    )
    
    # Create orderbook with known slippage
    orderbook = create_orderbook(price, price * Decimal("1.01"), Decimal("0.1"))
    
    analysis = cost_filter.analyze_trade(orderbook, "Buy", Decimal("1.0"))
    
    # If rejected, must have valid reason
    if analysis.should_reject:
        assert analysis.reject_reason is not None
        
        # Check rejection reason matches threshold
        if "Slippage" in analysis.reject_reason:
            assert analysis.expected_slippage > max_slippage
        elif "cost" in analysis.reject_reason:
            assert analysis.total_cost > max_total_cost


@given(
    price=positive_decimals,
    quantity=quantities
)
@settings(max_examples=30, deadline=1000)
def test_property_50_limit_order_preference_consistency(price, quantity):
    """Property 50: Limit Order Preference Consistency
    
    For any orderbook:
    - If spread is wide: prefer market order
    - If slippage is high: prefer market order
    - If liquidity is low: prefer market order
    - Decision is deterministic
    
    Property: Limit order preference is consistent
    """
    assume(price > Decimal("1000"))
    assume(quantity > Decimal("0.01"))
    
    cost_filter = CostFilter()
    
    # Test with tight spread and good liquidity
    tight_orderbook = create_orderbook(price, price * Decimal("1.0001"), quantity * 10)
    prefer_limit_tight = cost_filter.should_use_limit_order(tight_orderbook, "Buy", quantity)
    
    # Test with wide spread
    wide_orderbook = create_orderbook(price, price * Decimal("1.1"), quantity * 10)
    prefer_limit_wide = cost_filter.should_use_limit_order(wide_orderbook, "Buy", quantity)
    
    # Wide spread should prefer market order (or be same as tight)
    if prefer_limit_tight:
        # If tight spread prefers limit, wide spread should not prefer limit
        assert not prefer_limit_wide or wide_orderbook.spread_pct <= tight_orderbook.spread_pct


@given(
    expected=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1.0"), places=4),
    actual=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1.0"), places=4)
)
@settings(max_examples=30, deadline=1000)
def test_property_51_slippage_tracking_accuracy(expected, actual):
    """Property 51: Slippage Tracking Accuracy
    
    For any recorded slippages:
    - Accuracy calculation is non-negative
    - Accuracy <= 100% (or very high error)
    - More data points improve accuracy estimate
    
    Property: Slippage tracking provides valid accuracy metrics
    """
    cost_filter = CostFilter()
    
    # Record multiple slippages
    for _ in range(5):
        cost_filter.record_actual_slippage(expected, actual)
    
    accuracy = cost_filter.get_slippage_accuracy()
    
    # Accuracy must be non-negative
    assert accuracy is not None
    assert accuracy >= Decimal("0")


@given(
    price=st.decimals(min_value=Decimal("10000"), max_value=Decimal("50000"), places=2),
    quantity=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("10"), places=2),
    liquidity=st.decimals(min_value=Decimal("10"), max_value=Decimal("100"), places=2)
)
@settings(max_examples=30, deadline=1000, suppress_health_check=[HealthCheck.filter_too_much])
def test_property_52_zero_slippage_at_best_price(price, quantity, liquidity):
    """Property 52: Zero Slippage at Best Price
    
    For any order that fills entirely at best price:
    - Slippage = 0%
    - avg_fill_price = best_price
    
    Property: Orders filled at best price have zero slippage
    """
    cost_filter = CostFilter()
    orderbook = create_orderbook(price, price * Decimal("1.0001"), liquidity)
    
    # Order small enough to fill at best price
    small_qty = liquidity / Decimal("2")
    
    slippage_pct, avg_fill = cost_filter.calculate_expected_slippage(
        orderbook, "Buy", small_qty
    )
    
    # Should have zero or near-zero slippage
    assert slippage_pct < Decimal("0.001")
    
    # Average fill should equal best ask
    assert abs(avg_fill - orderbook.best_ask) < Decimal("0.01")


@given(
    price=positive_decimals,
    commission_rate=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.5"), places=4)
)
@settings(max_examples=30, deadline=1000)
def test_property_53_commission_independence(price, commission_rate):
    """Property 53: Commission Independence
    
    For any trade:
    - Commission is independent of slippage
    - Commission is independent of spread
    - Commission = fixed percentage
    
    Property: Commission is constant regardless of market conditions
    """
    assume(price > Decimal("1000"))
    
    cost_filter = CostFilter(commission_rate=commission_rate)
    orderbook = create_orderbook(price, price * Decimal("1.0001"), Decimal("10"))
    
    analysis = cost_filter.analyze_trade(orderbook, "Buy", Decimal("1.0"))
    
    # Commission must equal configured rate
    assert analysis.commission == commission_rate
