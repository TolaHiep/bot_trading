"""Property-based tests for signal generation

Property 17: Volume Confirmation for Breakouts
Property 18: Multi-Timeframe Alignment Requirement
Property 19: Confidence Score Range
Property 20: Low Confidence Signal Suppression
"""

import pytest
import os
from hypothesis import given, strategies as st, settings, assume
from src.alpha.signal_engine import SignalGenerator, SignalType
from src.alpha.breakout_filter import BreakoutFilter


@pytest.fixture(scope="module")
def check_config():
    """Check if config file exists"""
    if not os.path.exists("config/alpha_params.yaml"):
        pytest.skip("Config file not found")


@given(
    num_bars=st.integers(min_value=30, max_value=100),
    volume_multiplier=st.floats(min_value=0.5, max_value=3.0)
)
@settings(max_examples=30, deadline=3000)
def test_property_17_volume_confirmation_for_breakouts(num_bars, volume_multiplier):
    """Property 17: Volume Confirmation for Breakouts
    
    Valid breakouts must have volume >= min_volume_ratio * average_volume.
    
    Property: For all detected breakouts marked as valid,
    volume_ratio >= min_volume_ratio must hold.
    """
    filter = BreakoutFilter(
        "BTCUSDT",
        "15m",
        min_volume_ratio=1.5,
        level_lookback=30
    )
    
    base_volume = 1000.0
    
    # Add bars to establish pattern
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        high = 100.0 + (i % 10) * 1.0
        low = 99.0 + (i % 10) * 1.0
        close = 99.5 + (i % 10) * 1.0
        volume = base_volume * (0.8 + (i % 5) * 0.1)
        
        result = filter.add_bar(timestamp, high, low, close, volume)
        
        # Property: If breakout is valid, volume ratio must meet threshold
        if result['breakout_detected'] and result['breakout_signal']:
            breakout = result['breakout_signal']
            
            if breakout.is_valid:
                assert breakout.volume_ratio >= filter.min_volume_ratio, \
                    f"Valid breakout has insufficient volume: {breakout.volume_ratio:.2f} < {filter.min_volume_ratio}"


@given(
    num_bars=st.integers(min_value=60, max_value=150)
)
@settings(max_examples=20, deadline=5000)
def test_property_18_multi_timeframe_alignment_requirement(num_bars, check_config):
    """Property 18: Multi-Timeframe Alignment Requirement
    
    Signals should only be generated when minimum number of timeframes align.
    
    Property: For all non-NEUTRAL signals,
    aligned_timeframes >= min_timeframe_alignment must hold.
    """
    generator = SignalGenerator("BTCUSDT", "config/alpha_params.yaml")
    min_alignment = generator.signal_config['min_timeframe_alignment']
    
    # Add data to all timeframes
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        price = 100.0 + i * 0.3
        
        for tf in generator.signal_config['timeframes']:
            generator.add_kline(
                timeframe=tf,
                timestamp=timestamp,
                open_price=price,
                high=price + 1.0,
                low=price - 0.5,
                close=price + 0.5,
                volume=1000.0 + i * 20
            )
    
    # Property: Non-suppressed BUY/SELL signals must meet alignment requirement
    for signal in generator.signals:
        if not signal.suppressed and signal.signal_type != SignalType.NEUTRAL:
            assert signal.aligned_timeframes >= min_alignment, \
                f"Signal generated with insufficient alignment: {signal.aligned_timeframes} < {min_alignment}"


@given(
    num_bars=st.integers(min_value=50, max_value=120)
)
@settings(max_examples=30, deadline=5000)
def test_property_19_confidence_score_range(num_bars, check_config):
    """Property 19: Confidence Score Range
    
    All confidence scores must be in range [0, 100].
    
    Property: For all generated signals,
    0 <= confidence <= 100 must hold.
    """
    generator = SignalGenerator("BTCUSDT", "config/alpha_params.yaml")
    
    # Add data
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        price = 100.0 + i * 0.2
        
        generator.add_kline(
            timeframe="15m",
            timestamp=timestamp,
            open_price=price,
            high=price + 0.8,
            low=price - 0.5,
            close=price + 0.3,
            volume=1000.0 + i * 15
        )
    
    # Property: All confidence scores in valid range
    for signal in generator.signals:
        assert 0.0 <= signal.confidence <= 100.0, \
            f"Confidence out of range: {signal.confidence}"


@given(
    num_bars=st.integers(min_value=50, max_value=120)
)
@settings(max_examples=30, deadline=5000)
def test_property_20_low_confidence_signal_suppression(num_bars, check_config):
    """Property 20: Low Confidence Signal Suppression
    
    Signals with confidence < min_confidence must be suppressed.
    
    Property: For all signals with confidence < min_confidence,
    suppressed flag must be True.
    """
    generator = SignalGenerator("BTCUSDT", "config/alpha_params.yaml")
    min_confidence = generator.signal_config['min_confidence']
    
    # Add data
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        price = 100.0 + (i % 20) * 0.5
        
        generator.add_kline(
            timeframe="15m",
            timestamp=timestamp,
            open_price=price,
            high=price + 0.6,
            low=price - 0.4,
            close=price + 0.2,
            volume=1000.0
        )
    
    # Property: Low confidence signals must be suppressed
    for signal in generator.signals:
        if signal.confidence < min_confidence:
            assert signal.suppressed is True, \
                f"Low confidence signal not suppressed: confidence={signal.confidence}, suppressed={signal.suppressed}"


@given(
    num_bars=st.integers(min_value=40, max_value=100)
)
@settings(max_examples=30, deadline=3000)
def test_property_breakout_price_move_requirement(num_bars):
    """Property: Valid breakouts must have minimum price move
    
    For all valid breakouts, price_move_pct >= min_price_move must hold.
    """
    filter = BreakoutFilter(
        "BTCUSDT",
        "15m",
        min_price_move=0.005,
        level_lookback=30
    )
    
    # Add bars
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        high = 100.0 + (i % 8) * 1.2
        low = 99.0 + (i % 8) * 1.2
        close = 99.5 + (i % 8) * 1.2
        volume = 1000.0 + i * 10
        
        result = filter.add_bar(timestamp, high, low, close, volume)
        
        # Property: Valid breakouts must have sufficient price move
        if result['breakout_detected'] and result['breakout_signal']:
            breakout = result['breakout_signal']
            
            if breakout.is_valid:
                assert breakout.price_move_pct >= filter.min_price_move, \
                    f"Valid breakout has insufficient price move: {breakout.price_move_pct:.4f} < {filter.min_price_move}"


@given(
    num_bars=st.integers(min_value=50, max_value=120)
)
@settings(max_examples=30, deadline=5000)
def test_property_signal_type_validity(num_bars, check_config):
    """Property: All signals must have valid signal type
    
    For all generated signals, signal_type must be BUY, SELL, or NEUTRAL.
    """
    generator = SignalGenerator("BTCUSDT", "config/alpha_params.yaml")
    
    valid_types = {SignalType.BUY, SignalType.SELL, SignalType.NEUTRAL}
    
    # Add data
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        price = 100.0 + i * 0.25
        
        generator.add_kline(
            timeframe="15m",
            timestamp=timestamp,
            open_price=price,
            high=price + 0.7,
            low=price - 0.4,
            close=price + 0.3,
            volume=1000.0 + i * 12
        )
    
    # Property: All signal types must be valid
    for signal in generator.signals:
        assert signal.signal_type in valid_types, \
            f"Invalid signal type: {signal.signal_type}"


@given(
    num_bars=st.integers(min_value=50, max_value=120)
)
@settings(max_examples=30, deadline=5000)
def test_property_signal_timestamp_ordering(num_bars, check_config):
    """Property: Signals must be in chronological order
    
    For all consecutive signals, timestamp[i+1] >= timestamp[i] must hold.
    """
    generator = SignalGenerator("BTCUSDT", "config/alpha_params.yaml")
    
    # Add data
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        price = 100.0 + i * 0.3
        
        generator.add_kline(
            timeframe="15m",
            timestamp=timestamp,
            open_price=price,
            high=price + 0.8,
            low=price - 0.5,
            close=price + 0.4,
            volume=1000.0 + i * 15
        )
    
    # Property: Signals in chronological order
    for i in range(1, len(generator.signals)):
        assert generator.signals[i].timestamp >= generator.signals[i-1].timestamp, \
            f"Signals not in chronological order: {generator.signals[i-1].timestamp} > {generator.signals[i].timestamp}"


@given(
    num_bars=st.integers(min_value=30, max_value=80)
)
@settings(max_examples=30, deadline=3000)
def test_property_support_resistance_ordering(num_bars):
    """Property: Support levels must be below current price, resistance above
    
    For nearest support/resistance, support < current_price < resistance must hold.
    """
    filter = BreakoutFilter("BTCUSDT", "15m", level_lookback=30)
    
    # Add bars
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        high = 100.0 + (i % 12) * 1.5
        low = 99.0 + (i % 12) * 1.5
        close = 99.5 + (i % 12) * 1.5
        volume = 1000.0
        
        filter.add_bar(timestamp, high, low, close, volume)
    
    if len(filter.closes) > 0:
        current_price = filter.closes[-1]
        support = filter.get_nearest_support()
        resistance = filter.get_nearest_resistance()
        
        # Property: Support below current price
        if support is not None:
            assert support < current_price, \
                f"Support {support} not below current price {current_price}"
        
        # Property: Resistance above current price
        if resistance is not None:
            assert resistance > current_price, \
                f"Resistance {resistance} not above current price {current_price}"


@given(
    num_bars=st.integers(min_value=50, max_value=120)
)
@settings(max_examples=30, deadline=5000)
def test_property_reset_clears_signals(num_bars, check_config):
    """Property: Reset must clear all signals
    
    After reset, signals list must be empty.
    """
    generator = SignalGenerator("BTCUSDT", "config/alpha_params.yaml")
    
    # Add data
    for i in range(num_bars):
        timestamp = 1000 + i * 900
        price = 100.0 + i * 0.4
        
        generator.add_kline(
            timeframe="15m",
            timestamp=timestamp,
            open_price=price,
            high=price + 0.9,
            low=price - 0.6,
            close=price + 0.5,
            volume=1000.0 + i * 18
        )
    
    # Reset
    generator.reset()
    
    # Property: Signals cleared
    assert len(generator.signals) == 0, "Signals not cleared after reset"
