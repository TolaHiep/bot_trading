"""Wyckoff Phase Detector

This module detects Wyckoff market phases based on price action and volume.
"""

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Dict, List, Optional

import numpy as np

from .swing_detector import SwingDetector

logger = logging.getLogger(__name__)


class WyckoffPhase(Enum):
    """Wyckoff market phases"""
    UNKNOWN = "UNKNOWN"
    ACCUMULATION = "ACCUMULATION"
    MARKUP = "MARKUP"
    DISTRIBUTION = "DISTRIBUTION"
    MARKDOWN = "MARKDOWN"


@dataclass
class PhaseTransition:
    """Represents a phase transition event"""
    timestamp: int
    from_phase: WyckoffPhase
    to_phase: WyckoffPhase
    confidence: float


@dataclass
class WyckoffEvent:
    """Represents a Wyckoff event (Spring, Upthrust, etc.)"""
    timestamp: int
    event_type: str  # 'SPRING', 'UPTHRUST', 'SIGN_OF_STRENGTH', 'SIGN_OF_WEAKNESS'
    price: float
    description: str


class WyckoffDetector:
    """Detect Wyckoff phases and events"""
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        lookback_period: int = 50,
        swing_lookback: int = 5
    ):
        """Initialize Wyckoff detector
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            lookback_period: Number of bars for phase detection
            swing_lookback: Lookback for swing detection
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_period = lookback_period
        
        # Swing detector
        self.swing_detector = SwingDetector(symbol, timeframe, swing_lookback)
        
        # Price and volume history
        self.highs: Deque[float] = deque(maxlen=lookback_period)
        self.lows: Deque[float] = deque(maxlen=lookback_period)
        self.closes: Deque[float] = deque(maxlen=lookback_period)
        self.volumes: Deque[float] = deque(maxlen=lookback_period)
        self.timestamps: Deque[int] = deque(maxlen=lookback_period)
        
        # Current phase
        self.current_phase = WyckoffPhase.UNKNOWN
        self.phase_confidence = 0.0
        
        # Phase history
        self.phase_transitions: List[PhaseTransition] = []
        
        # Detected events
        self.events: List[WyckoffEvent] = []
        
    def add_bar(
        self,
        timestamp: int,
        high: float,
        low: float,
        close: float,
        volume: float
    ) -> Dict:
        """Add bar and detect Wyckoff phase
        
        Args:
            timestamp: Bar timestamp
            high: Bar high price
            low: Bar low price
            close: Bar close price
            volume: Bar volume
            
        Returns:
            Dictionary with phase detection results
        """
        # Add to history
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        self.volumes.append(volume)
        self.timestamps.append(timestamp)
        
        # Update swing detector
        swing_result = self.swing_detector.add_bar(timestamp, high, low)
        
        # Detect phase
        phase_result = self._detect_phase()
        
        # Detect events
        events = self._detect_events()
        
        return {
            'phase': self.current_phase.value,
            'confidence': self.phase_confidence,
            'swing_high': swing_result.get('swing_high'),
            'swing_low': swing_result.get('swing_low'),
            'events': events,
            'phase_changed': phase_result.get('phase_changed', False)
        }
    
    def _detect_phase(self) -> Dict:
        """Detect current Wyckoff phase
        
        Returns:
            Dictionary with detection results
        """
        if len(self.closes) < self.lookback_period:
            return {'phase_changed': False}
        
        # Calculate metrics
        price_range = self._calculate_price_range()
        volume_trend = self._calculate_volume_trend()
        price_trend = self._calculate_price_trend()
        
        # Detect phase based on metrics
        new_phase, confidence = self._classify_phase(price_range, volume_trend, price_trend)
        
        # Check for phase transition
        phase_changed = False
        if new_phase != self.current_phase:
            # Emit phase transition event
            transition = PhaseTransition(
                timestamp=self.timestamps[-1],
                from_phase=self.current_phase,
                to_phase=new_phase,
                confidence=confidence
            )
            self.phase_transitions.append(transition)
            
            logger.info(
                f"Phase transition: {self.current_phase.value} -> {new_phase.value} "
                f"(confidence: {confidence:.2f})"
            )
            
            self.current_phase = new_phase
            phase_changed = True
        
        self.phase_confidence = confidence
        
        return {'phase_changed': phase_changed}
    
    def _calculate_price_range(self) -> float:
        """Calculate price range (volatility)
        
        Returns:
            Price range as percentage
        """
        if len(self.highs) < 20:
            return 0.0
        
        recent_highs = list(self.highs)[-20:]
        recent_lows = list(self.lows)[-20:]
        
        max_high = max(recent_highs)
        min_low = min(recent_lows)
        
        if min_low == 0:
            return 0.0
        
        return (max_high - min_low) / min_low
    
    def _calculate_volume_trend(self) -> str:
        """Calculate volume trend
        
        Returns:
            'INCREASING', 'DECREASING', or 'STABLE'
        """
        if len(self.volumes) < 20:
            return 'STABLE'
        
        recent_volumes = list(self.volumes)[-20:]
        first_half = np.mean(recent_volumes[:10])
        second_half = np.mean(recent_volumes[10:])
        
        if second_half > first_half * 1.2:
            return 'INCREASING'
        elif second_half < first_half * 0.8:
            return 'DECREASING'
        else:
            return 'STABLE'
    
    def _calculate_price_trend(self) -> str:
        """Calculate price trend
        
        Returns:
            'UPTREND', 'DOWNTREND', or 'RANGING'
        """
        if len(self.closes) < 20:
            return 'RANGING'
        
        # Check swing structure
        if self.swing_detector.is_higher_high() and self.swing_detector.is_higher_low():
            return 'UPTREND'
        elif self.swing_detector.is_lower_high() and self.swing_detector.is_lower_low():
            return 'DOWNTREND'
        else:
            return 'RANGING'
    
    def _classify_phase(
        self,
        price_range: float,
        volume_trend: str,
        price_trend: str
    ) -> tuple:
        """Classify Wyckoff phase based on metrics
        
        Args:
            price_range: Price range (volatility)
            volume_trend: Volume trend
            price_trend: Price trend
            
        Returns:
            Tuple of (WyckoffPhase, confidence)
        """
        confidence = 0.5
        
        # ACCUMULATION: Ranging + Decreasing volume
        if price_trend == 'RANGING' and volume_trend == 'DECREASING' and price_range < 0.05:
            confidence = 0.7
            return WyckoffPhase.ACCUMULATION, confidence
        
        # MARKUP: Uptrend + Increasing volume
        if price_trend == 'UPTREND' and volume_trend == 'INCREASING':
            confidence = 0.8
            return WyckoffPhase.MARKUP, confidence
        
        # DISTRIBUTION: Ranging + Increasing volume
        if price_trend == 'RANGING' and volume_trend == 'INCREASING' and price_range > 0.03:
            confidence = 0.7
            return WyckoffPhase.DISTRIBUTION, confidence
        
        # MARKDOWN: Downtrend + Increasing volume
        if price_trend == 'DOWNTREND' and volume_trend == 'INCREASING':
            confidence = 0.8
            return WyckoffPhase.MARKDOWN, confidence
        
        # UNKNOWN
        return WyckoffPhase.UNKNOWN, 0.5
    
    def _detect_events(self) -> List[WyckoffEvent]:
        """Detect Wyckoff events (Spring, Upthrust, etc.)
        
        Returns:
            List of detected WyckoffEvent objects
        """
        events = []
        
        if len(self.closes) < 20:
            return events
        
        # Detect Spring (false breakdown in Accumulation)
        if self.current_phase == WyckoffPhase.ACCUMULATION:
            spring = self._detect_spring()
            if spring:
                events.append(spring)
                self.events.append(spring)
        
        # Detect Upthrust (false breakout in Distribution)
        if self.current_phase == WyckoffPhase.DISTRIBUTION:
            upthrust = self._detect_upthrust()
            if upthrust:
                events.append(upthrust)
                self.events.append(upthrust)
        
        return events
    
    def _detect_spring(self) -> Optional[WyckoffEvent]:
        """Detect Spring event
        
        A Spring is a false breakdown below support that quickly reverses.
        
        Returns:
            WyckoffEvent if Spring detected, None otherwise
        """
        if len(self.lows) < 10:
            return None
        
        recent_lows = list(self.lows)[-10:]
        recent_closes = list(self.closes)[-10:]
        
        # Check if recent low broke below previous lows but closed back above
        support = min(recent_lows[:-3])
        latest_low = recent_lows[-1]
        latest_close = recent_closes[-1]
        
        if latest_low < support * 0.99 and latest_close > support:
            return WyckoffEvent(
                timestamp=self.timestamps[-1],
                event_type='SPRING',
                price=latest_low,
                description='False breakdown below support with quick reversal'
            )
        
        return None
    
    def _detect_upthrust(self) -> Optional[WyckoffEvent]:
        """Detect Upthrust event
        
        An Upthrust is a false breakout above resistance that quickly reverses.
        
        Returns:
            WyckoffEvent if Upthrust detected, None otherwise
        """
        if len(self.highs) < 10:
            return None
        
        recent_highs = list(self.highs)[-10:]
        recent_closes = list(self.closes)[-10:]
        
        # Check if recent high broke above previous highs but closed back below
        resistance = max(recent_highs[:-3])
        latest_high = recent_highs[-1]
        latest_close = recent_closes[-1]
        
        if latest_high > resistance * 1.01 and latest_close < resistance:
            return WyckoffEvent(
                timestamp=self.timestamps[-1],
                event_type='UPTHRUST',
                price=latest_high,
                description='False breakout above resistance with quick reversal'
            )
        
        return None
    
    def get_current_phase(self) -> WyckoffPhase:
        """Get current Wyckoff phase
        
        Returns:
            Current WyckoffPhase
        """
        return self.current_phase
    
    def get_phase_confidence(self) -> float:
        """Get confidence of current phase
        
        Returns:
            Confidence score (0-1)
        """
        return self.phase_confidence
    
    def get_phase_transitions(self) -> List[PhaseTransition]:
        """Get phase transition history
        
        Returns:
            List of PhaseTransition objects
        """
        return self.phase_transitions.copy()
    
    def get_events(self) -> List[WyckoffEvent]:
        """Get detected Wyckoff events
        
        Returns:
            List of WyckoffEvent objects
        """
        return self.events.copy()
    
    def reset(self) -> None:
        """Reset Wyckoff detector"""
        self.swing_detector.reset()
        self.highs.clear()
        self.lows.clear()
        self.closes.clear()
        self.volumes.clear()
        self.timestamps.clear()
        self.current_phase = WyckoffPhase.UNKNOWN
        self.phase_confidence = 0.0
        self.phase_transitions.clear()
        self.events.clear()


class WyckoffEngine:
    """Manage Wyckoff detection for multiple symbols and timeframes"""
    
    def __init__(self):
        """Initialize Wyckoff engine"""
        self.detectors: Dict[tuple, WyckoffDetector] = {}
        
    def get_or_create_detector(
        self,
        symbol: str,
        timeframe: str,
        lookback_period: int = 50
    ) -> WyckoffDetector:
        """Get or create Wyckoff detector
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            lookback_period: Lookback period
            
        Returns:
            WyckoffDetector instance
        """
        key = (symbol, timeframe)
        
        if key not in self.detectors:
            self.detectors[key] = WyckoffDetector(
                symbol=symbol,
                timeframe=timeframe,
                lookback_period=lookback_period
            )
            logger.info(f"Created Wyckoff detector for {symbol} {timeframe}")
        
        return self.detectors[key]
    
    def add_bar(
        self,
        symbol: str,
        timeframe: str,
        timestamp: int,
        high: float,
        low: float,
        close: float,
        volume: float
    ) -> Dict:
        """Add bar to detector
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            timestamp: Bar timestamp
            high: Bar high
            low: Bar low
            close: Bar close
            volume: Bar volume
            
        Returns:
            Dictionary with detection results
        """
        detector = self.get_or_create_detector(symbol, timeframe)
        return detector.add_bar(timestamp, high, low, close, volume)
    
    def get_phase(self, symbol: str, timeframe: str) -> WyckoffPhase:
        """Get current phase
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Current WyckoffPhase
        """
        key = (symbol, timeframe)
        
        if key not in self.detectors:
            return WyckoffPhase.UNKNOWN
        
        return self.detectors[key].get_current_phase()
    
    def reset(self, symbol: str, timeframe: str) -> None:
        """Reset detector
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        """
        key = (symbol, timeframe)
        
        if key in self.detectors:
            self.detectors[key].reset()
            logger.info(f"Reset Wyckoff detector for {symbol} {timeframe}")
