"""False Breakout Filter

This module filters false breakouts based on volume confirmation and price action.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SupportResistanceLevel:
    """Support or resistance level"""
    price: float
    level_type: str  # 'SUPPORT' or 'RESISTANCE'
    touches: int
    first_touch: int
    last_touch: int
    strength: float  # 0-1, based on number of touches


@dataclass
class BreakoutSignal:
    """Breakout signal with validation"""
    timestamp: int
    price: float
    direction: str  # 'UP' or 'DOWN'
    level_broken: float
    volume_ratio: float
    price_move_pct: float
    is_valid: bool
    rejection_reason: Optional[str] = None


class BreakoutFilter:
    """Filter false breakouts based on volume and price action"""
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        min_volume_ratio: float = 1.5,
        min_price_move: float = 0.005,
        level_lookback: int = 50,
        level_tolerance: float = 0.002,
        confirmation_bars: int = 2,
        max_history: int = 100
    ):
        """Initialize breakout filter
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            min_volume_ratio: Minimum volume ratio for valid breakout
            min_price_move: Minimum price move percentage
            level_lookback: Lookback period for S/R levels
            level_tolerance: Tolerance for level matching
            confirmation_bars: Bars needed to confirm breakout
            max_history: Maximum bars to keep in history (circular buffer limit)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.min_volume_ratio = min_volume_ratio
        self.min_price_move = min_price_move
        # Limit lookback to max_history for memory optimization
        self.level_lookback = min(level_lookback, max_history)
        self.level_tolerance = level_tolerance
        self.confirmation_bars = confirmation_bars
        self.max_history = max_history
        
        # Price and volume history (circular buffers with strict limits)
        self.highs: Deque[float] = deque(maxlen=self.max_history)
        self.lows: Deque[float] = deque(maxlen=self.max_history)
        self.closes: Deque[float] = deque(maxlen=self.max_history)
        self.volumes: Deque[float] = deque(maxlen=self.max_history)
        self.timestamps: Deque[int] = deque(maxlen=self.max_history)
        
        # Support/resistance levels
        self.support_levels: List[SupportResistanceLevel] = []
        self.resistance_levels: List[SupportResistanceLevel] = []
        
        # Pending breakouts (waiting for confirmation)
        self.pending_breakouts: List[BreakoutSignal] = []
        
    def add_bar(
        self,
        timestamp: int,
        high: float,
        low: float,
        close: float,
        volume: float
    ) -> Dict:
        """Add bar and check for breakouts
        
        Args:
            timestamp: Bar timestamp
            high: Bar high
            low: Bar low
            close: Bar close
            volume: Bar volume
            
        Returns:
            Dictionary with breakout analysis
        """
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        self.volumes.append(volume)
        self.timestamps.append(timestamp)
        
        result = {
            'breakout_detected': False,
            'breakout_signal': None,
            'support_levels': [],
            'resistance_levels': []
        }
        
        # Need enough data
        if len(self.closes) < 20:
            return result
        
        # Update support/resistance levels
        self._update_levels()
        
        # Check for breakouts
        breakout = self._check_breakout(timestamp, high, low, close, volume)
        
        if breakout:
            result['breakout_detected'] = True
            result['breakout_signal'] = breakout
            
            if breakout.is_valid:
                logger.info(
                    f"Valid breakout detected: {breakout.direction} at {breakout.price:.2f}, "
                    f"volume ratio: {breakout.volume_ratio:.2f}x"
                )
            else:
                logger.debug(
                    f"False breakout filtered: {breakout.rejection_reason}"
                )
        
        result['support_levels'] = self.support_levels.copy()
        result['resistance_levels'] = self.resistance_levels.copy()
        
        return result
    
    def _update_levels(self) -> None:
        """Update support and resistance levels"""
        if len(self.highs) < self.level_lookback:
            return
        
        # Find swing highs and lows with float32 for memory optimization
        highs_array = np.array(list(self.highs), dtype=np.float32)
        lows_array = np.array(list(self.lows), dtype=np.float32)
        
        # Identify resistance levels (swing highs)
        self.resistance_levels = self._find_levels(
            highs_array,
            'RESISTANCE'
        )
        
        # Identify support levels (swing lows)
        self.support_levels = self._find_levels(
            lows_array,
            'SUPPORT'
        )
    
    def _find_levels(
        self,
        prices: np.ndarray,
        level_type: str
    ) -> List[SupportResistanceLevel]:
        """Find support or resistance levels
        
        Args:
            prices: Price array
            level_type: 'SUPPORT' or 'RESISTANCE'
            
        Returns:
            List of SupportResistanceLevel objects
        """
        levels = []
        
        # Convert to float32 for memory optimization
        prices = prices.astype(np.float32)
        
        # Find local extrema
        if level_type == 'RESISTANCE':
            # Find local maxima
            extrema_indices = []
            for i in range(2, len(prices) - 2):
                if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and
                    prices[i] > prices[i+1] and prices[i] > prices[i+2]):
                    extrema_indices.append(i)
        else:
            # Find local minima
            extrema_indices = []
            for i in range(2, len(prices) - 2):
                if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and
                    prices[i] < prices[i+1] and prices[i] < prices[i+2]):
                    extrema_indices.append(i)
        
        if not extrema_indices:
            return levels
        
        # Cluster nearby extrema into levels
        extrema_prices = prices[extrema_indices]
        
        for i, price in enumerate(extrema_prices):
            # Check if price is close to existing level
            found_level = False
            for level in levels:
                if abs(price - level.price) / level.price < self.level_tolerance:
                    # Update existing level
                    level.touches += 1
                    level.last_touch = extrema_indices[i]
                    level.price = (level.price * (level.touches - 1) + price) / level.touches
                    level.strength = min(1.0, level.touches / 5.0)
                    found_level = True
                    break
            
            if not found_level:
                # Create new level
                levels.append(SupportResistanceLevel(
                    price=float(price),
                    level_type=level_type,
                    touches=1,
                    first_touch=extrema_indices[i],
                    last_touch=extrema_indices[i],
                    strength=0.2
                ))
        
        # Sort by strength
        levels.sort(key=lambda x: x.strength, reverse=True)
        
        # Keep top 5 levels
        return levels[:5]
    
    def _check_breakout(
        self,
        timestamp: int,
        high: float,
        low: float,
        close: float,
        volume: float
    ) -> Optional[BreakoutSignal]:
        """Check for breakout
        
        Args:
            timestamp: Current timestamp
            high: Current high
            low: Current low
            close: Current close
            volume: Current volume
            
        Returns:
            BreakoutSignal if breakout detected, None otherwise
        """
        # Calculate average volume
        avg_volume = np.mean(list(self.volumes)[:-1]) if len(self.volumes) > 1 else volume
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
        
        # Check for resistance breakout (upward)
        for level in self.resistance_levels:
            if close > level.price:
                # Calculate price move
                price_move_pct = (close - level.price) / level.price
                
                # Validate breakout
                is_valid = True
                rejection_reason = None
                
                # Check volume confirmation
                if volume_ratio < self.min_volume_ratio:
                    is_valid = False
                    rejection_reason = f"Insufficient volume: {volume_ratio:.2f}x < {self.min_volume_ratio}x"
                
                # Check price move
                elif price_move_pct < self.min_price_move:
                    is_valid = False
                    rejection_reason = f"Insufficient price move: {price_move_pct:.2%} < {self.min_price_move:.2%}"
                
                return BreakoutSignal(
                    timestamp=timestamp,
                    price=close,
                    direction='UP',
                    level_broken=level.price,
                    volume_ratio=volume_ratio,
                    price_move_pct=price_move_pct,
                    is_valid=is_valid,
                    rejection_reason=rejection_reason
                )
        
        # Check for support breakdown (downward)
        for level in self.support_levels:
            if close < level.price:
                # Calculate price move
                price_move_pct = abs(close - level.price) / level.price
                
                # Validate breakout
                is_valid = True
                rejection_reason = None
                
                # Check volume confirmation
                if volume_ratio < self.min_volume_ratio:
                    is_valid = False
                    rejection_reason = f"Insufficient volume: {volume_ratio:.2f}x < {self.min_volume_ratio}x"
                
                # Check price move
                elif price_move_pct < self.min_price_move:
                    is_valid = False
                    rejection_reason = f"Insufficient price move: {price_move_pct:.2%} < {self.min_price_move:.2%}"
                
                return BreakoutSignal(
                    timestamp=timestamp,
                    price=close,
                    direction='DOWN',
                    level_broken=level.price,
                    volume_ratio=volume_ratio,
                    price_move_pct=price_move_pct,
                    is_valid=is_valid,
                    rejection_reason=rejection_reason
                )
        
        return None
    
    def get_nearest_support(self) -> Optional[float]:
        """Get nearest support level below current price
        
        Returns:
            Support price or None
        """
        if not self.support_levels or not self.closes:
            return None
        
        current_price = self.closes[-1]
        
        # Find support below current price
        supports_below = [
            level.price for level in self.support_levels
            if level.price < current_price
        ]
        
        if not supports_below:
            return None
        
        return max(supports_below)
    
    def get_nearest_resistance(self) -> Optional[float]:
        """Get nearest resistance level above current price
        
        Returns:
            Resistance price or None
        """
        if not self.resistance_levels or not self.closes:
            return None
        
        current_price = self.closes[-1]
        
        # Find resistance above current price
        resistances_above = [
            level.price for level in self.resistance_levels
            if level.price > current_price
        ]
        
        if not resistances_above:
            return None
        
        return min(resistances_above)
    
    def reset(self) -> None:
        """Reset breakout filter"""
        self.highs.clear()
        self.lows.clear()
        self.closes.clear()
        self.volumes.clear()
        self.timestamps.clear()
        self.support_levels.clear()
        self.resistance_levels.clear()
        self.pending_breakouts.clear()
