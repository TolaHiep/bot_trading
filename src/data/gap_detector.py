"""Gap Detector Module

This module detects and fills gaps in time-series data.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeGap:
    """Represents a gap in time-series data"""
    symbol: str
    timeframe: str
    gap_start: datetime
    gap_end: datetime
    expected_records: int


class GapDetector:
    """Detect and fill gaps in time-series data"""
    
    # Timeframe intervals in seconds
    TIMEFRAME_INTERVALS = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400
    }
    
    def __init__(self, rest_client=None, db_writer=None):
        """Initialize gap detector
        
        Args:
            rest_client: Bybit REST client for fetching historical data
            db_writer: TimescaleDB writer for storing filled data
        """
        self.rest_client = rest_client
        self.db_writer = db_writer
        self.last_timestamps: Dict[tuple, datetime] = {}  # (symbol, timeframe) -> last_timestamp
        
    def detect_gap(
        self,
        symbol: str,
        timeframe: str,
        last_timestamp: datetime,
        current_timestamp: datetime
    ) -> Optional[TimeGap]:
        """Detect gap by comparing timestamps
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '1m', '5m')
            last_timestamp: Last known timestamp
            current_timestamp: Current timestamp
            
        Returns:
            TimeGap if gap detected, None otherwise
        """
        if timeframe not in self.TIMEFRAME_INTERVALS:
            logger.warning(f"Unknown timeframe: {timeframe}")
            return None
        
        interval_seconds = self.TIMEFRAME_INTERVALS[timeframe]
        expected_next = last_timestamp + timedelta(seconds=interval_seconds)
        
        # Allow small tolerance for timing variations (1 second)
        tolerance = timedelta(seconds=1)
        
        if current_timestamp > expected_next + tolerance:
            # Gap detected
            gap_duration = (current_timestamp - last_timestamp).total_seconds()
            expected_records = int(gap_duration / interval_seconds) - 1
            
            if expected_records > 0:
                gap = TimeGap(
                    symbol=symbol,
                    timeframe=timeframe,
                    gap_start=last_timestamp,
                    gap_end=current_timestamp,
                    expected_records=expected_records
                )
                
                logger.warning(
                    f"Gap detected: {symbol} {timeframe} from {last_timestamp} to {current_timestamp} "
                    f"({expected_records} missing records)"
                )
                
                return gap
        
        return None
    
    def update_last_timestamp(self, symbol: str, timeframe: str, timestamp: datetime) -> None:
        """Update last known timestamp for symbol/timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            timestamp: Timestamp to record
        """
        key = (symbol, timeframe)
        self.last_timestamps[key] = timestamp
    
    def get_last_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get last known timestamp for symbol/timeframe
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Last timestamp or None if not tracked
        """
        key = (symbol, timeframe)
        return self.last_timestamps.get(key)
    
    async def fill_gap(self, gap: TimeGap) -> List[Dict]:
        """Fill gap by fetching historical data from REST API
        
        Steps:
            1. Call Bybit REST API to fetch missing data
            2. Validate fetched data
            3. Store to TimescaleDB
            4. Return filled records
        
        Args:
            gap: TimeGap object describing the gap
            
        Returns:
            List of filled kline records
        """
        if not self.rest_client:
            logger.error("Cannot fill gap: REST client not configured")
            return []
        
        try:
            logger.info(
                f"Filling gap: {gap.symbol} {gap.timeframe} "
                f"from {gap.gap_start} to {gap.gap_end} ({gap.expected_records} records)"
            )
            
            # Convert timeframe to Bybit interval format
            interval_map = {
                '1m': '1',
                '5m': '5',
                '15m': '15',
                '1h': '60',
                '4h': '240',
                '1d': 'D'
            }
            
            interval = interval_map.get(gap.timeframe)
            if not interval:
                logger.error(f"Unsupported timeframe for gap filling: {gap.timeframe}")
                return []
            
            # Convert timestamps to milliseconds
            start_time = int(gap.gap_start.timestamp() * 1000)
            end_time = int(gap.gap_end.timestamp() * 1000)
            
            # Fetch historical data from Bybit
            # Bybit returns max 200 records per request
            all_klines = []
            current_start = start_time
            
            while current_start < end_time:
                klines = await self.rest_client.get_klines(
                    symbol=gap.symbol,
                    interval=interval,
                    start_time=current_start,
                    end_time=end_time,
                    limit=200
                )
                
                if not klines:
                    break
                
                # Bybit returns klines in reverse chronological order
                klines.reverse()
                
                # Convert Bybit format to our format
                for kline in klines:
                    # Bybit kline format: [timestamp, open, high, low, close, volume, turnover]
                    kline_dict = {
                        'timestamp': int(kline[0]),
                        'symbol': gap.symbol,
                        'timeframe': gap.timeframe,
                        'open': kline[1],
                        'high': kline[2],
                        'low': kline[3],
                        'close': kline[4],
                        'volume': kline[5]
                    }
                    all_klines.append(kline_dict)
                
                # Update start time for next batch
                if klines:
                    current_start = int(klines[-1][0]) + 1
                else:
                    break
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.1)
            
            # Store filled data to database
            if all_klines and self.db_writer:
                await self.db_writer.batch_write_klines(all_klines)
                logger.info(f"Successfully filled gap with {len(all_klines)} records")
            
            return all_klines
            
        except Exception as e:
            logger.error(f"Failed to fill gap: {e}")
            return []
    
    async def check_and_fill_gap(
        self,
        symbol: str,
        timeframe: str,
        current_timestamp: datetime
    ) -> Optional[List[Dict]]:
        """Check for gap and fill if detected
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            current_timestamp: Current timestamp
            
        Returns:
            List of filled records if gap was filled, None otherwise
        """
        last_timestamp = self.get_last_timestamp(symbol, timeframe)
        
        if last_timestamp is None:
            # First data point, no gap to check
            self.update_last_timestamp(symbol, timeframe, current_timestamp)
            return None
        
        gap = self.detect_gap(symbol, timeframe, last_timestamp, current_timestamp)
        
        if gap:
            # Gap detected, attempt to fill
            filled_records = await self.fill_gap(gap)
            
            # Update last timestamp
            self.update_last_timestamp(symbol, timeframe, current_timestamp)
            
            return filled_records
        else:
            # No gap, update timestamp
            self.update_last_timestamp(symbol, timeframe, current_timestamp)
            return None
    
    def get_gap_statistics(self) -> Dict[str, int]:
        """Get statistics about tracked symbols/timeframes
        
        Returns:
            Dictionary with statistics
        """
        return {
            'tracked_pairs': len(self.last_timestamps),
            'symbols': len(set(k[0] for k in self.last_timestamps.keys())),
            'timeframes': len(set(k[1] for k in self.last_timestamps.keys()))
        }
