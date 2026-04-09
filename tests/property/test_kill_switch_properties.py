"""Property-based tests for kill switch

Property 33: Kill Switch Activation on Daily Drawdown
Property 34: Kill Switch Activation on Consecutive Losses
Property 35: Kill Switch Activation on API Error Rate
Property 36: Kill Switch Activation on Abnormal Price Movement
Property 37: Kill Switch Alert Notification
Property 38: Kill Switch Activation Logging
"""

import pytest
from hypothesis import given, strategies as st, settings
from src.risk.kill_switch import KillSwitch, KillSwitchConfig, KillSwitchReason
from src.risk.drawdown_monitor import DrawdownMonitor


@given(
    starting_balance=st.floats(min_value=1000.0, max_value=100000.0),
    drawdown_pct=st.floats(min_value=0.06, max_value=0.50)
)
@settings(max_examples=50, deadline=2000)
@pytest.mark.asyncio
async def test_property_33_kill_switch_activation_on_daily_drawdown(
    starting_balance, drawdown_pct
):
    """Property 33: Kill Switch Activation on Daily Drawdown
    
    Kill switch must activate when daily drawdown exceeds threshold.
    
    Property: For drawdown > 5%, kill switch activates
    """
    config = KillSwitchConfig(max_daily_drawdown=0.05)
    kill_switch = KillSwitch(config)
    
    current_balance = starting_balance * (1 - drawdown_pct)
    
    activated = await kill_switch.check_daily_drawdown(
        current_balance, starting_balance
    )
    
    # Should activate if drawdown > 5%
    if drawdown_pct > 0.05:
        assert activated, \
            f"Should activate with {drawdown_pct*100:.2f}% drawdown"
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.DAILY_DRAWDOWN
    else:
        assert not activated, \
            f"Should NOT activate with {drawdown_pct*100:.2f}% drawdown"


@given(
    consecutive_losses=st.integers(min_value=0, max_value=20)
)
@settings(max_examples=50, deadline=2000)
@pytest.mark.asyncio
async def test_property_34_kill_switch_activation_on_consecutive_losses(
    consecutive_losses
):
    """Property 34: Kill Switch Activation on Consecutive Losses
    
    Kill switch must activate when consecutive losses >= threshold.
    
    Property: For losses >= 5, kill switch activates
    """
    config = KillSwitchConfig(max_consecutive_losses=5)
    kill_switch = KillSwitch(config)
    
    activated = await kill_switch.check_consecutive_losses(consecutive_losses)
    
    # Should activate if losses >= 5
    if consecutive_losses >= 5:
        assert activated, \
            f"Should activate with {consecutive_losses} consecutive losses"
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.CONSECUTIVE_LOSSES
    else:
        assert not activated, \
            f"Should NOT activate with {consecutive_losses} consecutive losses"


@given(
    error_count=st.integers(min_value=0, max_value=50),
    total_requests=st.integers(min_value=1, max_value=100)
)
@settings(max_examples=50, deadline=2000)
@pytest.mark.asyncio
async def test_property_35_kill_switch_activation_on_api_error_rate(
    error_count, total_requests
):
    """Property 35: Kill Switch Activation on API Error Rate
    
    Kill switch must activate when API error rate > threshold.
    
    Property: For error rate > 20%, kill switch activates
    """
    config = KillSwitchConfig(max_api_error_rate=0.20)
    kill_switch = KillSwitch(config)
    
    # Record errors
    for _ in range(min(error_count, total_requests)):
        kill_switch.record_api_error("Test error")
    
    activated = await kill_switch.check_api_error_rate(total_requests)
    
    error_rate = error_count / total_requests if total_requests > 0 else 0
    
    # Should activate if error rate > 20%
    if error_rate > 0.20:
        assert activated, \
            f"Should activate with {error_rate*100:.2f}% error rate"
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.API_ERROR_RATE
    else:
        assert not activated, \
            f"Should NOT activate with {error_rate*100:.2f}% error rate"


@given(
    start_price=st.floats(min_value=100.0, max_value=100000.0),
    movement_pct=st.floats(min_value=0.01, max_value=0.50)
)
@settings(max_examples=50, deadline=2000)
@pytest.mark.asyncio
async def test_property_36_kill_switch_activation_on_abnormal_price_movement(
    start_price, movement_pct
):
    """Property 36: Kill Switch Activation on Abnormal Price Movement
    
    Kill switch must activate when price movement > threshold.
    
    Property: For movement > 10%, kill switch activates
    """
    config = KillSwitchConfig(max_price_movement=0.10)
    kill_switch = KillSwitch(config)
    
    # Record prices
    kill_switch.record_price(start_price)
    end_price = start_price * (1 + movement_pct)
    kill_switch.record_price(end_price)
    
    activated = await kill_switch.check_price_movement()
    
    # Calculate actual movement (same as implementation)
    actual_movement = abs(end_price - start_price) / start_price
    
    # Should activate if movement > 10% (strictly greater)
    if actual_movement > 0.10:
        assert activated, \
            f"Should activate with {actual_movement*100:.2f}% price movement"
        assert kill_switch.is_activated
        assert kill_switch.activation_reason == KillSwitchReason.ABNORMAL_PRICE_MOVEMENT
    else:
        assert not activated, \
            f"Should NOT activate with {actual_movement*100:.2f}% price movement"


@given(
    initial_balance=st.floats(min_value=1000.0, max_value=100000.0),
    balance_change=st.floats(min_value=-0.50, max_value=0.50)
)
@settings(max_examples=50, deadline=2000)
def test_property_drawdown_calculation_accuracy(initial_balance, balance_change):
    """Property: Drawdown calculation must be accurate
    
    Drawdown = (peak - current) / peak
    """
    monitor = DrawdownMonitor(initial_balance)
    
    new_balance = initial_balance * (1 + balance_change)
    monitor.update_balance(new_balance)
    
    if balance_change >= 0:
        # Profit - no drawdown
        assert monitor.get_current_drawdown() == 0.0
        assert monitor.peak_balance == new_balance
    else:
        # Loss - calculate expected drawdown
        expected_dd = abs(balance_change)
        actual_dd = monitor.get_current_drawdown()
        
        assert abs(actual_dd - expected_dd) < 0.0001, \
            f"Drawdown {actual_dd} != expected {expected_dd}"


@given(
    initial_balance=st.floats(min_value=1000.0, max_value=100000.0)
)
@settings(max_examples=50, deadline=2000)
def test_property_peak_balance_never_decreases(initial_balance):
    """Property: Peak balance never decreases
    
    Peak can only stay same or increase
    """
    monitor = DrawdownMonitor(initial_balance)
    
    # Simulate balance changes
    balances = [
        initial_balance * 1.1,  # +10%
        initial_balance * 0.9,  # -10%
        initial_balance * 1.2,  # +20%
        initial_balance * 0.8   # -20%
    ]
    
    previous_peak = initial_balance
    
    for balance in balances:
        monitor.update_balance(balance)
        current_peak = monitor.peak_balance
        
        # Peak should never decrease
        assert current_peak >= previous_peak, \
            f"Peak decreased from {previous_peak} to {current_peak}"
        
        previous_peak = current_peak
