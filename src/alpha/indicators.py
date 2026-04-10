"""Technical Indicators Engine

This module calculates technical indicators with < 50ms update latency.
"""

import logging
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np

from .incremental_ema import IncrementalEMA, IncrementalRSI

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators for a single symbol/timeframe"""
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        sma_periods: List[int] = [9, 21, 50, 200],
        ema_periods: List[int] = [9, 21, 50, 200],
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        volume_profile_hours: int = 24,
        max_history: int = 200
    ):
        """Initialize technical indicators
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe (e.g., '1m', '5m', '15m', '1h')
            sma_periods: SMA periods to calculate
            ema_periods: EMA periods to calculate
            rsi_period: RSI period
            macd_fast: MACD fast period
            macd_slow: MACD slow period
            macd_signal: MACD signal period
            bb_period: Bollinger Bands period
            bb_std: Bollinger Bands standard deviation multiplier
            volume_profile_hours: Volume profile window in hours
            max_history: Maximum bars to keep in history (circular buffer limit)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        
        # Configuration
        self.sma_periods = sma_periods
        self.ema_periods = ema_periods
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_profile_hours = volume_profile_hours
        self.max_history = max_history
        
        # Data storage (rolling windows with circular buffer limit)
        # Limit to max_history bars to prevent memory bloat
        max_period = min(max(sma_periods + ema_periods + [bb_period, macd_slow]), max_history)
        self.closes = deque(maxlen=max_period)
        self.volumes = deque(maxlen=max_period)
        
        # Volume profile limited to max_history
        vp_window = min(self._get_volume_profile_window(), max_history)
        self.prices_for_volume_profile = deque(maxlen=vp_window)
        self.volumes_for_profile = deque(maxlen=vp_window)
        
        # Incremental calculators
        self.ema_calculators: Dict[int, IncrementalEMA] = {
            period: IncrementalEMA(period) for period in ema_periods
        }
        self.rsi_calculator = IncrementalRSI(rsi_period)
        
        # MACD incremental calculators
        self.macd_fast_ema = IncrementalEMA(macd_fast)
        self.macd_slow_ema = IncrementalEMA(macd_slow)
        self.macd_signal_ema = IncrementalEMA(macd_signal)
        
        # Current indicator values
        self.current_values: Dict = {}
        
    def _get_volume_profile_window(self) -> int:
        """Calculate volume profile window size based on timeframe
        
        Returns:
            Number of candles in the window
        """
        # Map timeframe to minutes
        timeframe_minutes = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }
        
        minutes = timeframe_minutes.get(self.timeframe, 60)
        window_minutes = self.volume_profile_hours * 60
        return window_minutes // minutes
    
    def update(self, close: float, volume: float) -> Dict:
        """Update all indicators with new kline data
        
        This method updates all indicators incrementally in < 50ms.
        
        Args:
            close: Close price
            volume: Volume
            
        Returns:
            Dictionary with all current indicator values
        """
        start_time = time.perf_counter()
        
        # Add to rolling windows
        self.closes.append(close)
        self.volumes.append(volume)
        self.prices_for_volume_profile.append(close)
        self.volumes_for_profile.append(volume)
        
        # Calculate indicators
        indicators = {}
        
        # SMA
        for period in self.sma_periods:
            sma = self._calculate_sma(period)
            if sma is not None:
                indicators[f'sma_{period}'] = sma
        
        # EMA (incremental)
        for period in self.ema_periods:
            ema = self.ema_calculators[period].update(close)
            if ema is not None:
                indicators[f'ema_{period}'] = ema
        
        # RSI (incremental)
        rsi = self.rsi_calculator.update(close)
        if rsi is not None:
            indicators['rsi'] = rsi
        
        # MACD (incremental)
        macd_values = self._calculate_macd_incremental(close)
        if macd_values:
            indicators.update(macd_values)
        
        # Bollinger Bands
        bb_values = self._calculate_bollinger_bands()
        if bb_values:
            indicators.update(bb_values)
        
        # Volume Profile
        vp_values = self._calculate_volume_profile()
        if vp_values:
            indicators.update(vp_values)
            
        # VWAP
        vwap = self._calculate_vwap()
        if vwap is not None:
            indicators['vwap'] = vwap
        
        # Store current values
        self.current_values = indicators
        
        # Calculate elapsed time
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        if elapsed_ms > 50:
            logger.warning(
                f"Indicator update exceeded 50ms: {elapsed_ms:.2f}ms "
                f"for {self.symbol} {self.timeframe}"
            )
        
        logger.debug(
            f"Updated indicators for {self.symbol} {self.timeframe} "
            f"in {elapsed_ms:.2f}ms"
        )
        
        return indicators
    
    def _calculate_sma(self, period: int) -> Optional[float]:
        """Calculate Simple Moving Average
        
        Args:
            period: SMA period
            
        Returns:
            SMA value or None if insufficient data
        """
        if len(self.closes) < period:
            return None
        
        # Use numpy with float32 for 50% memory reduction
        closes_array = np.array(list(self.closes)[-period:], dtype=np.float32)
        return float(np.mean(closes_array))
    
    def _calculate_macd_incremental(self, close: float) -> Dict:
        """Calculate MACD using incremental EMAs
        
        Args:
            close: Current close price
            
        Returns:
            Dictionary with MACD values or empty dict if insufficient data
        """
        # Update fast and slow EMAs
        fast_ema = self.macd_fast_ema.update(close)
        slow_ema = self.macd_slow_ema.update(close)
        
        if fast_ema is None or slow_ema is None:
            return {}
        
        # MACD line = fast EMA - slow EMA
        macd_line = fast_ema - slow_ema
        
        # Signal line = EMA of MACD line
        signal_line = self.macd_signal_ema.update(macd_line)
        
        if signal_line is None:
            return {
                'macd_line': macd_line,
                'macd_signal': None,
                'macd_histogram': None
            }
        
        # Histogram = MACD line - signal line
        histogram = macd_line - signal_line
        
        return {
            'macd_line': macd_line,
            'macd_signal': signal_line,
            'macd_histogram': histogram
        }
    
    def _calculate_bollinger_bands(self) -> Dict:
        """Calculate Bollinger Bands
        
        Returns:
            Dictionary with BB values or empty dict if insufficient data
        """
        if len(self.closes) < self.bb_period:
            return {}
        
        # Use numpy with float32 for 50% memory reduction
        closes_array = np.array(list(self.closes)[-self.bb_period:], dtype=np.float32)
        
        # Middle band = SMA
        middle = float(np.mean(closes_array))
        
        # Standard deviation
        std = float(np.std(closes_array, ddof=0))
        
        # Upper and lower bands
        upper = middle + (self.bb_std * std)
        lower = middle - (self.bb_std * std)
        
        return {
            'bb_upper': upper,
            'bb_middle': middle,
            'bb_lower': lower,
            'bb_width': upper - lower
        }
    
    def _calculate_volume_profile(self) -> Dict:
        """Calculate Volume Profile for last 24 hours
        
        Returns:
            Dictionary with volume profile values or empty dict if insufficient data
        """
        if len(self.prices_for_volume_profile) < 10:
            return {}
        
        # Convert to numpy arrays with float32 for 50% memory reduction
        prices = np.array(list(self.prices_for_volume_profile), dtype=np.float32)
        volumes = np.array(list(self.volumes_for_profile), dtype=np.float32)
        
        # Create price bins (20 bins)
        num_bins = 20
        price_min = np.min(prices)
        price_max = np.max(prices)
        
        if price_max == price_min:
            return {}
        
        bins = np.linspace(price_min, price_max, num_bins + 1, dtype=np.float32)
        
        # Aggregate volume by price bins
        volume_by_bin = np.zeros(num_bins, dtype=np.float32)
        
        for i in range(len(prices)):
            bin_idx = np.searchsorted(bins[:-1], prices[i], side='right') - 1
            bin_idx = max(0, min(num_bins - 1, bin_idx))
            volume_by_bin[bin_idx] += volumes[i]
        
        # Find high volume node (HVN) and low volume node (LVN)
        max_volume_idx = np.argmax(volume_by_bin)
        min_volume_idx = np.argmin(volume_by_bin)
        
        hvn_price = (bins[max_volume_idx] + bins[max_volume_idx + 1]) / 2
        lvn_price = (bins[min_volume_idx] + bins[min_volume_idx + 1]) / 2
        
        # Point of Control (POC) = price level with highest volume
        poc_price = hvn_price
        
        # Value Area (70% of volume)
        total_volume = np.sum(volume_by_bin)
        value_area_volume = total_volume * 0.7
        
        # Find value area high and low
        sorted_indices = np.argsort(volume_by_bin)[::-1]
        cumulative_volume = 0
        value_area_indices = []
        
        for idx in sorted_indices:
            cumulative_volume += volume_by_bin[idx]
            value_area_indices.append(idx)
            if cumulative_volume >= value_area_volume:
                break
        
        value_area_low = bins[min(value_area_indices)]
        value_area_high = bins[max(value_area_indices) + 1]
        
        return {
            'vp_poc': float(poc_price),  # Point of Control
            'vp_hvn': float(hvn_price),  # High Volume Node
            'vp_lvn': float(lvn_price),  # Low Volume Node
            'vp_value_area_high': float(value_area_high),
            'vp_value_area_low': float(value_area_low),
            'vp_total_volume': float(total_volume)
        }
    
    def _calculate_vwap(self) -> Optional[float]:
        """Calculate Rolling VWAP
        
        Returns:
            VWAP value or None
        """
        if len(self.prices_for_volume_profile) == 0:
            return None
            
        prices = np.array(list(self.prices_for_volume_profile), dtype=np.float32)
        volumes = np.array(list(self.volumes_for_profile), dtype=np.float32)
        
        cumulative_volume = np.sum(volumes)
        if cumulative_volume == 0:
            return float(prices[-1])  # Fallback to last price if volume is 0
            
        vwap = np.sum(prices * volumes) / cumulative_volume
        return float(vwap)
    
    def get_current_values(self) -> Dict:
        """Get current indicator values
        
        Returns:
            Dictionary with all current indicator values
        """
        return self.current_values.copy()
    
    def reset(self) -> None:
        """Reset all indicators"""
        self.closes.clear()
        self.volumes.clear()
        self.prices_for_volume_profile.clear()
        self.volumes_for_profile.clear()
        
        for ema_calc in self.ema_calculators.values():
            ema_calc.reset()
        
        self.rsi_calculator.reset()
        self.macd_fast_ema.reset()
        self.macd_slow_ema.reset()
        self.macd_signal_ema.reset()
        
        self.current_values.clear()


class IndicatorEngine:
    """Manage indicators for multiple symbols and timeframes"""
    
    def __init__(self):
        """Initialize indicator engine"""
        self.indicators: Dict[Tuple[str, str], TechnicalIndicators] = {}
        
    def get_or_create_indicators(
        self,
        symbol: str,
        timeframe: str,
        **kwargs
    ) -> TechnicalIndicators:
        """Get or create indicators for symbol/timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            **kwargs: Configuration values passed to TechnicalIndicators
            
        Returns:
            TechnicalIndicators instance
        """
        key = (symbol, timeframe)
        
        if key not in self.indicators:
            self.indicators[key] = TechnicalIndicators(symbol, timeframe, **kwargs)
            logger.info(f"Created indicators for {symbol} {timeframe}")
        
        return self.indicators[key]
    
    def update(
        self,
        symbol: str,
        timeframe: str,
        close: float,
        volume: float,
        **kwargs
    ) -> Dict:
        """Update indicators for symbol/timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            close: Close price
            volume: Volume
            
        Returns:
            Dictionary with all current indicator values
        """
        indicators = self.get_or_create_indicators(symbol, timeframe, **kwargs)
        return indicators.update(close, volume)
    
    def get_values(self, symbol: str, timeframe: str) -> Dict:
        """Get current indicator values
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Dictionary with indicator values or empty dict if not found
        """
        key = (symbol, timeframe)
        
        if key not in self.indicators:
            return {}
        
        return self.indicators[key].get_current_values()
    
    def reset(self, symbol: str, timeframe: str) -> None:
        """Reset indicators for symbol/timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        """
        key = (symbol, timeframe)
        
        if key in self.indicators:
            self.indicators[key].reset()
            logger.info(f"Reset indicators for {symbol} {timeframe}")
    
    def get_tracked_pairs(self) -> List[Tuple[str, str]]:
        """Get list of tracked symbol/timeframe pairs
        
        Returns:
            List of (symbol, timeframe) tuples
        """
        return list(self.indicators.keys())
