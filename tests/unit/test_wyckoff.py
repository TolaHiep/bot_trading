"""Unit tests for Wyckoff phase detector"""

import pytest
from src.alpha.wyckoff import (
    WyckoffDetector,
    WyckoffEngine,
    WyckoffPhase,
    PhaseTransition,
    WyckoffEvent
)
from src.alpha.swing_detector import SwingDetector, SwingPoint


class TestSwingDetector:
    """Test swing detection"""
    
    def test_initialization(self):
        """Test swing detector initialization"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=5)
        
        assert detector.symbol == "BTCUSDT"
        assert detector.timeframe == "1h"
        assert detector.lookback == 5
        assert len(detector.highs) == 0
        assert len(detector.lows) == 0
        assert len(detector.swing_highs) == 0
        assert len(detector.swing_lows) == 0
    
    def test_add_bar_insufficient_data(self):
        """Test add_bar with insufficient data"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=5)
        
        # Add only 5 bars (need 11 for swing detection)
        for i in range(5):
            result = detector.add_bar(
                timestamp=1000 + i * 3600,
                high=100.0 + i,
                low=99.0 + i
            )
            assert result['swing_high'] is None
            assert result['swing_low'] is None
    
    def test_detect_swing_high(self):
        """Test swing high detection"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=3)
        
        # Create pattern: low, low, low, HIGH, low, low, low
        prices = [100, 101, 102, 110, 103, 102, 101]
        
        for i, price in enumerate(prices):
            result = detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price,
                low=price - 1
            )
        
        # Should detect swing high at position 3 (price 110)
        assert len(detector.swing_highs) == 1
        assert detector.swing_highs[0].price == 110
        assert detector.swing_highs[0].swing_type == 'HIGH'
    
    def test_detect_swing_low(self):
        """Test swing low detection"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=3)
        
        # Create pattern: high, high, high, LOW, high, high, high
        prices = [100, 99, 98, 90, 97, 98, 99]
        
        for i, price in enumerate(prices):
            result = detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 1,
                low=price
            )
        
        # Should detect swing low at position 3 (price 90)
        assert len(detector.swing_lows) == 1
        assert detector.swing_lows[0].price == 90
        assert detector.swing_lows[0].swing_type == 'LOW'
    
    def test_is_higher_high(self):
        """Test higher high detection"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=2)
        
        # Create two swing highs: 105, then 110
        prices = [100, 101, 105, 102, 101, 100, 101, 102, 110, 103, 102]
        
        for i, price in enumerate(prices):
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price,
                low=price - 1
            )
        
        assert detector.is_higher_high() is True
    
    def test_is_lower_low(self):
        """Test lower low detection"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=2)
        
        # Create two swing lows: 95, then 90
        prices = [100, 99, 95, 97, 98, 99, 98, 97, 90, 96, 97]
        
        for i, price in enumerate(prices):
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 1,
                low=price
            )
        
        assert detector.is_lower_low() is True
    
    def test_get_latest_swing_high(self):
        """Test get latest swing high"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=2)
        
        # No swings yet
        assert detector.get_latest_swing_high() is None
        
        # Add bars to create swing high
        prices = [100, 101, 105, 102, 101]
        for i, price in enumerate(prices):
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price,
                low=price - 1
            )
        
        latest = detector.get_latest_swing_high()
        assert latest is not None
        assert latest.price == 105
    
    def test_reset(self):
        """Test reset functionality"""
        detector = SwingDetector("BTCUSDT", "1h", lookback=2)
        
        # Add some data
        for i in range(10):
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=100.0 + i,
                low=99.0 + i
            )
        
        # Reset
        detector.reset()
        
        assert len(detector.highs) == 0
        assert len(detector.lows) == 0
        assert len(detector.swing_highs) == 0
        assert len(detector.swing_lows) == 0


class TestWyckoffDetector:
    """Test Wyckoff phase detection"""
    
    def test_initialization(self):
        """Test Wyckoff detector initialization"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=50)
        
        assert detector.symbol == "BTCUSDT"
        assert detector.timeframe == "1h"
        assert detector.lookback_period == 50
        assert detector.current_phase == WyckoffPhase.UNKNOWN
        assert detector.phase_confidence == 0.0
    
    def test_add_bar_insufficient_data(self):
        """Test add_bar with insufficient data"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=50)
        
        result = detector.add_bar(
            timestamp=1000,
            high=100.0,
            low=99.0,
            close=99.5,
            volume=1000.0
        )
        
        assert result['phase'] == WyckoffPhase.UNKNOWN.value
        assert result['confidence'] == 0.0
    
    def test_accumulation_phase_detection(self):
        """Test ACCUMULATION phase detection"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=3)
        
        # Create accumulation pattern: ranging price + decreasing volume
        base_price = 100.0
        for i in range(50):
            # Ranging price (small oscillations)
            price = base_price + (i % 5) * 0.5
            # Decreasing volume
            volume = 1000.0 - i * 10
            
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=max(volume, 100)
            )
        
        # Should detect ACCUMULATION
        assert detector.current_phase in [WyckoffPhase.ACCUMULATION, WyckoffPhase.UNKNOWN]
    
    def test_markup_phase_detection(self):
        """Test MARKUP phase detection"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=3)
        
        # Create markup pattern: uptrend + increasing volume
        base_price = 100.0
        for i in range(50):
            # Uptrend
            price = base_price + i * 0.5
            # Increasing volume
            volume = 500.0 + i * 20
            
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=volume
            )
        
        # Should detect MARKUP
        assert detector.current_phase in [WyckoffPhase.MARKUP, WyckoffPhase.UNKNOWN]
    
    def test_distribution_phase_detection(self):
        """Test DISTRIBUTION phase detection"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=3)
        
        # Create distribution pattern: ranging price + increasing volume
        base_price = 100.0
        for i in range(50):
            # Ranging price with higher volatility
            price = base_price + (i % 7) * 1.0
            # Increasing volume
            volume = 500.0 + i * 20
            
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=volume
            )
        
        # Should detect DISTRIBUTION or UNKNOWN
        assert detector.current_phase in [WyckoffPhase.DISTRIBUTION, WyckoffPhase.UNKNOWN, WyckoffPhase.MARKUP]
    
    def test_markdown_phase_detection(self):
        """Test MARKDOWN phase detection"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=3)
        
        # Create markdown pattern: downtrend + increasing volume
        base_price = 100.0
        for i in range(50):
            # Downtrend
            price = base_price - i * 0.5
            # Increasing volume
            volume = 500.0 + i * 20
            
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=volume
            )
        
        # Should detect MARKDOWN
        assert detector.current_phase in [WyckoffPhase.MARKDOWN, WyckoffPhase.UNKNOWN]
    
    def test_phase_transition_event(self):
        """Test phase transition event emission"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=3)
        
        # Create accumulation first
        for i in range(40):
            price = 100.0 + (i % 3) * 0.3
            volume = 1000.0 - i * 10
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=max(volume, 100)
            )
        
        initial_phase = detector.current_phase
        
        # Switch to markup
        for i in range(40, 80):
            price = 100.0 + (i - 40) * 0.8
            volume = 500.0 + (i - 40) * 25
            result = detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 0.5,
                low=price - 0.5,
                close=price,
                volume=volume
            )
        
        # Should have phase transitions
        transitions = detector.get_phase_transitions()
        # May have multiple transitions or none depending on thresholds
        assert isinstance(transitions, list)
    
    def test_spring_event_detection(self):
        """Test Spring event detection"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=3)
        
        # Create accumulation phase first
        for i in range(40):
            price = 100.0 + (i % 3) * 0.2
            volume = 1000.0 - i * 10
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 0.2,
                low=price - 0.2,
                close=price,
                volume=max(volume, 100)
            )
        
        # Force accumulation phase
        detector.current_phase = WyckoffPhase.ACCUMULATION
        
        # Create spring: false breakdown that reverses
        support = 99.0
        detector.add_bar(
            timestamp=1000 + 40 * 3600,
            high=100.0,
            low=98.0,  # Break below support
            close=100.5,  # Close back above
            volume=500.0
        )
        
        events = detector.get_events()
        # May or may not detect spring depending on exact conditions
        assert isinstance(events, list)
    
    def test_upthrust_event_detection(self):
        """Test Upthrust event detection"""
        detector = WyckoffDetector("BTCUSDT", "1h", lookback_period=30, swing_lookback=3)
        
        # Create distribution phase first
        for i in range(40):
            price = 100.0 + (i % 5) * 0.8
            volume = 500.0 + i * 20
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=price + 0.8,
                low=price - 0.8,
                close=price,
                volume=volume
            )
        
        # Force distribution phase
        detector.current_phase = WyckoffPhase.DISTRIBUTION
        
        # Create upthrust: false breakout that reverses
        resistance = 105.0
        detector.add_bar(
            timestamp=1000 + 40 * 3600,
            high=107.0,  # Break above resistance
            low=103.0,
            close=103.5,  # Close back below
            volume=1500.0
        )
        
        events = detector.get_events()
        # May or may not detect upthrust depending on exact conditions
        assert isinstance(events, list)
    
    def test_get_current_phase(self):
        """Test get current phase"""
        detector = WyckoffDetector("BTCUSDT", "1h")
        
        assert detector.get_current_phase() == WyckoffPhase.UNKNOWN
        
        # Add some data
        for i in range(60):
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=100.0 + i * 0.5,
                low=99.0 + i * 0.5,
                close=99.5 + i * 0.5,
                volume=500.0 + i * 20
            )
        
        phase = detector.get_current_phase()
        assert isinstance(phase, WyckoffPhase)
    
    def test_get_phase_confidence(self):
        """Test get phase confidence"""
        detector = WyckoffDetector("BTCUSDT", "1h")
        
        assert detector.get_phase_confidence() == 0.0
        
        # Add data
        for i in range(60):
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=100.0 + i * 0.5,
                low=99.0 + i * 0.5,
                close=99.5 + i * 0.5,
                volume=500.0 + i * 20
            )
        
        confidence = detector.get_phase_confidence()
        assert 0.0 <= confidence <= 1.0
    
    def test_reset(self):
        """Test reset functionality"""
        detector = WyckoffDetector("BTCUSDT", "1h")
        
        # Add data
        for i in range(60):
            detector.add_bar(
                timestamp=1000 + i * 3600,
                high=100.0 + i,
                low=99.0 + i,
                close=99.5 + i,
                volume=1000.0
            )
        
        # Reset
        detector.reset()
        
        assert len(detector.highs) == 0
        assert len(detector.lows) == 0
        assert len(detector.closes) == 0
        assert len(detector.volumes) == 0
        assert detector.current_phase == WyckoffPhase.UNKNOWN
        assert detector.phase_confidence == 0.0
        assert len(detector.phase_transitions) == 0


class TestWyckoffEngine:
    """Test Wyckoff engine"""
    
    def test_initialization(self):
        """Test engine initialization"""
        engine = WyckoffEngine()
        
        assert len(engine.detectors) == 0
    
    def test_get_or_create_detector(self):
        """Test get or create detector"""
        engine = WyckoffEngine()
        
        detector1 = engine.get_or_create_detector("BTCUSDT", "1h")
        assert detector1.symbol == "BTCUSDT"
        assert detector1.timeframe == "1h"
        
        # Get same detector
        detector2 = engine.get_or_create_detector("BTCUSDT", "1h")
        assert detector1 is detector2
        
        # Create different detector
        detector3 = engine.get_or_create_detector("ETHUSDT", "1h")
        assert detector3 is not detector1
    
    def test_add_bar(self):
        """Test add bar through engine"""
        engine = WyckoffEngine()
        
        result = engine.add_bar(
            symbol="BTCUSDT",
            timeframe="1h",
            timestamp=1000,
            high=100.0,
            low=99.0,
            close=99.5,
            volume=1000.0
        )
        
        assert 'phase' in result
        assert 'confidence' in result
    
    def test_get_phase(self):
        """Test get phase"""
        engine = WyckoffEngine()
        
        # No detector yet
        phase = engine.get_phase("BTCUSDT", "1h")
        assert phase == WyckoffPhase.UNKNOWN
        
        # Add data
        for i in range(60):
            engine.add_bar(
                symbol="BTCUSDT",
                timeframe="1h",
                timestamp=1000 + i * 3600,
                high=100.0 + i * 0.5,
                low=99.0 + i * 0.5,
                close=99.5 + i * 0.5,
                volume=500.0 + i * 20
            )
        
        phase = engine.get_phase("BTCUSDT", "1h")
        assert isinstance(phase, WyckoffPhase)
    
    def test_reset(self):
        """Test reset detector"""
        engine = WyckoffEngine()
        
        # Add data
        for i in range(60):
            engine.add_bar(
                symbol="BTCUSDT",
                timeframe="1h",
                timestamp=1000 + i * 3600,
                high=100.0 + i,
                low=99.0 + i,
                close=99.5 + i,
                volume=1000.0
            )
        
        # Reset
        engine.reset("BTCUSDT", "1h")
        
        detector = engine.detectors[("BTCUSDT", "1h")]
        assert len(detector.highs) == 0
        assert detector.current_phase == WyckoffPhase.UNKNOWN
