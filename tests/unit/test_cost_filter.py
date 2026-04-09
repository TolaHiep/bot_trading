"""
Unit tests for Cost Filter
"""

import pytest
from decimal import Decimal

from src.execution.cost_filter import (
    CostFilter,
    Orderbook,
    OrderbookLevel,
    CostAnalysis
)


@pytest.fixture
def cost_filter():
    """Create CostFilter instance"""
    return CostFilter(
        max_slippage_pct=Decimal("0.1"),
        max_total_cost_pct=Decimal("0.2"),
        max_spread_pct=Decimal("0.05"),
        commission_rate=Decimal("0.06")
    )


@pytest.fixture
def sample_orderbook():
    """Create sample orderbook"""
    return Orderbook(
        symbol="BTCUSDT",
        bids=[
            OrderbookLevel(price=Decimal("50000"), quantity=Decimal("1.0")),
            OrderbookLevel(price=Decimal("49990"), quantity=Decimal("2.0")),
            OrderbookLevel(price=Decimal("49980"), quantity=Decimal("3.0")),
        ],
        asks=[
            OrderbookLevel(price=Decimal("50010"), quantity=Decimal("1.0")),
            OrderbookLevel(price=Decimal("50020"), quantity=Decimal("2.0")),
            OrderbookLevel(price=Decimal("50030"), quantity=Decimal("3.0")),
        ],
        timestamp=1234567890.0
    )


class TestOrderbook:
    """Test Orderbook functionality"""
    
    def test_best_bid(self, sample_orderbook):
        """Test best bid price"""
        assert sample_orderbook.best_bid == Decimal("50000")
    
    def test_best_ask(self, sample_orderbook):
        """Test best ask price"""
        assert sample_orderbook.best_ask == Decimal("50010")
    
    def test_spread(self, sample_orderbook):
        """Test bid-ask spread"""
        assert sample_orderbook.spread == Decimal("10")
    
    def test_spread_pct(self, sample_orderbook):
        """Test spread percentage"""
        # Mid price = (50000 + 50010) / 2 = 50005
        # Spread % = 10 / 50005 * 100 ≈ 0.02%
        spread_pct = sample_orderbook.spread_pct
        assert Decimal("0.019") < spread_pct < Decimal("0.021")
    
    def test_empty_orderbook(self):
        """Test empty orderbook"""
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[],
            asks=[],
            timestamp=1234567890.0
        )
        
        assert orderbook.best_bid == Decimal("0")
        assert orderbook.best_ask == Decimal("0")
        assert orderbook.spread == Decimal("0")
        assert orderbook.spread_pct == Decimal("0")


class TestSlippageCalculation:
    """Test slippage calculation"""
    
    def test_calculate_slippage_small_order(self, cost_filter, sample_orderbook):
        """Test slippage for small order (fills at best price)"""
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            sample_orderbook, "Buy", Decimal("0.5")
        )
        
        # Should fill entirely at best ask (50010)
        assert avg_price == Decimal("50010")
        assert slippage_pct == Decimal("0")
    
    def test_calculate_slippage_medium_order(self, cost_filter, sample_orderbook):
        """Test slippage for medium order (fills across multiple levels)"""
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            sample_orderbook, "Buy", Decimal("2.0")
        )
        
        # Should fill: 1.0 @ 50010, 1.0 @ 50020
        # Avg = (1.0 * 50010 + 1.0 * 50020) / 2.0 = 50015
        expected_avg = Decimal("50015")
        assert avg_price == expected_avg
        
        # Slippage = (50015 - 50010) / 50010 * 100 ≈ 0.01%
        assert Decimal("0.009") < slippage_pct < Decimal("0.011")
    
    def test_calculate_slippage_large_order(self, cost_filter, sample_orderbook):
        """Test slippage for large order (fills all levels)"""
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            sample_orderbook, "Buy", Decimal("6.0")
        )
        
        # Should fill: 1.0 @ 50010, 2.0 @ 50020, 3.0 @ 50030
        # Avg = (1.0*50010 + 2.0*50020 + 3.0*50030) / 6.0 = 50023.33
        expected_avg = (
            Decimal("1.0") * Decimal("50010") +
            Decimal("2.0") * Decimal("50020") +
            Decimal("3.0") * Decimal("50030")
        ) / Decimal("6.0")
        
        assert abs(avg_price - expected_avg) < Decimal("0.01")
        
        # Slippage should be > 0
        assert slippage_pct > Decimal("0")
    
    def test_calculate_slippage_insufficient_liquidity(self, cost_filter, sample_orderbook):
        """Test slippage when insufficient liquidity"""
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            sample_orderbook, "Buy", Decimal("100.0")
        )
        
        # Should return 100% slippage (reject)
        assert slippage_pct == Decimal("100")
        assert avg_price == Decimal("0")
    
    def test_calculate_slippage_sell_order(self, cost_filter, sample_orderbook):
        """Test slippage for sell order"""
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            sample_orderbook, "Sell", Decimal("0.5")
        )
        
        # Should fill entirely at best bid (50000)
        assert avg_price == Decimal("50000")
        assert slippage_pct == Decimal("0")


class TestCostAnalysis:
    """Test cost analysis"""
    
    def test_analyze_trade_approved(self, cost_filter, sample_orderbook):
        """Test trade approval with acceptable costs"""
        analysis = cost_filter.analyze_trade(
            sample_orderbook, "Buy", Decimal("0.5")
        )
        
        assert not analysis.should_reject
        assert analysis.reject_reason is None
        assert analysis.expected_slippage == Decimal("0")
        assert analysis.commission == Decimal("0.06")
        assert analysis.total_cost < cost_filter.max_total_cost_pct
    
    def test_analyze_trade_high_slippage(self, cost_filter):
        """Test trade rejection due to high slippage"""
        # Create orderbook with wide levels
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("50000"), quantity=Decimal("0.1")),
                OrderbookLevel(price=Decimal("49000"), quantity=Decimal("1.0")),
            ],
            asks=[
                OrderbookLevel(price=Decimal("50010"), quantity=Decimal("0.1")),
                OrderbookLevel(price=Decimal("51000"), quantity=Decimal("1.0")),
            ],
            timestamp=1234567890.0
        )
        
        analysis = cost_filter.analyze_trade(
            orderbook, "Buy", Decimal("1.0")
        )
        
        assert analysis.should_reject
        assert "Slippage too high" in analysis.reject_reason
    
    def test_analyze_trade_wide_spread(self, cost_filter):
        """Test trade rejection due to wide spread"""
        # Create orderbook with wide spread
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("50000"), quantity=Decimal("1.0")),
            ],
            asks=[
                OrderbookLevel(price=Decimal("53000"), quantity=Decimal("1.0")),
            ],
            timestamp=1234567890.0
        )
        
        analysis = cost_filter.analyze_trade(
            orderbook, "Buy", Decimal("0.5")
        )
        
        assert analysis.should_reject
        assert "Spread too wide" in analysis.reject_reason
    
    def test_analyze_trade_high_total_cost(self, cost_filter):
        """Test trade rejection due to high total cost"""
        # Create orderbook with moderate slippage but high total cost
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("50000"), quantity=Decimal("0.1")),
                OrderbookLevel(price=Decimal("49950"), quantity=Decimal("1.0")),
            ],
            asks=[
                OrderbookLevel(price=Decimal("50010"), quantity=Decimal("0.1")),
                OrderbookLevel(price=Decimal("50100"), quantity=Decimal("1.0")),
            ],
            timestamp=1234567890.0
        )
        
        analysis = cost_filter.analyze_trade(
            orderbook, "Buy", Decimal("1.0")
        )
        
        # Should be rejected (either slippage or total cost)
        assert analysis.should_reject


class TestLimitOrderPreference:
    """Test limit order preference logic"""
    
    def test_prefer_limit_tight_spread(self, cost_filter, sample_orderbook):
        """Test limit order preference with tight spread"""
        should_use_limit = cost_filter.should_use_limit_order(
            sample_orderbook, "Buy", Decimal("0.5")
        )
        
        assert should_use_limit is True
    
    def test_prefer_market_wide_spread(self, cost_filter):
        """Test market order preference with wide spread"""
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("50000"), quantity=Decimal("1.0")),
            ],
            asks=[
                OrderbookLevel(price=Decimal("53000"), quantity=Decimal("1.0")),
            ],
            timestamp=1234567890.0
        )
        
        should_use_limit = cost_filter.should_use_limit_order(
            orderbook, "Buy", Decimal("0.5")
        )
        
        assert should_use_limit is False
    
    def test_prefer_market_high_slippage(self, cost_filter):
        """Test market order preference with high expected slippage"""
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("50000"), quantity=Decimal("0.01")),
                OrderbookLevel(price=Decimal("49900"), quantity=Decimal("1.0")),
            ],
            asks=[
                OrderbookLevel(price=Decimal("50010"), quantity=Decimal("0.01")),
                OrderbookLevel(price=Decimal("50100"), quantity=Decimal("1.0")),
            ],
            timestamp=1234567890.0
        )
        
        should_use_limit = cost_filter.should_use_limit_order(
            orderbook, "Buy", Decimal("1.0")
        )
        
        assert should_use_limit is False


class TestSlippageTracking:
    """Test slippage tracking and accuracy"""
    
    def test_record_actual_slippage(self, cost_filter):
        """Test recording actual slippage"""
        cost_filter.record_actual_slippage(
            expected_slippage=Decimal("0.05"),
            actual_slippage=Decimal("0.06")
        )
        
        assert len(cost_filter.expected_slippages) == 1
        assert len(cost_filter.actual_slippages) == 1
        assert cost_filter.expected_slippages[0] == Decimal("0.05")
        assert cost_filter.actual_slippages[0] == Decimal("0.06")
    
    def test_get_slippage_accuracy(self, cost_filter):
        """Test slippage accuracy calculation"""
        # Record multiple slippages
        cost_filter.record_actual_slippage(Decimal("0.05"), Decimal("0.06"))
        cost_filter.record_actual_slippage(Decimal("0.10"), Decimal("0.11"))
        cost_filter.record_actual_slippage(Decimal("0.08"), Decimal("0.09"))
        
        accuracy = cost_filter.get_slippage_accuracy()
        
        # Average error should be around 20%
        # (0.01/0.05 + 0.01/0.10 + 0.01/0.08) / 3 * 100
        assert accuracy is not None
        assert Decimal("10") < accuracy < Decimal("30")
    
    def test_get_slippage_accuracy_no_data(self, cost_filter):
        """Test slippage accuracy with no data"""
        accuracy = cost_filter.get_slippage_accuracy()
        assert accuracy is None


class TestCostBreakdown:
    """Test cost breakdown logging"""
    
    def test_log_cost_breakdown(self, cost_filter, sample_orderbook):
        """Test cost breakdown logging"""
        import logging
        
        # Set up logging to capture output
        logger = logging.getLogger("src.execution.cost_filter")
        logger.setLevel(logging.INFO)
        
        analysis = cost_filter.analyze_trade(
            sample_orderbook, "Buy", Decimal("0.5")
        )
        
        # Just verify the method runs without error
        cost_filter.log_cost_breakdown(
            analysis, "BTCUSDT", "Buy", Decimal("0.5")
        )


class TestEdgeCases:
    """Test edge cases"""
    
    def test_zero_quantity(self, cost_filter, sample_orderbook):
        """Test with zero quantity"""
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            sample_orderbook, "Buy", Decimal("0")
        )
        
        # Should handle gracefully
        assert slippage_pct >= Decimal("0")
    
    def test_empty_bids(self, cost_filter):
        """Test with empty bids"""
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[],
            asks=[
                OrderbookLevel(price=Decimal("50010"), quantity=Decimal("1.0")),
            ],
            timestamp=1234567890.0
        )
        
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            orderbook, "Sell", Decimal("0.5")
        )
        
        # Should return 100% slippage
        assert slippage_pct == Decimal("100")
    
    def test_empty_asks(self, cost_filter):
        """Test with empty asks"""
        orderbook = Orderbook(
            symbol="BTCUSDT",
            bids=[
                OrderbookLevel(price=Decimal("50000"), quantity=Decimal("1.0")),
            ],
            asks=[],
            timestamp=1234567890.0
        )
        
        slippage_pct, avg_price = cost_filter.calculate_expected_slippage(
            orderbook, "Buy", Decimal("0.5")
        )
        
        # Should return 100% slippage
        assert slippage_pct == Decimal("100")
