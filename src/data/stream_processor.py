"""Stream Processor Module

This module processes real-time market data streams with < 100ms latency.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Set

from .gap_detector import GapDetector
from .timescaledb_writer import TimescaleDBWriter
from .validator import DataValidator

logger = logging.getLogger(__name__)


class StreamProcessor:
    """Process real-time market data streams with validation and deduplication"""
    
    def __init__(
        self,
        db_writer: TimescaleDBWriter,
        gap_detector: Optional[GapDetector] = None,
        validator: Optional[DataValidator] = None
    ):
        """Initialize stream processor
        
        Args:
            db_writer: TimescaleDB writer instance
            gap_detector: Gap detector instance (optional)
            validator: Data validator instance (optional)
        """
        self.db_writer = db_writer
        self.gap_detector = gap_detector or GapDetector()
        self.validator = validator or DataValidator()
        
        # Deduplication tracking
        self.seen_klines: Set[tuple] = set()  # (symbol, timestamp, timeframe)
        self.seen_trades: Set[tuple] = set()  # (symbol, timestamp, trade_id)
        self.seen_orderbooks: Set[tuple] = set()  # (symbol, timestamp)
        
        # Performance metrics
        self.processing_times = []
        self.processed_count = {
            'klines': 0,
            'trades': 0,
            'orderbooks': 0
        }
        self.validation_errors = {
            'klines': 0,
            'trades': 0,
            'orderbooks': 0
        }
        
    async def process_kline(self, kline_data: Dict) -> bool:
        """Process kline data in < 100ms
        
        Steps:
            1. Validate data (completeness and correctness)
            2. Deduplicate based on (symbol, timestamp, timeframe)
            3. Check for gaps and fill if needed
            4. Store to TimescaleDB
            5. Track processing time
        
        Args:
            kline_data: Kline data dictionary
            
        Returns:
            True if processed successfully, False otherwise
        """
        start_time = time.perf_counter()
        
        try:
            # Step 1: Validate data
            validation_result = self.validator.validate_kline(kline_data)
            if not validation_result.is_valid:
                self.validation_errors['klines'] += 1
                logger.warning(f"Invalid kline data: {validation_result.errors}")
                return False
            
            # Step 2: Deduplicate
            dedup_key = (
                kline_data['symbol'],
                kline_data['timestamp'],
                kline_data['timeframe']
            )
            
            if dedup_key in self.seen_klines:
                logger.debug(f"Duplicate kline detected: {dedup_key}")
                return False
            
            self.seen_klines.add(dedup_key)
            
            # Limit dedup cache size (keep last 10000 entries)
            if len(self.seen_klines) > 10000:
                # Remove oldest entries (approximate FIFO)
                self.seen_klines = set(list(self.seen_klines)[-5000:])
            
            # Step 3: Check for gaps
            if self.gap_detector:
                # Convert timestamp to datetime
                if isinstance(kline_data['timestamp'], (int, float)):
                    current_timestamp = datetime.fromtimestamp(kline_data['timestamp'] / 1000)
                else:
                    current_timestamp = kline_data['timestamp']
                
                # Check and fill gap (non-blocking)
                asyncio.create_task(
                    self.gap_detector.check_and_fill_gap(
                        kline_data['symbol'],
                        kline_data['timeframe'],
                        current_timestamp
                    )
                )
            
            # Step 4: Store to database
            await self.db_writer.write_kline(kline_data)
            
            # Step 5: Track metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.processing_times.append(elapsed_ms)
            
            # Keep only last 1000 measurements
            if len(self.processing_times) > 1000:
                self.processing_times = self.processing_times[-1000:]
            
            self.processed_count['klines'] += 1
            
            # Log warning if processing took too long
            if elapsed_ms > 100:
                logger.warning(f"Kline processing exceeded 100ms: {elapsed_ms:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing kline: {e}")
            return False
    
    async def process_trade(self, trade_data: Dict) -> bool:
        """Process trade data
        
        Steps:
            1. Validate data
            2. Deduplicate based on (symbol, timestamp, trade_id)
            3. Store to TimescaleDB
        
        Args:
            trade_data: Trade data dictionary
            
        Returns:
            True if processed successfully, False otherwise
        """
        start_time = time.perf_counter()
        
        try:
            # Validate
            validation_result = self.validator.validate_trade(trade_data)
            if not validation_result.is_valid:
                self.validation_errors['trades'] += 1
                logger.warning(f"Invalid trade data: {validation_result.errors}")
                return False
            
            # Deduplicate
            dedup_key = (
                trade_data['symbol'],
                trade_data['timestamp'],
                trade_data['trade_id']
            )
            
            if dedup_key in self.seen_trades:
                logger.debug(f"Duplicate trade detected: {dedup_key}")
                return False
            
            self.seen_trades.add(dedup_key)
            
            # Limit cache size
            if len(self.seen_trades) > 10000:
                self.seen_trades = set(list(self.seen_trades)[-5000:])
            
            # Store to database
            await self.db_writer.write_trade(trade_data)
            
            # Track metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.processing_times.append(elapsed_ms)
            
            if len(self.processing_times) > 1000:
                self.processing_times = self.processing_times[-1000:]
            
            self.processed_count['trades'] += 1
            
            if elapsed_ms > 100:
                logger.warning(f"Trade processing exceeded 100ms: {elapsed_ms:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
            return False
    
    async def process_orderbook(self, orderbook_data: Dict) -> bool:
        """Process orderbook snapshot
        
        Steps:
            1. Validate data (including 20 levels requirement)
            2. Deduplicate based on (symbol, timestamp)
            3. Store to TimescaleDB
        
        Args:
            orderbook_data: Orderbook data dictionary
            
        Returns:
            True if processed successfully, False otherwise
        """
        start_time = time.perf_counter()
        
        try:
            # Validate
            validation_result = self.validator.validate_orderbook(orderbook_data)
            if not validation_result.is_valid:
                self.validation_errors['orderbooks'] += 1
                logger.warning(f"Invalid orderbook data: {validation_result.errors}")
                return False
            
            # Deduplicate
            dedup_key = (
                orderbook_data['symbol'],
                orderbook_data['timestamp']
            )
            
            if dedup_key in self.seen_orderbooks:
                logger.debug(f"Duplicate orderbook detected: {dedup_key}")
                return False
            
            self.seen_orderbooks.add(dedup_key)
            
            # Limit cache size
            if len(self.seen_orderbooks) > 10000:
                self.seen_orderbooks = set(list(self.seen_orderbooks)[-5000:])
            
            # Store to database
            await self.db_writer.write_orderbook(orderbook_data)
            
            # Track metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.processing_times.append(elapsed_ms)
            
            if len(self.processing_times) > 1000:
                self.processing_times = self.processing_times[-1000:]
            
            self.processed_count['orderbooks'] += 1
            
            if elapsed_ms > 100:
                logger.warning(f"Orderbook processing exceeded 100ms: {elapsed_ms:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing orderbook: {e}")
            return False
    
    def get_performance_metrics(self) -> Dict:
        """Get performance metrics
        
        Returns:
            Dictionary with performance statistics
        """
        if not self.processing_times:
            return {
                'avg_latency_ms': 0,
                'p50_latency_ms': 0,
                'p95_latency_ms': 0,
                'p99_latency_ms': 0,
                'max_latency_ms': 0,
                'processed_count': self.processed_count,
                'validation_errors': self.validation_errors
            }
        
        sorted_times = sorted(self.processing_times)
        n = len(sorted_times)
        
        return {
            'avg_latency_ms': sum(sorted_times) / n,
            'p50_latency_ms': sorted_times[int(n * 0.5)],
            'p95_latency_ms': sorted_times[int(n * 0.95)],
            'p99_latency_ms': sorted_times[int(n * 0.99)],
            'max_latency_ms': sorted_times[-1],
            'processed_count': self.processed_count.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics"""
        self.processing_times.clear()
        self.processed_count = {
            'klines': 0,
            'trades': 0,
            'orderbooks': 0
        }
        self.validation_errors = {
            'klines': 0,
            'trades': 0,
            'orderbooks': 0
        }
    
    def get_dedup_stats(self) -> Dict:
        """Get deduplication statistics
        
        Returns:
            Dictionary with dedup cache sizes
        """
        return {
            'klines_cache_size': len(self.seen_klines),
            'trades_cache_size': len(self.seen_trades),
            'orderbooks_cache_size': len(self.seen_orderbooks)
        }
