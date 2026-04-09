"""
Slippage Model - Orderbook-based slippage calculation

Provides realistic slippage estimation dựa trên orderbook depth.
"""

import logging
from decimal import Decimal
from typing import Dict, List

logger = logging.getLogger(__name__)


class SlippageModel:
    """
    Orderbook-based slippage calculator
    
    Features:
    - Walk through orderbook levels
    - Calculate weighted average fill price
    - Market impact estimation
    """
    
    def __init__(self):
        """Initialize Slippage Model"""
        logger.info("SlippageModel initialized")
    
    def calculate_slippage(
        self,
        orderbook: Dict,
        side: str,
        quantity: Decimal,
        order_type: str
    ) -> Decimal:
        """
        Calculate expected slippage from orderbook
        
        Args:
            orderbook: Orderbook data with bids and asks
            side: "BUY" or "SELL"
            quantity: Order quantity
            order_type: "LIMIT" or "MARKET"
        
        Returns:
            Slippage as percentage (e.g., 0.0005 = 0.05%)
        
        Algorithm:
            1. Get relevant orderbook side (asks for BUY, bids for SELL)
            2. Walk through levels to simulate fill
            3. Calculate weighted average fill price
            4. slippage = abs(avg_fill_price - best_price) / best_price
        """
        # Limit orders have minimal slippage (assume fill at limit price)
        if order_type == "LIMIT":
            return Decimal("0")
        
        # Get orderbook levels
        if side == "BUY":
            levels = orderbook.get("asks", [])
        else:
            levels = orderbook.get("bids", [])
        
        if not levels:
            # No orderbook data, use default slippage
            logger.warning("No orderbook data available, using default slippage")
            return Decimal("0.0005")  # 0.05% default
        
        # Get best price
        best_price = Decimal(str(levels[0][0]))
        
        # Simulate market order fill
        remaining_qty = quantity
        total_cost = Decimal("0")
        total_filled = Decimal("0")
        
        for price_str, qty_str in levels:
            price = Decimal(str(price_str))
            available_qty = Decimal(str(qty_str))
            
            # Fill as much as possible at this level
            fill_qty = min(remaining_qty, available_qty)
            
            total_cost += price * fill_qty
            total_filled += fill_qty
            remaining_qty -= fill_qty
            
            if remaining_qty <= 0:
                break
        
        # Check if order can be fully filled
        if remaining_qty > 0:
            # Not enough liquidity, apply penalty
            logger.warning(
                f"Insufficient liquidity: {remaining_qty} unfilled out of {quantity}"
            )
            # Apply additional slippage for unfilled portion
            penalty = Decimal("0.002")  # 0.2% penalty
            return penalty
        
        # Calculate weighted average fill price
        avg_fill_price = total_cost / total_filled
        
        # Calculate slippage
        slippage = abs(avg_fill_price - best_price) / best_price
        
        logger.debug(
            f"Slippage calculated: {slippage*100:.3f}% "
            f"(best: {best_price}, avg: {avg_fill_price})"
        )
        
        return slippage
    
    def estimate_market_impact(
        self,
        orderbook: Dict,
        side: str,
        quantity: Decimal
    ) -> Decimal:
        """
        Estimate market impact of large order
        
        Args:
            orderbook: Orderbook data
            side: "BUY" or "SELL"
            quantity: Order quantity
        
        Returns:
            Market impact as percentage
        
        Algorithm:
            Market impact increases with order size relative to orderbook depth
        """
        # Get orderbook levels
        if side == "BUY":
            levels = orderbook.get("asks", [])
        else:
            levels = orderbook.get("bids", [])
        
        if not levels:
            return Decimal("0.001")  # 0.1% default
        
        # Calculate total liquidity within 0.5% of best price
        best_price = Decimal(str(levels[0][0]))
        price_threshold = best_price * Decimal("1.005")
        
        total_liquidity = Decimal("0")
        for price_str, qty_str in levels:
            price = Decimal(str(price_str))
            if side == "BUY" and price > price_threshold:
                break
            if side == "SELL" and price < price_threshold:
                break
            
            total_liquidity += Decimal(str(qty_str))
        
        # Market impact proportional to order size / liquidity
        if total_liquidity > 0:
            impact_ratio = quantity / total_liquidity
            market_impact = impact_ratio * Decimal("0.01")  # 1% per 100% of liquidity
        else:
            market_impact = Decimal("0.001")
        
        # Cap market impact at 1%
        market_impact = min(market_impact, Decimal("0.01"))
        
        return market_impact
