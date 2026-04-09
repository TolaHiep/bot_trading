"""Swing High/Low Detector

This module detects swing highs and lows in price action.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SwingPoint:
    """Represents a swing high or low point"""
    timestamp: int
    price: float
    swing_type: str  # 'HIGH' or 'LOW'
    index: int  # Position in price series


class SwingDetector:
    """Detect swing highs and lows in price action"""
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        lookback: int = 5
    ):
        """Initialize swing detector
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            lookback: Number of bars to look back/forward for swing detection
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback = lookback
        
        # Price history
        self.highs: Deque[float] = deque(maxlen=lookback * 3)
        self.lows: Deque[float] = deque(maxlen=lookback * 3)
        self.timestamps: Deque[int] = deque(maxlen=lookback * 3)
        
        # Detected swings
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        
    def add_bar(
        self,
        timestamp: int,
        high: float,
        low: float
    ) -> dict:
        """Add bar and detect swings
        
        Args:
            timestamp: Bar timestamp
            high: Bar high price
            low: Bar low price
            
        Returns:
            Dictionary with detected swings
        """
        self.highs.append(high)
        self.lows.append(low)
        self.timestamps.append(timestamp)
        
        result = {
            'swing_high': None,
            'swing_low': None
        }
        
        # Need enough data for swing detection
        if len(self.highs) < self.lookback * 2 + 1:
            return result
        
        # Check for swing high at lookback position
        swing_high = self._detect_swing_high()
        if swing_high:
            self.swing_highs.append(swing_high)
            result['swing_high'] = swing_high
        
        # Check for swing low at lookback position
        swing_low = self._detect_swing_low()
        if swing_low:
            self.swing_lows.append(swing_low)
            result['swing_low'] = swing_low
        
        return result
    
    def _detect_swing_high(self) -> Optional[SwingPoint]:
        """Detect swing high at lookback position
        
        A swing high occurs when the high at position is higher than
        lookback bars before and after it.
        
        Returns:
            SwingPoint if swing high detected, None otherwise
        """
        if len(self.highs) < self.lookback * 2 + 1:
            return None
        
        # Check middle position (lookback bars from end)
        center_idx = len(self.highs) - self.lookback - 1
        center_high = self.highs[center_idx]
        
        # Check if center is higher than all bars in lookback window
        for i in range(center_idx - self.lookback, center_idx):
            if self.highs[i] >= center_high:
                return None
        
        for i in range(center_idx + 1, center_idx + self.lookback + 1):
            if self.highs[i] >= center_high:
                return None
        
        # Swing high detected
        return SwingPoint(
            timestamp=self.timestamps[center_idx],
            price=center_high,
            swing_type='HIGH',
            index=center_idx
        )
    
    def _detect_swing_low(self) -> Optional[SwingPoint]:
        """Detect swing low at lookback position
        
        A swing low occurs when the low at position is lower than
        lookback bars before and after it.
        
        Returns:
            SwingPoint if swing low detected, None otherwise
        """
        if len(self.lows) < self.lookback * 2 + 1:
            return None
        
        # Check middle position (lookback bars from end)
        center_idx = len(self.lows) - self.lookback - 1
        center_low = self.lows[center_idx]
        
        # Check if center is lower than all bars in lookback window
        for i in range(center_idx - self.lookback, center_idx):
            if self.lows[i] <= center_low:
                return None
        
        for i in range(center_idx + 1, center_idx + self.lookback + 1):
            if self.lows[i] <= center_low:
                return None
        
        # Swing low detected
        return SwingPoint(
            timestamp=self.timestamps[center_idx],
            price=center_low,
            swing_type='LOW',
            index=center_idx
        )
    
    def get_latest_swing_high(self) -> Optional[SwingPoint]:
        """Get latest swing high
        
        Returns:
            Latest SwingPoint or None
        """
        if not self.swing_highs:
            return None
        return self.swing_highs[-1]
    
    def get_latest_swing_low(self) -> Optional[SwingPoint]:
        """Get latest swing low
        
        Returns:
            Latest SwingPoint or None
        """
        if not self.swing_lows:
            return None
        return self.swing_lows[-1]
    
    def is_higher_high(self) -> bool:
        """Check if latest swing high is higher than previous
        
        Returns:
            True if higher high, False otherwise
        """
        if len(self.swing_highs) < 2:
            return False
        return self.swing_highs[-1].price > self.swing_highs[-2].price
    
    def is_lower_high(self) -> bool:
        """Check if latest swing high is lower than previous
        
        Returns:
            True if lower high, False otherwise
        """
        if len(self.swing_highs) < 2:
            return False
        return self.swing_highs[-1].price < self.swing_highs[-2].price
    
    def is_higher_low(self) -> bool:
        """Check if latest swing low is higher than previous
        
        Returns:
            True if higher low, False otherwise
        """
        if len(self.swing_lows) < 2:
            return False
        return self.swing_lows[-1].price > self.swing_lows[-2].price
    
    def is_lower_low(self) -> bool:
        """Check if latest swing low is lower than previous
        
        Returns:
            True if lower low, False otherwise
        """
        if len(self.swing_lows) < 2:
            return False
        return self.swing_lows[-1].price < self.swing_lows[-2].price
    
    def get_swing_count(self) -> dict:
        """Get count of detected swings
        
        Returns:
            Dictionary with swing counts
        """
        return {
            'swing_highs': len(self.swing_highs),
            'swing_lows': len(self.swing_lows),
            'total': len(self.swing_highs) + len(self.swing_lows)
        }
    
    def reset(self) -> None:
        """Reset swing detector"""
        self.highs.clear()
        self.lows.clear()
        self.timestamps.clear()
        self.swing_highs.clear()
        self.swing_lows.clear()
