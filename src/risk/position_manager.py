"""Position Manager - Manages capital allocation across multiple symbols

This module tracks positions across multiple symbols and enforces capital allocation limits
to prevent over-leverage and ensure proper risk management.
"""

import logging
from decimal import Decimal
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """Information about a position for tracking"""
    symbol: str
    position_value: Decimal
    current_price: Decimal
    quantity: Decimal


class PositionManager:
    """
    Manages capital allocation across multiple symbols
    
    Features:
    - Tracks positions across multiple symbols
    - Enforces maximum position size per symbol (default 5% of equity)
    - Enforces maximum total exposure (default 80% of equity)
    - Calculates available balance for new positions
    - Supports up to 16 concurrent positions (80% / 5%)
    """
    
    def __init__(
        self,
        initial_equity: Decimal,
        max_position_pct: Decimal = Decimal("0.05"),  # 5% per position
        max_exposure_pct: Decimal = Decimal("0.80")   # 80% total exposure
    ):
        """
        Initialize Position Manager
        
        Args:
            initial_equity: Initial account equity
            max_position_pct: Maximum position size as % of equity (default: 0.05 = 5%)
            max_exposure_pct: Maximum total exposure as % of equity (default: 0.80 = 80%)
        """
        # Validate inputs
        if initial_equity <= 0:
            raise ValueError("Initial equity must be positive")
        
        # Convert to Decimal for comparison
        max_position_pct = Decimal(str(max_position_pct))
        max_exposure_pct = Decimal(str(max_exposure_pct))
        
        if not (Decimal("0.02") <= max_position_pct <= Decimal("0.05")):
            raise ValueError("max_position_pct must be between 0.02 (2%) and 0.05 (5%)")
        
        if max_exposure_pct <= 0 or max_exposure_pct > 1:
            raise ValueError("max_exposure_pct must be between 0 and 1")
        
        self.initial_equity = initial_equity
        self.current_balance = initial_equity
        self.max_position_pct = max_position_pct
        self.max_exposure_pct = max_exposure_pct
        
        # Track positions by symbol
        self.positions: Dict[str, PositionInfo] = {}
        
        logger.info(
            f"PositionManager initialized: equity={initial_equity}, "
            f"max_position={max_position_pct*100:.1f}%, "
            f"max_exposure={max_exposure_pct*100:.1f}%"
        )
    
    def can_open_position(
        self,
        symbol: str,
        position_value: Decimal
    ) -> Tuple[bool, str]:
        """
        Check if a new position can be opened
        
        Args:
            symbol: Trading symbol
            position_value: Value of the proposed position
        
        Returns:
            Tuple of (can_open: bool, reason: str)
        """
        # Check if position already exists for this symbol
        if symbol in self.positions:
            return False, f"Position already exists for {symbol}"
        
        # Check if position value exceeds maximum per-position limit
        max_position_value = self.initial_equity * self.max_position_pct
        if position_value > max_position_value:
            return False, (
                f"Position value {position_value:.2f} exceeds maximum "
                f"{max_position_value:.2f} ({self.max_position_pct*100:.1f}% of equity)"
            )
        
        # Check if total exposure would exceed limit
        current_exposure = self.get_total_exposure()
        new_exposure = current_exposure + position_value
        max_exposure = self.initial_equity * self.max_exposure_pct
        
        if new_exposure > max_exposure:
            return False, (
                f"Total exposure {new_exposure:.2f} would exceed maximum "
                f"{max_exposure:.2f} ({self.max_exposure_pct*100:.1f}% of equity)"
            )
        
        # Check if available balance is sufficient
        available = self.get_available_balance()
        if position_value > available:
            return False, (
                f"Insufficient available balance: required={position_value:.2f}, "
                f"available={available:.2f}"
            )
        
        # Check if available balance after this position would be too low
        # (must maintain at least 5% of equity available for new opportunities)
        min_available = self.initial_equity * self.max_position_pct
        if available - position_value < min_available:
            return False, (
                f"Opening position would leave insufficient balance "
                f"({available - position_value:.2f} < {min_available:.2f})"
            )
        
        return True, "Position can be opened"
    
    def get_available_balance(self) -> Decimal:
        """
        Calculate available balance for new positions
        
        Returns:
            Available balance (current_balance - sum of open position values)
        """
        total_position_value = sum(
            pos.position_value for pos in self.positions.values()
        )
        available = self.current_balance - total_position_value
        return max(Decimal("0"), available)
    
    def get_total_exposure(self) -> Decimal:
        """
        Calculate total exposure across all positions
        
        Returns:
            Sum of all open position values
        """
        return sum(pos.position_value for pos in self.positions.values())
    
    def get_position_count(self) -> int:
        """
        Get count of open positions
        
        Returns:
            Number of open positions
        """
        return len(self.positions)
    
    def get_positions_by_symbol(self) -> Dict[str, PositionInfo]:
        """
        Get all positions indexed by symbol
        
        Returns:
            Dictionary mapping symbol to PositionInfo
        """
        return self.positions.copy()
    
    def update_position_value(
        self,
        symbol: str,
        current_price: Decimal
    ) -> None:
        """
        Update position value based on current price
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
        """
        if symbol not in self.positions:
            logger.warning(f"Cannot update position value: {symbol} not found")
            return
        
        position = self.positions[symbol]
        position.current_price = current_price
        position.position_value = position.quantity * current_price
        
        logger.debug(
            f"Updated position {symbol}: price={current_price}, "
            f"value={position.position_value:.2f}"
        )
    
    def add_position(
        self,
        symbol: str,
        quantity: Decimal,
        entry_price: Decimal
    ) -> bool:
        """
        Add a new position to tracking
        
        Args:
            symbol: Trading symbol
            quantity: Position quantity
            entry_price: Entry price
        
        Returns:
            True if position added successfully, False otherwise
        """
        if symbol in self.positions:
            logger.error(f"Position already exists for {symbol}")
            return False
        
        position_value = quantity * entry_price
        
        # Verify position can be opened
        can_open, reason = self.can_open_position(symbol, position_value)
        if not can_open:
            logger.error(f"Cannot add position: {reason}")
            return False
        
        # Add position
        self.positions[symbol] = PositionInfo(
            symbol=symbol,
            position_value=position_value,
            current_price=entry_price,
            quantity=quantity
        )
        
        logger.info(
            f"Position added: {symbol}, quantity={quantity}, "
            f"value={position_value:.2f}, "
            f"exposure={self.get_total_exposure():.2f} "
            f"({self.get_total_exposure()/self.initial_equity*100:.1f}%)"
        )
        
        return True
    
    def remove_position(self, symbol: str) -> bool:
        """
        Remove a position from tracking
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if position removed successfully, False if not found
        """
        if symbol not in self.positions:
            logger.warning(f"Cannot remove position: {symbol} not found")
            return False
        
        position = self.positions.pop(symbol)
        
        logger.info(
            f"Position removed: {symbol}, value={position.position_value:.2f}, "
            f"remaining exposure={self.get_total_exposure():.2f}"
        )
        
        return True
    
    def update_balance(self, new_balance: Decimal) -> None:
        """
        Update current balance (e.g., after realized P&L)
        
        Args:
            new_balance: New account balance
        """
        old_balance = self.current_balance
        self.current_balance = new_balance
        
        logger.info(
            f"Balance updated: {old_balance:.2f} -> {new_balance:.2f} "
            f"(change: {new_balance - old_balance:+.2f})"
        )
    
    def get_exposure_percentage(self) -> Decimal:
        """
        Get current exposure as percentage of initial equity
        
        Returns:
            Exposure percentage (0-1)
        """
        if self.initial_equity == 0:
            return Decimal("0")
        
        return self.get_total_exposure() / self.initial_equity
    
    def get_max_position_value(self) -> Decimal:
        """
        Get maximum allowed position value
        
        Returns:
            Maximum position value
        """
        return self.initial_equity * self.max_position_pct
    
    def get_max_total_exposure(self) -> Decimal:
        """
        Get maximum allowed total exposure
        
        Returns:
            Maximum total exposure value
        """
        return self.initial_equity * self.max_exposure_pct
    
    def get_summary(self) -> Dict:
        """
        Get summary of position manager state
        
        Returns:
            Dictionary with current state information
        """
        total_exposure = self.get_total_exposure()
        exposure_pct = self.get_exposure_percentage()
        available = self.get_available_balance()
        
        return {
            "initial_equity": float(self.initial_equity),
            "current_balance": float(self.current_balance),
            "total_exposure": float(total_exposure),
            "exposure_percentage": float(exposure_pct * 100),
            "available_balance": float(available),
            "position_count": self.get_position_count(),
            "max_position_value": float(self.get_max_position_value()),
            "max_total_exposure": float(self.get_max_total_exposure()),
            "max_positions": int(self.max_exposure_pct / self.max_position_pct),
            "positions": {
                symbol: {
                    "value": float(pos.position_value),
                    "price": float(pos.current_price),
                    "quantity": float(pos.quantity)
                }
                for symbol, pos in self.positions.items()
            }
        }
