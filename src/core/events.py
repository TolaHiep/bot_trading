"""
Event types for the automated trading system.

All modules communicate through these events using the event bus.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


class OrderSide(Enum):
    """Order side types."""
    BUY = "BUY"
    SELL = "SELL"


class OrderState(Enum):
    """Order state types."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Event:
    """Base event class for all system events."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = field(init=False)

    def __post_init__(self):
        """Set event_type based on class name."""
        if not hasattr(self, 'event_type') or self.event_type is None:
            self.event_type = self.__class__.__name__


@dataclass
class MarketDataEvent(Event):
    """Event for new market data (kline or trade)."""
    symbol: str = ""
    timeframe: str = ""
    data_type: str = ""  # "kline" or "trade"
    
    # Kline data
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    
    # Trade data
    price: Optional[float] = None
    quantity: Optional[float] = None
    side: Optional[str] = None


@dataclass
class SignalGeneratedEvent(Event):
    """Event for a generated trading signal."""
    symbol: str = ""
    signal_type: SignalType = SignalType.NEUTRAL
    confidence: float = 0.0  # 0-100
    price: float = 0.0
    reason: str = ""
    
    # Alpha factors
    wyckoff_phase: str = ""
    delta: float = 0.0
    breakout_direction: Optional[str] = None
    volume_ratio: float = 0.0
    trend_aligned: bool = False
    momentum_score: float = 0.0


@dataclass
class OrderPlacedEvent(Event):
    """Event for an order placed on the exchange."""
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: Decimal = Decimal("0")
    price: Optional[Decimal] = None
    order_type: str = "LIMIT"  # LIMIT or MARKET
    state: OrderState = OrderState.PENDING


@dataclass
class OrderFilledEvent(Event):
    """Event for an order filled by the exchange."""
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    filled_qty: Decimal = Decimal("0")
    avg_fill_price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    exchange_order_id: Optional[str] = None


@dataclass
class PositionOpenedEvent(Event):
    """Event for a new position opened."""
    position_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    entry_price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    stop_loss: Optional[Decimal] = None
    trailing_stop: Optional[Decimal] = None


@dataclass
class PositionClosedEvent(Event):
    """Event for a position closed."""
    position_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    entry_price: Decimal = Decimal("0")
    exit_price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    exit_reason: str = ""


@dataclass
class KillSwitchActivatedEvent(Event):
    """Event for kill switch activation."""
    reason: str = ""
    daily_drawdown: Optional[float] = None
    consecutive_losses: Optional[int] = None
    api_error_rate: Optional[float] = None
    price_volatility: Optional[float] = None


@dataclass
class SystemHealthEvent(Event):
    """Event for periodic system health check."""
    uptime_seconds: int = 0
    signals_processed: int = 0
    orders_placed: int = 0
    errors_count: int = 0
    error_rate: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_pct: float = 0.0
