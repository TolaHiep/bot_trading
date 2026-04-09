"""Unit Tests for Data Pipeline

Tests for validator, stream processor, gap detector, and TimescaleDB writer.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.data.validator import DataValidator, ValidationResult
from src.data.gap_detector import GapDetector, TimeGap
from src.data.stream_processor import StreamProcessor
from src.data.timescaledb_writer import TimescaleDBWriter


class TestDataValidator:
    """Test DataValidator"""
    
    def test_validate_kline_valid(self):
        """Test validation of valid kline data"""
        validator = DataValidator()
        
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            'high': '50100.0',
            'low': '49900.0',
            'close': '50050.0',
            'volume': '100.5'
        }
        
        result = validator.validate_kline(kline)
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_kline_missing_field(self):
        """Test validation fails when required field is missing"""
        validator = DataValidator()
        
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            # Missing 'high'
            'low': '49900.0',
            'close': '50050.0',
            'volume': '100.5'
        }
        
        result = validator.validate_kline(kline)
        assert not result.is_valid
        assert any('high' in error for error in result.errors)
    
    def test_validate_kline_invalid_ohlc(self):
        """Test validation fails when OHLC constraints violated"""
        validator = DataValidator()
        
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            'high': '49000.0',  # High < Low (invalid)
            'low': '49900.0',
            'close': '50050.0',
            'volume': '100.5'
        }
        
        result = validator.validate_kline(kline)
        assert not result.is_valid
        assert any('high' in error.lower() and 'low' in error.lower() for error in result.errors)
    
    def test_validate_kline_negative_volume(self):
        """Test validation fails for negative volume"""
        validator = DataValidator()
        
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            'high': '50100.0',
            'low': '49900.0',
            'close': '50050.0',
            'volume': '-100.5'  # Negative volume
        }
        
        result = validator.validate_kline(kline)
        assert not result.is_valid
        assert any('volume' in error.lower() for error in result.errors)
    
    def test_validate_trade_valid(self):
        """Test validation of valid trade data"""
        validator = DataValidator()
        
        trade = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'trade_id': 'trade123',
            'price': '50000.0',
            'quantity': '0.5',
            'side': 'Buy'
        }
        
        result = validator.validate_trade(trade)
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_trade_invalid_side(self):
        """Test validation fails for invalid side"""
        validator = DataValidator()
        
        trade = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'trade_id': 'trade123',
            'price': '50000.0',
            'quantity': '0.5',
            'side': 'Invalid'  # Invalid side
        }
        
        result = validator.validate_trade(trade)
        assert not result.is_valid
        assert any('side' in error.lower() for error in result.errors)
    
    def test_validate_orderbook_valid(self):
        """Test validation of valid orderbook data"""
        validator = DataValidator()
        
        # Create 20 levels of bids and asks
        bids = [[str(50000 - i * 10), str(1.0 + i * 0.1)] for i in range(20)]
        asks = [[str(50100 + i * 10), str(1.0 + i * 0.1)] for i in range(20)]
        
        orderbook = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'bids': bids,
            'asks': asks
        }
        
        result = validator.validate_orderbook(orderbook)
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_orderbook_insufficient_depth(self):
        """Test validation fails when depth < 20 levels"""
        validator = DataValidator()
        
        # Only 10 levels
        bids = [[str(50000 - i * 10), str(1.0)] for i in range(10)]
        asks = [[str(50100 + i * 10), str(1.0)] for i in range(10)]
        
        orderbook = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'bids': bids,
            'asks': asks
        }
        
        result = validator.validate_orderbook(orderbook)
        assert not result.is_valid
        assert any('depth' in error.lower() for error in result.errors)


class TestGapDetector:
    """Test GapDetector"""
    
    def test_detect_gap_no_gap(self):
        """Test no gap detected when timestamps are consecutive"""
        detector = GapDetector()
        
        last_timestamp = datetime(2024, 1, 1, 12, 0, 0)
        current_timestamp = datetime(2024, 1, 1, 12, 1, 0)  # 1 minute later
        
        gap = detector.detect_gap('BTCUSDT', '1m', last_timestamp, current_timestamp)
        assert gap is None
    
    def test_detect_gap_with_gap(self):
        """Test gap detected when timestamps have missing data"""
        detector = GapDetector()
        
        last_timestamp = datetime(2024, 1, 1, 12, 0, 0)
        current_timestamp = datetime(2024, 1, 1, 12, 5, 0)  # 5 minutes later (4 missing)
        
        gap = detector.detect_gap('BTCUSDT', '1m', last_timestamp, current_timestamp)
        assert gap is not None
        assert gap.symbol == 'BTCUSDT'
        assert gap.timeframe == '1m'
        assert gap.expected_records == 4
    
    def test_update_and_get_last_timestamp(self):
        """Test updating and retrieving last timestamp"""
        detector = GapDetector()
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        detector.update_last_timestamp('BTCUSDT', '1m', timestamp)
        
        retrieved = detector.get_last_timestamp('BTCUSDT', '1m')
        assert retrieved == timestamp
    
    @pytest.mark.asyncio
    async def test_fill_gap_no_rest_client(self):
        """Test fill_gap returns empty list when no REST client configured"""
        detector = GapDetector()
        
        gap = TimeGap(
            symbol='BTCUSDT',
            timeframe='1m',
            gap_start=datetime(2024, 1, 1, 12, 0, 0),
            gap_end=datetime(2024, 1, 1, 12, 5, 0),
            expected_records=4
        )
        
        result = await detector.fill_gap(gap)
        assert result == []


class TestStreamProcessor:
    """Test StreamProcessor"""
    
    @pytest.mark.asyncio
    async def test_process_kline_valid(self):
        """Test processing valid kline data"""
        # Mock dependencies
        db_writer = MagicMock()
        db_writer.write_kline = AsyncMock()
        
        processor = StreamProcessor(db_writer)
        
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            'high': '50100.0',
            'low': '49900.0',
            'close': '50050.0',
            'volume': '100.5'
        }
        
        result = await processor.process_kline(kline)
        assert result is True
        db_writer.write_kline.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_kline_invalid(self):
        """Test processing invalid kline data"""
        db_writer = MagicMock()
        processor = StreamProcessor(db_writer)
        
        # Invalid kline (missing fields)
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT'
        }
        
        result = await processor.process_kline(kline)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_process_kline_deduplication(self):
        """Test deduplication of duplicate klines"""
        db_writer = MagicMock()
        db_writer.write_kline = AsyncMock()
        
        processor = StreamProcessor(db_writer)
        
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            'high': '50100.0',
            'low': '49900.0',
            'close': '50050.0',
            'volume': '100.5'
        }
        
        # Process first time
        result1 = await processor.process_kline(kline)
        assert result1 is True
        
        # Process duplicate
        result2 = await processor.process_kline(kline)
        assert result2 is False
        
        # Should only write once
        assert db_writer.write_kline.call_count == 1
    
    @pytest.mark.asyncio
    async def test_process_trade_valid(self):
        """Test processing valid trade data"""
        db_writer = MagicMock()
        db_writer.write_trade = AsyncMock()
        
        processor = StreamProcessor(db_writer)
        
        trade = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'trade_id': 'trade123',
            'price': '50000.0',
            'quantity': '0.5',
            'side': 'Buy'
        }
        
        result = await processor.process_trade(trade)
        assert result is True
        db_writer.write_trade.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_orderbook_valid(self):
        """Test processing valid orderbook data"""
        db_writer = MagicMock()
        db_writer.write_orderbook = AsyncMock()
        
        processor = StreamProcessor(db_writer)
        
        bids = [[str(50000 - i * 10), str(1.0)] for i in range(20)]
        asks = [[str(50100 + i * 10), str(1.0)] for i in range(20)]
        
        orderbook = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'bids': bids,
            'asks': asks
        }
        
        result = await processor.process_orderbook(orderbook)
        assert result is True
        db_writer.write_orderbook.assert_called_once()
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        db_writer = MagicMock()
        processor = StreamProcessor(db_writer)
        
        metrics = processor.get_performance_metrics()
        assert 'avg_latency_ms' in metrics
        assert 'p95_latency_ms' in metrics
        assert 'processed_count' in metrics
        assert 'validation_errors' in metrics
    
    def test_get_dedup_stats(self):
        """Test getting deduplication statistics"""
        db_writer = MagicMock()
        processor = StreamProcessor(db_writer)
        
        stats = processor.get_dedup_stats()
        assert 'klines_cache_size' in stats
        assert 'trades_cache_size' in stats
        assert 'orderbooks_cache_size' in stats


class TestTimescaleDBWriter:
    """Test TimescaleDBWriter"""
    
    def test_init(self):
        """Test initialization"""
        writer = TimescaleDBWriter('postgresql://localhost/test')
        assert writer.database_url == 'postgresql://localhost/test'
        assert writer.buffer_size == 10000
        assert len(writer.kline_buffer) == 0
    
    def test_get_buffer_status(self):
        """Test getting buffer status"""
        writer = TimescaleDBWriter('postgresql://localhost/test')
        
        status = writer.get_buffer_status()
        assert status['klines'] == 0
        assert status['trades'] == 0
        assert status['orderbooks'] == 0
        assert status['capacity'] == 10000
    
    def test_is_connected(self):
        """Test connection status check"""
        writer = TimescaleDBWriter('postgresql://localhost/test')
        assert writer.is_connected() is False
    
    @pytest.mark.asyncio
    async def test_write_kline_when_disconnected(self):
        """Test kline is buffered when database is disconnected"""
        writer = TimescaleDBWriter('postgresql://localhost/test')
        
        kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            'high': '50100.0',
            'low': '49900.0',
            'close': '50050.0',
            'volume': '100.5'
        }
        
        await writer.write_kline(kline)
        
        # Should be buffered
        assert len(writer.kline_buffer) == 1
        assert writer.kline_buffer[0] == kline
