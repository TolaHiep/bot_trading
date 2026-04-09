"""Property-Based Tests for Order Flow Analysis

Tests for order flow properties and invariants.
"""

import pytest
from hypothesis import given, settings, strategies as st

from src.alpha.order_flow import OrderFlowAnalyzer, OrderFlowEngine
from src.alpha.footprint import FootprintGenerator


class TestProperty11CumulativeDeltaCalculation:
    """Property 11: Cumulative Delta Calculation
    
    **Validates: Requirements 5.1**
    
    For any sequence of trades, cumulative delta should equal
    sum of buy volumes minus sum of sell volumes.
    """
    
    @given(
        trades=st.lists(
            st.tuples(
                st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),  # price
                st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),  # quantity
                st.sampled_from(['Buy', 'Sell'])  # side
            ),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=100, deadline=2000)
    def test_cumulative_delta_equals_buy_minus_sell(self, trades):
        """Test cumulative delta = buy volume - sell volume"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        expected_buy_volume = 0.0
        expected_sell_volume = 0.0
        
        for i, (price, quantity, side) in enumerate(trades):
            analyzer.add_trade(
                timestamp=1000000 + i,
                price=price,
                quantity=quantity,
                side=side
            )
            
            if side == 'Buy':
                expected_buy_volume += quantity
            else:
                expected_sell_volume += quantity
        
        expected_delta = expected_buy_volume - expected_sell_volume
        actual_delta = analyzer.cumulative_delta
        
        # Allow small floating point error
        assert abs(actual_delta - expected_delta) < 0.001


class TestProperty12FootprintAggregationConsistency:
    """Property 12: Footprint Aggregation Consistency
    
    **Validates: Requirements 5.2**
    
    For any footprint bar, the sum of volumes across all price levels
    should equal the total bar volume.
    """
    
    @given(
        trades=st.lists(
            st.tuples(
                st.floats(min_value=49000.0, max_value=51000.0, allow_nan=False, allow_infinity=False),  # price
                st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),  # quantity
                st.sampled_from(['Buy', 'Sell'])  # side
            ),
            min_size=10,
            max_size=50
        )
    )
    @settings(max_examples=50, deadline=3000)
    def test_footprint_volume_consistency(self, trades):
        """Test footprint bar volumes are consistent"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add all trades to same bar
        for i, (price, quantity, side) in enumerate(trades):
            generator.add_trade(
                timestamp=1000000,  # Same timestamp
                price=price,
                quantity=quantity,
                side=side,
                bar_open=50000.0,
                bar_high=51000.0,
                bar_low=49000.0,
                bar_close=50500.0
            )
        
        # Complete bar
        completed_bar = generator.add_trade(
            timestamp=2000000,  # New timestamp
            price=50000.0,
            quantity=1.0,
            side='Buy',
            bar_open=50000.0,
            bar_high=50010.0,
            bar_low=49990.0,
            bar_close=50005.0
        )
        
        if completed_bar is None:
            return
        
        # Sum volumes across all price levels
        total_buy_from_levels = sum(
            level['buy'] for level in completed_bar.price_levels.values()
        )
        total_sell_from_levels = sum(
            level['sell'] for level in completed_bar.price_levels.values()
        )
        
        # Should match bar totals
        assert abs(total_buy_from_levels - completed_bar.total_buy_volume) < 0.001
        assert abs(total_sell_from_levels - completed_bar.total_sell_volume) < 0.001


class TestProperty13ImbalanceZoneDetection:
    """Property 13: Imbalance Zone Detection
    
    **Validates: Requirements 5.3**
    
    For any detected imbalance zone, the volume ratio in one direction
    should exceed the configured threshold (default 70%).
    """
    
    @given(
        imbalance_threshold=st.floats(min_value=0.6, max_value=0.9)
    )
    @settings(max_examples=50)
    def test_imbalance_zones_exceed_threshold(self, imbalance_threshold):
        """Test all detected imbalance zones exceed threshold"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', imbalance_threshold=imbalance_threshold)
        
        # Add trades with clear imbalances
        # High buy volume at 50000
        for i in range(20):
            analyzer.add_trade(1000000 + i, 50000.0, 1.0, 'Buy')
        
        # High sell volume at 50100
        for i in range(20):
            analyzer.add_trade(1000100 + i, 50100.0, 1.0, 'Sell')
        
        # Balanced at 50050
        for i in range(10):
            analyzer.add_trade(1000200 + i, 50050.0, 1.0, 'Buy')
        for i in range(10):
            analyzer.add_trade(1000300 + i, 50050.0, 1.0, 'Sell')
        
        zones = analyzer.get_imbalance_zones(num_bins=20)
        
        # All detected zones should exceed threshold
        for zone in zones:
            assert abs(zone.imbalance_ratio) > imbalance_threshold


class TestProperty14RollingWindowSizeConstraint:
    """Property 14: Rolling Window Size Constraint
    
    **Validates: Requirements 5.4**
    
    For any order flow analyzer, the number of stored trades should
    never exceed the configured window size.
    """
    
    @given(
        window_size=st.integers(min_value=10, max_value=100),
        num_trades=st.integers(min_value=1, max_value=200)
    )
    @settings(max_examples=100, deadline=2000)
    def test_rolling_window_respects_size_limit(self, window_size, num_trades):
        """Test rolling window never exceeds size limit"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', window_size=window_size)
        
        # Add trades
        for i in range(num_trades):
            analyzer.add_trade(
                timestamp=1000000 + i,
                price=50000.0 + i * 0.1,
                quantity=1.0,
                side='Buy' if i % 2 == 0 else 'Sell'
            )
            
            # Window size should never exceed limit
            assert len(analyzer.trades) <= window_size


class TestProperty15TradeClassificationCompleteness:
    """Property 15: Trade Classification Completeness
    
    **Validates: Requirements 5.5**
    
    For any trade, it must be classified as either 'Buy' or 'Sell',
    and contribute to exactly one of buy_volume or sell_volume.
    """
    
    @given(
        trades=st.lists(
            st.tuples(
                st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(['Buy', 'Sell'])
            ),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=100, deadline=2000)
    def test_all_trades_classified(self, trades):
        """Test all trades are classified and counted"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        for i, (price, quantity, side) in enumerate(trades):
            analyzer.add_trade(
                timestamp=1000000 + i,
                price=price,
                quantity=quantity,
                side=side
            )
        
        metrics = analyzer.get_current_metrics()
        
        # Total volume should equal buy + sell
        total_volume = metrics['total_volume']
        buy_volume = metrics['buy_volume']
        sell_volume = metrics['sell_volume']
        
        assert abs(total_volume - (buy_volume + sell_volume)) < 0.001
        
        # Buy ratio + sell ratio should equal 1.0
        if total_volume > 0:
            assert abs(metrics['buy_ratio'] + metrics['sell_ratio'] - 1.0) < 0.001


class TestOrderFlowInvariants:
    """Test order flow invariants"""
    
    @given(
        trades=st.lists(
            st.tuples(
                st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(['Buy', 'Sell'])
            ),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_buy_sell_ratios_between_0_and_1(self, trades):
        """Test buy/sell ratios are always between 0 and 1"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        for i, (price, quantity, side) in enumerate(trades):
            metrics = analyzer.add_trade(
                timestamp=1000000 + i,
                price=price,
                quantity=quantity,
                side=side
            )
            
            assert 0.0 <= metrics['buy_ratio'] <= 1.0
            assert 0.0 <= metrics['sell_ratio'] <= 1.0
    
    @given(
        trades=st.lists(
            st.tuples(
                st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(['Buy', 'Sell'])
            ),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_volumes_always_non_negative(self, trades):
        """Test volumes are always non-negative"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        for i, (price, quantity, side) in enumerate(trades):
            metrics = analyzer.add_trade(
                timestamp=1000000 + i,
                price=price,
                quantity=quantity,
                side=side
            )
            
            assert metrics['buy_volume'] >= 0
            assert metrics['sell_volume'] >= 0
            assert metrics['total_volume'] >= 0


class TestFootprintInvariants:
    """Test footprint chart invariants"""
    
    @given(
        trades=st.lists(
            st.tuples(
                st.floats(min_value=49000.0, max_value=51000.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(['Buy', 'Sell'])
            ),
            min_size=5,
            max_size=30
        )
    )
    @settings(max_examples=50, deadline=3000)
    def test_footprint_delta_consistency(self, trades):
        """Test footprint delta = buy volume - sell volume"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add all trades to same bar
        for i, (price, quantity, side) in enumerate(trades):
            generator.add_trade(
                timestamp=1000000,
                price=price,
                quantity=quantity,
                side=side,
                bar_open=50000.0,
                bar_high=51000.0,
                bar_low=49000.0,
                bar_close=50500.0
            )
        
        # Complete bar
        completed_bar = generator.add_trade(
            timestamp=2000000,
            price=50000.0,
            quantity=1.0,
            side='Buy',
            bar_open=50000.0,
            bar_high=50010.0,
            bar_low=49990.0,
            bar_close=50005.0
        )
        
        if completed_bar is None:
            return
        
        # Delta should equal buy - sell
        expected_delta = completed_bar.total_buy_volume - completed_bar.total_sell_volume
        assert abs(completed_bar.total_delta - expected_delta) < 0.001
    
    @given(
        trades=st.lists(
            st.tuples(
                st.floats(min_value=49000.0, max_value=51000.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.sampled_from(['Buy', 'Sell'])
            ),
            min_size=5,
            max_size=30
        )
    )
    @settings(max_examples=50, deadline=3000)
    def test_poc_within_price_range(self, trades):
        """Test POC is within bar's price range"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        prices = [t[0] for t in trades]
        bar_low = min(prices)
        bar_high = max(prices)
        
        # Add all trades
        for i, (price, quantity, side) in enumerate(trades):
            generator.add_trade(
                timestamp=1000000,
                price=price,
                quantity=quantity,
                side=side,
                bar_open=prices[0],
                bar_high=bar_high,
                bar_low=bar_low,
                bar_close=prices[-1]
            )
        
        # Complete bar
        completed_bar = generator.add_trade(
            timestamp=2000000,
            price=50000.0,
            quantity=1.0,
            side='Buy',
            bar_open=50000.0,
            bar_high=50010.0,
            bar_low=49990.0,
            bar_close=50005.0
        )
        
        if completed_bar is None:
            return
        
        # POC should be within bar's price range
        assert bar_low <= completed_bar.poc_price <= bar_high


class TestOrderFlowEngineProperties:
    """Test OrderFlowEngine properties"""
    
    @given(
        symbols=st.lists(
            st.sampled_from(['BTCUSDT', 'ETHUSDT', 'SOLUSDT']),
            min_size=1,
            max_size=3
        ),
        timeframes=st.lists(
            st.sampled_from(['1m', '5m', '15m']),
            min_size=1,
            max_size=3
        )
    )
    @settings(max_examples=30, deadline=2000)
    def test_engine_tracks_independent_pairs(self, symbols, timeframes):
        """Test engine maintains independent state for each pair"""
        engine = OrderFlowEngine()
        
        # Add trades to all combinations
        for symbol in symbols:
            for timeframe in timeframes:
                engine.add_trade(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=1000000,
                    price=50000.0,
                    quantity=1.0,
                    side='Buy'
                )
        
        # Should track all unique pairs
        tracked = engine.get_tracked_pairs()
        expected_pairs = set((s, t) for s in symbols for t in timeframes)
        
        assert len(tracked) == len(expected_pairs)
        assert set(tracked) == expected_pairs
