"""Footprint Chart Generator

This module generates footprint charts for order flow visualization.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FootprintBar:
    """Represents a single bar in footprint chart"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    price_levels: Dict[float, Dict[str, float]]  # price -> {'buy': vol, 'sell': vol, 'delta': delta}
    total_buy_volume: float
    total_sell_volume: float
    total_delta: float
    poc_price: float  # Point of Control (highest volume price)


class FootprintGenerator:
    """Generate footprint charts from trade data"""
    
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        tick_size: float = 0.5
    ):
        """Initialize footprint generator
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            tick_size: Price tick size for aggregation
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.tick_size = tick_size
        
        # Current bar being built
        self.current_bar: Optional[Dict] = None
        self.current_timestamp: Optional[int] = None
        
        # Completed bars
        self.bars: List[FootprintBar] = []
        
    def add_trade(
        self,
        timestamp: int,
        price: float,
        quantity: float,
        side: str,
        bar_open: float,
        bar_high: float,
        bar_low: float,
        bar_close: float
    ) -> Optional[FootprintBar]:
        """Add trade to footprint chart
        
        Args:
            timestamp: Trade timestamp (milliseconds)
            price: Trade price
            quantity: Trade quantity
            side: Trade side ('Buy' or 'Sell')
            bar_open: Bar open price
            bar_high: Bar high price
            bar_low: Bar low price
            bar_close: Bar close price
            
        Returns:
            Completed FootprintBar if bar finished, None otherwise
        """
        # Round price to tick size
        price_level = self._round_to_tick(price)
        
        # Check if new bar
        if self.current_timestamp is None or timestamp != self.current_timestamp:
            # Complete previous bar if exists
            completed_bar = self._complete_current_bar()
            
            # Start new bar
            self.current_timestamp = timestamp
            self.current_bar = {
                'timestamp': timestamp,
                'open': bar_open,
                'high': bar_high,
                'low': bar_low,
                'close': bar_close,
                'price_levels': {},
                'total_buy_volume': 0.0,
                'total_sell_volume': 0.0
            }
            
            # Add trade to new bar
            self._add_trade_to_current_bar(price_level, quantity, side)
            
            return completed_bar
        
        # Add to current bar
        self._add_trade_to_current_bar(price_level, quantity, side)
        
        # Update OHLC
        self.current_bar['high'] = max(self.current_bar['high'], bar_high)
        self.current_bar['low'] = min(self.current_bar['low'], bar_low)
        self.current_bar['close'] = bar_close
        
        return None
    
    def _round_to_tick(self, price: float) -> float:
        """Round price to tick size
        
        Args:
            price: Price to round
            
        Returns:
            Rounded price
        """
        return round(price / self.tick_size) * self.tick_size
    
    def _add_trade_to_current_bar(
        self,
        price_level: float,
        quantity: float,
        side: str
    ) -> None:
        """Add trade to current bar
        
        Args:
            price_level: Price level (rounded to tick)
            quantity: Trade quantity
            side: Trade side ('Buy' or 'Sell')
        """
        if self.current_bar is None:
            return
        
        # Initialize price level if not exists
        if price_level not in self.current_bar['price_levels']:
            self.current_bar['price_levels'][price_level] = {
                'buy': 0.0,
                'sell': 0.0,
                'delta': 0.0
            }
        
        # Add volume
        if side == 'Buy':
            self.current_bar['price_levels'][price_level]['buy'] += quantity
            self.current_bar['price_levels'][price_level]['delta'] += quantity
            self.current_bar['total_buy_volume'] += quantity
        elif side == 'Sell':
            self.current_bar['price_levels'][price_level]['sell'] += quantity
            self.current_bar['price_levels'][price_level]['delta'] -= quantity
            self.current_bar['total_sell_volume'] += quantity
    
    def _complete_current_bar(self) -> Optional[FootprintBar]:
        """Complete current bar and create FootprintBar object
        
        Returns:
            FootprintBar or None if no current bar
        """
        if self.current_bar is None:
            return None
        
        # Calculate total delta
        total_delta = self.current_bar['total_buy_volume'] - self.current_bar['total_sell_volume']
        
        # Find Point of Control (price with highest volume)
        poc_price = self.current_bar['open']
        max_volume = 0.0
        
        for price, volumes in self.current_bar['price_levels'].items():
            total_volume = volumes['buy'] + volumes['sell']
            if total_volume > max_volume:
                max_volume = total_volume
                poc_price = price
        
        # Create FootprintBar
        bar = FootprintBar(
            timestamp=self.current_bar['timestamp'],
            open=self.current_bar['open'],
            high=self.current_bar['high'],
            low=self.current_bar['low'],
            close=self.current_bar['close'],
            price_levels=self.current_bar['price_levels'].copy(),
            total_buy_volume=self.current_bar['total_buy_volume'],
            total_sell_volume=self.current_bar['total_sell_volume'],
            total_delta=total_delta,
            poc_price=poc_price
        )
        
        self.bars.append(bar)
        
        return bar
    
    def get_bars(self) -> List[FootprintBar]:
        """Get all completed footprint bars
        
        Returns:
            List of FootprintBar objects
        """
        return self.bars.copy()
    
    def get_latest_bar(self) -> Optional[FootprintBar]:
        """Get latest completed bar
        
        Returns:
            Latest FootprintBar or None
        """
        if not self.bars:
            return None
        return self.bars[-1]
    
    def get_bar_summary(self, bar: FootprintBar) -> Dict:
        """Get summary statistics for a bar
        
        Args:
            bar: FootprintBar object
            
        Returns:
            Dictionary with summary statistics
        """
        # Calculate imbalances at each price level
        imbalances = []
        
        for price, volumes in bar.price_levels.items():
            total_volume = volumes['buy'] + volumes['sell']
            if total_volume > 0:
                buy_ratio = volumes['buy'] / total_volume
                
                # Significant imbalance if > 70% one direction
                if buy_ratio > 0.7:
                    imbalances.append({
                        'price': price,
                        'type': 'BUY',
                        'ratio': buy_ratio,
                        'volume': total_volume
                    })
                elif buy_ratio < 0.3:
                    imbalances.append({
                        'price': price,
                        'type': 'SELL',
                        'ratio': 1 - buy_ratio,
                        'volume': total_volume
                    })
        
        # Sort imbalances by volume
        imbalances.sort(key=lambda x: x['volume'], reverse=True)
        
        return {
            'timestamp': bar.timestamp,
            'ohlc': {
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close
            },
            'volume': {
                'buy': bar.total_buy_volume,
                'sell': bar.total_sell_volume,
                'total': bar.total_buy_volume + bar.total_sell_volume,
                'delta': bar.total_delta
            },
            'poc_price': bar.poc_price,
            'num_price_levels': len(bar.price_levels),
            'imbalances': imbalances[:5]  # Top 5 imbalances
        }
    
    def reset(self) -> None:
        """Reset footprint generator"""
        self.current_bar = None
        self.current_timestamp = None
        self.bars.clear()


class FootprintEngine:
    """Manage footprint generation for multiple symbols and timeframes"""
    
    def __init__(self):
        """Initialize footprint engine"""
        self.generators: Dict[tuple, FootprintGenerator] = {}
        
    def get_or_create_generator(
        self,
        symbol: str,
        timeframe: str,
        tick_size: float = 0.5
    ) -> FootprintGenerator:
        """Get or create footprint generator
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            tick_size: Price tick size
            
        Returns:
            FootprintGenerator instance
        """
        key = (symbol, timeframe)
        
        if key not in self.generators:
            self.generators[key] = FootprintGenerator(
                symbol=symbol,
                timeframe=timeframe,
                tick_size=tick_size
            )
            logger.info(f"Created footprint generator for {symbol} {timeframe}")
        
        return self.generators[key]
    
    def add_trade(
        self,
        symbol: str,
        timeframe: str,
        timestamp: int,
        price: float,
        quantity: float,
        side: str,
        bar_open: float,
        bar_high: float,
        bar_low: float,
        bar_close: float
    ) -> Optional[FootprintBar]:
        """Add trade to footprint
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            timestamp: Trade timestamp
            price: Trade price
            quantity: Trade quantity
            side: Trade side
            bar_open: Bar open price
            bar_high: Bar high price
            bar_low: Bar low price
            bar_close: Bar close price
            
        Returns:
            Completed FootprintBar if bar finished, None otherwise
        """
        generator = self.get_or_create_generator(symbol, timeframe)
        return generator.add_trade(
            timestamp, price, quantity, side,
            bar_open, bar_high, bar_low, bar_close
        )
    
    def get_bars(self, symbol: str, timeframe: str) -> List[FootprintBar]:
        """Get footprint bars
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            List of FootprintBar objects
        """
        key = (symbol, timeframe)
        
        if key not in self.generators:
            return []
        
        return self.generators[key].get_bars()
    
    def get_latest_bar(self, symbol: str, timeframe: str) -> Optional[FootprintBar]:
        """Get latest footprint bar
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Latest FootprintBar or None
        """
        key = (symbol, timeframe)
        
        if key not in self.generators:
            return None
        
        return self.generators[key].get_latest_bar()
    
    def reset(self, symbol: str, timeframe: str) -> None:
        """Reset generator
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        """
        key = (symbol, timeframe)
        
        if key in self.generators:
            self.generators[key].reset()
            logger.info(f"Reset footprint generator for {symbol} {timeframe}")
