"""Scalping Signal Generation Engine

This module specifically calculates high-frequency scalping logic based on 1m and indicators like VWAP, RSI(7), EMA.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml

from src.alpha.indicators import IndicatorEngine
from src.alpha.signal_engine import SignalType, TradingSignal

logger = logging.getLogger(__name__)

class ScalpingSignalGenerator:
    """Generate scalping signals from 1m timeframe data"""
    
    def __init__(
        self,
        symbol: str,
        config_path: str = "config/config.yaml"
    ):
        """Initialize scalping generator
        
        Args:
            symbol: Trading symbol
            config_path: Path to configuration file
        """
        self.symbol = symbol
        
        # Load configuration
        with open(config_path, 'r') as f:
            full_config = yaml.safe_load(f)
            
        self.config = full_config.get('scalping', {})
        if not self.config:
            logger.warning("No 'scalping' config found in config.yaml, using defaults")
            
        self.rsi_period = self.config.get('rsi_period', 7)
        self.ema_periods = self.config.get('ema_periods', [9, 21, 200])
        self.bb_params = self.config.get('bb_params', [20, 2])
        self.min_confidence = 60.0
        
        # Tracking previous values for cross-over detection
        self.prev_rsi: Optional[float] = None
        self.prev_ema_9: Optional[float] = None
        self.prev_ema_21: Optional[float] = None
        
        # Indicator engine with specific scalping kwargs
        self.indicator_engine = IndicatorEngine()
        self.indicator_kwargs = {
            'rsi_period': self.rsi_period,
            'ema_periods': self.ema_periods,
            'bb_period': self.bb_params[0],
            'bb_std': float(self.bb_params[1])
        }
        
        self.signals: List[TradingSignal] = []
        self.max_signal_history = 500
        
        logger.info(
            f"Initialized ScalpingSignalGenerator for {symbol} "
            f"(RSI: {self.rsi_period}, EMAs: {self.ema_periods})"
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
        # Only process 1m timeframe for scalping
        if timeframe != "1m":
            return None
            
        # Update indicator engine
        indicators = self.indicator_engine.update(
            symbol=self.symbol,
            timeframe=timeframe,
            close=close,
            volume=volume,
            **self.indicator_kwargs
        )
        
        # Generate signal
        return self._generate_signal(timestamp, close, indicators, low, high)
    
    def _generate_signal(
        self,
        timestamp: int,
        price: float,
        indicators: dict,
        low: float,
        high: float
    ) -> Optional[TradingSignal]:
        """Generate scalping signal based on indicators"""
        
        vwap = indicators.get('vwap')
        ema_200 = indicators.get('ema_200')
        ema_9 = indicators.get('ema_9')
        ema_21 = indicators.get('ema_21')
        rsi = indicators.get('rsi')
        bb_lower = indicators.get('bb_lower')
        bb_upper = indicators.get('bb_upper')
        
        # We need all these to make a decision
        if None in (vwap, ema_200, ema_9, ema_21, rsi, bb_lower, bb_upper):
            # Also keep track of prev values early on
            self.prev_rsi = rsi
            self.prev_ema_9 = ema_9
            self.prev_ema_21 = ema_21
            return None
            
        # 1. Trend Filter: Price vs VWAP
        above_vwap = price > vwap
        below_vwap = price < vwap
        
        # 2. Trend Filter: EMA crossover / positioning
        # EMA 200 acts as baseline, EMA9/21 cross acts as momentum trigger
        above_ema200 = price > ema_200
        below_ema200 = price < ema_200
        
        ema_cross_up = (
            self.prev_ema_9 is not None and self.prev_ema_21 is not None and
            self.prev_ema_9 <= self.prev_ema_21 and ema_9 > ema_21
        )
        ema_cross_down = (
            self.prev_ema_9 is not None and self.prev_ema_21 is not None and
            self.prev_ema_9 >= self.prev_ema_21 and ema_9 < ema_21
        )
        
        # 3. Oscillator: RSI Oversold/Overbought reversal
        rsi_oversold_cross = (
            self.prev_rsi is not None and 
            self.prev_rsi < 30 and rsi >= 30
        )
        rsi_overbought_cross = (
            self.prev_rsi is not None and 
            self.prev_rsi > 70 and rsi <= 70
        )
        # We also accept if it's deeply oversold currently as a condition
        rsi_is_oversold = rsi < 30
        rsi_is_overbought = rsi > 70
        
        # 4. Volatility bands: Bollinger interaction
        touches_lower_bb = low <= bb_lower
        touches_upper_bb = high >= bb_upper
        
        # Decision Logic - BUY
        # - Above VWAP
        # - Above EMA200 OR EMA9 crosses above EMA21
        # - RSI dropping below 30 and reversing up (or deeply oversold) + Touches Lower BB
        
        buy_signal = False
        sell_signal = False
        reason = ""
        
        if above_vwap and (above_ema200 or ema_cross_up):
            if (rsi_oversold_cross or rsi_is_oversold) and touches_lower_bb:
                buy_signal = True
                reason = f"Above VWAP & EMA200, RSI={rsi:.1f} (oversold), touching BB-Lower"
                
        # Decision Logic - SELL
        if below_vwap and (below_ema200 or ema_cross_down):
            if (rsi_overbought_cross or rsi_is_overbought) and touches_upper_bb:
                sell_signal = True
                reason = f"Below VWAP & EMA200, RSI={rsi:.1f} (overbought), touching BB-Upper"
        
        # Save previous states
        self.prev_rsi = rsi
        self.prev_ema_9 = ema_9
        self.prev_ema_21 = ema_21

        if not buy_signal and not sell_signal:
            return None
            
        signal_type = SignalType.BUY if buy_signal else SignalType.SELL
        confidence = 100.0  # Since it's rule-based
        
        signal = TradingSignal(
            timestamp=timestamp,
            symbol=self.symbol,
            signal_type=signal_type,
            confidence=confidence,
            price=price,
            wyckoff_phase="N/A",  # Not used in scalping
            delta=0.0,
            breakout_direction=None,
            volume_ratio=1.0,
            timeframe_alignment={"1m": True},
            aligned_timeframes=1,
            trend_aligned=above_ema200 if buy_signal else below_ema200,
            momentum_score=1.0 if (ema_cross_up or ema_cross_down) else 0.5,
            reason=reason,
            suppressed=False
        )
        
        self.signals.append(signal)
        
        if len(self.signals) > self.max_signal_history:
            self.signals = self.signals[-self.max_signal_history:]
            
        logger.info(f"[SCALP] Signal generated: {signal_type.value} at {price:.2f}, reason: {reason}")
            
        return signal

    def get_latest_signal(self) -> Optional[TradingSignal]:
        if not self.signals:
            return None
        return self.signals[-1]
    
    def reset(self):
        self.prev_rsi = None
        self.prev_ema_9 = None
        self.prev_ema_21 = None
        self.signals.clear()
