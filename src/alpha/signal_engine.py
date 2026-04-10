"""Signal Generation Engine

This module aggregates indicators, order flow, and Wyckoff analysis to generate trading signals.
"""

import gc
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import yaml

from .breakout_filter import BreakoutFilter
from .indicators import IndicatorEngine
from .order_flow import OrderFlowAnalyzer
from .wyckoff import WyckoffEngine, WyckoffPhase

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types"""
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass
class TradingSignal:
    """Trading signal with confidence score"""
    timestamp: int
    symbol: str
    signal_type: SignalType
    confidence: float  # 0-100
    price: float
    
    # Contributing factors
    wyckoff_phase: str
    delta: float
    breakout_direction: Optional[str]
    volume_ratio: float
    
    # Multi-timeframe alignment
    timeframe_alignment: Dict[str, bool]
    aligned_timeframes: int
    
    # Indicator signals
    trend_aligned: bool
    momentum_score: float
    
    # Metadata
    reason: str
    suppressed: bool = False


class SignalGenerator:
    """Generate trading signals from multiple alpha sources"""
    
    def __init__(
        self,
        symbol: str,
        config_path: str = "config/alpha_params.yaml"
    ):
        """Initialize signal generator
        
        Args:
            symbol: Trading symbol
            config_path: Path to configuration file
        """
        self.symbol = symbol
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.signal_config = self.config['signal_generation']
        self.breakout_config = self.config['breakout_filter']
        
        # Initialize components with memory optimization limits
        self.indicator_engine = IndicatorEngine()
        self.wyckoff_engine = WyckoffEngine()
        self.order_flow_analyzers: Dict[str, OrderFlowAnalyzer] = {}
        self.breakout_filters: Dict[str, BreakoutFilter] = {}
        
        # Initialize for each timeframe with circular buffer limits
        for tf in self.signal_config['timeframes']:
            # Order flow limited to 1000 trades
            self.order_flow_analyzers[tf] = OrderFlowAnalyzer(
                symbol=symbol,
                timeframe=tf,
                window_size=1000  # Explicit limit for memory optimization
            )
            # Breakout filter limited to 100 bars
            self.breakout_filters[tf] = BreakoutFilter(
                symbol=symbol,
                timeframe=tf,
                min_volume_ratio=self.breakout_config['min_volume_ratio'],
                min_price_move=self.breakout_config['min_price_move'],
                level_lookback=self.breakout_config['level_lookback'],
                max_history=100  # Explicit limit for memory optimization
            )
        
        # Signal history (limited to prevent memory bloat)
        self.signals: List[TradingSignal] = []
        self.max_signal_history = 1000  # Keep last 1000 signals
        
        logger.info(
            f"Initialized SignalGenerator for {symbol} with memory optimization: "
            f"indicators=200 bars, order_flow=1000 trades, breakout=100 bars"
        )
        
    def add_kline(
        self,
        timeframe: str,
        timestamp: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float
    ) -> Optional[TradingSignal]:
        """Add kline and generate signal
        
        Args:
            timeframe: Timeframe
            timestamp: Kline timestamp
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
            
        Returns:
            TradingSignal if generated, None otherwise
        """
        # Update indicator engine
        self.indicator_engine.update(
            symbol=self.symbol,
            timeframe=timeframe,
            close=close,
            volume=volume
        )
        
        # Update Wyckoff detector
        self.wyckoff_engine.add_bar(
            symbol=self.symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            high=high,
            low=low,
            close=close,
            volume=volume
        )
        
        # Update breakout filter
        if timeframe in self.breakout_filters:
            self.breakout_filters[timeframe].add_bar(
                timestamp=timestamp,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
        
        # Generate signal only on primary timeframe (15m)
        if timeframe == "15m":
            return self._generate_signal(timestamp, close)
        
        return None
    
    def add_trade(
        self,
        timeframe: str,
        timestamp: int,
        price: float,
        quantity: float,
        side: str
    ) -> None:
        """Add trade for order flow analysis
        
        Args:
            timeframe: Timeframe
            timestamp: Trade timestamp
            price: Trade price
            quantity: Trade quantity
            side: Trade side ('Buy' or 'Sell')
        """
        if timeframe in self.order_flow_analyzers:
            self.order_flow_analyzers[timeframe].add_trade(
                timestamp=timestamp,
                price=price,
                quantity=quantity,
                side=side
            )
    
    def _generate_signal(
        self,
        timestamp: int,
        price: float
    ) -> Optional[TradingSignal]:
        """Generate trading signal
        
        Args:
            timestamp: Current timestamp
            price: Current price
            
        Returns:
            TradingSignal if conditions met, None otherwise
        """
        # Get Wyckoff phase (primary timeframe)
        wyckoff_phase = self.wyckoff_engine.get_phase(self.symbol, "15m")
        
        # Get order flow delta (primary timeframe)
        delta = 0.0
        if "15m" in self.order_flow_analyzers:
            delta = self.order_flow_analyzers["15m"].cumulative_delta
        
        # Get breakout signal (primary timeframe)
        breakout_direction = None
        volume_ratio = 1.0
        if "15m" in self.breakout_filters:
            nearest_resistance = self.breakout_filters["15m"].get_nearest_resistance()
            nearest_support = self.breakout_filters["15m"].get_nearest_support()
            
            if nearest_resistance and price > nearest_resistance:
                breakout_direction = "UP"
            elif nearest_support and price < nearest_support:
                breakout_direction = "DOWN"
            
            # Get volume ratio from last bar
            if len(self.breakout_filters["15m"].volumes) > 1:
                current_vol = self.breakout_filters["15m"].volumes[-1]
                avg_vol = sum(list(self.breakout_filters["15m"].volumes)[:-1]) / (len(self.breakout_filters["15m"].volumes) - 1)
                volume_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        
        # Check multi-timeframe alignment
        timeframe_alignment = self._check_timeframe_alignment()
        aligned_timeframes = sum(timeframe_alignment.values())
        
        # Check trend alignment
        trend_aligned = self._check_trend_alignment()
        
        # Calculate momentum score
        momentum_score = self._calculate_momentum_score()
        
        # Determine signal type
        signal_type, confidence, reason = self._determine_signal(
            wyckoff_phase=wyckoff_phase,
            delta=delta,
            breakout_direction=breakout_direction,
            volume_ratio=volume_ratio,
            aligned_timeframes=aligned_timeframes,
            trend_aligned=trend_aligned,
            momentum_score=momentum_score
        )
        
        # Create signal
        signal = TradingSignal(
            timestamp=timestamp,
            symbol=self.symbol,
            signal_type=signal_type,
            confidence=confidence,
            price=price,
            wyckoff_phase=wyckoff_phase.value,
            delta=delta,
            breakout_direction=breakout_direction,
            volume_ratio=volume_ratio,
            timeframe_alignment=timeframe_alignment,
            aligned_timeframes=aligned_timeframes,
            trend_aligned=trend_aligned,
            momentum_score=momentum_score,
            reason=reason,
            suppressed=confidence < self.signal_config['min_confidence']
        )
        
        # Log signal
        if not signal.suppressed:
            logger.info(
                f"Signal generated: {signal.signal_type.value} at {price:.2f}, "
                f"confidence: {confidence:.1f}, reason: {reason}"
            )
        else:
            logger.debug(
                f"Signal suppressed: {signal.signal_type.value}, "
                f"confidence {confidence:.1f} < {self.signal_config['min_confidence']}"
            )
        
        self.signals.append(signal)
        
        # Limit signal history to prevent memory bloat
        if len(self.signals) > self.max_signal_history:
            self.signals = self.signals[-self.max_signal_history:]
        
        return signal if not signal.suppressed else None
    
    def _check_timeframe_alignment(self) -> Dict[str, bool]:
        """Check if multiple timeframes agree
        
        Returns:
            Dictionary of timeframe alignment
        """
        alignment = {}
        
        for tf in self.signal_config['timeframes']:
            phase = self.wyckoff_engine.get_phase(self.symbol, tf)
            
            # Consider aligned if phase is MARKUP or MARKDOWN
            alignment[tf] = phase in [WyckoffPhase.MARKUP, WyckoffPhase.MARKDOWN]
        
        return alignment
    
    def _check_trend_alignment(self) -> bool:
        """Check if EMAs are aligned
        
        Returns:
            True if trend aligned, False otherwise
        """
        # Get EMAs from primary timeframe
        indicators = self.indicator_engine.get_values(self.symbol, "15m")
        
        if not indicators:
            return False
        
        ema_9 = indicators.get('ema_9')
        ema_21 = indicators.get('ema_21')
        ema_50 = indicators.get('ema_50')
        
        if ema_9 is None or ema_21 is None or ema_50 is None:
            return False
        
        # Uptrend: EMA9 > EMA21 > EMA50
        # Downtrend: EMA9 < EMA21 < EMA50
        uptrend = ema_9 > ema_21 > ema_50
        downtrend = ema_9 < ema_21 < ema_50
        
        return uptrend or downtrend
    
    def _calculate_momentum_score(self) -> float:
        """Calculate momentum score from RSI and MACD
        
        Returns:
            Momentum score (0-1)
        """
        indicators = self.indicator_engine.get_values(self.symbol, "15m")
        
        if not indicators:
            return 0.5
        
        rsi = indicators.get('rsi')
        macd = indicators.get('macd')
        macd_signal = indicators.get('macd_signal')
        
        score = 0.5
        
        # RSI contribution
        if rsi is not None:
            if rsi > 50:
                score += (rsi - 50) / 100  # 0 to 0.5
            else:
                score -= (50 - rsi) / 100  # -0.5 to 0
        
        # MACD contribution
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                score += 0.2
            else:
                score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _determine_signal(
        self,
        wyckoff_phase: WyckoffPhase,
        delta: float,
        breakout_direction: Optional[str],
        volume_ratio: float,
        aligned_timeframes: int,
        trend_aligned: bool,
        momentum_score: float
    ) -> tuple:
        """Determine signal type and confidence
        
        Args:
            wyckoff_phase: Current Wyckoff phase
            delta: Order flow delta
            breakout_direction: Breakout direction
            volume_ratio: Volume ratio
            aligned_timeframes: Number of aligned timeframes
            trend_aligned: Whether trend is aligned
            momentum_score: Momentum score
            
        Returns:
            Tuple of (SignalType, confidence, reason)
        """
        weights = self.signal_config['indicator_weights']
        wyckoff_weights = self.signal_config['wyckoff_weights']
        min_alignment = self.signal_config['min_timeframe_alignment']
        min_volume = self.signal_config['volume_multiplier']
        
        # Get Wyckoff phase weight
        phase_weight = wyckoff_weights.get(wyckoff_phase.value, 0.0)
        
        # If phase weight is 0, no signals
        if phase_weight == 0.0:
            return SignalType.NEUTRAL, 0.0, f"Wyckoff phase {wyckoff_phase.value} has 0 weight"
        
        # Check BUY conditions
        # Allow BUY if: positive delta + breakout UP + volume confirmation
        if (delta > self.signal_config['delta_threshold'] and
            breakout_direction == "UP" and
            volume_ratio >= min_volume):
            
            # Calculate confidence
            confidence = 0.0
            
            # Wyckoff weight (scaled by phase weight)
            confidence += weights['wyckoff'] * phase_weight * 100
            
            # Order flow weight
            confidence += weights['order_flow'] * min(delta / 1000, 1.0) * 100
            
            # Volume weight
            confidence += weights['volume'] * min(volume_ratio / 3.0, 1.0) * 100
            
            # Trend alignment weight
            if trend_aligned:
                confidence += weights['trend_alignment'] * 100
            
            # Momentum weight
            confidence += weights['momentum'] * momentum_score * 100
            
            # Multi-timeframe bonus
            if aligned_timeframes >= min_alignment:
                tf_bonus = (aligned_timeframes / len(self.signal_config['timeframes'])) * 10
                confidence += tf_bonus
            
            confidence = min(100, confidence)
            
            reason = (
                f"Wyckoff={wyckoff_phase.value}(w={phase_weight}), delta={delta:.0f}, breakout=UP, "
                f"volume={volume_ratio:.1f}x, aligned={aligned_timeframes}/{len(self.signal_config['timeframes'])}"
            )
            
            return SignalType.BUY, confidence, reason
        
        # Check SELL conditions
        # Allow SELL if: negative delta + breakout DOWN + volume confirmation
        if (delta < -self.signal_config['delta_threshold'] and
            breakout_direction == "DOWN" and
            volume_ratio >= min_volume):
            
            # Calculate confidence
            confidence = 0.0
            
            # Wyckoff weight (scaled by phase weight)
            confidence += weights['wyckoff'] * phase_weight * 100
            
            # Order flow weight
            confidence += weights['order_flow'] * min(abs(delta) / 1000, 1.0) * 100
            
            # Volume weight
            confidence += weights['volume'] * min(volume_ratio / 3.0, 1.0) * 100
            
            # Trend alignment weight
            if trend_aligned:
                confidence += weights['trend_alignment'] * 100
            
            # Momentum weight
            confidence += weights['momentum'] * (1.0 - momentum_score) * 100
            
            # Multi-timeframe bonus
            if aligned_timeframes >= min_alignment:
                tf_bonus = (aligned_timeframes / len(self.signal_config['timeframes'])) * 10
                confidence += tf_bonus
            
            confidence = min(100, confidence)
            
            reason = (
                f"Wyckoff={wyckoff_phase.value}(w={phase_weight}), delta={delta:.0f}, breakout=DOWN, "
                f"volume={volume_ratio:.1f}x, aligned={aligned_timeframes}/{len(self.signal_config['timeframes'])}"
            )
            
            return SignalType.SELL, confidence, reason
        
        # NEUTRAL signal
        reason = "Conditions not met for BUY or SELL"
        
        if phase_weight < 0.5:
            reason = f"Wyckoff phase {wyckoff_phase.value} has low weight ({phase_weight})"
        elif breakout_direction is None:
            reason = "No breakout detected"
        elif volume_ratio < min_volume:
            reason = f"Insufficient volume: {volume_ratio:.1f}x < {min_volume}x"
        elif abs(delta) <= self.signal_config['delta_threshold']:
            reason = f"Weak order flow delta: {delta:.0f}"
        
        return SignalType.NEUTRAL, 0.0, reason
    
    def get_latest_signal(self) -> Optional[TradingSignal]:
        """Get latest signal
        
        Returns:
            Latest TradingSignal or None
        """
        if not self.signals:
            return None
        return self.signals[-1]
    
    def get_current_price(self) -> Optional[float]:
        """Get current price from latest signal
        
        Returns:
            Current price or None
        """
        latest_signal = self.get_latest_signal()
        if latest_signal:
            return latest_signal.price
        return None
    
    def get_signals(
        self,
        signal_type: Optional[SignalType] = None,
        min_confidence: float = 0.0
    ) -> List[TradingSignal]:
        """Get signals with filters
        
        Args:
            signal_type: Filter by signal type
            min_confidence: Minimum confidence
            
        Returns:
            List of TradingSignal objects
        """
        signals = self.signals
        
        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]
        
        if min_confidence > 0:
            signals = [s for s in signals if s.confidence >= min_confidence]
        
        return signals
    
    def reset(self) -> None:
        """Reset signal generator"""
        # Reset all tracked indicator pairs
        for symbol, timeframe in self.indicator_engine.get_tracked_pairs():
            self.indicator_engine.reset(symbol, timeframe)
        
        for analyzer in self.order_flow_analyzers.values():
            analyzer.reset()
        for filter in self.breakout_filters.values():
            filter.reset()
        self.signals.clear()
    
    def cleanup(self) -> None:
        """Cleanup resources and trigger garbage collection
        
        This method should be called when a SignalGenerator instance is no longer needed
        to free up memory resources.
        """
        logger.info(f"Cleaning up SignalGenerator for {self.symbol}")
        
        # Clear all data structures
        self.reset()
        
        # Clear component references
        self.order_flow_analyzers.clear()
        self.breakout_filters.clear()
        
        # Trigger garbage collection to free memory
        gc.collect()
        
        logger.debug(f"SignalGenerator cleanup complete for {self.symbol}")
    
    def __del__(self):
        """Destructor to ensure cleanup on deletion"""
        try:
            self.cleanup()
        except Exception as e:
            logger.error(f"Error during SignalGenerator cleanup: {e}")
