"""Unit Tests for Order Flow Analysis

Tests for order flow analyzer and footprint generator.
"""

import pytest
import numpy as np

from src.alpha.order_flow import OrderFlowAnalyzer, OrderFlowEngine, Trade, ImbalanceZone
from src.alpha.footprint import FootprintGenerator, FootprintEngine, FootprintBar


class TestOrderFlowAnalyzer:
    """Test OrderFlowAnalyzer"""
    
    def test_init(self):
        """Test initialization"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', window_size=1000)
        assert analyzer.symbol == 'BTCUSDT'
        assert analyzer.timeframe == '1m'
        assert analyzer.window_size == 1000
        assert analyzer.cumulative_delta == 0.0
        assert len(analyzer.trades) == 0
    
    def test_add_buy_trade(self):
        """Test adding buy trade increases delta"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        metrics = analyzer.add_trade(
            timestamp=1000000,
            price=50000.0,
            quantity=1.0,
            side='Buy'
        )
        
        assert analyzer.cumulative_delta == 1.0
        assert metrics['cumulative_delta'] == 1.0
        assert metrics['buy_volume'] == 1.0
        assert metrics['sell_volume'] == 0.0
    
    def test_add_sell_trade(self):
        """Test adding sell trade decreases delta"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        metrics = analyzer.add_trade(
            timestamp=1000000,
            price=50000.0,
            quantity=1.0,
            side='Sell'
        )
        
        assert analyzer.cumulative_delta == -1.0
        assert metrics['cumulative_delta'] == -1.0
        assert metrics['buy_volume'] == 0.0
        assert metrics['sell_volume'] == 1.0
    
    def test_cumulative_delta_calculation(self):
        """Test cumulative delta calculation"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        # Add buy trades
        analyzer.add_trade(1000000, 50000.0, 2.0, 'Buy')
        analyzer.add_trade(1000001, 50010.0, 1.5, 'Buy')
        
        # Add sell trades
        analyzer.add_trade(1000002, 50005.0, 1.0, 'Sell')
        
        # Delta = 2.0 + 1.5 - 1.0 = 2.5
        assert analyzer.cumulative_delta == 2.5
    
    def test_buy_sell_ratios(self):
        """Test buy/sell ratio calculation"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        # Add 3 buy, 1 sell
        analyzer.add_trade(1000000, 50000.0, 1.0, 'Buy')
        analyzer.add_trade(1000001, 50010.0, 1.0, 'Buy')
        analyzer.add_trade(1000002, 50020.0, 1.0, 'Buy')
        metrics = analyzer.add_trade(1000003, 50015.0, 1.0, 'Sell')
        
        # Buy ratio = 3/4 = 0.75
        # Sell ratio = 1/4 = 0.25
        assert abs(metrics['buy_ratio'] - 0.75) < 0.01
        assert abs(metrics['sell_ratio'] - 0.25) < 0.01
    
    def test_imbalance_detection_buy(self):
        """Test buy imbalance detection"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', imbalance_threshold=0.7)
        
        # Add 8 buy, 2 sell (80% buy)
        for i in range(8):
            analyzer.add_trade(1000000 + i, 50000.0, 1.0, 'Buy')
        
        for i in range(2):
            metrics = analyzer.add_trade(1000010 + i, 50000.0, 1.0, 'Sell')
        
        assert metrics['imbalance'] == 'BUY'
        assert metrics['imbalance_strength'] > 0.7
    
    def test_imbalance_detection_sell(self):
        """Test sell imbalance detection"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', imbalance_threshold=0.7)
        
        # Add 2 buy, 8 sell (80% sell)
        for i in range(2):
            analyzer.add_trade(1000000 + i, 50000.0, 1.0, 'Buy')
        
        for i in range(8):
            metrics = analyzer.add_trade(1000010 + i, 50000.0, 1.0, 'Sell')
        
        assert metrics['imbalance'] == 'SELL'
        assert metrics['imbalance_strength'] > 0.7
    
    def test_imbalance_detection_neutral(self):
        """Test neutral (no imbalance) detection"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', imbalance_threshold=0.7)
        
        # Add 5 buy, 5 sell (50/50)
        for i in range(5):
            analyzer.add_trade(1000000 + i, 50000.0, 1.0, 'Buy')
        
        for i in range(5):
            metrics = analyzer.add_trade(1000010 + i, 50000.0, 1.0, 'Sell')
        
        assert metrics['imbalance'] == 'NEUTRAL'
    
    def test_rolling_window(self):
        """Test rolling window maintains size limit"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', window_size=10)
        
        # Add 20 trades
        for i in range(20):
            analyzer.add_trade(1000000 + i, 50000.0, 1.0, 'Buy')
        
        # Should only keep last 10
        assert len(analyzer.trades) == 10
    
    def test_get_imbalance_zones(self):
        """Test getting imbalance zones by price level"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m', imbalance_threshold=0.7)
        
        # Add trades at different price levels
        # High buy volume at 50000
        for i in range(10):
            analyzer.add_trade(1000000 + i, 50000.0, 1.0, 'Buy')
        
        # High sell volume at 50100
        for i in range(10):
            analyzer.add_trade(1000100 + i, 50100.0, 1.0, 'Sell')
        
        zones = analyzer.get_imbalance_zones(num_bins=10)
        
        # Should detect imbalance zones
        assert len(zones) > 0
        
        # Check zone properties
        for zone in zones:
            assert isinstance(zone, ImbalanceZone)
            assert zone.buy_volume >= 0
            assert zone.sell_volume >= 0
            assert abs(zone.imbalance_ratio) > 0.7
    
    def test_reset(self):
        """Test resetting analyzer"""
        analyzer = OrderFlowAnalyzer('BTCUSDT', '1m')
        
        # Add data
        analyzer.add_trade(1000000, 50000.0, 1.0, 'Buy')
        analyzer.add_trade(1000001, 50010.0, 1.0, 'Sell')
        
        # Reset
        analyzer.reset()
        
        assert len(analyzer.trades) == 0
        assert analyzer.cumulative_delta == 0.0
        assert len(analyzer.current_metrics) == 0


class TestOrderFlowEngine:
    """Test OrderFlowEngine"""
    
    def test_init(self):
        """Test initialization"""
        engine = OrderFlowEngine()
        assert len(engine.analyzers) == 0
    
    def test_get_or_create_analyzer(self):
        """Test getting or creating analyzer"""
        engine = OrderFlowEngine()
        
        analyzer = engine.get_or_create_analyzer('BTCUSDT', '1m')
        assert analyzer.symbol == 'BTCUSDT'
        assert analyzer.timeframe == '1m'
        
        # Should return same instance
        analyzer2 = engine.get_or_create_analyzer('BTCUSDT', '1m')
        assert analyzer is analyzer2
    
    def test_add_trade(self):
        """Test adding trade"""
        engine = OrderFlowEngine()
        
        metrics = engine.add_trade(
            symbol='BTCUSDT',
            timeframe='1m',
            timestamp=1000000,
            price=50000.0,
            quantity=1.0,
            side='Buy'
        )
        
        assert metrics['cumulative_delta'] == 1.0
    
    def test_multiple_symbols_timeframes(self):
        """Test managing multiple symbols and timeframes"""
        engine = OrderFlowEngine()
        
        # Add trades for different pairs
        engine.add_trade('BTCUSDT', '1m', 1000000, 50000.0, 1.0, 'Buy')
        engine.add_trade('BTCUSDT', '5m', 1000000, 50100.0, 1.0, 'Sell')
        engine.add_trade('ETHUSDT', '1m', 1000000, 3000.0, 1.0, 'Buy')
        
        # Should have 3 analyzers
        assert len(engine.analyzers) == 3
        
        # Each should have independent metrics
        btc_1m = engine.get_metrics('BTCUSDT', '1m')
        btc_5m = engine.get_metrics('BTCUSDT', '5m')
        eth_1m = engine.get_metrics('ETHUSDT', '1m')
        
        assert btc_1m['cumulative_delta'] == 1.0
        assert btc_5m['cumulative_delta'] == -1.0
        assert eth_1m['cumulative_delta'] == 1.0
    
    def test_get_tracked_pairs(self):
        """Test getting tracked pairs"""
        engine = OrderFlowEngine()
        
        engine.add_trade('BTCUSDT', '1m', 1000000, 50000.0, 1.0, 'Buy')
        engine.add_trade('ETHUSDT', '5m', 1000000, 3000.0, 1.0, 'Sell')
        
        pairs = engine.get_tracked_pairs()
        assert len(pairs) == 2
        assert ('BTCUSDT', '1m') in pairs
        assert ('ETHUSDT', '5m') in pairs


class TestFootprintGenerator:
    """Test FootprintGenerator"""
    
    def test_init(self):
        """Test initialization"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=0.5)
        assert generator.symbol == 'BTCUSDT'
        assert generator.timeframe == '1m'
        assert generator.tick_size == 0.5
        assert len(generator.bars) == 0
    
    def test_add_trade_creates_bar(self):
        """Test adding trade creates footprint bar"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add first trade
        result = generator.add_trade(
            timestamp=1000000,
            price=50000.0,
            quantity=1.0,
            side='Buy',
            bar_open=50000.0,
            bar_high=50010.0,
            bar_low=49990.0,
            bar_close=50005.0
        )
        
        # First trade should not complete a bar
        assert result is None
        assert generator.current_bar is not None
    
    def test_new_timestamp_completes_bar(self):
        """Test new timestamp completes previous bar"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add trade for timestamp 1
        generator.add_trade(1000000, 50000.0, 1.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)
        
        # Add trade for timestamp 2 (should complete bar 1)
        completed_bar = generator.add_trade(
            2000000, 50100.0, 1.0, 'Sell',
            50100.0, 50110.0, 50090.0, 50105.0
        )
        
        assert completed_bar is not None
        assert isinstance(completed_bar, FootprintBar)
        assert completed_bar.timestamp == 1000000
        assert len(generator.bars) == 1
    
    def test_footprint_bar_structure(self):
        """Test footprint bar contains correct data"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add trades
        generator.add_trade(1000000, 50000.0, 2.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)
        generator.add_trade(1000000, 50001.0, 1.0, 'Sell', 50000.0, 50010.0, 49990.0, 50005.0)
        
        # Complete bar
        completed_bar = generator.add_trade(
            2000000, 50100.0, 1.0, 'Buy',
            50100.0, 50110.0, 50090.0, 50105.0
        )
        
        assert completed_bar.total_buy_volume == 2.0
        assert completed_bar.total_sell_volume == 1.0
        assert completed_bar.total_delta == 1.0
        assert len(completed_bar.price_levels) > 0
    
    def test_price_level_aggregation(self):
        """Test trades are aggregated by price level"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add multiple trades at same price level
        generator.add_trade(1000000, 50000.0, 1.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)
        generator.add_trade(1000000, 50000.5, 1.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)  # Rounds to 50000
        generator.add_trade(1000000, 50000.0, 0.5, 'Sell', 50000.0, 50010.0, 49990.0, 50005.0)
        
        # Complete bar
        completed_bar = generator.add_trade(
            2000000, 50100.0, 1.0, 'Buy',
            50100.0, 50110.0, 50090.0, 50105.0
        )
        
        # Check aggregation at 50000 level
        assert 50000.0 in completed_bar.price_levels
        level = completed_bar.price_levels[50000.0]
        assert level['buy'] == 2.0
        assert level['sell'] == 0.5
        assert level['delta'] == 1.5
    
    def test_poc_calculation(self):
        """Test Point of Control calculation"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add high volume at 50000
        for i in range(10):
            generator.add_trade(1000000, 50000.0, 1.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)
        
        # Add low volume at 50005
        generator.add_trade(1000000, 50005.0, 0.5, 'Sell', 50000.0, 50010.0, 49990.0, 50005.0)
        
        # Complete bar
        completed_bar = generator.add_trade(
            2000000, 50100.0, 1.0, 'Buy',
            50100.0, 50110.0, 50090.0, 50105.0
        )
        
        # POC should be at 50000 (highest volume)
        assert completed_bar.poc_price == 50000.0
    
    def test_get_bar_summary(self):
        """Test getting bar summary"""
        generator = FootprintGenerator('BTCUSDT', '1m', tick_size=1.0)
        
        # Add trades
        for i in range(10):
            generator.add_trade(1000000, 50000.0, 1.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)
        
        # Complete bar
        completed_bar = generator.add_trade(
            2000000, 50100.0, 1.0, 'Buy',
            50100.0, 50110.0, 50090.0, 50105.0
        )
        
        summary = generator.get_bar_summary(completed_bar)
        
        assert 'timestamp' in summary
        assert 'ohlc' in summary
        assert 'volume' in summary
        assert 'poc_price' in summary
        assert 'imbalances' in summary
    
    def test_reset(self):
        """Test resetting generator"""
        generator = FootprintGenerator('BTCUSDT', '1m')
        
        # Add data
        generator.add_trade(1000000, 50000.0, 1.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)
        generator.add_trade(2000000, 50100.0, 1.0, 'Sell', 50100.0, 50110.0, 50090.0, 50105.0)
        
        # Reset
        generator.reset()
        
        assert len(generator.bars) == 0
        assert generator.current_bar is None


class TestFootprintEngine:
    """Test FootprintEngine"""
    
    def test_init(self):
        """Test initialization"""
        engine = FootprintEngine()
        assert len(engine.generators) == 0
    
    def test_get_or_create_generator(self):
        """Test getting or creating generator"""
        engine = FootprintEngine()
        
        generator = engine.get_or_create_generator('BTCUSDT', '1m')
        assert generator.symbol == 'BTCUSDT'
        assert generator.timeframe == '1m'
        
        # Should return same instance
        generator2 = engine.get_or_create_generator('BTCUSDT', '1m')
        assert generator is generator2
    
    def test_add_trade(self):
        """Test adding trade"""
        engine = FootprintEngine()
        
        result = engine.add_trade(
            symbol='BTCUSDT',
            timeframe='1m',
            timestamp=1000000,
            price=50000.0,
            quantity=1.0,
            side='Buy',
            bar_open=50000.0,
            bar_high=50010.0,
            bar_low=49990.0,
            bar_close=50005.0
        )
        
        # First trade should not complete a bar
        assert result is None
    
    def test_multiple_symbols_timeframes(self):
        """Test managing multiple symbols and timeframes"""
        engine = FootprintEngine()
        
        # Add trades for different pairs
        engine.add_trade('BTCUSDT', '1m', 1000000, 50000.0, 1.0, 'Buy', 50000.0, 50010.0, 49990.0, 50005.0)
        engine.add_trade('BTCUSDT', '5m', 1000000, 50100.0, 1.0, 'Sell', 50100.0, 50110.0, 50090.0, 50105.0)
        engine.add_trade('ETHUSDT', '1m', 1000000, 3000.0, 1.0, 'Buy', 3000.0, 3010.0, 2990.0, 3005.0)
        
        # Should have 3 generators
        assert len(engine.generators) == 3
