"""Incremental EMA Calculator

This module provides efficient incremental EMA calculation without full recalculation.
"""

import logging
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class IncrementalEMA:
    """Calculate EMA incrementally for performance"""
    
    def __init__(self, period: int):
        """Initialize incremental EMA calculator
        
        Args:
            period: EMA period (e.g., 9, 21, 50, 200)
        """
        self.period = period
        self.k = 2.0 / (period + 1)  # Smoothing factor
        self.ema: Optional[float] = None
        self.initialized = False
        
    def update(self, price: float) -> Optional[float]:
        """Update EMA with new price
        
        Args:
            price: New price value
            
        Returns:
            Current EMA value, or None if not enough data
        """
        if not self.initialized:
            # First value: EMA = price
            self.ema = price
            self.initialized = True
            return self.ema
        
        # Incremental update: EMA = price * k + EMA_prev * (1 - k)
        self.ema = price * self.k + self.ema * (1 - self.k)
        return self.ema
    
    def get_value(self) -> Optional[float]:
        """Get current EMA value
        
        Returns:
            Current EMA or None if not initialized
        """
        return self.ema
    
    def reset(self) -> None:
        """Reset EMA state"""
        self.ema = None
        self.initialized = False


class IncrementalRSI:
    """Calculate RSI incrementally using Wilder's smoothing"""
    
    def __init__(self, period: int = 14):
        """Initialize incremental RSI calculator
        
        Args:
            period: RSI period (default: 14)
        """
        self.period = period
        self.prev_price: Optional[float] = None
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
        self.gains = []
        self.losses = []
        
    def update(self, price: float) -> Optional[float]:
        """Update RSI with new price
        
        Args:
            price: New price value
            
        Returns:
            Current RSI value (0-100), or None if not enough data
        """
        if self.prev_price is None:
            # First price, no change to calculate
            self.prev_price = price
            return None
        
        # Calculate price change
        change = price - self.prev_price
        gain = max(change, 0)
        loss = max(-change, 0)
        
        if self.avg_gain is None:
            # Accumulate initial period
            self.gains.append(gain)
            self.losses.append(loss)
            
            if len(self.gains) >= self.period:
                # Initialize averages
                self.avg_gain = sum(self.gains) / self.period
                self.avg_loss = sum(self.losses) / self.period
                
                # Clear lists to save memory
                self.gains.clear()
                self.losses.clear()
                
                # Calculate RSI
                if self.avg_loss == 0:
                    rsi = 100.0
                else:
                    rs = self.avg_gain / self.avg_loss
                    rsi = 100.0 - (100.0 / (1.0 + rs))
                
                self.prev_price = price
                return rsi
            
            self.prev_price = price
            return None
        
        # Wilder's smoothing (similar to EMA)
        self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
        self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
        
        # Calculate RSI
        if self.avg_loss == 0:
            rsi = 100.0
        else:
            rs = self.avg_gain / self.avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        self.prev_price = price
        return rsi
    
    def get_value(self) -> Optional[float]:
        """Get current RSI value
        
        Returns:
            Current RSI or None if not enough data
        """
        if self.avg_gain is None or self.avg_loss is None:
            return None
        
        if self.avg_loss == 0:
            return 100.0
        
        rs = self.avg_gain / self.avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
    
    def reset(self) -> None:
        """Reset RSI state"""
        self.prev_price = None
        self.avg_gain = None
        self.avg_loss = None
        self.gains.clear()
        self.losses.clear()
