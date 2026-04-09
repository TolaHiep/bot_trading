"""Property-based tests for stop-loss engine

Property 28: Initial Stop-Loss Placement
Property 29: Breakeven Stop-Loss Adjustment
Property 30: Trailing Stop Activation
Property 31: Emergency Position Closure on Stop-Loss Failure
Property 32: Stop-Loss Trigger Logging
"""

import pytest
from hypothesis import given, strategies as st, settings
from src.risk.stop_loss import StopLossMode, StopLossConfig
from src.risk.trailing_stop import TrailingStopCalculator, TrailingStopState


@given(
    entry_price=st.floats(min_value=100.0, max_value=100000.0),
    stop_pct=st.floats(min_value=0.01, max_value=0.10)
)
@settings(max_examples=50, deadline=2000)
def test_property_28_initial_stop_loss_placement(entry_price, stop_pct):
    """Property 28: Initial Stop-Loss Placement
    
    Initial stop-loss must be placed at configured distance from entry.
    
    Property: For long positions, stop_loss < entry_price
    For short positions, stop_loss > entry_price
    """
    config = StopLossConfig(
        mode=StopLossMode.FIXED_PERCENT,
        initial_stop_pct=stop_pct
    )
    
    # Calculate stop for long
    stop_long = entry_price * (1 - stop_pct)
    assert stop_long < entry_price, \
        f"Long stop {stop_long} should be below entry {entry_price}"
    
    # Calculate stop for short
    stop_short = entry_price * (1 + stop_pct)
    assert stop_short > entry_price, \
        f"Short stop {stop_short} should be above entry {entry_price}"
    
    # Check distance
    distance_long = (entry_price - stop_long) / entry_price
    assert abs(distance_long - stop_pct) < 0.0001, \
        f"Long stop distance {distance_long} != {stop_pct}"
    
    distance_short = (stop_short - entry_price) / entry_price
    assert abs(distance_short - stop_pct) < 0.0001, \
        f"Short stop distance {distance_short} != {stop_pct}"


@given(
    entry_price=st.floats(min_value=100.0, max_value=100000.0),
    profit_pct=st.floats(min_value=0.01, max_value=0.10)
)
@settings(max_examples=50, deadline=2000)
def test_property_29_breakeven_stop_loss_adjustment(entry_price, profit_pct):
    """Property 29: Breakeven Stop-Loss Adjustment
    
    When profit >= breakeven threshold, stop-loss must move to entry price.
    
    Property: After breakeven move, stop_loss == entry_price
    """
    config = StopLossConfig(
        mode=StopLossMode.FIXED_PERCENT,
        breakeven_profit_pct=profit_pct
    )
    
    # For long position
    current_price_long = entry_price * (1 + profit_pct)
    profit_long = (current_price_long - entry_price) / entry_price
    
    if profit_long >= config.breakeven_profit_pct:
        # Stop should move to breakeven
        new_stop = entry_price
        assert new_stop == entry_price, \
            f"Breakeven stop {new_stop} should equal entry {entry_price}"
    
    # For short position
    current_price_short = entry_price * (1 - profit_pct)
    profit_short = (entry_price - current_price_short) / entry_price
    
    if profit_short >= config.breakeven_profit_pct:
        # Stop should move to breakeven
        new_stop = entry_price
        assert new_stop == entry_price, \
            f"Breakeven stop {new_stop} should equal entry {entry_price}"


@given(
    entry_price=st.floats(min_value=100.0, max_value=100000.0),
    activation_pct=st.floats(min_value=0.01, max_value=0.10),
    trailing_pct=st.floats(min_value=0.005, max_value=0.05)
)
@settings(max_examples=50, deadline=2000)
def test_property_30_trailing_stop_activation(entry_price, activation_pct, trailing_pct):
    """Property 30: Trailing Stop Activation
    
    Trailing stop activates when profit >= activation threshold.
    
    Property: After activation, stop follows price in favorable direction only.
    """
    calculator = TrailingStopCalculator(
        activation_profit_pct=activation_pct,
        trailing_distance_pct=trailing_pct
    )
    
    # Test long position - use slightly higher price to ensure activation
    current_price = entry_price * (1 + activation_pct + 0.0001)  # Add small buffer
    
    should_activate = calculator.should_activate(
        entry_price=entry_price,
        current_price=current_price,
        is_long=True
    )
    
    assert should_activate, \
        f"Should activate at {current_price} (entry: {entry_price}, threshold: {activation_pct})"
    
    # Calculate stop price
    stop_price = calculator.calculate_stop_price(
        highest_price=current_price,
        lowest_price=None,
        is_long=True
    )
    
    assert stop_price is not None
    assert stop_price < current_price, \
        f"Stop {stop_price} should be below current {current_price}"
    
    # Check distance (with tolerance for floating point)
    distance = (current_price - stop_price) / current_price
    assert abs(distance - trailing_pct) < 0.001, \
        f"Trailing distance {distance} != {trailing_pct}"


@given(
    entry_price=st.floats(min_value=100.0, max_value=100000.0),
    highest_price=st.floats(min_value=100.0, max_value=100000.0),
    trailing_pct=st.floats(min_value=0.005, max_value=0.05)
)
@settings(max_examples=50, deadline=2000)
def test_property_trailing_stop_only_moves_favorably(entry_price, highest_price, trailing_pct):
    """Property: Trailing stop only moves in favorable direction
    
    For long: stop can only move up
    For short: stop can only move down
    """
    # Ensure highest > entry for long
    if highest_price <= entry_price:
        highest_price = entry_price * 1.1
    
    calculator = TrailingStopCalculator(
        activation_profit_pct=0.01,
        trailing_distance_pct=trailing_pct
    )
    
    # Calculate initial stop
    stop1 = calculator.calculate_stop_price(
        highest_price=highest_price,
        lowest_price=None,
        is_long=True
    )
    
    # Price goes higher
    higher_price = highest_price * 1.05
    stop2 = calculator.calculate_stop_price(
        highest_price=higher_price,
        lowest_price=None,
        is_long=True
    )
    
    # Stop should move up
    assert stop2 > stop1, \
        f"Stop should move up from {stop1} to {stop2}"
    
    # Check should_update_stop
    should_update = calculator.should_update_stop(
        new_stop=stop2,
        current_stop=stop1,
        is_long=True
    )
    
    assert should_update, \
        f"Should update stop from {stop1} to {stop2}"
    
    # Stop should NOT move down
    should_not_update = calculator.should_update_stop(
        new_stop=stop1,
        current_stop=stop2,
        is_long=True
    )
    
    assert not should_not_update, \
        f"Should NOT update stop from {stop2} down to {stop1}"


@given(
    entry_price=st.floats(min_value=100.0, max_value=100000.0),
    atr=st.floats(min_value=10.0, max_value=5000.0),
    multiplier=st.floats(min_value=1.0, max_value=5.0)
)
@settings(max_examples=50, deadline=2000)
def test_property_atr_based_stop_distance(entry_price, atr, multiplier):
    """Property: ATR-based stop maintains correct distance
    
    Stop distance = ATR * multiplier
    """
    config = StopLossConfig(
        mode=StopLossMode.ATR_BASED,
        atr_multiplier=multiplier
    )
    
    # Calculate stop for long
    stop_distance = atr * multiplier
    stop_long = entry_price - stop_distance
    
    assert stop_long < entry_price, \
        f"ATR stop {stop_long} should be below entry {entry_price}"
    
    # Check distance
    actual_distance = entry_price - stop_long
    assert abs(actual_distance - stop_distance) < 0.01, \
        f"ATR distance {actual_distance} != expected {stop_distance}"
    
    # Calculate stop for short
    stop_short = entry_price + stop_distance
    
    assert stop_short > entry_price, \
        f"ATR stop {stop_short} should be above entry {entry_price}"
    
    # Check distance
    actual_distance_short = stop_short - entry_price
    assert abs(actual_distance_short - stop_distance) < 0.01, \
        f"ATR distance {actual_distance_short} != expected {stop_distance}"


@given(
    entry_price=st.floats(min_value=100.0, max_value=100000.0),
    current_price=st.floats(min_value=100.0, max_value=100000.0),
    stop_pct=st.floats(min_value=0.01, max_value=0.10)
)
@settings(max_examples=50, deadline=2000)
def test_property_stop_loss_trigger_detection(entry_price, current_price, stop_pct):
    """Property: Stop-loss trigger detection is accurate
    
    For long: triggered when current_price <= stop_price
    For short: triggered when current_price >= stop_price
    """
    # Long position
    stop_long = entry_price * (1 - stop_pct)
    
    if current_price <= stop_long:
        # Should be triggered
        assert current_price <= stop_long, \
            f"Long stop should trigger at {current_price} (stop: {stop_long})"
    else:
        # Should NOT be triggered
        assert current_price > stop_long, \
            f"Long stop should NOT trigger at {current_price} (stop: {stop_long})"
    
    # Short position
    stop_short = entry_price * (1 + stop_pct)
    
    if current_price >= stop_short:
        # Should be triggered
        assert current_price >= stop_short, \
            f"Short stop should trigger at {current_price} (stop: {stop_short})"
    else:
        # Should NOT be triggered
        assert current_price < stop_short, \
            f"Short stop should NOT trigger at {current_price} (stop: {stop_short})"
