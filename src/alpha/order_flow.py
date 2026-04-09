"""Order Flow Analyzer Module

This module analyzes order flow to calculate cumulative delta, detect imbalances,
and identify delta divergences.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade"""
    timestamp: int
    price: float
    quantity: float
    side: str  # 'Buy' or 'Sell'


@dataclass
class ImbalanceZone:
    """Represents a volume imbalance zone"""
    price_level: float
    buy_volume: float
    sell_volume: float
    imbalance_ratio: float  # Positive for buy, negative for sell
    timestamp: int


class OrderFlowAnalyzer:
    """Analyze order flow to calculate delta and detect imbalances"""
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        window_size: int = 1000,
        imbalance_threshold: float = 0.7
    ):
        """Initialize order flow analyzer
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            window_size: Number of trades to maintain in rolling window
            imbalance_threshold: Threshold for imbalance detection (0.7 = 70%)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.window_size = window_size
        self.imbalance_threshold = imbalance_threshold
        
        # Rolling window of trades
        self.trades: Deque[Trade] = deque(maxlen=window_size)
        
        # Cumulative delta
        self.cumulative_delta = 0.0
        
        # Delta history for divergence detection
        self.delta_history: Deque[float] = deque(maxlen=100)
        self.price_history: Deque[float] = deque(maxlen=100)
        
        # Current metrics
        self.current_metrics: Dict = {}
        
    def add_trade(
        self,
        timestamp: int,
        price: float,
        quantity: float,
        side: str
    ) -> Dict:
        """Add a trade and update order flow metrics
        
        Args:
            timestamp: Trade timestamp (milliseconds)
            price: Trade price
            quantity: Trade quantity
            side: Trade side ('Buy' or 'Sell')
            
        Returns:
            Dictionary with current order flow metrics
        """
        # Create trade object
        trade = Trade(
            timestamp=timestamp,
            price=price,
            quantity=quantity,
            side=side
        )
        
        # Add to rolling window
        self.trades.append(trade)
        
        # Update cumulative delta
        if side == 'Buy':
            self.cumulative_delta += quantity
        elif side == 'Sell':
            self.cumulative_delta -= quantity
        
        # Update histories
        self.delta_history.append(self.cumulative_delta)
        self.price_history.append(price)
        
        # Calculate metrics
        metrics = self._calculate_metrics()
        self.current_metrics = metrics
        
        return metrics
    
    def _calculate_metrics(self) -> Dict:
        """Calculate all order flow metrics
        
        Returns:
            Dictionary with order flow metrics
        """
        if len(self.trades) == 0:
            return {}
        
        metrics = {
            'cumulative_delta': self.cumulative_delta,
            'trade_count': len(self.trades),
        }
        
        # Calculate buy/sell volumes
        buy_volume = sum(t.quantity for t in self.trades if t.side == 'Buy')
        sell_volume = sum(t.quantity for t in self.trades if t.side == 'Sell')
        total_volume = buy_volume + sell_volume
        
        metrics['buy_volume'] = buy_volume
        metrics['sell_volume'] = sell_volume
        metrics['total_volume'] = total_volume
        
        # Calculate buy/sell ratios
        if total_volume > 0:
            metrics['buy_ratio'] = buy_volume / total_volume
            metrics['sell_ratio'] = sell_volume / total_volume
        else:
            metrics['buy_ratio'] = 0.5
            metrics['sell_ratio'] = 0.5
        
        # Detect current imbalance
        if total_volume > 0:
            if metrics['buy_ratio'] > self.imbalance_threshold:
                metrics['imbalance'] = 'BUY'
                metrics['imbalance_strength'] = metrics['buy_ratio']
            elif metrics['sell_ratio'] > self.imbalance_threshold:
                metrics['imbalance'] = 'SELL'
                metrics['imbalance_strength'] = metrics['sell_ratio']
            else:
                metrics['imbalance'] = 'NEUTRAL'
                metrics['imbalance_strength'] = 0.5
        else:
            metrics['imbalance'] = 'NEUTRAL'
            metrics['imbalance_strength'] = 0.5
        
        # Calculate delta divergence
        divergence = self._detect_delta_divergence()
        if divergence:
            metrics['delta_divergence'] = divergence
        
        return metrics
    
    def _detect_delta_divergence(self) -> Optional[str]:
        """Detect delta divergence with price
        
        Divergence occurs when:
        - Price makes higher high but delta makes lower high (bearish)
        - Price makes lower low but delta makes higher low (bullish)
        
        Returns:
            'BULLISH', 'BEARISH', or None
        """
        if len(self.delta_history) < 20 or len(self.price_history) < 20:
            return None
        
        # Get recent data
        recent_deltas = list(self.delta_history)[-20:]
        recent_prices = list(self.price_history)[-20:]
        
        # Find peaks and troughs
        price_peaks = self._find_peaks(recent_prices)
        delta_peaks = self._find_peaks(recent_deltas)
        
        price_troughs = self._find_troughs(recent_prices)
        delta_troughs = self._find_troughs(recent_deltas)
        
        # Check for bearish divergence (price higher high, delta lower high)
        if len(price_peaks) >= 2 and len(delta_peaks) >= 2:
            if price_peaks[-1] > price_peaks[-2] and delta_peaks[-1] < delta_peaks[-2]:
                return 'BEARISH'
        
        # Check for bullish divergence (price lower low, delta higher low)
        if len(price_troughs) >= 2 and len(delta_troughs) >= 2:
            if price_troughs[-1] < price_troughs[-2] and delta_troughs[-1] > delta_troughs[-2]:
                return 'BULLISH'
        
        return None
    
    def _find_peaks(self, data: List[float]) -> List[float]:
        """Find local peaks in data
        
        Args:
            data: List of values
            
        Returns:
            List of peak values
        """
        if len(data) < 3:
            return []
        
        peaks = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                peaks.append(data[i])
        
        return peaks
    
    def _find_troughs(self, data: List[float]) -> List[float]:
        """Find local troughs in data
        
        Args:
            data: List of values
            
        Returns:
            List of trough values
        """
        if len(data) < 3:
            return []
        
        troughs = []
        for i in range(1, len(data) - 1):
            if data[i] < data[i-1] and data[i] < data[i+1]:
                troughs.append(data[i])
        
        return troughs
    
    def get_imbalance_zones(self, num_bins: int = 20) -> List[ImbalanceZone]:
        """Get volume imbalance zones by price level
        
        Args:
            num_bins: Number of price bins
            
        Returns:
            List of ImbalanceZone objects
        """
        if len(self.trades) < 10:
            return []
        
        # Get price range
        prices = [t.price for t in self.trades]
        price_min = min(prices)
        price_max = max(prices)
        
        if price_max == price_min:
            return []
        
        # Create price bins
        bins = np.linspace(price_min, price_max, num_bins + 1)
        
        # Aggregate volume by price bin
        buy_volumes = np.zeros(num_bins)
        sell_volumes = np.zeros(num_bins)
        
        for trade in self.trades:
            bin_idx = np.searchsorted(bins[:-1], trade.price, side='right') - 1
            bin_idx = max(0, min(num_bins - 1, bin_idx))
            
            if trade.side == 'Buy':
                buy_volumes[bin_idx] += trade.quantity
            else:
                sell_volumes[bin_idx] += trade.quantity
        
        # Create imbalance zones
        imbalance_zones = []
        
        for i in range(num_bins):
            total_volume = buy_volumes[i] + sell_volumes[i]
            
            if total_volume == 0:
                continue
            
            buy_ratio = buy_volumes[i] / total_volume
            sell_ratio = sell_volumes[i] / total_volume
            
            # Check for imbalance
            if buy_ratio > self.imbalance_threshold or sell_ratio > self.imbalance_threshold:
                price_level = (bins[i] + bins[i + 1]) / 2
                
                # Positive ratio for buy imbalance, negative for sell
                if buy_ratio > self.imbalance_threshold:
                    imbalance_ratio = buy_ratio
                else:
                    imbalance_ratio = -sell_ratio
                
                zone = ImbalanceZone(
                    price_level=price_level,
                    buy_volume=buy_volumes[i],
                    sell_volume=sell_volumes[i],
                    imbalance_ratio=imbalance_ratio,
                    timestamp=self.trades[-1].timestamp if self.trades else 0
                )
                
                imbalance_zones.append(zone)
        
        return imbalance_zones
    
    def get_current_metrics(self) -> Dict:
        """Get current order flow metrics
        
        Returns:
            Dictionary with current metrics
        """
        return self.current_metrics.copy()
    
    def reset(self) -> None:
        """Reset order flow analyzer"""
        self.trades.clear()
        self.cumulative_delta = 0.0
        self.delta_history.clear()
        self.price_history.clear()
        self.current_metrics.clear()


class OrderFlowEngine:
    """Manage order flow analysis for multiple symbols and timeframes"""
    
    def __init__(self):
        """Initialize order flow engine"""
        self.analyzers: Dict[Tuple[str, str], OrderFlowAnalyzer] = {}
        
    def get_or_create_analyzer(
        self,
        symbol: str,
        timeframe: str,
        window_size: int = 1000,
        imbalance_threshold: float = 0.7
    ) -> OrderFlowAnalyzer:
        """Get or create order flow analyzer
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            window_size: Rolling window size
            imbalance_threshold: Imbalance detection threshold
            
        Returns:
            OrderFlowAnalyzer instance
        """
        key = (symbol, timeframe)
        
        if key not in self.analyzers:
            self.analyzers[key] = OrderFlowAnalyzer(
                symbol=symbol,
                timeframe=timeframe,
                window_size=window_size,
                imbalance_threshold=imbalance_threshold
            )
            logger.info(f"Created order flow analyzer for {symbol} {timeframe}")
        
        return self.analyzers[key]
    
    def add_trade(
        self,
        symbol: str,
        timeframe: str,
        timestamp: int,
        price: float,
        quantity: float,
        side: str
    ) -> Dict:
        """Add trade to analyzer
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            timestamp: Trade timestamp
            price: Trade price
            quantity: Trade quantity
            side: Trade side ('Buy' or 'Sell')
            
        Returns:
            Dictionary with current metrics
        """
        analyzer = self.get_or_create_analyzer(symbol, timeframe)
        return analyzer.add_trade(timestamp, price, quantity, side)
    
    def get_metrics(self, symbol: str, timeframe: str) -> Dict:
        """Get current metrics
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Dictionary with metrics or empty dict if not found
        """
        key = (symbol, timeframe)
        
        if key not in self.analyzers:
            return {}
        
        return self.analyzers[key].get_current_metrics()
    
    def get_imbalance_zones(
        self,
        symbol: str,
        timeframe: str,
        num_bins: int = 20
    ) -> List[ImbalanceZone]:
        """Get imbalance zones
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            num_bins: Number of price bins
            
        Returns:
            List of ImbalanceZone objects
        """
        key = (symbol, timeframe)
        
        if key not in self.analyzers:
            return []
        
        return self.analyzers[key].get_imbalance_zones(num_bins)
    
    def reset(self, symbol: str, timeframe: str) -> None:
        """Reset analyzer
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        """
        key = (symbol, timeframe)
        
        if key in self.analyzers:
            self.analyzers[key].reset()
            logger.info(f"Reset order flow analyzer for {symbol} {timeframe}")
    
    def get_tracked_pairs(self) -> List[Tuple[str, str]]:
        """Get list of tracked symbol/timeframe pairs
        
        Returns:
            List of (symbol, timeframe) tuples
        """
        return list(self.analyzers.keys())
