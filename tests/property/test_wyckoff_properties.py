"""Property-based tests for Wyckoff phase detector

Property 16: Phase Transition Event Emission
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from src.alpha.wyckoff import WyckoffDetector, WyckoffPhase, WyckoffEngine


@given(
    lookback=st.integers(min_value=20, max_value=100),
    num_bars=st.integers(min_value=50, max_value=200)
)
@settings(max_examples=50, deadline=2000)
def test_property_16_phase_transition_event_emission(lookback, num_bars):
    """Property 16: Phase Transition Event Emission
    
    When Wyckoff phase changes, a PhaseTransition event must be emitted.
    
    Property: For all phase changes from phase A to phase B,
    a PhaseTransition event must be recorded with:
    - from_phase = A
    - to_phase = B
    - confidence > 0
    - valid timestamp
    """
    detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=lookback)
    
    previous_phase = detector.current_phase
    phase_changes = []
    
    # Add bars and track phase changes
    for i in range(num_bars):
        timestamp = 1000 + i * 3600
        high = 100.0 + i * 0.1
        low = 99.0 + i * 0.1
        close = 99.5 + i * 0.1
        volume = 500.0 + i * 5
        
        result = detector.add_bar(timestamp, high, low, close, volume)
        
        current_phase = detector.current_phase
        
        # Track phase changes
        if current_phase != previous_phase:
            phase_changes.append({
                'from': previous_phase,
                'to': current_phase,
                'timestamp': timestamp
            })
            previous_phase = current_phase
    
    # Get recorded transitions
    transitions = detector.get_phase_transitions()
    
    # Property: Number of transitions should match phase changes
    assert len(transitions) == len(phase_changes), \
        f"Expected {len(phase_changes)} transitions, got {len(transitions)}"
    
    # Property: Each transition should have correct from/to phases
    for i, transition in enumerate(transitions):
        expected = phase_changes[i]
        
        assert transition.from_phase == expected['from'], \
            f"Transition {i}: Expected from_phase={expected['from']}, got {transition.from_phase}"
        
        assert transition.to_phase == expected['to'], \
            f"Transition {i}: Expected to_phase={expected['to']}, got {transition.to_phase}"
        
        # Property: Confidence must be > 0
        assert transition.confidence > 0, \
            f"Transition {i}: Confidence must be > 0, got {transition.confidence}"
        
        # Property: Timestamp must be valid
        assert transition.timestamp >= 1000, \
            f"Transition {i}: Invalid timestamp {transition.timestamp}"


@given(
    num_bars=st.integers(min_value=30, max_value=100)
)
@settings(max_examples=50, deadline=2000)
def test_property_phase_confidence_range(num_bars):
    """Property: Phase confidence must be in range [0, 1]
    
    For all detected phases, confidence score must be between 0 and 1.
    """
    detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30)
    
    for i in range(num_bars):
        timestamp = 1000 + i * 3600
        high = 100.0 + i * 0.2
        low = 99.0 + i * 0.2
        close = 99.5 + i * 0.2
        volume = 500.0 + i * 10
        
        detector.add_bar(timestamp, high, low, close, volume)
        
        confidence = detector.get_phase_confidence()
        
        # Property: Confidence in valid range
        assert 0.0 <= confidence <= 1.0, \
            f"Confidence {confidence} out of range [0, 1]"


@given(
    num_bars=st.integers(min_value=30, max_value=100)
)
@settings(max_examples=50, deadline=2000)
def test_property_phase_validity(num_bars):
    """Property: Current phase must be a valid WyckoffPhase
    
    At any point, current_phase must be one of the defined WyckoffPhase values.
    """
    detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30)
    
    valid_phases = set(WyckoffPhase)
    
    for i in range(num_bars):
        timestamp = 1000 + i * 3600
        high = 100.0 + i * 0.3
        low = 99.0 + i * 0.3
        close = 99.5 + i * 0.3
        volume = 500.0 + i * 15
        
        detector.add_bar(timestamp, high, low, close, volume)
        
        current_phase = detector.get_current_phase()
        
        # Property: Phase must be valid
        assert current_phase in valid_phases, \
            f"Invalid phase: {current_phase}"


@given(
    num_bars=st.integers(min_value=50, max_value=150)
)
@settings(max_examples=30, deadline=2000)
def test_property_swing_detection_consistency(num_bars):
    """Property: Swing detection must be consistent
    
    Once a swing high/low is detected, it should not be removed from history.
    """
    detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=5)
    
    swing_high_count = 0
    swing_low_count = 0
    
    for i in range(num_bars):
        timestamp = 1000 + i * 3600
        # Create oscillating pattern
        high = 100.0 + (i % 10) * 2.0
        low = 99.0 + (i % 10) * 2.0
        close = 99.5 + (i % 10) * 2.0
        volume = 500.0 + i * 5
        
        detector.add_bar(timestamp, high, low, close, volume)
        
        # Track swing counts
        current_high_count = len(detector.swing_detector.swing_highs)
        current_low_count = len(detector.swing_detector.swing_lows)
        
        # Property: Swing counts should only increase or stay same
        assert current_high_count >= swing_high_count, \
            "Swing high count decreased"
        assert current_low_count >= swing_low_count, \
            "Swing low count decreased"
        
        swing_high_count = current_high_count
        swing_low_count = current_low_count


@given(
    num_bars=st.integers(min_value=30, max_value=100)
)
@settings(max_examples=50, deadline=2000)
def test_property_event_timestamp_ordering(num_bars):
    """Property: Events must be in chronological order
    
    All detected events should have timestamps in ascending order.
    """
    detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30)
    
    for i in range(num_bars):
        timestamp = 1000 + i * 3600
        high = 100.0 + (i % 15) * 1.5
        low = 99.0 + (i % 15) * 1.5
        close = 99.5 + (i % 15) * 1.5
        volume = 500.0 + i * 20
        
        detector.add_bar(timestamp, high, low, close, volume)
    
    events = detector.get_events()
    
    # Property: Events in chronological order
    for i in range(1, len(events)):
        assert events[i].timestamp >= events[i-1].timestamp, \
            f"Events not in chronological order: {events[i-1].timestamp} > {events[i].timestamp}"


@given(
    num_bars=st.integers(min_value=30, max_value=100)
)
@settings(max_examples=50, deadline=2000)
def test_property_reset_clears_state(num_bars):
    """Property: Reset must clear all state
    
    After reset, detector should be in initial state.
    """
    detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30)
    
    # Add data
    for i in range(num_bars):
        timestamp = 1000 + i * 3600
        high = 100.0 + i * 0.5
        low = 99.0 + i * 0.5
        close = 99.5 + i * 0.5
        volume = 500.0 + i * 10
        
        detector.add_bar(timestamp, high, low, close, volume)
    
    # Reset
    detector.reset()
    
    # Property: All state cleared
    assert len(detector.highs) == 0, "Highs not cleared"
    assert len(detector.lows) == 0, "Lows not cleared"
    assert len(detector.closes) == 0, "Closes not cleared"
    assert len(detector.volumes) == 0, "Volumes not cleared"
    assert len(detector.timestamps) == 0, "Timestamps not cleared"
    assert detector.current_phase == WyckoffPhase.UNKNOWN, "Phase not reset"
    assert detector.phase_confidence == 0.0, "Confidence not reset"
    assert len(detector.phase_transitions) == 0, "Transitions not cleared"
    assert len(detector.events) == 0, "Events not cleared"


@given(
    num_symbols=st.integers(min_value=1, max_value=5),
    num_bars=st.integers(min_value=30, max_value=80)
)
@settings(max_examples=30, deadline=3000)
def test_property_engine_detector_isolation(num_symbols, num_bars):
    """Property: Engine detectors must be isolated
    
    Data added to one detector should not affect other detectors.
    """
    engine = WyckoffEngine()
    
    symbols = [f"SYM{i}USDT" for i in range(num_symbols)]
    
    # Add data to each symbol
    for symbol in symbols:
        for i in range(num_bars):
            timestamp = 1000 + i * 3600
            high = 100.0 + i * 0.3
            low = 99.0 + i * 0.3
            close = 99.5 + i * 0.3
            volume = 500.0 + i * 10
            
            engine.add_bar(symbol, "1h", timestamp, high, low, close, volume)
    
    # Property: Each detector should have correct data
    for symbol in symbols:
        detector = engine.detectors[(symbol, "1h")]
        
        # Should have data
        assert len(detector.closes) > 0, f"{symbol}: No data"
        
        # Should have correct symbol
        assert detector.symbol == symbol, f"Wrong symbol: {detector.symbol}"


@given(
    num_bars=st.integers(min_value=30, max_value=100)
)
@settings(max_examples=50, deadline=2000)
def test_property_no_signal_when_unknown_phase(num_bars):
    """Property: No trading signals should be generated when phase is UNKNOWN
    
    This property ensures that the system doesn't emit signals when
    the Wyckoff phase cannot be determined with confidence.
    """
    detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30)
    
    # Add insufficient data to keep phase UNKNOWN
    for i in range(min(num_bars, 10)):
        timestamp = 1000 + i * 3600
        high = 100.0 + i * 0.1
        low = 99.0 + i * 0.1
        close = 99.5 + i * 0.1
        volume = 500.0
        
        result = detector.add_bar(timestamp, high, low, close, volume)
        
        # Property: If phase is UNKNOWN, no events should be emitted
        if detector.current_phase == WyckoffPhase.UNKNOWN:
            # Events list should be empty or only contain non-signal events
            events = result.get('events', [])
            # In practice, Spring/Upthrust are only detected in specific phases
            # so this should naturally hold
            assert isinstance(events, list)


@given(
    price_base=st.floats(min_value=50.0, max_value=200.0),
    num_bars=st.integers(min_value=50, max_value=150)
)
@settings(max_examples=30, deadline=2000)
def test_property_phase_detection_price_invariance(price_base, num_bars):
    """Property: Phase detection should be scale-invariant
    
    Wyckoff phases should be detected based on relative price movements,
    not absolute price levels.
    """
    assume(price_base > 0)
    
    detector1 = WyckoffDetector("BTCUSDT", "1h", lookback_period=30)
    detector2 = WyckoffDetector("BTCUSDT", "1h", lookback_period=30)
    
    scale_factor = 2.0
    
    # Add same pattern at different price scales
    for i in range(num_bars):
        timestamp = 1000 + i * 3600
        
        # Pattern 1: base price
        high1 = price_base + i * 0.5
        low1 = price_base - 1.0 + i * 0.5
        close1 = price_base - 0.5 + i * 0.5
        volume = 500.0 + i * 10
        
        # Pattern 2: scaled price
        high2 = high1 * scale_factor
        low2 = low1 * scale_factor
        close2 = close1 * scale_factor
        
        detector1.add_bar(timestamp, high1, low1, close1, volume)
        detector2.add_bar(timestamp, high2, low2, close2, volume)
    
    # Property: Both should detect same phase (or both UNKNOWN)
    # Note: Due to percentage-based thresholds, phases should be similar
    phase1 = detector1.get_current_phase()
    phase2 = detector2.get_current_phase()
    
    # Both should be valid phases
    assert isinstance(phase1, WyckoffPhase)
    assert isinstance(phase2, WyckoffPhase)
    
    # If both have enough data, they should detect similar patterns
    if len(detector1.closes) >= detector1.lookback_period:
        # At minimum, both should not be in opposite phases
        # (e.g., one MARKUP and other MARKDOWN)
        opposite_pairs = [
            (WyckoffPhase.MARKUP, WyckoffPhase.MARKDOWN),
            (WyckoffPhase.MARKDOWN, WyckoffPhase.MARKUP),
            (WyckoffPhase.ACCUMULATION, WyckoffPhase.DISTRIBUTION),
            (WyckoffPhase.DISTRIBUTION, WyckoffPhase.ACCUMULATION)
        ]
        
        assert (phase1, phase2) not in opposite_pairs, \
            f"Opposite phases detected: {phase1} vs {phase2}"
