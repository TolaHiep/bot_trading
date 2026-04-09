"""Position Sizing Calculator

This module calculates position sizes based on risk management rules.
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SizingMethod(Enum):
    """Position sizing methods"""
    FIXED_PERCENT = "FIXED_PERCENT"
    KELLY_CRITERION = "KELLY_CRITERION"


@dataclass
class PositionSize:
    """Position size calculation result"""
    quantity: float
    risk_amount: float
    position_value: float
    risk_percent: float
    method: str
    adjusted_for_confidence: bool
    adjusted_for_drawdown: bool
    leverage: float
    reason: str


class PositionSizer:
    """Calculate position sizes with risk management"""
    
    def __init__(
        self,
        max_risk_per_trade: float = 0.02,  # 2%
        max_position_size: float = 0.10,  # 10%
        drawdown_threshold: float = 0.10,  # 10%
        drawdown_reduction: float = 0.50,  # 50%
        min_confidence: float = 60.0,
        max_confidence: float = 100.0
    ):
        """Initialize position sizer
        
        Args:
            max_risk_per_trade: Maximum risk per trade (0.02 = 2%)
            max_position_size: Maximum position size as % of balance (0.10 = 10%)
            drawdown_threshold: Drawdown threshold for reduction (0.10 = 10%)
            drawdown_reduction: Position reduction factor (0.50 = 50%)
            min_confidence: Minimum signal confidence
            max_confidence: Maximum signal confidence
        """
        self.max_risk_per_trade = max_risk_per_trade
        self.max_position_size = max_position_size
        self.drawdown_threshold = drawdown_threshold
        self.drawdown_reduction = drawdown_reduction
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
        
        # Track current drawdown
        self.current_drawdown = 0.0
        
    def calculate_position_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss_price: float,
        signal_confidence: float = 100.0,
        method: SizingMethod = SizingMethod.FIXED_PERCENT,
        leverage: float = 1.0,
        min_qty: float = 0.001,
        qty_step: float = 0.001,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None
    ) -> PositionSize:
        """Calculate position size
        
        Args:
            balance: Account balance
            entry_price: Entry price
            stop_loss_price: Stop loss price
            signal_confidence: Signal confidence (0-100)
            method: Sizing method
            leverage: Leverage multiplier
            min_qty: Minimum order quantity
            qty_step: Quantity step size
            win_rate: Win rate for Kelly Criterion (optional)
            avg_win: Average win for Kelly Criterion (optional)
            avg_loss: Average loss for Kelly Criterion (optional)
            
        Returns:
            PositionSize object
        """
        # Validate inputs
        if balance <= 0:
            return self._zero_position("Invalid balance")
        
        if entry_price <= 0 or stop_loss_price <= 0:
            return self._zero_position("Invalid prices")
        
        if leverage < 1.0:
            leverage = 1.0
        
        # Calculate stop loss distance
        stop_loss_distance = abs(entry_price - stop_loss_price) / entry_price
        
        if stop_loss_distance <= 0:
            return self._zero_position("Invalid stop loss distance")
        
        # Calculate base risk amount
        risk_percent = self.max_risk_per_trade
        
        # Adjust for signal confidence
        adjusted_for_confidence = False
        if signal_confidence < self.max_confidence:
            confidence_factor = signal_confidence / self.max_confidence
            risk_percent *= confidence_factor
            adjusted_for_confidence = True
        
        # Adjust for drawdown
        adjusted_for_drawdown = False
        if self.current_drawdown > self.drawdown_threshold:
            risk_percent *= self.drawdown_reduction
            adjusted_for_drawdown = True
        
        # Calculate position size based on method
        if method == SizingMethod.KELLY_CRITERION and win_rate and avg_win and avg_loss:
            quantity = self._calculate_kelly_size(
                balance=balance,
                entry_price=entry_price,
                stop_loss_distance=stop_loss_distance,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                leverage=leverage
            )
            method_name = "KELLY_CRITERION"
        else:
            quantity = self._calculate_fixed_percent_size(
                balance=balance,
                entry_price=entry_price,
                stop_loss_distance=stop_loss_distance,
                risk_percent=risk_percent,
                leverage=leverage
            )
            method_name = "FIXED_PERCENT"
        
        # Apply maximum position size limit
        max_position_value = balance * self.max_position_size * leverage
        max_quantity = max_position_value / entry_price
        
        if quantity > max_quantity:
            quantity = max_quantity
            logger.debug(f"Position size limited to {self.max_position_size*100}% of balance")
        
        # Round to lot size
        quantity = self._round_to_lot_size(quantity, qty_step)
        
        # Check minimum quantity
        if quantity < min_qty:
            return self._zero_position(f"Position size {quantity} < minimum {min_qty}")
        
        # Calculate final metrics
        position_value = quantity * entry_price / leverage
        risk_amount = quantity * entry_price * stop_loss_distance
        actual_risk_percent = risk_amount / balance
        
        # Verify risk limit
        if actual_risk_percent > self.max_risk_per_trade:
            # Reduce quantity to meet risk limit
            quantity = (balance * self.max_risk_per_trade) / (entry_price * stop_loss_distance)
            quantity = self._round_to_lot_size(quantity, qty_step)
            
            if quantity < min_qty:
                return self._zero_position(f"Risk-adjusted size {quantity} < minimum {min_qty}")
            
            position_value = quantity * entry_price / leverage
            risk_amount = quantity * entry_price * stop_loss_distance
            actual_risk_percent = risk_amount / balance
        
        reason = f"Risk: {actual_risk_percent*100:.2f}%, Position: {(position_value/balance)*100:.2f}%"
        
        if adjusted_for_confidence:
            reason += f", Confidence adjusted: {signal_confidence:.0f}%"
        
        if adjusted_for_drawdown:
            reason += f", Drawdown adjusted: {self.current_drawdown*100:.1f}%"
        
        return PositionSize(
            quantity=quantity,
            risk_amount=risk_amount,
            position_value=position_value,
            risk_percent=actual_risk_percent,
            method=method_name,
            adjusted_for_confidence=adjusted_for_confidence,
            adjusted_for_drawdown=adjusted_for_drawdown,
            leverage=leverage,
            reason=reason
        )
    
    def _calculate_fixed_percent_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss_distance: float,
        risk_percent: float,
        leverage: float
    ) -> float:
        """Calculate position size using fixed percent method
        
        Formula: quantity = (balance × risk_pct) / (entry_price × stop_loss_distance)
        
        Args:
            balance: Account balance
            entry_price: Entry price
            stop_loss_distance: Stop loss distance as percentage
            risk_percent: Risk percentage
            leverage: Leverage multiplier
            
        Returns:
            Position quantity
        """
        risk_amount = balance * risk_percent
        quantity = risk_amount / (entry_price * stop_loss_distance)
        
        return quantity
    
    def _calculate_kelly_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss_distance: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        leverage: float
    ) -> float:
        """Calculate position size using Kelly Criterion
        
        Kelly % = W - [(1 - W) / R]
        where W = win rate, R = avg_win / avg_loss
        
        Args:
            balance: Account balance
            entry_price: Entry price
            stop_loss_distance: Stop loss distance
            win_rate: Historical win rate (0-1)
            avg_win: Average win percentage
            avg_loss: Average loss percentage
            leverage: Leverage multiplier
            
        Returns:
            Position quantity
        """
        # Calculate Kelly percentage
        if avg_loss == 0:
            kelly_pct = 0.0
        else:
            win_loss_ratio = avg_win / avg_loss
            kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)
        
        # Use fractional Kelly (50%) for safety
        kelly_pct = max(0.0, kelly_pct * 0.5)
        
        # Cap at max risk
        kelly_pct = min(kelly_pct, self.max_risk_per_trade)
        
        # Calculate quantity
        risk_amount = balance * kelly_pct
        quantity = risk_amount / (entry_price * stop_loss_distance)
        
        return quantity
    
    def _round_to_lot_size(self, quantity: float, qty_step: float) -> float:
        """Round quantity to lot size
        
        Args:
            quantity: Raw quantity
            qty_step: Quantity step size
            
        Returns:
            Rounded quantity
        """
        if qty_step <= 0:
            return quantity
        
        # Round down to nearest step
        rounded = math.floor(quantity / qty_step) * qty_step
        
        # Round to appropriate decimal places
        decimals = len(str(qty_step).split('.')[-1]) if '.' in str(qty_step) else 0
        rounded = round(rounded, decimals)
        
        return rounded
    
    def _zero_position(self, reason: str) -> PositionSize:
        """Return zero position
        
        Args:
            reason: Reason for zero position
            
        Returns:
            PositionSize with zero quantity
        """
        logger.debug(f"Zero position: {reason}")
        
        return PositionSize(
            quantity=0.0,
            risk_amount=0.0,
            position_value=0.0,
            risk_percent=0.0,
            method="NONE",
            adjusted_for_confidence=False,
            adjusted_for_drawdown=False,
            leverage=1.0,
            reason=reason
        )
    
    def update_drawdown(self, current_drawdown: float) -> None:
        """Update current drawdown
        
        Args:
            current_drawdown: Current drawdown as percentage (0-1)
        """
        self.current_drawdown = max(0.0, current_drawdown)
        
        if self.current_drawdown > self.drawdown_threshold:
            logger.warning(
                f"Drawdown {self.current_drawdown*100:.1f}% exceeds threshold "
                f"{self.drawdown_threshold*100:.1f}%, reducing position sizes by "
                f"{self.drawdown_reduction*100:.0f}%"
            )
    
    def get_max_position_value(self, balance: float, leverage: float = 1.0) -> float:
        """Get maximum position value
        
        Args:
            balance: Account balance
            leverage: Leverage multiplier
            
        Returns:
            Maximum position value
        """
        return balance * self.max_position_size * leverage
    
    def get_max_risk_amount(self, balance: float) -> float:
        """Get maximum risk amount per trade
        
        Args:
            balance: Account balance
            
        Returns:
            Maximum risk amount
        """
        risk_amount = balance * self.max_risk_per_trade
        
        # Adjust for drawdown
        if self.current_drawdown > self.drawdown_threshold:
            risk_amount *= self.drawdown_reduction
        
        return risk_amount
    
    def validate_position_size(
        self,
        quantity: float,
        entry_price: float,
        stop_loss_price: float,
        balance: float,
        leverage: float = 1.0
    ) -> Dict:
        """Validate if position size meets risk requirements
        
        Args:
            quantity: Position quantity
            entry_price: Entry price
            stop_loss_price: Stop loss price
            balance: Account balance
            leverage: Leverage multiplier
            
        Returns:
            Dictionary with validation results
        """
        # Calculate metrics
        position_value = quantity * entry_price / leverage
        stop_loss_distance = abs(entry_price - stop_loss_price) / entry_price
        risk_amount = quantity * entry_price * stop_loss_distance
        risk_percent = risk_amount / balance
        position_percent = position_value / balance
        
        # Check constraints
        valid = True
        violations = []
        
        if risk_percent > self.max_risk_per_trade:
            valid = False
            violations.append(
                f"Risk {risk_percent*100:.2f}% exceeds maximum {self.max_risk_per_trade*100:.2f}%"
            )
        
        if position_percent > self.max_position_size:
            valid = False
            violations.append(
                f"Position size {position_percent*100:.2f}% exceeds maximum {self.max_position_size*100:.2f}%"
            )
        
        return {
            'valid': valid,
            'violations': violations,
            'risk_percent': risk_percent,
            'position_percent': position_percent,
            'risk_amount': risk_amount,
            'position_value': position_value
        }
