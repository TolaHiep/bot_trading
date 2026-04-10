"""
Cost Filter - Slippage và cost analysis

Filters trades based on expected slippage and total trading costs.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


@dataclass
class OrderbookLevel:
    """Single orderbook level"""
    price: Decimal
    quantity: Decimal


@dataclass
class Orderbook:
    """Orderbook snapshot"""
    symbol: str
    bids: List[OrderbookLevel]  # Sorted descending by price
    asks: List[OrderbookLevel]  # Sorted ascending by price
    timestamp: float
    
    @property
    def best_bid(self) -> Decimal:
        """Get best bid price"""
        return self.bids[0].price if self.bids else Decimal("0")
    
    @property
    def best_ask(self) -> Decimal:
        """Get best ask price"""
        return self.asks[0].price if self.asks else Decimal("0")
    
    @property
    def spread(self) -> Decimal:
        """Get bid-ask spread"""
        if not self.bids or not self.asks:
            return Decimal("0")
        return self.best_ask - self.best_bid
    
    @property
    def spread_pct(self) -> Decimal:
        """Get spread as percentage of mid price"""
        if not self.bids or not self.asks:
            return Decimal("0")
        mid_price = (self.best_bid + self.best_ask) / Decimal("2")
        return (self.spread / mid_price) * Decimal("100")


@dataclass
class CostAnalysis:
    """Cost analysis result"""
    expected_slippage: Decimal  # As percentage
    commission: Decimal         # As percentage
    spread_cost: Decimal        # As percentage
    total_cost: Decimal         # As percentage
    avg_fill_price: Decimal     # Expected average fill price
    should_reject: bool
    reject_reason: Optional[str] = None
    
    def __str__(self) -> str:
        return (
            f"CostAnalysis(slippage={self.expected_slippage:.4f}%, "
            f"commission={self.commission:.4f}%, "
            f"spread={self.spread_cost:.4f}%, "
            f"total={self.total_cost:.4f}%, "
            f"reject={self.should_reject})"
        )


class CostFilter:
    """
    Cost Filter - Analyze and filter trades based on costs
    
    Features:
    - Calculate expected slippage from orderbook depth
    - Calculate total trading cost (commission + slippage + spread)
    - Reject trades exceeding cost thresholds
    - Track actual vs expected slippage
    """
    
    def __init__(
        self,
        max_slippage_pct: Decimal = Decimal("0.1"),
        max_total_cost_pct: Decimal = Decimal("0.2"),
        max_spread_pct: Decimal = Decimal("0.5"),  # 0.5% for scalping (increased from 0.05%)
        commission_rate: Decimal = Decimal("0.06")  # 0.06% Bybit taker fee
    ):
        """
        Initialize Cost Filter
        
        Args:
            max_slippage_pct: Maximum acceptable slippage (%)
            max_total_cost_pct: Maximum acceptable total cost (%)
            max_spread_pct: Maximum acceptable spread (%)
            commission_rate: Exchange commission rate (%)
        """
        self.max_slippage_pct = max_slippage_pct
        self.max_total_cost_pct = max_total_cost_pct
        self.max_spread_pct = max_spread_pct
        self.commission_rate = commission_rate
        
        # Track actual slippage for analysis
        self.actual_slippages: List[Decimal] = []
        self.expected_slippages: List[Decimal] = []
        
        logger.info(
            f"CostFilter initialized (max_slippage={max_slippage_pct}%, "
            f"max_total_cost={max_total_cost_pct}%, "
            f"max_spread={max_spread_pct}%)"
        )
    
    def analyze_trade(
        self,
        orderbook: Orderbook,
        side: str,  # "Buy" or "Sell"
        quantity: Decimal
    ) -> CostAnalysis:
        """
        Analyze trade costs
        
        Args:
            orderbook: Current orderbook snapshot
            side: Order side ("Buy" or "Sell")
            quantity: Order quantity
        
        Returns:
            CostAnalysis with cost breakdown and rejection decision
        """
        # Check spread first
        spread_pct = orderbook.spread_pct
        if spread_pct > self.max_spread_pct:
            logger.warning(
                f"Spread {spread_pct:.4f}% exceeds max {self.max_spread_pct}%"
            )
            return CostAnalysis(
                expected_slippage=Decimal("0"),
                commission=self.commission_rate,
                spread_cost=spread_pct,
                total_cost=spread_pct + self.commission_rate,
                avg_fill_price=Decimal("0"),
                should_reject=True,
                reject_reason=f"Spread too wide: {spread_pct:.4f}%"
            )
        
        # Calculate expected slippage
        slippage_pct, avg_fill_price = self.calculate_expected_slippage(
            orderbook, side, quantity
        )
        
        # Calculate spread cost (half spread for taker)
        spread_cost = spread_pct / Decimal("2")
        
        # Calculate total cost
        total_cost = slippage_pct + self.commission_rate + spread_cost
        
        # Determine if should reject
        should_reject = False
        reject_reason = None
        
        if slippage_pct > self.max_slippage_pct:
            should_reject = True
            reject_reason = f"Slippage too high: {slippage_pct:.4f}%"
            logger.warning(reject_reason)
        elif total_cost > self.max_total_cost_pct:
            should_reject = True
            reject_reason = f"Total cost too high: {total_cost:.4f}%"
            logger.warning(reject_reason)
        
        analysis = CostAnalysis(
            expected_slippage=slippage_pct,
            commission=self.commission_rate,
            spread_cost=spread_cost,
            total_cost=total_cost,
            avg_fill_price=avg_fill_price,
            should_reject=should_reject,
            reject_reason=reject_reason
        )
        
        if not should_reject:
            logger.info(f"Trade approved: {analysis}")
        
        return analysis
    
    def calculate_expected_slippage(
        self,
        orderbook: Orderbook,
        side: str,
        quantity: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate expected slippage from orderbook depth
        
        Simulates market order execution by walking through orderbook levels.
        
        Args:
            orderbook: Current orderbook snapshot
            side: Order side ("Buy" or "Sell")
            quantity: Order quantity
        
        Returns:
            Tuple of (slippage_pct, avg_fill_price)
        """
        # Select appropriate side of orderbook
        if side == "Buy":
            levels = orderbook.asks  # Buy from asks
            best_price = orderbook.best_ask
        else:
            levels = orderbook.bids  # Sell to bids
            best_price = orderbook.best_bid
        
        if not levels or best_price == Decimal("0"):
            logger.error("Empty orderbook")
            return Decimal("100"), Decimal("0")  # 100% slippage = reject
        
        # Simulate market order execution
        remaining_qty = quantity
        total_cost = Decimal("0")
        filled_qty = Decimal("0")
        
        for level in levels:
            if remaining_qty <= Decimal("0"):
                break
            
            # Fill at this level
            fill_qty = min(remaining_qty, level.quantity)
            total_cost += fill_qty * level.price
            filled_qty += fill_qty
            remaining_qty -= fill_qty
        
        # Check if we can fill the entire order
        if remaining_qty > Decimal("0"):
            # Not enough liquidity
            logger.warning(
                f"Insufficient liquidity: {filled_qty}/{quantity} fillable"
            )
            return Decimal("100"), Decimal("0")  # 100% slippage = reject
        
        # Handle zero filled quantity (edge case)
        if filled_qty == Decimal("0"):
            return Decimal("100"), Decimal("0")
        
        # Calculate average fill price
        avg_fill_price = total_cost / filled_qty
        
        # Calculate slippage
        slippage = abs(avg_fill_price - best_price) / best_price
        slippage_pct = slippage * Decimal("100")
        
        logger.debug(
            f"Expected slippage: {slippage_pct:.4f}% "
            f"(best={best_price}, avg={avg_fill_price})"
        )
        
        return slippage_pct, avg_fill_price
    
    def record_actual_slippage(
        self,
        expected_slippage: Decimal,
        actual_slippage: Decimal
    ) -> None:
        """
        Record actual slippage for analysis
        
        Args:
            expected_slippage: Expected slippage (%)
            actual_slippage: Actual slippage (%)
        """
        self.expected_slippages.append(expected_slippage)
        self.actual_slippages.append(actual_slippage)
        
        # Calculate error
        if expected_slippage > Decimal("0"):
            error_pct = abs(actual_slippage - expected_slippage) / expected_slippage * Decimal("100")
            logger.info(
                f"Slippage: expected={expected_slippage:.4f}%, "
                f"actual={actual_slippage:.4f}%, "
                f"error={error_pct:.2f}%"
            )
    
    def get_slippage_accuracy(self) -> Optional[Decimal]:
        """
        Get slippage estimation accuracy
        
        Returns:
            Average error percentage, or None if no data
        """
        if not self.expected_slippages or not self.actual_slippages:
            return None
        
        errors = []
        for expected, actual in zip(self.expected_slippages, self.actual_slippages):
            if expected > Decimal("0"):
                error = abs(actual - expected) / expected * Decimal("100")
                errors.append(error)
        
        if not errors:
            return None
        
        avg_error = sum(errors) / Decimal(str(len(errors)))
        return avg_error
    
    def should_use_limit_order(
        self,
        orderbook: Orderbook,
        side: str,
        quantity: Decimal
    ) -> bool:
        """
        Determine if limit order should be preferred over market order
        
        Prefer limit order if:
        - Spread is reasonable (< max_spread)
        - Expected slippage is low (< max_slippage / 2)
        - Sufficient liquidity at best price
        
        Args:
            orderbook: Current orderbook snapshot
            side: Order side ("Buy" or "Sell")
            quantity: Order quantity
        
        Returns:
            True if limit order is preferred
        """
        # Check spread
        if orderbook.spread_pct > self.max_spread_pct:
            return False
        
        # Check slippage
        slippage_pct, _ = self.calculate_expected_slippage(orderbook, side, quantity)
        if slippage_pct > self.max_slippage_pct / Decimal("2"):
            return False
        
        # Check liquidity at best price
        if side == "Buy":
            best_level = orderbook.asks[0] if orderbook.asks else None
        else:
            best_level = orderbook.bids[0] if orderbook.bids else None
        
        if not best_level:
            return False
        
        # Prefer limit if we can fill at least 50% at best price
        if best_level.quantity >= quantity / Decimal("2"):
            return True
        
        return False
    
    def log_cost_breakdown(
        self,
        analysis: CostAnalysis,
        symbol: str,
        side: str,
        quantity: Decimal
    ) -> None:
        """
        Log detailed cost breakdown
        
        Args:
            analysis: Cost analysis result
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
        """
        logger.info(
            f"Cost Breakdown for {side} {quantity} {symbol}:\n"
            f"  Expected Slippage: {analysis.expected_slippage:.4f}%\n"
            f"  Commission:        {analysis.commission:.4f}%\n"
            f"  Spread Cost:       {analysis.spread_cost:.4f}%\n"
            f"  Total Cost:        {analysis.total_cost:.4f}%\n"
            f"  Avg Fill Price:    {analysis.avg_fill_price}\n"
            f"  Decision:          {'REJECT' if analysis.should_reject else 'APPROVE'}"
            + (f"\n  Reason:            {analysis.reject_reason}" if analysis.reject_reason else "")
        )
