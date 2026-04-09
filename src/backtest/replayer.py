"""
Historical Data Replayer - Replay historical data chronologically

Provides chronological data replay từ TimescaleDB để prevent look-ahead bias.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List
import asyncpg

from src.backtest.engine import EventEngine, KlineEvent, TradeEvent

logger = logging.getLogger(__name__)


class HistoricalDataReplayer:
    """
    Replay historical data chronologically
    
    Features:
    - Load data từ TimescaleDB
    - Chronological ordering (prevent look-ahead bias)
    - Multi-timeframe support
    - Performance optimization (>= 1000 candles/second)
    """
    
    def __init__(
        self,
        db_connection_string: str,
        symbol: str,
        timeframes: List[str] = None
    ):
        """
        Initialize Historical Data Replayer
        
        Args:
            db_connection_string: PostgreSQL connection string
            symbol: Trading symbol (e.g., "BTCUSDT")
            timeframes: List of timeframes to replay (default: ["1m", "5m", "15m", "1h"])
        """
        self.db_connection_string = db_connection_string
        self.symbol = symbol
        self.timeframes = timeframes or ["1m", "5m", "15m", "1h"]
        
        self.db_pool: Optional[asyncpg.Pool] = None
        self.current_timestamp: Optional[datetime] = None
        
        logger.info(
            f"HistoricalDataReplayer initialized for {symbol}, "
            f"timeframes: {self.timeframes}"
        )
    
    async def connect(self) -> None:
        """Connect to TimescaleDB"""
        try:
            self.db_pool = await asyncpg.create_pool(
                self.db_connection_string,
                min_size=1,
                max_size=5
            )
            logger.info("Connected to TimescaleDB")
        except Exception as e:
            logger.error(f"Failed to connect to TimescaleDB: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from TimescaleDB"""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Disconnected from TimescaleDB")
    
    async def load_klines(
        self,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> List[Dict]:
        """
        Load klines from TimescaleDB
        
        Args:
            start_date: Start date
            end_date: End date
            timeframe: Timeframe (e.g., "1m")
        
        Returns:
            List of kline records sorted by timestamp
        """
        query = """
            SELECT 
                timestamp,
                symbol,
                timeframe,
                open,
                high,
                low,
                close,
                volume
            FROM klines
            WHERE symbol = $1
                AND timeframe = $2
                AND timestamp >= $3
                AND timestamp <= $4
            ORDER BY timestamp ASC
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                self.symbol,
                timeframe,
                start_date,
                end_date
            )
        
        klines = [dict(row) for row in rows]
        logger.info(
            f"Loaded {len(klines)} klines for {timeframe} "
            f"from {start_date} to {end_date}"
        )
        
        return klines
    
    async def load_trades(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Load trades from TimescaleDB
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of trade records sorted by timestamp
        """
        query = """
            SELECT 
                timestamp,
                symbol,
                price,
                quantity,
                side,
                trade_id
            FROM trades
            WHERE symbol = $1
                AND timestamp >= $2
                AND timestamp <= $3
            ORDER BY timestamp ASC
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                self.symbol,
                start_date,
                end_date
            )
        
        trades = [dict(row) for row in rows]
        logger.info(
            f"Loaded {len(trades)} trades from {start_date} to {end_date}"
        )
        
        return trades
    
    async def replay(
        self,
        event_engine: EventEngine,
        start_date: datetime,
        end_date: datetime,
        include_trades: bool = False
    ) -> None:
        """
        Replay historical data chronologically
        
        Args:
            event_engine: Event engine to emit events
            start_date: Backtest start date
            end_date: Backtest end date
            include_trades: Whether to include trade data (default: False)
        
        Algorithm:
            1. Load all klines for all timeframes
            2. Optionally load trades
            3. Merge and sort all data by timestamp
            4. Emit events chronologically
        
        Performance: >= 1000 candles/second
        """
        logger.info(f"Starting replay: {start_date} to {end_date}")
        
        # Connect to database
        if not self.db_pool:
            await self.connect()
        
        # Load klines for all timeframes
        all_klines = []
        for timeframe in self.timeframes:
            klines = await self.load_klines(start_date, end_date, timeframe)
            all_klines.extend(klines)
        
        # Optionally load trades
        all_trades = []
        if include_trades:
            all_trades = await self.load_trades(start_date, end_date)
        
        # Merge and sort by timestamp
        all_data = []
        
        for kline in all_klines:
            all_data.append({
                "type": "kline",
                "timestamp": kline["timestamp"],
                "data": kline
            })
        
        for trade in all_trades:
            all_data.append({
                "type": "trade",
                "timestamp": trade["timestamp"],
                "data": trade
            })
        
        # Sort chronologically (CRITICAL: prevent look-ahead bias)
        all_data.sort(key=lambda x: x["timestamp"])
        
        logger.info(
            f"Replaying {len(all_data)} data points "
            f"({len(all_klines)} klines, {len(all_trades)} trades)"
        )
        
        # Emit events chronologically
        events_emitted = 0
        
        for item in all_data:
            self.current_timestamp = item["timestamp"]
            
            if item["type"] == "kline":
                event = self._create_kline_event(item["data"])
                await event_engine.emit(event)
            
            elif item["type"] == "trade":
                event = self._create_trade_event(item["data"])
                await event_engine.emit(event)
            
            events_emitted += 1
            
            # Yield control every 100 events for responsiveness
            if events_emitted % 100 == 0:
                await asyncio.sleep(0)
        
        logger.info(f"Replay complete: {events_emitted} events emitted")
    
    def _create_kline_event(self, kline_data: Dict) -> KlineEvent:
        """Create KlineEvent from database record"""
        return KlineEvent(
            timestamp=kline_data["timestamp"],
            symbol=kline_data["symbol"],
            timeframe=kline_data["timeframe"],
            open=Decimal(str(kline_data["open"])),
            high=Decimal(str(kline_data["high"])),
            low=Decimal(str(kline_data["low"])),
            close=Decimal(str(kline_data["close"])),
            volume=Decimal(str(kline_data["volume"]))
        )
    
    def _create_trade_event(self, trade_data: Dict) -> TradeEvent:
        """Create TradeEvent from database record"""
        return TradeEvent(
            timestamp=trade_data["timestamp"],
            symbol=trade_data["symbol"],
            price=Decimal(str(trade_data["price"])),
            quantity=Decimal(str(trade_data["quantity"])),
            side=trade_data["side"]
        )
    
    def get_current_timestamp(self) -> Optional[datetime]:
        """Get current replay timestamp"""
        return self.current_timestamp
