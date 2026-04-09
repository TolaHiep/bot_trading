"""Property-Based Tests for Indicator Calculations

Tests for indicator performance and correctness properties.
"""

import time
import pytest
import numpy as np
from hypothesis import given, settings, strategies as st

from src.alpha.indicators import IndicatorEngine, TechnicalIndicators
from src.alpha.incremental_ema import IncrementalEMA, IncrementalRSI


class TestProperty10IndicatorUpdatePerformance:
    """Property 10: Indicator Update Performance
    
    **Validates: Requirements 4.1**
    
    For any new kline data, all technical indicators should be updated
    within 50 milliseconds.
    """
    
    @given(
        close=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
        volume=st.floats(min_value=0.0, max_value=1000000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=1000)
    def test_single_update_performance(self, close, volume):
        """Test single indicator update completes in < 50ms"""
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        # Warm up with some data
        for i in range(50):
            indicators.update(close + i * 0.1, volume)
        
        # Measure update time
        start_time = time.perf_counter()
        indicators.update(close, volume)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Should complete in < 50ms
        assert elapsed_ms < 50, f"Update took {elapsed_ms:.2f}ms (> 50ms)"
    
    @pytest.mark.parametrize("num_updates", [10, 50, 100])
    def test_multiple_updates_performance(self, num_updates):
        """Test multiple updates maintain < 50ms latency"""
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        # Warm up
        for i in range(50):
            indicators.update(50000.0 + i, 1000)
        
        # Measure multiple updates
        update_times = []
        
        for i in range(num_updates):
            start_time = time.perf_counter()
            indicators.update(50000.0 + i, 1000)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            update_times.append(elapsed_ms)
        
        # All updates should be < 50ms
        max_time = max(update_times)
        avg_time = sum(update_times) / len(update_times)
        
        assert max_time < 50, f"Max update time: {max_time:.2f}ms (> 50ms)"
        assert avg_time < 25, f"Avg update time: {avg_time:.2f}ms (should be well under 50ms)"
    
    def test_engine_update_performance(self):
        """Test IndicatorEngine update performance"""
        engine = IndicatorEngine()
        
        # Warm up
        for i in range(50):
            engine.update('BTCUSDT', '1m', 50000.0 + i, 1000)
        
        # Measure update
        start_time = time.perf_counter()
        engine.update('BTCUSDT', '1m', 50100.0, 1000)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        assert elapsed_ms < 50, f"Engine update took {elapsed_ms:.2f}ms (> 50ms)"


class TestEMAProperties:
    """Test EMA calculation properties"""
    
    @given(
        period=st.integers(min_value=2, max_value=200),
        prices=st.lists(
            st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=100
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_ema_smoothness(self, period, prices):
        """Test EMA is smoother than price changes"""
        ema = IncrementalEMA(period)
        
        ema_values = []
        for price in prices:
            result = ema.update(price)
            if result is not None:
                ema_values.append(result)
        
        if len(ema_values) < 2:
            return
        
        # EMA changes should be smaller than price changes (smoothing effect)
        price_changes = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        ema_changes = [abs(ema_values[i] - ema_values[i-1]) for i in range(1, len(ema_values))]
        
        avg_price_change = sum(price_changes) / len(price_changes)
        avg_ema_change = sum(ema_changes) / len(ema_changes)
        
        # EMA should smooth out price movements
        assert avg_ema_change <= avg_price_change * 1.5
    
    @given(
        period=st.integers(min_value=2, max_value=50),
        constant_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_ema_converges_to_constant(self, period, constant_price):
        """Test EMA converges to constant price"""
        ema = IncrementalEMA(period)
        
        # Feed constant price
        for _ in range(period * 5):
            result = ema.update(constant_price)
        
        # EMA should converge to the constant price
        assert abs(result - constant_price) < constant_price * 0.01


class TestRSIProperties:
    """Test RSI calculation properties"""
    
    @given(
        prices=st.lists(
            st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_rsi_range(self, prices):
        """Test RSI stays in 0-100 range"""
        rsi = IncrementalRSI(period=14)
        
        for price in prices:
            result = rsi.update(price)
            if result is not None:
                assert 0 <= result <= 100, f"RSI out of range: {result}"
    
    def test_rsi_uptrend(self):
        """Test RSI is high during uptrend"""
        rsi = IncrementalRSI(period=14)
        
        # Strong uptrend
        for i in range(30):
            rsi.update(100.0 + i * 2)
        
        result = rsi.get_value()
        assert result is not None
        assert result > 70, f"RSI should be > 70 in uptrend, got {result}"
    
    def test_rsi_downtrend(self):
        """Test RSI is low during downtrend"""
        rsi = IncrementalRSI(period=14)
        
        # Strong downtrend
        for i in range(30):
            rsi.update(100.0 - i * 2)
        
        result = rsi.get_value()
        assert result is not None
        assert result < 30, f"RSI should be < 30 in downtrend, got {result}"


class TestSMAProperties:
    """Test SMA calculation properties"""
    
    @given(
        period=st.integers(min_value=2, max_value=50),
        prices=st.lists(
            st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=100
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_sma_within_price_range(self, period, prices):
        """Test SMA stays within min/max price range"""
        if len(prices) < period:
            return
        
        indicators = TechnicalIndicators('BTCUSDT', '1m', sma_periods=[period])
        
        for price in prices:
            indicators.update(price, 1000)
        
        values = indicators.get_current_values()
        sma_key = f'sma_{period}'
        
        if sma_key in values:
            sma = values[sma_key]
            recent_prices = prices[-period:]
            
            # SMA should be within min/max of recent prices
            assert min(recent_prices) <= sma <= max(recent_prices)
    
    @given(
        period=st.integers(min_value=2, max_value=20),
        constant_price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_sma_equals_constant_price(self, period, constant_price):
        """Test SMA equals constant price when all prices are same"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', sma_periods=[period])
        
        # Feed constant price
        for _ in range(period):
            indicators.update(constant_price, 1000)
        
        values = indicators.get_current_values()
        sma_key = f'sma_{period}'
        
        assert sma_key in values
        assert abs(values[sma_key] - constant_price) < 0.001


class TestBollingerBandsProperties:
    """Test Bollinger Bands properties"""
    
    @given(
        prices=st.lists(
            st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_bb_ordering(self, prices):
        """Test Bollinger Bands ordering: upper > middle > lower"""
        indicators = TechnicalIndicators('BTCUSDT', '1m', bb_period=20)
        
        for price in prices:
            indicators.update(price, 1000)
        
        values = indicators.get_current_values()
        
        if 'bb_upper' in values:
            assert values['bb_upper'] >= values['bb_middle']
            assert values['bb_middle'] >= values['bb_lower']
            assert values['bb_width'] >= 0
    
    def test_bb_width_with_volatility(self):
        """Test BB width increases with volatility"""
        # Low volatility
        indicators_low = TechnicalIndicators('BTCUSDT', '1m', bb_period=20)
        for i in range(20):
            indicators_low.update(100.0 + np.random.randn() * 0.1, 1000)
        
        values_low = indicators_low.get_current_values()
        
        # High volatility
        indicators_high = TechnicalIndicators('BTCUSDT', '1m', bb_period=20)
        for i in range(20):
            indicators_high.update(100.0 + np.random.randn() * 10, 1000)
        
        values_high = indicators_high.get_current_values()
        
        # High volatility should have wider bands
        assert values_high['bb_width'] > values_low['bb_width']


class TestMACDProperties:
    """Test MACD properties"""
    
    @given(
        prices=st.lists(
            st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=50,
            max_size=100
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_macd_histogram_consistency(self, prices):
        """Test MACD histogram = MACD line - signal line"""
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        for price in prices:
            indicators.update(price, 1000)
        
        values = indicators.get_current_values()
        
        if all(k in values for k in ['macd_line', 'macd_signal', 'macd_histogram']):
            expected_histogram = values['macd_line'] - values['macd_signal']
            assert abs(values['macd_histogram'] - expected_histogram) < 0.001


class TestVolumeProfileProperties:
    """Test Volume Profile properties"""
    
    @given(
        prices=st.lists(
            st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=50,
            max_size=100
        ),
        volumes=st.lists(
            st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
            min_size=50,
            max_size=100
        )
    )
    @settings(max_examples=30, deadline=3000)
    def test_vp_poc_within_price_range(self, prices, volumes):
        """Test Volume Profile POC is within price range"""
        if len(prices) != len(volumes):
            volumes = volumes[:len(prices)]
        
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        for price, volume in zip(prices, volumes):
            indicators.update(price, volume)
        
        values = indicators.get_current_values()
        
        if 'vp_poc' in values:
            # POC should be within observed price range
            assert min(prices) <= values['vp_poc'] <= max(prices)
    
    @given(
        prices=st.lists(
            st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
            min_size=50,
            max_size=100
        ),
        volumes=st.lists(
            st.floats(min_value=1.0, max_value=1000000.0, allow_nan=False, allow_infinity=False),
            min_size=50,
            max_size=100
        )
    )
    @settings(max_examples=30, deadline=3000)
    def test_vp_value_area_ordering(self, prices, volumes):
        """Test Value Area High >= Value Area Low"""
        if len(prices) != len(volumes):
            volumes = volumes[:len(prices)]
        
        indicators = TechnicalIndicators('BTCUSDT', '1m')
        
        for price, volume in zip(prices, volumes):
            indicators.update(price, volume)
        
        values = indicators.get_current_values()
        
        if 'vp_value_area_high' in values and 'vp_value_area_low' in values:
            assert values['vp_value_area_high'] >= values['vp_value_area_low']


class TestIndicatorEngineProperties:
    """Test IndicatorEngine properties"""
    
    @given(
        symbols=st.lists(
            st.sampled_from(['BTCUSDT', 'ETHUSDT', 'SOLUSDT']),
            min_size=1,
            max_size=5
        ),
        timeframes=st.lists(
            st.sampled_from(['1m', '5m', '15m', '1h']),
            min_size=1,
            max_size=4
        )
    )
    @settings(max_examples=30, deadline=3000)
    def test_engine_tracks_all_pairs(self, symbols, timeframes):
        """Test engine tracks all symbol/timeframe pairs independently"""
        engine = IndicatorEngine()
        
        # Update all combinations
        for symbol in symbols:
            for timeframe in timeframes:
                engine.update(symbol, timeframe, 50000.0, 1000)
        
        # Should track all unique pairs
        tracked = engine.get_tracked_pairs()
        expected_pairs = set((s, t) for s in symbols for t in timeframes)
        
        assert len(tracked) == len(expected_pairs)
        assert set(tracked) == expected_pairs
