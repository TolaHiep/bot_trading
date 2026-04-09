"""
Backtesting Engine - Event-driven backtesting với realistic simulation

Provides event-driven architecture để test chiến lược trên historical data.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Callable, Any, Type
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event class"""
    timestamp: datetime
    event_type: str = ""


@dataclass
class KlineEvent(Event):
    """Kline data event"""
    symbol: str = ""
    timeframe: str = ""
    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    close: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    
    def __post_init__(self):
        self.event_type = "kline"


@dataclass
class TradeEvent(Event):
    """Trade data event"""
    symbol: str = ""
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    side: str = ""  # "Buy" or "Sell"
    
    def __post_init__(self):
        self.event_type = "trade"


@dataclass
class SignalEvent(Event):
    """Trading signal event"""
    symbol: str = ""
    signal_type: str = ""  # "BUY", "SELL", "NEUTRAL"
    confidence: int = 0
    reason: str = ""
    
    def __post_init__(self):
        self.event_type = "signal"


@dataclass
class OrderEvent(Event):
    """Order execution event"""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    order_type: str = ""
    
    def __post_init__(self):
        self.event_type = "order"


@dataclass
class FillEvent(Event):
    """Order fill event"""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: Decimal = Decimal("0")
    fill_price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    
    def __post_init__(self):
        self.event_type = "fill"


@dataclass
class BacktestResult:
    """Backtest execution result"""
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal
    final_balance: Decimal
    total_pnl: Decimal
    total_return: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    trades: List[Dict] = field(default_factory=list)
    equity_curve: List[Dict] = field(default_factory=list)
    execution_time: float = 0.0
    candles_processed: int = 0
    
    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate"""
        if self.total_trades == 0:
            return Decimal("0")
        return Decimal(self.winning_trades) / Decimal(self.total_trades) * Decimal("100")
    
    @property
    def candles_per_second(self) -> float:
        """Calculate processing speed"""
        if self.execution_time == 0:
            return 0.0
        return self.candles_processed / self.execution_time


class EventEngine:
    """
    Event-driven Backtesting Engine
    
    Features:
    - Asynchronous event processing
    - Handler registration per event type
    - Event queue management
    - Performance tracking
    """
    
    def __init__(self):
        """Initialize Event Engine"""
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.is_running = False
        self.events_processed = 0
        
        logger.info("EventEngine initialized")
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[Event], Any]
    ) -> None:
        """
        Register event handler
        
        Args:
            event_type: Type of event to handle
            handler: Async function to handle event
        """
        self.handlers[event_type].append(handler)
        logger.debug(f"Registered handler for {event_type}")
    
    async def emit(self, event: Event) -> None:
        """
        Emit event to queue
        
        Args:
            event: Event to emit
        """
        await self.event_queue.put(event)
    
    async def process_events(self) -> None:
        """Process events from queue"""
        self.is_running = True
        
        while self.is_running:
            try:
                # Get event with timeout
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=0.1
                )
                
                # Get handlers for this event type
                handlers = self.handlers.get(event.event_type, [])
                
                # Execute all handlers
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(
                            f"Error in handler for {event.event_type}: {e}",
                            exc_info=True
                        )
                
                self.events_processed += 1
                
            except asyncio.TimeoutError:
                # No events in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)
    
    async def stop(self) -> None:
        """Stop event processing"""
        self.is_running = False
        logger.info(f"EventEngine stopped. Processed {self.events_processed} events")
    
    def get_stats(self) -> Dict:
        """Get engine statistics"""
        return {
            "events_processed": self.events_processed,
            "handlers_registered": sum(len(h) for h in self.handlers.values()),
            "queue_size": self.event_queue.qsize()
        }


class BacktestRunner:
    """
    Backtest Runner - Orchestrates backtest execution
    
    Features:
    - Event-driven architecture
    - Component initialization
    - Result collection
    - Performance tracking
    """
    
    def __init__(
        self,
        initial_balance: Decimal,
        commission_rate: Decimal = Decimal("0.0006")
    ):
        """
        Initialize Backtest Runner
        
        Args:
            initial_balance: Starting balance
            commission_rate: Commission rate (default: 0.06%)
        """
        self.initial_balance = initial_balance
        self.commission_rate = commission_rate
        
        # Components
        self.event_engine = EventEngine()
        
        # State
        self.current_balance = initial_balance
        self.positions: Dict[str, Any] = {}
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        
        # Stats
        self.start_time: Optional[float] = None
        self.candles_processed = 0
        
        logger.info(
            f"BacktestRunner initialized with balance: {initial_balance}, "
            f"commission: {commission_rate*100:.2f}%"
        )
    
    def register_handlers(self) -> None:
        """Register event handlers"""
        # Register handlers for different event types
        self.event_engine.register_handler("kline", self._handle_kline)
        self.event_engine.register_handler("signal", self._handle_signal)
        self.event_engine.register_handler("order", self._handle_order)
        self.event_engine.register_handler("fill", self._handle_fill)
        
        logger.info("Event handlers registered")
    
    async def _handle_kline(self, event: KlineEvent) -> None:
        """Handle kline event"""
        self.candles_processed += 1
        
        # Update equity curve
        self.equity_curve.append({
            "timestamp": event.timestamp,
            "balance": float(self.current_balance),
            "equity": float(self.current_balance)  # Simplified
        })
    
    async def _handle_signal(self, event: SignalEvent) -> None:
        """Handle signal event"""
        logger.debug(
            f"Signal: {event.signal_type} {event.symbol} "
            f"(confidence: {event.confidence})"
        )
    
    async def _handle_order(self, event: OrderEvent) -> None:
        """Handle order event"""
        logger.debug(f"Order: {event.side} {event.quantity} {event.symbol}")
    
    async def _handle_fill(self, event: FillEvent) -> None:
        """Handle fill event"""
        # Record trade
        trade = {
            "timestamp": event.timestamp.isoformat(),
            "symbol": event.symbol,
            "side": event.side,
            "quantity": float(event.quantity),
            "price": float(event.fill_price),
            "commission": float(event.commission),
            "slippage": float(event.slippage)
        }
        
        self.trades.append(trade)
        
        # Update balance
        position_value = event.fill_price * event.quantity
        if event.side == "BUY":
            self.current_balance -= (position_value + event.commission)
        else:
            self.current_balance += (position_value - event.commission)
        
        logger.debug(
            f"Fill: {event.side} {event.quantity} {event.symbol} @ {event.fill_price}"
        )
    
    async def run(
        self,
        start_date: datetime,
        end_date: datetime,
        data_replayer: 'HistoricalDataReplayer'
    ) -> BacktestResult:
        """
        Run backtest
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            data_replayer: Historical data replayer
        
        Returns:
            BacktestResult with trades and metrics
        """
        logger.info(f"Starting backtest: {start_date} to {end_date}")
        
        # Register handlers
        self.register_handlers()
        
        # Start event processing
        self.start_time = time.time()
        event_processor = asyncio.create_task(self.event_engine.process_events())
        
        try:
            # Replay historical data
            await data_replayer.replay(self.event_engine, start_date, end_date)
            
            # Wait for all events to be processed
            await asyncio.sleep(0.5)
            
        finally:
            # Stop event engine
            await self.event_engine.stop()
            event_processor.cancel()
            
            try:
                await event_processor
            except asyncio.CancelledError:
                pass
        
        # Calculate results
        execution_time = time.time() - self.start_time
        total_pnl = self.current_balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * Decimal("100")
        
        # Count winning/losing trades
        winning_trades = 0
        losing_trades = 0
        # Simplified - would need to track P&L per trade
        
        result = BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_balance=self.initial_balance,
            final_balance=self.current_balance,
            total_pnl=total_pnl,
            total_return=total_return,
            total_trades=len(self.trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            trades=self.trades,
            equity_curve=self.equity_curve,
            execution_time=execution_time,
            candles_processed=self.candles_processed
        )
        
        logger.info(
            f"Backtest complete: {result.total_trades} trades, "
            f"P&L: {result.total_pnl:.2f}, "
            f"Return: {result.total_return:.2f}%, "
            f"Speed: {result.candles_per_second:.0f} candles/s"
        )
        
        return result
    
    def export_trades_csv(self, filename: str) -> None:
        """Export trades to CSV"""
        import csv
        
        if not self.trades:
            logger.warning("No trades to export")
            return
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.trades[0].keys())
            writer.writeheader()
            writer.writerows(self.trades)
        
        logger.info(f"Trades exported to {filename}")
