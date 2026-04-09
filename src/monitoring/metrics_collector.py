"""
Metrics Collector - Thu thập và tổng hợp metrics từ trading system

Cung cấp metrics cho dashboard và monitoring.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System health metrics"""
    api_status: str  # "healthy", "degraded", "down"
    db_status: str
    last_tick_time: Optional[datetime]
    error_rate: Decimal  # Percentage
    uptime_seconds: int
    total_requests: int
    failed_requests: int
    
    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy"""
        return (
            self.api_status == "healthy" and
            self.db_status == "healthy" and
            self.error_rate < Decimal("5.0")
        )


@dataclass
class TradingMetrics:
    """Trading performance metrics"""
    current_balance: Decimal
    initial_balance: Decimal
    equity: Decimal
    total_pnl: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    open_positions: int
    
    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate"""
        if self.total_trades == 0:
            return Decimal("0")
        return Decimal(self.winning_trades) / Decimal(self.total_trades) * Decimal("100")
    
    @property
    def total_return(self) -> Decimal:
        """Calculate total return percentage"""
        if self.initial_balance == 0:
            return Decimal("0")
        return (self.total_pnl / self.initial_balance) * Decimal("100")


@dataclass
class SignalMetrics:
    """Recent signal metrics"""
    timestamp: datetime
    symbol: str
    signal_type: str  # "BUY", "SELL", "NEUTRAL"
    confidence: int
    wyckoff_phase: str
    order_flow_delta: Decimal


class MetricsCollector:
    """
    Metrics Collector
    
    Thu thập và lưu trữ metrics từ trading system để hiển thị trên dashboard.
    """
    
    def __init__(self, max_signals: int = 100):
        """
        Initialize Metrics Collector
        
        Args:
            max_signals: Maximum number of recent signals to keep
        """
        self.max_signals = max_signals
        
        # Metrics storage
        self.system_metrics: Optional[SystemMetrics] = None
        self.trading_metrics: Optional[TradingMetrics] = None
        self.recent_signals: deque = deque(maxlen=max_signals)
        self.equity_history: List[Dict] = []
        
        # Error tracking
        self.error_log: deque = deque(maxlen=100)
        
        logger.info("MetricsCollector initialized")
    
    def update_system_metrics(
        self,
        api_status: str,
        db_status: str,
        last_tick_time: Optional[datetime],
        error_rate: Decimal,
        uptime_seconds: int,
        total_requests: int,
        failed_requests: int
    ) -> None:
        """Update system health metrics"""
        self.system_metrics = SystemMetrics(
            api_status=api_status,
            db_status=db_status,
            last_tick_time=last_tick_time,
            error_rate=error_rate,
            uptime_seconds=uptime_seconds,
            total_requests=total_requests,
            failed_requests=failed_requests
        )
    
    def update_trading_metrics(
        self,
        current_balance: Decimal,
        initial_balance: Decimal,
        equity: Decimal,
        total_pnl: Decimal,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        open_positions: int
    ) -> None:
        """Update trading performance metrics"""
        self.trading_metrics = TradingMetrics(
            current_balance=current_balance,
            initial_balance=initial_balance,
            equity=equity,
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            open_positions=open_positions
        )
        
        # Record equity history
        self.equity_history.append({
            "timestamp": datetime.now(),
            "equity": float(equity),
            "balance": float(current_balance),
            "pnl": float(total_pnl)
        })
    
    def add_signal(
        self,
        symbol: str,
        signal_type: str,
        confidence: int,
        wyckoff_phase: str,
        order_flow_delta: Decimal
    ) -> None:
        """Add new signal to recent signals"""
        signal = SignalMetrics(
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            wyckoff_phase=wyckoff_phase,
            order_flow_delta=order_flow_delta
        )
        
        self.recent_signals.append(signal)
        
        logger.info(
            f"Signal recorded: {signal_type} {symbol} "
            f"(confidence: {confidence}, phase: {wyckoff_phase})"
        )
    
    def log_error(self, error_type: str, error_message: str) -> None:
        """Log error for monitoring"""
        self.error_log.append({
            "timestamp": datetime.now(),
            "type": error_type,
            "message": error_message
        })
    
    def get_system_status(self) -> Dict:
        """Get current system status"""
        if not self.system_metrics:
            return {"status": "unknown"}
        
        return {
            "status": "healthy" if self.system_metrics.is_healthy else "degraded",
            "api_status": self.system_metrics.api_status,
            "db_status": self.system_metrics.db_status,
            "last_tick": self.system_metrics.last_tick_time.isoformat() if self.system_metrics.last_tick_time else None,
            "error_rate": float(self.system_metrics.error_rate),
            "uptime_hours": self.system_metrics.uptime_seconds / 3600,
            "total_requests": self.system_metrics.total_requests,
            "failed_requests": self.system_metrics.failed_requests
        }
    
    def get_trading_summary(self) -> Dict:
        """Get trading performance summary"""
        if not self.trading_metrics:
            return {"status": "no_data"}
        
        return {
            "current_balance": float(self.trading_metrics.current_balance),
            "initial_balance": float(self.trading_metrics.initial_balance),
            "equity": float(self.trading_metrics.equity),
            "total_pnl": float(self.trading_metrics.total_pnl),
            "realized_pnl": float(self.trading_metrics.realized_pnl),
            "unrealized_pnl": float(self.trading_metrics.unrealized_pnl),
            "total_return": float(self.trading_metrics.total_return),
            "total_trades": self.trading_metrics.total_trades,
            "winning_trades": self.trading_metrics.winning_trades,
            "losing_trades": self.trading_metrics.losing_trades,
            "win_rate": float(self.trading_metrics.win_rate),
            "open_positions": self.trading_metrics.open_positions
        }
    
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Get recent signals"""
        signals = list(self.recent_signals)[-limit:]
        
        return [
            {
                "timestamp": signal.timestamp.isoformat(),
                "symbol": signal.symbol,
                "signal_type": signal.signal_type,
                "confidence": signal.confidence,
                "wyckoff_phase": signal.wyckoff_phase,
                "order_flow_delta": float(signal.order_flow_delta)
            }
            for signal in signals
        ]
    
    def get_equity_curve(self, days: int = 30) -> List[Dict]:
        """Get equity curve for last N days"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        return [
            point for point in self.equity_history
            if point["timestamp"] >= cutoff_time
        ]
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """Get recent errors"""
        errors = list(self.error_log)[-limit:]
        
        return [
            {
                "timestamp": error["timestamp"].isoformat(),
                "type": error["type"],
                "message": error["message"]
            }
            for error in errors
        ]
