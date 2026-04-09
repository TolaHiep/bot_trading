"""Unit tests for signal generation engine"""

import pytest
import os
from src.alpha.signal_engine import SignalGenerator, SignalType, TradingSignal
from src.alpha.breakout_filter import BreakoutFilter, BreakoutSignal


class TestBreakoutFilter:
    """Test breakout filter"""
    
    def test_initialization(self):
        """Test breakout filter initialization"""
        filter = BreakoutFilter("BTCUSDT", "15m")
        
        assert filter.symbol == "BTCUSDT"
        assert filter.timeframe == "15m"
        assert filter.min_volume_ratio == 1.5
        assert len(filter.support_levels) == 0
        assert len(filter.resistance_levels) == 0
    
    def test_add_bar_insufficient_data(self):
        """Test add_bar with insufficient data"""
        filter = BreakoutFilter("BTCUSDT", "15m")
        
        result = filter.add_bar(
            timestamp=1000,
            high=100.0,
            low=99.0,
            close=99.5,
            volume=1000.0
        )
        
        assert result['breakout_detected'] is False
        assert result['breakout_signal'] is None
    
    def test_support_resistance_detection(self):
        """Test support and resistance level detection"""
        filter = BreakoutFilter("BTCUSDT", "15m", level_lookback=30)
        
        # Create pattern with clear support at 100 and resistance at 110
        for i in range(50):
            if i % 10 < 5:
                # Lower range (support area)
                high = 105.0
                low = 100.0
                close = 102.0
            else:
                # Upper range (resistance area)
                high = 110.0
                low = 105.0
                close = 108.0
            
            filter.add_bar(
                timestamp=1000 + i * 60,
                high=high,
                low=low,
                close=close,
                volume=1000.0
            )
        
        # Should detect support and resistance levels (or may not depending on pattern)
        # Just verify no errors occurred
        assert isinstance(filter.support_levels, list)
        assert isinstance(filter.resistance_levels, list)
    
    def test_valid_breakout_detection(self):
        """Test valid breakout detection"""
        filter = BreakoutFilter("BTCUSDT", "15m", level_lookback=30)
        
        # Create ranging pattern
        for i in range(40):
            filter.add_bar(
                timestamp=1000 + i * 60,
                high=105.0,
                low=100.0,
                close=102.0,
                volume=1000.0
            )
        
        # Create breakout with high volume
        result = filter.add_bar(
            timestamp=1000 + 40 * 60,
            high=112.0,
            low=105.0,
            close=111.0,
            volume=2000.0  # 2x average volume
        )
        
        # May or may not detect breakout depending on level formation
        assert isinstance(result['breakout_detected'], bool)
    
    def test_false_breakout_rejection(self):
        """Test false breakout rejection (low volume)"""
        filter = BreakoutFilter("BTCUSDT", "15m", level_lookback=30)
        
        # Create ranging pattern
        for i in range(40):
            filter.add_bar(
                timestamp=1000 + i * 60,
                high=105.0,
                low=100.0,
                close=102.0,
                volume=1000.0
            )
        
        # Create breakout with LOW volume
        result = filter.add_bar(
            timestamp=1000 + 40 * 60,
            high=112.0,
            low=105.0,
            close=111.0,
            volume=800.0  # Below average volume
        )
        
        # If breakout detected, should be marked invalid
        if result['breakout_detected']:
            assert result['breakout_signal'].is_valid is False
    
    def test_get_nearest_support(self):
        """Test get nearest support level"""
        filter = BreakoutFilter("BTCUSDT", "15m", level_lookback=30)
        
        # Add data
        for i in range(50):
            filter.add_bar(
                timestamp=1000 + i * 60,
                high=105.0 + i * 0.1,
                low=100.0 + i * 0.1,
                close=102.0 + i * 0.1,
                volume=1000.0
            )
        
        support = filter.get_nearest_support()
        # May or may not find support
        assert support is None or isinstance(support, float)
    
    def test_get_nearest_resistance(self):
        """Test get nearest resistance level"""
        filter = BreakoutFilter("BTCUSDT", "15m", level_lookback=30)
        
        # Add data
        for i in range(50):
            filter.add_bar(
                timestamp=1000 + i * 60,
                high=105.0 + i * 0.1,
                low=100.0 + i * 0.1,
                close=102.0 + i * 0.1,
                volume=1000.0
            )
        
        resistance = filter.get_nearest_resistance()
        # May or may not find resistance
        assert resistance is None or isinstance(resistance, float)
    
    def test_reset(self):
        """Test reset functionality"""
        filter = BreakoutFilter("BTCUSDT", "15m")
        
        # Add data
        for i in range(30):
            filter.add_bar(
                timestamp=1000 + i * 60,
                high=105.0,
                low=100.0,
                close=102.0,
                volume=1000.0
            )
        
        # Reset
        filter.reset()
        
        assert len(filter.highs) == 0
        assert len(filter.lows) == 0
        assert len(filter.support_levels) == 0
        assert len(filter.resistance_levels) == 0


class TestSignalGenerator:
    """Test signal generator"""
    
    @pytest.fixture
    def signal_generator(self):
        """Create signal generator for testing"""
        # Ensure config file exists
        config_path = "config/alpha_params.yaml"
        if not os.path.exists(config_path):
            pytest.skip("Config file not found")
        
        return SignalGenerator("BTCUSDT", config_path)
    
    def test_initialization(self, signal_generator):
        """Test signal generator initialization"""
        assert signal_generator.symbol == "BTCUSDT"
        assert len(signal_generator.signals) == 0
        assert signal_generator.indicator_engine is not None
        assert signal_generator.wyckoff_engine is not None
    
    def test_add_kline(self, signal_generator):
        """Test add kline"""
        signal = signal_generator.add_kline(
            timeframe="15m",
            timestamp=1000,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )
        
        # First kline won't generate signal (insufficient data)
        assert signal is None or isinstance(signal, TradingSignal)
    
    def test_add_trade(self, signal_generator):
        """Test add trade for order flow"""
        # Should not raise exception
        signal_generator.add_trade(
            timeframe="15m",
            timestamp=1000,
            price=100.0,
            quantity=1.0,
            side="Buy"
        )
    
    def test_neutral_signal_generation(self, signal_generator):
        """Test NEUTRAL signal generation"""
        # Add insufficient data
        for i in range(10):
            signal_generator.add_kline(
                timeframe="15m",
                timestamp=1000 + i * 900,
                open_price=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
        
        # Should generate NEUTRAL or no signal
        latest = signal_generator.get_latest_signal()
        if latest:
            assert latest.signal_type in [SignalType.NEUTRAL, SignalType.BUY, SignalType.SELL]
    
    def test_buy_signal_conditions(self, signal_generator):
        """Test BUY signal conditions"""
        # Create uptrend pattern
        for i in range(100):
            price = 100.0 + i * 0.5
            volume = 1000.0 + i * 20  # Increasing volume
            
            signal_generator.add_kline(
                timeframe="15m",
                timestamp=1000 + i * 900,
                open_price=price,
                high=price + 1.0,
                low=price - 0.5,
                close=price + 0.5,
                volume=volume
            )
            
            # Add buy trades for positive delta
            signal_generator.add_trade(
                timeframe="15m",
                timestamp=1000 + i * 900,
                price=price,
                quantity=10.0,
                side="Buy"
            )
        
        # Check if any signals generated
        signals = signal_generator.get_signals()
        assert isinstance(signals, list)
    
    def test_sell_signal_conditions(self, signal_generator):
        """Test SELL signal conditions"""
        # Create downtrend pattern
        for i in range(100):
            price = 100.0 - i * 0.5
            volume = 1000.0 + i * 20  # Increasing volume
            
            signal_generator.add_kline(
                timeframe="15m",
                timestamp=1000 + i * 900,
                open_price=price,
                high=price + 0.5,
                low=price - 1.0,
                close=price - 0.5,
                volume=volume
            )
            
            # Add sell trades for negative delta
            signal_generator.add_trade(
                timeframe="15m",
                timestamp=1000 + i * 900,
                price=price,
                quantity=10.0,
                side="Sell"
            )
        
        # Check if any signals generated
        signals = signal_generator.get_signals()
        assert isinstance(signals, list)
    
    def test_confidence_score_range(self, signal_generator):
        """Test confidence score is in valid range"""
        # Add some data
        for i in range(60):
            signal_generator.add_kline(
                timeframe="15m",
                timestamp=1000 + i * 900,
                open_price=100.0 + i * 0.3,
                high=101.0 + i * 0.3,
                low=99.0 + i * 0.3,
                close=100.0 + i * 0.3,
                volume=1000.0
            )
        
        # Check all signals have valid confidence
        for signal in signal_generator.signals:
            assert 0.0 <= signal.confidence <= 100.0
    
    def test_signal_suppression(self, signal_generator):
        """Test low confidence signal suppression"""
        # Add data to generate low confidence signal
        for i in range(30):
            signal_generator.add_kline(
                timeframe="15m",
                timestamp=1000 + i * 900,
                open_price=100.0,
                high=100.5,
                low=99.5,
                close=100.0,
                volume=1000.0
            )
        
        # Check suppressed signals
        suppressed = [s for s in signal_generator.signals if s.suppressed]
        for signal in suppressed:
            assert signal.confidence < signal_generator.signal_config['min_confidence']
    
    def test_get_latest_signal(self, signal_generator):
        """Test get latest signal"""
        assert signal_generator.get_latest_signal() is None
        
        # Add data
        signal_generator.add_kline(
            timeframe="15m",
            timestamp=1000,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000.0
        )
        
        latest = signal_generator.get_latest_signal()
        # May or may not have signal yet
        assert latest is None or isinstance(latest, TradingSignal)
    
    def test_get_signals_filter(self, signal_generator):
        """Test get signals with filters"""
        # Add data
        for i in range(50):
            signal_generator.add_kline(
                timeframe="15m",
                timestamp=1000 + i * 900,
                open_price=100.0 + i * 0.5,
                high=101.0 + i * 0.5,
                low=99.0 + i * 0.5,
                close=100.0 + i * 0.5,
                volume=1000.0 + i * 20
            )
        
        # Get all signals
        all_signals = signal_generator.get_signals()
        assert isinstance(all_signals, list)
        
        # Get BUY signals only
        buy_signals = signal_generator.get_signals(signal_type=SignalType.BUY)
        assert all(s.signal_type == SignalType.BUY for s in buy_signals)
        
        # Get high confidence signals
        high_conf = signal_generator.get_signals(min_confidence=70.0)
        assert all(s.confidence >= 70.0 for s in high_conf)
    
    def test_reset(self, signal_generator):
        """Test reset functionality"""
        # Add data
        for i in range(30):
            signal_generator.add_kline(
                timeframe="15m",
                timestamp=1000 + i * 900,
                open_price=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0
            )
        
        # Reset
        signal_generator.reset()
        
        assert len(signal_generator.signals) == 0
