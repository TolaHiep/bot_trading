"""Trailing Stop Logic

This module provides trailing stop calculation utilities.
"""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TrailingStopState:
    """Trailing stop state"""
    activated: bool = False
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    current_stop: Optional[float] = None
    activation_price: Optional[float] = None


class TrailingStopCalculator:
    """Calculate trailing stop prices"""
    
    def __init__(
        self,
        activation_profit_pct: float = 0.02,  # 2%
        trailing_distance_pct: float = 0.01,  # 1%
    ):
        """Initialize trailing stop calculator
        
        Args:
            activation_profit_pct: Profit % to activate trailing stop
            trailing_distance_pct: Distance % from highest/lowest price
        """
        self.activation_profit_pct = activation_profit_pct
        self.trailing_distance_pct = trailing_distance_pct
        
    def should_activate(
        self,
        entry_price: float,
        current_price: float,
        is_long: bool
    ) -> bool:
        """Check if trailing stop should be activated
        
        Args:
            entry_price: Entry price
            current_price: Current price
            is_long: True for long position, False for short
            
        Returns:
            True if should activate
        """
        if is_long:
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price
            
        return profit_pct >= self.activation_profit_pct
        
    def calculate_stop_price(
        self,
        highest_price: Optional[float],
        lowest_price: Optional[float],
        is_long: bool
    ) -> Optional[float]:
        """Calculate trailing stop price
        
        Args:
            highest_price: Highest price since activation (for long)
            lowest_price: Lowest price since activation (for short)
            is_long: True for long position, False for short
            
        Returns:
            Stop price or None if not enough data
        """
        if is_long:
            if highest_price is None:
                return None
            return highest_price * (1 - self.trailing_distance_pct)
        else:
            if lowest_price is None:
                return None
            return lowest_price * (1 + self.trailing_distance_pct)
            
    def should_update_stop(
        self,
        new_stop: float,
        current_stop: Optional[float],
        is_long: bool
    ) -> bool:
        """Check if stop should be updated
        
        Trailing stop only moves in favorable direction.
        
        Args:
            new_stop: New stop price
            current_stop: Current stop price
            is_long: True for long position, False for short
            
        Returns:
            True if should update
        """
        if current_stop is None:
            return True
            
        if is_long:
            # For long, stop can only move up
            return new_stop > current_stop
        else:
            # For short, stop can only move down
            return new_stop < current_stop
            
    def update_extremes(
        self,
        state: TrailingStopState,
        current_price: float,
        is_long: bool
    ) -> TrailingStopState:
        """Update highest/lowest price
        
        Args:
            state: Current trailing stop state
            current_price: Current price
            is_long: True for long position, False for short
            
        Returns:
            Updated state
        """
        if is_long:
            if state.highest_price is None or current_price > state.highest_price:
                state.highest_price = current_price
        else:
            if state.lowest_price is None or current_price < state.lowest_price:
                state.lowest_price = current_price
                
        return state
        
    def calculate_and_update(
        self,
        state: TrailingStopState,
        entry_price: float,
        current_price: float,
        is_long: bool
    ) -> tuple[TrailingStopState, bool]:
        """Calculate and update trailing stop
        
        Args:
            state: Current trailing stop state
            entry_price: Entry price
            current_price: Current price
            is_long: True for long position, False for short
            
        Returns:
            Tuple of (updated_state, stop_updated)
        """
        # Check activation
        if not state.activated:
            if self.should_activate(entry_price, current_price, is_long):
                state.activated = True
                state.activation_price = current_price
                logger.info(
                    f"Trailing stop activated at {current_price:.2f} "
                    f"(entry: {entry_price:.2f})"
                )
        
        # Update extremes
        state = self.update_extremes(state, current_price, is_long)
        
        # Calculate new stop
        if state.activated:
            new_stop = self.calculate_stop_price(
                state.highest_price,
                state.lowest_price,
                is_long
            )
            
            if new_stop is not None:
                # Check if should update
                if self.should_update_stop(new_stop, state.current_stop, is_long):
                    old_stop = state.current_stop
                    state.current_stop = new_stop
                    
                    logger.debug(
                        f"Trailing stop updated from {old_stop} to {new_stop:.2f}"
                    )
                    
                    return state, True
                    
        return state, False
