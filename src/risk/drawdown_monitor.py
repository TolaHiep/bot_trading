"""Drawdown Monitor

Tracks account drawdown metrics.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DrawdownMetrics:
    """Drawdown metrics"""
    current_drawdown: float
    max_drawdown: float
    peak_balance: float
    current_balance: float
    daily_drawdown: float
    daily_starting_balance: float
    underwater_since: Optional[datetime] = None


class DrawdownMonitor:
    """Monitor account drawdown"""
    
    def __init__(self, initial_balance: float):
        """Initialize drawdown monitor"""
        self.initial_balance = initial_balance
        self.peak_balance = initial_balance
        self.current_balance = initial_balance
        self.max_drawdown = 0.0
        self.underwater_since: Optional[datetime] = None
        
        # Daily tracking
        self.current_date = date.today()
        self.daily_starting_balance = initial_balance
        
    def update_balance(self, new_balance: float):
        """Update balance and calculate drawdown"""
        self.current_balance = new_balance
        
        # Check if new day
        today = date.today()
        if today != self.current_date:
            self.current_date = today
            self.daily_starting_balance = new_balance
            logger.info(f"New trading day, starting balance: ${new_balance:.2f}")
        
        # Update peak
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
            self.underwater_since = None
        elif self.underwater_since is None and new_balance < self.peak_balance:
            self.underwater_since = datetime.now()
        
        # Calculate drawdown
        current_dd = self._calculate_drawdown(new_balance, self.peak_balance)
        if current_dd > self.max_drawdown:
            self.max_drawdown = current_dd
            
    def _calculate_drawdown(self, current: float, peak: float) -> float:
        """Calculate drawdown percentage"""
        if peak <= 0:
            return 0.0
        return (peak - current) / peak
        
    def get_current_drawdown(self) -> float:
        """Get current drawdown"""
        return self._calculate_drawdown(self.current_balance, self.peak_balance)
        
    def get_daily_drawdown(self) -> float:
        """Get daily drawdown"""
        return self._calculate_drawdown(self.current_balance, self.daily_starting_balance)
        
    def get_metrics(self) -> DrawdownMetrics:
        """Get all drawdown metrics"""
        return DrawdownMetrics(
            current_drawdown=self.get_current_drawdown(),
            max_drawdown=self.max_drawdown,
            peak_balance=self.peak_balance,
            current_balance=self.current_balance,
            daily_drawdown=self.get_daily_drawdown(),
            daily_starting_balance=self.daily_starting_balance,
            underwater_since=self.underwater_since
        )
        
    def reset_daily(self):
        """Reset daily metrics"""
        self.daily_starting_balance = self.current_balance
        self.current_date = date.today()
