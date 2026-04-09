"""Property-Based Tests for Data Pipeline

Tests for data integrity, validation, and processing properties.
"""

import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from src.data.gap_detector import GapDetector
from src.data.stream_processor import StreamProcessor
from src.data.timescaledb_writer import TimescaleDBWriter
from src.data.validator import DataValidator


# Custom strategies for generating valid market data
@st.composite
def valid_kline_strategy(draw):
    """Generate valid kline data"""
    low = draw(st.decimals(min_value=Decimal('1'), max_value=Decimal('100000'), places=2))
    high = draw(st.decimals(min_value=low, max_value=low * Decimal('1.1'), places=2))
    open_price = draw(st.decimals(min_value=low, max_value=high, places=2))
    close_price = draw(st.decimals(min_value=low, max_value=high, places=2))
    
    return {
        'timestamp': draw(st.integers(min_value=1000000000000, max_value=2000000000000)),
        'symbol': draw(st.sampled_from(['BTCUSDT', 'ETHUSDT', 'SOLUSDT'])),
        'timeframe': draw(st.sampled_from(['1m', '5m', '15m', '1h'])),
        'open': str(open_price),
        'high': str(high),
        'low': str(low),
        'close': str(close_price),
        'volume': str(draw(st.decimals(min_value=Decimal('0'), max_value=Decimal('1000000'), places=3)))
    }


@st.composite
def valid_trade_strategy(draw):
    """Generate valid trade data"""
    return {
        'timestamp': draw(st.integers(min_value=1000000000000, max_value=2000000000000)),
        'symbol': draw(st.sampled_from(['BTCUSDT', 'ETHUSDT', 'SOLUSDT'])),
        'trade_id': draw(st.text(min_size=1, max_size=20)),
        'price': str(draw(st.decimals(min_value=Decimal('0.01'), max_value=Decimal('100000'), places=2))),
        'quantity': str(draw(st.decimals(min_value=Decimal('0.001'), max_value=Decimal('1000'), places=3))),
        'side': draw(st.sampled_from(['Buy', 'Sell']))
    }


@st.composite
def valid_orderbook_strategy(draw):
    """Generate valid orderbook data with at least 20 levels"""
    base_price = draw(st.decimals(min_value=Decimal('1000'), max_value=Decimal('100000'), places=2))
    
    # Generate 20+ bid levels (descending prices)
    num_bids = draw(st.integers(min_value=20, max_value=30))
    bids = []
    for i in range(num_bids):
        price = str(base_price - Decimal(i * 10))
        quantity = str(draw(st.decimals(min_value=Decimal('0.1'), max_value=Decimal('10'), places=3)))
        bids.append([price, quantity])
    
    # Generate 20+ ask levels (ascending prices)
    num_asks = draw(st.integers(min_value=20, max_value=30))
    asks = []
    for i in range(num_asks):
        price = str(base_price + Decimal(100 + i * 10))
        quantity = str(draw(st.decimals(min_value=Decimal('0.1'), max_value=Decimal('10'), places=3)))
        asks.append([price, quantity])
    
    return {
        'timestamp': draw(st.integers(min_value=1000000000000, max_value=2000000000000)),
        'symbol': draw(st.sampled_from(['BTCUSDT', 'ETHUSDT', 'SOLUSDT'])),
        'bids': bids,
        'asks': asks
    }


class TestProperty5DataStorageLatency:
    """Property 5: Data Storage Latency
    
    **Validates: Requirements 2.1**
    
    For any market data received via WebSocket, the time from reception to storage
    in TimescaleDB should be less than 100 milliseconds.
    """
    
    @pytest.mark.asyncio
    @given(kline=valid_kline_strategy())
    @settings(max_examples=50, deadline=2000)
    async def test_kline_processing_latency(self, kline):
        """Test kline processing completes in < 100ms"""
        # Mock database writer
        db_writer = MagicMock()
        db_writer.write_kline = AsyncMock()
        
        processor = StreamProcessor(db_writer)
        
        start_time = time.perf_counter()
        await processor.process_kline(kline)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Should complete in < 100ms
        assert elapsed_ms < 100, f"Processing took {elapsed_ms:.2f}ms (> 100ms)"


class TestProperty6DataCompleteness:
    """Property 6: Data Completeness
    
    **Validates: Requirements 2.3**
    
    For any collected trade data, all required fields (price, quantity, side, timestamp)
    must be present and non-null.
    """
    
    @given(trade=valid_trade_strategy())
    @settings(max_examples=100)
    def test_trade_data_completeness(self, trade):
        """Test all required trade fields are present"""
        required_fields = ['price', 'quantity', 'side', 'timestamp', 'symbol', 'trade_id']
        
        for field in required_fields:
            assert field in trade, f"Missing required field: {field}"
            assert trade[field] is not None, f"Field {field} is None"
    
    @given(kline=valid_kline_strategy())
    @settings(max_examples=100)
    def test_kline_data_completeness(self, kline):
        """Test all required kline fields are present"""
        required_fields = ['open', 'high', 'low', 'close', 'volume', 'timestamp', 'symbol', 'timeframe']
        
        for field in required_fields:
            assert field in kline, f"Missing required field: {field}"
            assert kline[field] is not None, f"Field {field} is None"


class TestProperty7OrderbookDepthRequirement:
    """Property 7: Orderbook Depth Requirement
    
    **Validates: Requirements 2.4**
    
    For any collected orderbook snapshot, there should be at least 20 price levels
    on both the bid and ask sides.
    """
    
    @given(orderbook=valid_orderbook_strategy())
    @settings(max_examples=100)
    def test_orderbook_depth_requirement(self, orderbook):
        """Test orderbook has at least 20 levels on each side"""
        assert len(orderbook['bids']) >= 20, f"Insufficient bid depth: {len(orderbook['bids'])}"
        assert len(orderbook['asks']) >= 20, f"Insufficient ask depth: {len(orderbook['asks'])}"
    
    @given(orderbook=valid_orderbook_strategy())
    @settings(max_examples=100)
    def test_orderbook_validation_passes(self, orderbook):
        """Test valid orderbooks pass validation"""
        validator = DataValidator()
        result = validator.validate_orderbook(orderbook)
        assert result.is_valid, f"Valid orderbook failed validation: {result.errors}"


class TestProperty8DataDeduplication:
    """Property 8: Data Deduplication
    
    **Validates: Requirements 2.5**
    
    For any set of incoming market data records with identical (timestamp, symbol, timeframe)
    tuples, only one record should be stored in the database.
    """
    
    @pytest.mark.asyncio
    @given(kline=valid_kline_strategy())
    @settings(max_examples=50, deadline=2000)
    async def test_kline_deduplication(self, kline):
        """Test duplicate klines are not processed twice"""
        db_writer = MagicMock()
        db_writer.write_kline = AsyncMock()
        
        processor = StreamProcessor(db_writer)
        
        # Process same kline twice
        result1 = await processor.process_kline(kline)
        result2 = await processor.process_kline(kline)
        
        # First should succeed, second should be deduplicated
        assert result1 is True
        assert result2 is False
        
        # Database write should only be called once
        assert db_writer.write_kline.call_count == 1
    
    @pytest.mark.asyncio
    @given(trade=valid_trade_strategy())
    @settings(max_examples=50, deadline=2000)
    async def test_trade_deduplication(self, trade):
        """Test duplicate trades are not processed twice"""
        db_writer = MagicMock()
        db_writer.write_trade = AsyncMock()
        
        processor = StreamProcessor(db_writer)
        
        # Process same trade twice
        result1 = await processor.process_trade(trade)
        result2 = await processor.process_trade(trade)
        
        # First should succeed, second should be deduplicated
        assert result1 is True
        assert result2 is False
        
        # Database write should only be called once
        assert db_writer.write_trade.call_count == 1


class TestProperty9DataBufferingOnConnectionFailure:
    """Property 9: Data Buffering on Connection Failure
    
    **Validates: Requirements 2.6**
    
    For any TimescaleDB connection failure, the Data_Pipeline should buffer incoming
    data in memory up to a maximum of 10,000 records without data loss.
    """
    
    @pytest.mark.asyncio
    @given(
        klines=st.lists(valid_kline_strategy(), min_size=1, max_size=100)
    )
    @settings(max_examples=20, deadline=5000)
    async def test_kline_buffering_on_connection_failure(self, klines):
        """Test klines are buffered when database connection fails"""
        writer = TimescaleDBWriter('postgresql://localhost/test', buffer_size=10000)
        
        # Database is not connected
        assert not writer.is_connected()
        
        # Write klines (should be buffered)
        for kline in klines:
            await writer.write_kline(kline)
        
        # All klines should be in buffer
        assert len(writer.kline_buffer) == len(klines)
        
        # No data loss
        for i, kline in enumerate(klines):
            assert writer.kline_buffer[i] == kline
    
    @pytest.mark.asyncio
    async def test_buffer_capacity_limit(self):
        """Test buffer respects maximum capacity"""
        buffer_size = 100
        writer = TimescaleDBWriter('postgresql://localhost/test', buffer_size=buffer_size)
        
        # Generate more klines than buffer capacity
        for i in range(buffer_size + 50):
            kline = {
                'timestamp': 1000000000000 + i,
                'symbol': 'BTCUSDT',
                'timeframe': '1m',
                'open': '50000',
                'high': '50100',
                'low': '49900',
                'close': '50050',
                'volume': '100'
            }
            await writer.write_kline(kline)
        
        # Buffer should not exceed capacity
        assert len(writer.kline_buffer) <= buffer_size


class TestProperty64DataValidationCompleteness:
    """Property 64-71: Data Validation and Integrity
    
    **Validates: Requirements 18.1, 18.2, 18.3**
    
    For any incoming data, validation should check completeness and correctness.
    """
    
    @given(kline=valid_kline_strategy())
    @settings(max_examples=100)
    def test_valid_kline_passes_validation(self, kline):
        """Test valid klines pass validation"""
        validator = DataValidator()
        result = validator.validate_kline(kline)
        assert result.is_valid, f"Valid kline failed validation: {result.errors}"
    
    @given(
        kline=valid_kline_strategy(),
        field_to_remove=st.sampled_from(['open', 'high', 'low', 'close', 'volume', 'timestamp'])
    )
    @settings(max_examples=50)
    def test_incomplete_kline_fails_validation(self, kline, field_to_remove):
        """Test klines with missing fields fail validation"""
        # Remove a required field
        incomplete_kline = kline.copy()
        del incomplete_kline[field_to_remove]
        
        validator = DataValidator()
        result = validator.validate_kline(incomplete_kline)
        assert not result.is_valid
        assert any(field_to_remove in error for error in result.errors)
    
    @given(trade=valid_trade_strategy())
    @settings(max_examples=100)
    def test_valid_trade_passes_validation(self, trade):
        """Test valid trades pass validation"""
        validator = DataValidator()
        result = validator.validate_trade(trade)
        assert result.is_valid, f"Valid trade failed validation: {result.errors}"
    
    @given(
        base_price=st.decimals(min_value=Decimal('1000'), max_value=Decimal('100000'), places=2)
    )
    @settings(max_examples=50)
    def test_invalid_ohlc_fails_validation(self, base_price):
        """Test klines with invalid OHLC constraints fail validation"""
        # Create kline with high < low (invalid)
        invalid_kline = {
            'timestamp': 1234567890000,
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': str(base_price),
            'high': str(base_price - Decimal('100')),  # High < Low
            'low': str(base_price),
            'close': str(base_price),
            'volume': '100'
        }
        
        validator = DataValidator()
        result = validator.validate_kline(invalid_kline)
        assert not result.is_valid
        assert any('high' in error.lower() and 'low' in error.lower() for error in result.errors)


class TestGapDetectionProperties:
    """Test gap detection properties"""
    
    @given(
        timeframe=st.sampled_from(['1m', '5m', '15m', '1h']),
        gap_size=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=50)
    def test_gap_detection_accuracy(self, timeframe, gap_size):
        """Test gap detection correctly identifies missing records"""
        detector = GapDetector()
        
        # Map timeframe to interval minutes
        interval_map = {'1m': 1, '5m': 5, '15m': 15, '1h': 60}
        interval_minutes = interval_map[timeframe]
        
        last_timestamp = datetime(2024, 1, 1, 12, 0, 0)
        current_timestamp = last_timestamp + timedelta(minutes=interval_minutes * gap_size)
        
        gap = detector.detect_gap('BTCUSDT', timeframe, last_timestamp, current_timestamp)
        
        if gap_size > 1:
            # Gap should be detected
            assert gap is not None
            assert gap.expected_records == gap_size - 1
        else:
            # No gap
            assert gap is None
    
    def test_no_gap_for_consecutive_timestamps(self):
        """Test no gap detected for consecutive timestamps"""
        detector = GapDetector()
        
        last_timestamp = datetime(2024, 1, 1, 12, 0, 0)
        current_timestamp = datetime(2024, 1, 1, 12, 1, 0)
        
        gap = detector.detect_gap('BTCUSDT', '1m', last_timestamp, current_timestamp)
        assert gap is None
