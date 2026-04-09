"""Unit Tests for Technical Indicators

Tests for indicator calculations and performance.
"""

import pytest
import numpy as np

from src.alpha.indicators import IndicatorEngine, TechnicalIndicators
from src.alpha.incremental_ema import IncrementalEMA, IncrementalRSI


class TestIncrementalEMA:
    """Test IncrementalEMA"""
    
    def test_init(self):
        """Test initialization"""
        ema = IncrementalEMA(period=10)
        assert ema.period == 10
        assert ema.k == 2.0 / 11
        assert ema.ema is None
        assert not ema.initialized
    
    def test_first_update(self):
        """Test first update sets EMA to price"""
        ema = IncrementalEMA(period=10)
        result = ema.update(100.0)
        assert result == 100.0
        assert ema.initialized
    
    def test_incremental_updates(self):
        """Test incremental EMA calculation"""
        ema = IncrementalEMA(period=10)
        
        # First price
        ema.update(100.0)
        
        # Second price
        result = ema.update(110.0)
        
        # EMA = price * k + EMA_prev * (1 - k)
        # k = 2/11 = 0.1818...
        # EMA = 110 * 0.1818 + 100 * 0.8182 = 101.818...
        assert abs(result - 101.818) < 0.01
    
    def test_get_value(self):
        """Test getting current EMA value"""
        ema = IncrementalEMA(period=10)
        assert ema.get_value() is None
        
        ema.update(100.0)
        assert ema.get_value() == 100.0
    
    def test_reset(self):
        """Test resetting EMA"""
        ema = IncrementalEMA(period=10)
        ema.update(100.0)
        ema.update(110.0)
        
        ema.reset()
        assert ema.ema is None
        assert not ema.initialized


class TestIncrementalRSI:
    """Test IncrementalRSI"""
    
    def test_init(self):
        """Test initialization"""
        rsi = IncrementalRSI(period=14)
        assert rsi.period == 14
        assert rsi.prev_price is None
        assert rsi.avg_gain is None
        assert rsi.avg_loss is None
    
    def test_first_update_returns_none(self):
        """Test first update returns None (no previous price)"""
        rsi = IncrementalRSI(period=14)
        result = rsi.update(100.0)
        assert result is None
    
    def test_insufficient_data(self):
        """Test RSI returns None until enough data"""
        rsi = IncrementalRSI(period=14)
        
        # Need 15 prices (1 for prev + 14 for period)
        for i in range(14):
            result = rsi.update(100.0 + i)
            if i < 13:
                assert result is None
    
    def test_rsi_calculation(self):
        """Test RSI calculation with known values"""
        rsi = IncrementalRSI(period=14)
        
        # Simulate price increases (should give high RSI)
        prices = [100 + i for i in range(20)]
        
        for price in prices:
            result = rsi.update(price)
        
        # RSI should be high (near 100) for consistent uptrend
        assert result is not None
        assert result > 70
    
    def test_rsi_range(self):
        """Test RSI stays in 0-100 range"""
        rsi = IncrementalRSI(period=14)
        
        # Random prices
        np.random.seed(42)
        prices = 100 + np.random.randn(50) * 10
        
        for price in prices:
            result = rsi.update(price)
            if result is not None:
                assert 0 <= result <= 100
    
    def test_reset(self):
        """Test resetting RSI"""
        rsi = IncrementalRSI(period=14)
        
        for i in range(20):
            rsi.update(100.0 + i)
        
        rsi.reset()
        assert rsi.prev_price is None
        assert rsi.avg_gain is None
        assert rsi.avg_loss is None


class TestTechnicalIndicators:
    """Test TechnicalIndicators"""
    
    def test_init(self):
        """Test initialization"""
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        assert indicators.symbol == 'BTCUSDT'
        assert indicators.timeframe == '1m'
        assert len(indicators.closes) == 0
    
    def test_sma_calculation(self):
        """Test SMA calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', sma_periods=[5])
        
        # Add 5 prices
        prices = [100, 102, 104, 106, 108]
        for price in prices:
            indicators.update(price, 1000)
        
        values = indicators.get_current_values()
        
        # SMA(5) = (100 + 102 + 104 + 106 + 108) / 5 = 104
        assert 'sma_5' in values
        assert abs(values['sma_5'] - 104.0) < 0.01
    
    def test_ema_calculation(self):
        """Test EMA calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', ema_periods=[5])
        
        # Add prices
        prices = [100, 102, 104, 106, 108]
        for price in prices:
            indicators.update(price, 1000)
        
        values = indicators.get_current_values()
        assert 'ema_5' in values
        assert values['ema_5'] > 0
    
    def test_rsi_calculation(self):
        """Test RSI calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', rsi_period=14)
        
        # Add enough prices for RSI
        for i in range(20):
            indicators.update(100.0 + i, 1000)
        
        values = indicators.get_current_values()
        assert 'rsi' in values
        assert 0 <= values['rsi'] <= 100
    
    def test_macd_calculation(self):
        """Test MACD calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        # Add enough prices for MACD
        for i in range(50):
            indicators.update(100.0 + i * 0.5, 1000)
        
        values = indicators.get_current_values()
        assert 'macd_line' in values
        assert 'macd_signal' in values
        assert 'macd_histogram' in values
    
    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', bb_period=20)
        
        # Add 20 prices
        np.random.seed(42)
        prices = 100 + np.random.randn(20) * 5
        
        for price in prices:
            indicators.update(price, 1000)
        
        values = indicators.get_current_values()
        assert 'bb_upper' in values
        assert 'bb_middle' in values
        assert 'bb_lower' in values
        assert 'bb_width' in values
        
        # Upper should be > middle > lower
        assert values['bb_upper'] > values['bb_middle']
        assert values['bb_middle'] > values['bb_lower']
    
    def test_volume_profile_calculation(self):
        """Test Volume Profile calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        # Add prices with volumes
        np.random.seed(42)
        for i in range(50):
            price = 100 + np.random.randn() * 5
            volume = 1000 + np.random.rand() * 500
            indicators.update(price, volume)
        
        values = indicators.get_current_values()
        assert 'vp_poc' in values
        assert 'vp_hvn' in values
        assert 'vp_lvn' in values
        assert 'vp_value_area_high' in values
        assert 'vp_value_area_low' in values
        assert 'vp_total_volume' in values
    
    def test_insufficient_data(self):
        """Test indicators return None/empty when insufficient data"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', sma_periods=[50])
        
        # Add only 10 prices
        for i in range(10):
            indicators.update(100.0 + i, 1000)
        
        values = indicators.get_current_values()
        
        # SMA(50) should not be present
        assert 'sma_50' not in values
    
    def test_reset(self):
        """Test resetting indicators"""
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        # Add data
        for i in range(20):
            indicators.update(100.0 + i, 1000)
        
        # Reset
        indicators.reset()
        
        assert len(indicators.closes) == 0
        assert len(indicators.current_values) == 0


class TestIndicatorEngine:
    """Test IndicatorEngine"""
    
    def test_init(self):
        """Test initialization"""
        engine = IndicatorEngine()
        assert len(engine.indicators) == 0
    
    def test_get_or_create_indicators(self):
        """Test getting or creating indicators"""
        engine = IndicatorEngine()
        
        indicators = engine.get_or_create_indicators('BTCUSDT', '1m')
        assert indicators.symbol == 'BTCUSDT'
        assert indicators.timeframe == '1m'
        
        # Should return same instance
        indicators2 = engine.get_or_create_indicators('BTCUSDT', '1m')
        assert indicators is indicators2
    
    def test_update(self):
        """Test updating indicators"""
        engine = IndicatorEngine()
        
        # Update with data
        for i in range(20):
            engine.update('BTCUSDT', '1m', 100.0 + i, 1000)
        
        values = engine.get_values('BTCUSDT', '1m')
        assert len(values) > 0
    
    def test_multiple_symbols_timeframes(self):
        """Test managing multiple symbols and timeframes"""
        engine = IndicatorEngine()
        
        # Update different pairs
        engine.update('BTCUSDT', '1m', 50000, 1000)
        engine.update('BTCUSDT', '5m', 50100, 2000)
        engine.update('ETHUSDT', '1m', 3000, 500)
        
        # Should have 3 different indicator instances
        assert len(engine.indicators) == 3
        
        # Each should have independent values
        btc_1m = engine.get_values('BTCUSDT', '1m')
        btc_5m = engine.get_values('BTCUSDT', '5m')
        eth_1m = engine.get_values('ETHUSDT', '1m')
        
        assert btc_1m != btc_5m
        assert btc_1m != eth_1m
    
    def test_get_values_nonexistent(self):
        """Test getting values for non-existent pair"""
        engine = IndicatorEngine()
        values = engine.get_values('BTCUSDT', '1m')
        assert values == {}
    
    def test_reset(self):
        """Test resetting indicators"""
        engine = IndicatorEngine()
        
        # Add data
        for i in range(20):
            engine.update('BTCUSDT', '1m', 100.0 + i, 1000)
        
        # Reset
        engine.reset('BTCUSDT', '1m')
        
        values = engine.get_values('BTCUSDT', '1m')
        assert len(values) == 0
    
    def test_get_tracked_pairs(self):
        """Test getting tracked pairs"""
        engine = IndicatorEngine()
        
        engine.update('BTCUSDT', '1m', 50000, 1000)
        engine.update('ETHUSDT', '5m', 3000, 500)
        
        pairs = engine.get_tracked_pairs()
        assert len(pairs) == 2
        assert ('BTCUSDT', '1m') in pairs
        assert ('ETHUSDT', '5m') in pairs


class TestIndicatorAccuracy:
    """Test indicator accuracy against known values"""
    
    def test_sma_accuracy(self):
        """Test SMA matches manual calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', sma_periods=[5])
        
        prices = [10, 20, 30, 40, 50]
        for price in prices:
            indicators.update(price, 1000)
        
        values = indicators.get_current_values()
        
        # Manual SMA = (10 + 20 + 30 + 40 + 50) / 5 = 30
        assert abs(values['sma_5'] - 30.0) < 0.001
    
    def test_ema_accuracy(self):
        """Test EMA calculation accuracy"""
        ema = IncrementalEMA(period=10)
        
        # Known test case
        prices = [22.27, 22.19, 22.08, 22.17, 22.18, 22.13, 22.23, 22.43, 22.24, 22.29]
        
        for price in prices:
            result = ema.update(price)
        
        # First EMA should be first price
        # Subsequent EMAs should be calculated incrementally
        assert result is not None
        assert 22.0 < result < 23.0
    
    def test_bollinger_bands_width(self):
        """Test Bollinger Bands width calculation"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', bb_period=5, bb_std=2.0)
        
        # Constant prices (no volatility)
        for _ in range(5):
            indicators.update(100.0, 1000)
        
        values = indicators.get_current_values()
        
        # With no volatility, bands should be very close
        assert values['bb_width'] < 0.1
