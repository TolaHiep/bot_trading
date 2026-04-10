"""
Data Models for Multi-Symbol Trading

Defines dataclasses for symbol information, metrics, and position summaries.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime


@dataclass
class SymbolInfo:
    """Information about a trading symbol
    
    Attributes:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        status: Trading status ("Trading", "Closed", etc.)
        base_currency: Base currency (e.g., "BTC")
        quote_currency: Quote currency (e.g., "USDT")
        volume_24h: 24-hour trading volume in USD
        price: Current price
        spread_pct: Bid-ask spread percentage
        listing_time: When the symbol was listed
        price_scale: Number of decimal places for price
        qty_scale: Number of decimal places for quantity
        min_order_qty: Minimum order quantity
        max_order_qty: Maximum order quantity
        min_order_value: Minimum order value in quote currency
    """
    symbol: str
    status: str
    base_currency: str
    quote_currency: str
    volume_24h: float
    price: float
    spread_pct: float
    listing_time: Optional[datetime] = None
    price_scale: int = 2
    qty_scale: int = 4
    min_order_qty: float = 0.0
    max_order_qty: float = 0.0
    min_order_value: float = 0.0
    
    def __post_init__(self):
        """Validate symbol info after initialization"""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        if self.volume_24h < 0:
            raise ValueError("Volume cannot be negative")
        if self.price <= 0:
            raise ValueError("Price must be positive")
        if self.spread_pct < 0:
            raise ValueError("Spread percentage cannot be negative")


@dataclass
class PositionSummary:
    """Summary of an open position
    
    Attributes:
        symbol: Trading pair symbol
        side: Position side ("BUY" or "SELL")
        quantity: Position quantity
        entry_price: Entry price
        current_price: Current market price
        entry_time: When position was opened
        unrealized_pnl: Unrealized profit/loss
        unrealized_pnl_pct: Unrealized P&L percentage
        position_value: Current position value (quantity * current_price)
    """
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    entry_time: datetime
    unrealized_pnl: Decimal = Decimal("0")
    unrealized_pnl_pct: float = 0.0
    position_value: Decimal = Decimal("0")
    
    def __post_init__(self):
        """Calculate derived fields after initialization"""
        # Calculate position value
        self.position_value = self.quantity * self.current_price
        
        # Calculate unrealized P&L
        if self.side == "BUY":
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity
        else:  # SELL
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.quantity
        
        # Calculate P&L percentage
        if self.entry_price > 0:
            entry_value = self.quantity * self.entry_price
            if entry_value > 0:
                self.unrealized_pnl_pct = float(self.unrealized_pnl / entry_value * 100)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": float(self.quantity),
            "entry_price": float(self.entry_price),
            "current_price": float(self.current_price),
            "entry_time": self.entry_time.isoformat(),
            "unrealized_pnl": float(self.unrealized_pnl),
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "position_value": float(self.position_value)
        }


@dataclass
class MultiSymbolMetrics:
    """Metrics for multi-symbol trading
    
    Attributes:
        timestamp: Metrics timestamp
        monitored_symbols: Number of symbols being monitored
        active_symbols: List of active symbol names
        open_positions: Number of open positions
        total_equity: Total portfolio equity
        available_balance: Available balance for new positions
        total_exposure: Total exposure (sum of position values)
        exposure_pct: Exposure as percentage of equity
        positions: List of position summaries
        total_unrealized_pnl: Total unrealized P&L across all positions
        total_realized_pnl: Total realized P&L
        win_rate: Win rate percentage
        total_trades: Total number of trades
    """
    timestamp: datetime
    monitored_symbols: int
    active_symbols: List[str]
    open_positions: int
    total_equity: Decimal
    available_balance: Decimal
    total_exposure: Decimal
    exposure_pct: float
    positions: List[PositionSummary] = field(default_factory=list)
    total_unrealized_pnl: Decimal = Decimal("0")
    total_realized_pnl: Decimal = Decimal("0")
    win_rate: float = 0.0
    total_trades: int = 0
    
    def __post_init__(self):
        """Calculate derived metrics after initialization"""
        # Calculate total unrealized P&L from positions
        self.total_unrealized_pnl = sum(
            pos.unrealized_pnl for pos in self.positions
        )
        
        # Calculate exposure percentage
        if self.total_equity > 0:
            self.exposure_pct = float(self.total_exposure / self.total_equity * 100)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "monitored_symbols": self.monitored_symbols,
            "active_symbols": self.active_symbols,
            "open_positions": self.open_positions,
            "total_equity": float(self.total_equity),
            "available_balance": float(self.available_balance),
            "total_exposure": float(self.total_exposure),
            "exposure_pct": self.exposure_pct,
            "positions": [pos.to_dict() for pos in self.positions],
            "total_unrealized_pnl": float(self.total_unrealized_pnl),
            "total_realized_pnl": float(self.total_realized_pnl),
            "win_rate": self.win_rate,
            "total_trades": self.total_trades
        }
    
    def get_position_by_symbol(self, symbol: str) -> Optional[PositionSummary]:
        """Get position summary for a specific symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            PositionSummary if found, None otherwise
        """
        for pos in self.positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    def get_top_performers(self, limit: int = 5) -> List[PositionSummary]:
        """Get top performing positions by unrealized P&L
        
        Args:
            limit: Maximum number of positions to return
            
        Returns:
            List of top performing positions
        """
        sorted_positions = sorted(
            self.positions,
            key=lambda p: p.unrealized_pnl,
            reverse=True
        )
        return sorted_positions[:limit]
    
    def get_worst_performers(self, limit: int = 5) -> List[PositionSummary]:
        """Get worst performing positions by unrealized P&L
        
        Args:
            limit: Maximum number of positions to return
            
        Returns:
            List of worst performing positions
        """
        sorted_positions = sorted(
            self.positions,
            key=lambda p: p.unrealized_pnl
        )
        return sorted_positions[:limit]


@dataclass
class SymbolMetrics:
    """Metrics for a single symbol
    
    Attributes:
        symbol: Trading pair symbol
        current_price: Current market price
        volume_24h: 24-hour trading volume
        price_change_24h_pct: 24-hour price change percentage
        high_24h: 24-hour high price
        low_24h: 24-hour low price
        last_signal_time: Last time a signal was generated
        last_signal_type: Last signal type ("BUY", "SELL", "NEUTRAL")
        signals_generated: Total signals generated for this symbol
        has_open_position: Whether there's an open position
        position_side: Position side if open ("BUY" or "SELL")
        position_pnl: Position P&L if open
    """
    symbol: str
    current_price: float
    volume_24h: float
    price_change_24h_pct: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    last_signal_time: Optional[datetime] = None
    last_signal_type: Optional[str] = None
    signals_generated: int = 0
    has_open_position: bool = False
    position_side: Optional[str] = None
    position_pnl: Optional[Decimal] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "volume_24h": self.volume_24h,
            "price_change_24h_pct": self.price_change_24h_pct,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "last_signal_time": self.last_signal_time.isoformat() if self.last_signal_time else None,
            "last_signal_type": self.last_signal_type,
            "signals_generated": self.signals_generated,
            "has_open_position": self.has_open_position,
            "position_side": self.position_side,
            "position_pnl": float(self.position_pnl) if self.position_pnl else None
        }
