"""
Test Slippage Simulation

Ensures realistic slippage calculation based on orderbook.
"""

import pytest
from decimal import Decimal

from src.backtest.slippage_model import SlippageModel


class TestSlippageSimulation:
    """Test slippage simulation"""
    
    def test_slippage_model_initialization(self):
        """Test SlippageModel initializes correctly"""
        model = SlippageModel()
        assert model is not None
    
    def test_limit_order_no_slippage(self):
        """Test limit orders have no slippage"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [[50000, 1.0], [49990, 2.0]],
            "asks": [[50010, 1.0], [50020, 2.0]]
        }
        
        slippage = model.calculate_slippage(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("0.5"),
            order_type="LIMIT"
        )
        
        assert slippage == Decimal("0")
    
    def test_market_order_slippage_buy(self):
        """Test market BUY order slippage"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [[50000, 1.0], [49990, 2.0]],
            "asks": [[50010, 0.5], [50020, 1.0], [50030, 2.0]]
        }
        
        # Buy 1.0 BTC: 0.5 @ 50010, 0.5 @ 50020
        slippage = model.calculate_slippage(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("1.0"),
            order_type="MARKET"
        )
        
        # Expected avg price: (50010*0.5 + 50020*0.5) / 1.0 = 50015
        # Best price: 50010
        # Slippage: (50015 - 50010) / 50010 ≈ 0.0001 (0.01%)
        assert slippage > Decimal("0")
        assert slippage < Decimal("0.001")  # Less than 0.1%
    
    def test_market_order_slippage_sell(self):
        """Test market SELL order slippage"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [[50000, 0.5], [49990, 1.0], [49980, 2.0]],
            "asks": [[50010, 1.0], [50020, 2.0]]
        }
        
        # Sell 1.0 BTC: 0.5 @ 50000, 0.5 @ 49990
        slippage = model.calculate_slippage(
            orderbook=orderbook,
            side="SELL",
            quantity=Decimal("1.0"),
            order_type="MARKET"
        )
        
        # Expected avg price: (50000*0.5 + 49990*0.5) / 1.0 = 49995
        # Best price: 50000
        # Slippage: (50000 - 49995) / 50000 = 0.0001 (0.01%)
        assert slippage > Decimal("0")
        assert slippage < Decimal("0.001")
    
    def test_large_order_higher_slippage(self):
        """Test large orders have higher slippage"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [[50000, 1.0], [49990, 2.0]],
            "asks": [[50010, 0.5], [50020, 0.5], [50030, 1.0]]
        }
        
        # Small order
        small_slippage = model.calculate_slippage(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("0.3"),
            order_type="MARKET"
        )
        
        # Large order
        large_slippage = model.calculate_slippage(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("1.5"),
            order_type="MARKET"
        )
        
        # Large order should have higher slippage
        assert large_slippage > small_slippage
    
    def test_insufficient_liquidity_penalty(self):
        """Test penalty for insufficient liquidity"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [[50000, 1.0]],
            "asks": [[50010, 0.5]]  # Only 0.5 BTC available
        }
        
        # Try to buy 2.0 BTC (more than available)
        slippage = model.calculate_slippage(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("2.0"),
            order_type="MARKET"
        )
        
        # Should apply penalty for unfilled portion
        assert slippage >= Decimal("0.002")  # 0.2% penalty
    
    def test_empty_orderbook_default_slippage(self):
        """Test default slippage when orderbook is empty"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [],
            "asks": []
        }
        
        slippage = model.calculate_slippage(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("1.0"),
            order_type="MARKET"
        )
        
        # Should return default slippage
        assert slippage == Decimal("0.0005")  # 0.05%
    
    def test_market_impact_estimation(self):
        """Test market impact estimation"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [[50000, 10.0], [49990, 20.0]],
            "asks": [[50010, 10.0], [50020, 20.0]]
        }
        
        # Small order relative to liquidity
        small_impact = model.estimate_market_impact(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("1.0")
        )
        
        # Large order relative to liquidity
        large_impact = model.estimate_market_impact(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("15.0")
        )
        
        # Large order should have higher market impact
        assert large_impact > small_impact
    
    def test_market_impact_capped(self):
        """Test market impact is capped at 1%"""
        model = SlippageModel()
        
        orderbook = {
            "bids": [[50000, 1.0]],
            "asks": [[50010, 1.0]]
        }
        
        # Extremely large order
        impact = model.estimate_market_impact(
            orderbook=orderbook,
            side="BUY",
            quantity=Decimal("1000.0")
        )
        
        # Should be capped at 1%
        assert impact <= Decimal("0.01")
