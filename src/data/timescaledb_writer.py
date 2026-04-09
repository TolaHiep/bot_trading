"""TimescaleDB Writer Module

This module handles writing market data to TimescaleDB with buffering support.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any, Deque, Dict, List, Optional

import asyncpg
import ujson

logger = logging.getLogger(__name__)


class TimescaleDBWriter:
    """Write market data to TimescaleDB with connection failure buffering"""
    
    def __init__(self, database_url: str, buffer_size: int = 10000):
        """Initialize TimescaleDB writer
        
        Args:
            database_url: PostgreSQL connection string
            buffer_size: Maximum number of records to buffer when DB connection fails
        """
        self.database_url = database_url
        self.buffer_size = buffer_size
        self.pool: Optional[asyncpg.Pool] = None
        
        # In-memory buffers for connection failures
        self.kline_buffer: Deque[Dict] = deque(maxlen=buffer_size)
        self.trade_buffer: Deque[Dict] = deque(maxlen=buffer_size)
        self.orderbook_buffer: Deque[Dict] = deque(maxlen=buffer_size)
        
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> None:
        """Establish connection pool to TimescaleDB"""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            self._connected = True
            logger.info("Connected to TimescaleDB")
            
            # Flush buffered data if any
            await self._flush_buffers()
            
        except Exception as e:
            logger.error(f"Failed to connect to TimescaleDB: {e}")
            self._connected = False
            raise
    
    async def disconnect(self) -> None:
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self._connected = False
            logger.info("Disconnected from TimescaleDB")
    
    async def write_kline(self, kline: Dict) -> None:
        """Write kline data to hypertable
        
        Schema:
            - timestamp (TIMESTAMPTZ, primary key)
            - symbol (TEXT)
            - timeframe (TEXT)
            - open, high, low, close (NUMERIC)
            - volume (NUMERIC)
        
        Args:
            kline: Kline data dictionary with keys: timestamp, symbol, timeframe, open, high, low, close, volume
        """
        if not self._connected or not self.pool:
            # Buffer data when connection is down
            self.kline_buffer.append(kline)
            logger.debug(f"Buffered kline (buffer size: {len(self.kline_buffer)})")
            
            # Emit warning if buffer is getting full
            if len(self.kline_buffer) >= self.buffer_size * 0.8:
                logger.warning(f"Kline buffer at 80% capacity: {len(self.kline_buffer)}/{self.buffer_size}")
            
            # Start reconnection if not already running
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())
            
            return
        
        try:
            # Convert timestamp to datetime
            if isinstance(kline['timestamp'], (int, float)):
                timestamp = datetime.fromtimestamp(kline['timestamp'] / 1000)  # Bybit uses milliseconds
            else:
                timestamp = kline['timestamp']
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO klines (timestamp, symbol, timeframe, open, high, low, close, volume)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (timestamp, symbol, timeframe) DO NOTHING
                    """,
                    timestamp,
                    kline['symbol'],
                    kline['timeframe'],
                    Decimal(str(kline['open'])),
                    Decimal(str(kline['high'])),
                    Decimal(str(kline['low'])),
                    Decimal(str(kline['close'])),
                    Decimal(str(kline['volume']))
                )
            
            logger.debug(f"Wrote kline: {kline['symbol']} {kline['timeframe']} @ {timestamp}")
            
        except Exception as e:
            logger.error(f"Failed to write kline: {e}")
            # Buffer on error
            self.kline_buffer.append(kline)
            self._connected = False
            
            # Start reconnection
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())
    
    async def write_trade(self, trade: Dict) -> None:
        """Write trade data to hypertable
        
        Schema:
            - timestamp (TIMESTAMPTZ, primary key)
            - symbol (TEXT)
            - trade_id (TEXT)
            - price (NUMERIC)
            - quantity (NUMERIC)
            - side (TEXT)
        
        Args:
            trade: Trade data dictionary
        """
        if not self._connected or not self.pool:
            self.trade_buffer.append(trade)
            logger.debug(f"Buffered trade (buffer size: {len(self.trade_buffer)})")
            
            if len(self.trade_buffer) >= self.buffer_size * 0.8:
                logger.warning(f"Trade buffer at 80% capacity: {len(self.trade_buffer)}/{self.buffer_size}")
            
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())
            
            return
        
        try:
            # Convert timestamp
            if isinstance(trade['timestamp'], (int, float)):
                timestamp = datetime.fromtimestamp(trade['timestamp'] / 1000)
            else:
                timestamp = trade['timestamp']
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO trades (timestamp, symbol, trade_id, price, quantity, side)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (timestamp, symbol, trade_id) DO NOTHING
                    """,
                    timestamp,
                    trade['symbol'],
                    trade['trade_id'],
                    Decimal(str(trade['price'])),
                    Decimal(str(trade['quantity'])),
                    trade['side']
                )
            
            logger.debug(f"Wrote trade: {trade['symbol']} {trade['side']} @ {trade['price']}")
            
        except Exception as e:
            logger.error(f"Failed to write trade: {e}")
            self.trade_buffer.append(trade)
            self._connected = False
            
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())
    
    async def write_orderbook(self, orderbook: Dict) -> None:
        """Write orderbook snapshot to hypertable
        
        Schema:
            - timestamp (TIMESTAMPTZ, primary key)
            - symbol (TEXT)
            - bids (JSONB)
            - asks (JSONB)
        
        Args:
            orderbook: Orderbook data dictionary
        """
        if not self._connected or not self.pool:
            self.orderbook_buffer.append(orderbook)
            logger.debug(f"Buffered orderbook (buffer size: {len(self.orderbook_buffer)})")
            
            if len(self.orderbook_buffer) >= self.buffer_size * 0.8:
                logger.warning(f"Orderbook buffer at 80% capacity: {len(self.orderbook_buffer)}/{self.buffer_size}")
            
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())
            
            return
        
        try:
            # Convert timestamp
            if isinstance(orderbook['timestamp'], (int, float)):
                timestamp = datetime.fromtimestamp(orderbook['timestamp'] / 1000)
            else:
                timestamp = orderbook['timestamp']
            
            # Convert bids/asks to JSONB
            bids_json = ujson.dumps(orderbook['bids'])
            asks_json = ujson.dumps(orderbook['asks'])
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO orderbooks (timestamp, symbol, bids, asks)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (timestamp, symbol) DO NOTHING
                    """,
                    timestamp,
                    orderbook['symbol'],
                    bids_json,
                    asks_json
                )
            
            logger.debug(f"Wrote orderbook: {orderbook['symbol']} @ {timestamp}")
            
        except Exception as e:
            logger.error(f"Failed to write orderbook: {e}")
            self.orderbook_buffer.append(orderbook)
            self._connected = False
            
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._reconnect())
    
    async def batch_write_klines(self, klines: List[Dict]) -> None:
        """Write multiple klines in a single transaction
        
        Args:
            klines: List of kline dictionaries
        """
        if not self._connected or not self.pool:
            for kline in klines:
                self.kline_buffer.append(kline)
            logger.debug(f"Buffered {len(klines)} klines")
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for kline in klines:
                        if isinstance(kline['timestamp'], (int, float)):
                            timestamp = datetime.fromtimestamp(kline['timestamp'] / 1000)
                        else:
                            timestamp = kline['timestamp']
                        
                        await conn.execute(
                            """
                            INSERT INTO klines (timestamp, symbol, timeframe, open, high, low, close, volume)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (timestamp, symbol, timeframe) DO NOTHING
                            """,
                            timestamp,
                            kline['symbol'],
                            kline['timeframe'],
                            Decimal(str(kline['open'])),
                            Decimal(str(kline['high'])),
                            Decimal(str(kline['low'])),
                            Decimal(str(kline['close'])),
                            Decimal(str(kline['volume']))
                        )
            
            logger.info(f"Batch wrote {len(klines)} klines")
            
        except Exception as e:
            logger.error(f"Failed to batch write klines: {e}")
            for kline in klines:
                self.kline_buffer.append(kline)
            self._connected = False
    
    async def _flush_buffers(self) -> None:
        """Flush all buffered data to database"""
        if not self._connected or not self.pool:
            return
        
        # Flush klines
        if self.kline_buffer:
            logger.info(f"Flushing {len(self.kline_buffer)} buffered klines")
            klines = list(self.kline_buffer)
            self.kline_buffer.clear()
            await self.batch_write_klines(klines)
        
        # Flush trades
        if self.trade_buffer:
            logger.info(f"Flushing {len(self.trade_buffer)} buffered trades")
            trades = list(self.trade_buffer)
            self.trade_buffer.clear()
            for trade in trades:
                await self.write_trade(trade)
        
        # Flush orderbooks
        if self.orderbook_buffer:
            logger.info(f"Flushing {len(self.orderbook_buffer)} buffered orderbooks")
            orderbooks = list(self.orderbook_buffer)
            self.orderbook_buffer.clear()
            for orderbook in orderbooks:
                await self.write_orderbook(orderbook)
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect to database with exponential backoff"""
        max_retries = 5
        retry_delays = [1, 2, 4, 8, 16]
        
        for attempt in range(max_retries):
            try:
                delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                logger.info(f"Reconnection attempt {attempt + 1}/{max_retries} in {delay}s")
                
                await asyncio.sleep(delay)
                
                # Close old pool if exists
                if self.pool:
                    await self.pool.close()
                
                # Create new pool
                await self.connect()
                
                logger.info("Database reconnection successful")
                return
                
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                
                if attempt == max_retries - 1:
                    logger.critical("Max reconnection attempts reached. Data will continue to buffer.")
    
    def get_buffer_status(self) -> Dict[str, int]:
        """Get current buffer sizes
        
        Returns:
            Dictionary with buffer sizes for each data type
        """
        return {
            'klines': len(self.kline_buffer),
            'trades': len(self.trade_buffer),
            'orderbooks': len(self.orderbook_buffer),
            'total': len(self.kline_buffer) + len(self.trade_buffer) + len(self.orderbook_buffer),
            'capacity': self.buffer_size
        }
    
    def is_connected(self) -> bool:
        """Check if database is connected
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected and self.pool is not None
