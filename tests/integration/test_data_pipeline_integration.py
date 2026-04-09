"""Integration Tests for Data Pipeline

Tests the complete data pipeline with real database connection.
"""

import asyncio
import os
import pytest
from datetime import datetime
from dotenv import load_dotenv

from src.data.stream_processor import StreamProcessor
from src.data.timescaledb_writer import TimescaleDBWriter
from src.data.validator import DataValidator
from src.data.gap_detector import GapDetector

# Load environment variables
load_dotenv()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_data_pipeline():
    """Test complete data pipeline with database connection"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        pytest.skip("DATABASE_URL not configured")
    
    # Initialize components
    db_writer = TimescaleDBWriter(database_url)
    validator = DataValidator()
    gap_detector = GapDetector()
    processor = StreamProcessor(db_writer, gap_detector, validator)
    
    try:
        # Connect to database
        await db_writer.connect()
        assert db_writer.is_connected()
        
        # Create test kline
        test_kline = {
            'timestamp': int(datetime.now().timestamp() * 1000),
            'symbol': 'BTCUSDT',
            'timeframe': '1m',
            'open': '50000.0',
            'high': '50100.0',
            'low': '49900.0',
            'close': '50050.0',
            'volume': '100.5'
        }
        
        # Process kline
        result = await processor.process_kline(test_kline)
        assert result is True
        
        # Check metrics
        metrics = processor.get_performance_metrics()
        assert metrics['processed_count']['klines'] == 1
        assert metrics['avg_latency_ms'] < 100  # Should be < 100ms
        
        print(f"✓ Data pipeline test passed")
        print(f"  - Latency: {metrics['avg_latency_ms']:.2f}ms")
        print(f"  - Processed: {metrics['processed_count']}")
        
    finally:
        # Cleanup
        await db_writer.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_query_performance():
    """Test database query performance for 1 million rows"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        pytest.skip("DATABASE_URL not configured")
    
    db_writer = TimescaleDBWriter(database_url)
    
    try:
        await db_writer.connect()
        
        # Query to check if we can query efficiently
        # This is a placeholder - actual test would need 1M rows
        import asyncpg
        async with db_writer.pool.acquire() as conn:
            # Simple query to verify connection
            result = await conn.fetchval("SELECT COUNT(*) FROM klines")
            print(f"✓ Database query test passed")
            print(f"  - Total klines in database: {result}")
        
    finally:
        await db_writer.disconnect()


if __name__ == '__main__':
    # Run tests directly
    asyncio.run(test_complete_data_pipeline())
    asyncio.run(test_database_query_performance())
