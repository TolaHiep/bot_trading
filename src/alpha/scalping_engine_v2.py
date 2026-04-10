"""
Scalping Signal Generator V2 - Improved Strategy
Based on professional scalping principles:
- R:R ratio 1:1 to 1:2
- Tight stop loss: 0.3-0.5%
- Quick take profit: 0.4-0.8%
- Entry based on Order Flow + Support/Resistance
"""

import logging
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Deque

logger = logging.getLogger(__name__)


class ScalpSignalType(Enum):
    """Scalping signal types"""
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass
class ScalpingSignal:
    """Scalping trading signal"""
    timestamp: int
    symbol: str
    signal_type: ScalpSignalType
    price: float
    confidence: float  # 0-100
    
    # Entry factors
    rsi: float
    delta: float
    volume_ratio: float
    bb_position: str  # "lower", "middle", "upper"
    ema_trend: str  # "bullish", "bearish", "neutral"
    
    # Risk management
    stop_loss_price: float
    take_profit1_price: float
    take_profit2_price: float
    risk_reward_ratio: float
    
    reason: str


class ScalpingEngineV2:
    """
    Improved Scalping Signal Generator
    
    Features:
    - ATR-based stop loss
    - Multiple take profit targets
    - Order flow analysis
    - Bollinger Bands for entry/exit
    - Support/Resistance detection
    """
    
    def __init__(
        self,
        symbol: str,
        config: dict
    ):
        """Initialize scalping engine
        
        Args:
            symbol: Trading symbol
            config: Scalping configuration
        """
        self.symbol = symbol
        self.config = config
        
        # Entry config
        entry_cfg = config.get('entry', {})
        self.rsi_period = entry_cfg.get('rsi_period', 14)
        self.rsi_oversold = entry_cfg.get('rsi_oversold', 40)
        self.rsi_overbought = entry_cfg.get('rsi_overbought', 60)
        self.volume_multiplier = entry_cfg.get('volume_multiplier', 1.5)
        self.delta_threshold = entry_cfg.get('delta_threshold', 100)
        self.bb_period = entry_cfg.get('bb_period', 20)
        self.bb_std = entry_cfg.get('bb_std', 2)
        self.ema_fast = entry_cfg.get('ema_fast', 9)
        self.ema_slow = entry_cfg.get('ema_slow', 21)
        
        # Stop loss config
        sl_cfg = config.get('stop_loss', {})
        self.sl_method = sl_cfg.get('method', 'atr')
        self.atr_period = sl_cfg.get('atr_period', 14)
        self.atr_multiplier = sl_cfg.get('atr_multiplier', 1.0)
        self.fixed_sl_pct = sl_cfg.get('fixed_pct', 0.004)
        
        # Take profit config
        tp_cfg = config.get('take_profit', {})
        self.tp1_pct = tp_cfg.get('target1_pct', 0.004)  # 0.4%
        self.tp2_pct = tp_cfg.get('target2_pct', 0.008)  # 0.8%
        
        # Price history (limited to prevent memory bloat)
        self.closes: Deque[float] = deque(maxlen=200)
        self.highs: Deque[float] = deque(maxlen=200)
        self.lows: Deque[float] = deque(maxlen=200)
        self.volumes: Deque[float] = deque(maxlen=200)
        
        # Order flow
        self.cumulative_delta = 0.0
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        
        # Indicators cache
        self.rsi_value: Optional[float] = None
        self.atr_value: Optional[float] = None
        self.bb_upper: Optional[float] = None
        self.bb_middle: Optional[float] = None
        self.bb_lower: Optional[float] = None
        self.ema_fast_value: Optional[float] = None
        self.ema_slow_value: Optional[float] = None
        
        # Support/Resistance levels
        self.support_levels: Deque[float] = deque(maxlen=5)
        self.resistance_levels: Deque[float] = deque(maxlen=5)
        
        logger.info(
            f"ScalpingEngineV2 initialized for {symbol}: "
            f"SL={self.sl_method}, TP1={self.tp1_pct*100}%, TP2={self.tp2_pct*100}%"
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
    ) -> Optional[ScalpingSignal]:
        """Add kline and generate signal
        
        Args:
            timeframe: Timeframe (should be 1m)
            timestamp: Timestamp
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
            
        Returns:
            ScalpingSignal if generated, None otherwise
        """
        # Only process 1m timeframe
        if timeframe != "1m":
            return None
        
        # Add to history
        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)
        self.volumes.append(volume)
        
        # Need minimum data
        if len(self.closes) < max(self.rsi_period, self.bb_period, self.atr_period):
            return None
        
        # Update indicators
        self._update_indicators()
        
        # Update support/resistance
        self._update_support_resistance()
        
        # Generate signal
        return self._generate_signal(timestamp, close)
    
    def add_trade(
        self,
        timestamp: int,
        price: float,
        quantity: float,
        side: str
    ) -> None:
        """Add trade for order flow analysis
        
        Args:
            timestamp: Trade timestamp
            price: Trade price
            quantity: Trade quantity
            side: Trade side ('Buy' or 'Sell')
        """
        if side == "Buy":
            self.buy_volume += quantity
            self.cumulative_delta += quantity
        else:
            self.sell_volume += quantity
            self.cumulative_delta -= quantity
    
    def _update_indicators(self) -> None:
        """Update all indicators"""
        # RSI
        self.rsi_value = self._calculate_rsi()
        
        # ATR
        self.atr_value = self._calculate_atr()
        
        # Bollinger Bands
        self.bb_upper, self.bb_middle, self.bb_lower = self._calculate_bollinger_bands()
        
        # EMAs
        self.ema_fast_value = self._calculate_ema(self.ema_fast)
        self.ema_slow_value = self._calculate_ema(self.ema_slow)
    
    def _calculate_rsi(self) -> Optional[float]:
        """Calculate RSI"""
        if len(self.closes) < self.rsi_period + 1:
            return None
        
        closes_list = list(self.closes)
        gains = []
        losses = []
        
        for i in range(1, len(closes_list)):
            change = closes_list[i] - closes_list[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < self.rsi_period:
            return None
        
        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_atr(self) -> Optional[float]:
        """Calculate ATR"""
        if len(self.closes) < self.atr_period + 1:
            return None
        
        closes_list = list(self.closes)
        highs_list = list(self.highs)
        lows_list = list(self.lows)
        
        true_ranges = []
        for i in range(1, len(closes_list)):
            high_low = highs_list[i] - lows_list[i]
            high_close = abs(highs_list[i] - closes_list[i-1])
            low_close = abs(lows_list[i] - closes_list[i-1])
            true_range = max(high_low, high_close, low_close)
            true_ranges.append(true_range)
        
        if len(true_ranges) < self.atr_period:
            return None
        
        atr = sum(true_ranges[-self.atr_period:]) / self.atr_period
        return atr
    
    def _calculate_bollinger_bands(self) -> tuple:
        """Calculate Bollinger Bands
        
        Returns:
            Tuple of (upper, middle, lower)
        """
        if len(self.closes) < self.bb_period:
            return None, None, None
        
        closes_list = list(self.closes)[-self.bb_period:]
        
        # Middle band (SMA)
        middle = sum(closes_list) / len(closes_list)
        
        # Standard deviation
        variance = sum((x - middle) ** 2 for x in closes_list) / len(closes_list)
        std_dev = variance ** 0.5
        
        # Upper and lower bands
        upper = middle + (self.bb_std * std_dev)
        lower = middle - (self.bb_std * std_dev)
        
        return upper, middle, lower
    
    def _calculate_ema(self, period: int) -> Optional[float]:
        """Calculate EMA
        
        Args:
            period: EMA period
            
        Returns:
            EMA value or None
        """
        if len(self.closes) < period:
            return None
        
        closes_list = list(self.closes)
        multiplier = 2 / (period + 1)
        
        # Start with SMA
        ema = sum(closes_list[:period]) / period
        
        # Calculate EMA
        for close in closes_list[period:]:
            ema = (close * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _update_support_resistance(self) -> None:
        """Update support and resistance levels"""
        if len(self.closes) < 20:
            return
        
        closes_list = list(self.closes)[-50:]  # Last 50 bars
        highs_list = list(self.highs)[-50:]
        lows_list = list(self.lows)[-50:]
        
        # Find local highs (resistance)
        for i in range(2, len(highs_list) - 2):
            if (highs_list[i] > highs_list[i-1] and 
                highs_list[i] > highs_list[i-2] and
                highs_list[i] > highs_list[i+1] and
                highs_list[i] > highs_list[i+2]):
                if highs_list[i] not in self.resistance_levels:
                    self.resistance_levels.append(highs_list[i])
        
        # Find local lows (support)
        for i in range(2, len(lows_list) - 2):
            if (lows_list[i] < lows_list[i-1] and 
                lows_list[i] < lows_list[i-2] and
                lows_list[i] < lows_list[i+1] and
                lows_list[i] < lows_list[i+2]):
                if lows_list[i] not in self.support_levels:
                    self.support_levels.append(lows_list[i])
    
    def _generate_signal(
        self,
        timestamp: int,
        price: float
    ) -> Optional[ScalpingSignal]:
        """Generate scalping signal
        
        Args:
            timestamp: Current timestamp
            price: Current price
            
        Returns:
            ScalpingSignal if conditions met, None otherwise
        """
        # Check if we have all indicators
        if (self.rsi_value is None or 
            self.atr_value is None or 
            self.bb_upper is None or
            self.ema_fast_value is None or
            self.ema_slow_value is None):
            return None
        
        # Calculate volume ratio
        volume_ratio = 1.0
        if len(self.volumes) > 20:
            avg_volume = sum(list(self.volumes)[:-1]) / (len(self.volumes) - 1)
            current_volume = self.volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Determine BB position
        bb_position = "middle"
        if price <= self.bb_lower:
            bb_position = "lower"
        elif price >= self.bb_upper:
            bb_position = "upper"
        
        # Determine EMA trend
        ema_trend = "neutral"
        if self.ema_fast_value > self.ema_slow_value:
            ema_trend = "bullish"
        elif self.ema_fast_value < self.ema_slow_value:
            ema_trend = "bearish"
        
        # Check BUY conditions
        buy_score = 0
        buy_reasons = []
        
        if self.rsi_value < self.rsi_oversold:
            buy_score += 30
            buy_reasons.append(f"RSI oversold ({self.rsi_value:.1f})")
        
        if self.cumulative_delta > self.delta_threshold:
            buy_score += 25
            buy_reasons.append(f"Positive delta ({self.cumulative_delta:.0f})")
        
        if volume_ratio >= self.volume_multiplier:
            buy_score += 20
            buy_reasons.append(f"High volume ({volume_ratio:.1f}x)")
        
        if bb_position == "lower":
            buy_score += 15
            buy_reasons.append("Price at BB lower")
        
        if ema_trend == "bullish":
            buy_score += 10
            buy_reasons.append("Bullish EMA trend")
        
        # Check if near support
        if self.support_levels:
            nearest_support = min(self.support_levels, key=lambda x: abs(x - price))
            if abs(price - nearest_support) / price < 0.002:  # Within 0.2%
                buy_score += 10
                buy_reasons.append(f"Near support ({nearest_support:.2f})")
        
        # Check SELL conditions
        sell_score = 0
        sell_reasons = []
        
        if self.rsi_value > self.rsi_overbought:
            sell_score += 30
            sell_reasons.append(f"RSI overbought ({self.rsi_value:.1f})")
        
        if self.cumulative_delta < -self.delta_threshold:
            sell_score += 25
            sell_reasons.append(f"Negative delta ({self.cumulative_delta:.0f})")
        
        if volume_ratio >= self.volume_multiplier:
            sell_score += 20
            sell_reasons.append(f"High volume ({volume_ratio:.1f}x)")
        
        if bb_position == "upper":
            sell_score += 15
            sell_reasons.append("Price at BB upper")
        
        if ema_trend == "bearish":
            sell_score += 10
            sell_reasons.append("Bearish EMA trend")
        
        # Check if near resistance
        if self.resistance_levels:
            nearest_resistance = min(self.resistance_levels, key=lambda x: abs(x - price))
            if abs(price - nearest_resistance) / price < 0.002:  # Within 0.2%
                sell_score += 10
                sell_reasons.append(f"Near resistance ({nearest_resistance:.2f})")
        
        # Determine signal
        signal_type = ScalpSignalType.NEUTRAL
        confidence = 0.0
        reasons = []
        stop_loss_price = 0.0
        take_profit1_price = 0.0
        take_profit2_price = 0.0
        
        if buy_score >= 60:  # Minimum 60 points for BUY
            signal_type = ScalpSignalType.BUY
            confidence = min(100, buy_score)
            reasons = buy_reasons
            
            # Calculate stop loss
            if self.sl_method == "atr":
                stop_loss_price = price - (self.atr_value * self.atr_multiplier)
            else:  # fixed
                stop_loss_price = price * (1 - self.fixed_sl_pct)
            
            # Calculate take profits
            take_profit1_price = price * (1 + self.tp1_pct)
            take_profit2_price = price * (1 + self.tp2_pct)
            
        elif sell_score >= 60:  # Minimum 60 points for SELL
            signal_type = ScalpSignalType.SELL
            confidence = min(100, sell_score)
            reasons = sell_reasons
            
            # Calculate stop loss
            if self.sl_method == "atr":
                stop_loss_price = price + (self.atr_value * self.atr_multiplier)
            else:  # fixed
                stop_loss_price = price * (1 + self.fixed_sl_pct)
            
            # Calculate take profits
            take_profit1_price = price * (1 - self.tp1_pct)
            take_profit2_price = price * (1 - self.tp2_pct)
        
        if signal_type == ScalpSignalType.NEUTRAL:
            return None
        
        # Calculate R:R ratio
        risk = abs(price - stop_loss_price)
        reward = abs(take_profit1_price - price)
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Create signal
        signal = ScalpingSignal(
            timestamp=timestamp,
            symbol=self.symbol,
            signal_type=signal_type,
            price=price,
            confidence=confidence,
            rsi=self.rsi_value,
            delta=self.cumulative_delta,
            volume_ratio=volume_ratio,
            bb_position=bb_position,
            ema_trend=ema_trend,
            stop_loss_price=stop_loss_price,
            take_profit1_price=take_profit1_price,
            take_profit2_price=take_profit2_price,
            risk_reward_ratio=risk_reward_ratio,
            reason=", ".join(reasons)
        )
        
        logger.info(
            f"[SCALP V2] {signal_type.value} signal: {price:.2f}, "
            f"SL={stop_loss_price:.2f}, TP1={take_profit1_price:.2f}, TP2={take_profit2_price:.2f}, "
            f"R:R={risk_reward_ratio:.2f}, confidence={confidence:.0f}%"
        )
        
        # Reset order flow after signal
        self.cumulative_delta = 0.0
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        
        return signal
    
    def reset(self) -> None:
        """Reset engine state"""
        self.closes.clear()
        self.highs.clear()
        self.lows.clear()
        self.volumes.clear()
        self.cumulative_delta = 0.0
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.support_levels.clear()
        self.resistance_levels.clear()
