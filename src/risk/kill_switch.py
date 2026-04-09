"""Kill Switch Mechanism

This module implements emergency kill switch that stops all trading
when dangerous conditions are detected.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)


class KillSwitchReason(Enum):
    """Kill switch activation reasons"""
    DAILY_DRAWDOWN = "DAILY_DRAWDOWN"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    API_ERROR_RATE = "API_ERROR_RATE"
    ABNORMAL_PRICE_MOVEMENT = "ABNORMAL_PRICE_MOVEMENT"
    MANUAL = "MANUAL"


@dataclass
class KillSwitchConfig:
    """Kill switch configuration"""
    max_daily_drawdown: float = 0.05  # 5%
    max_consecutive_losses: int = 5
    max_api_error_rate: float = 0.20  # 20%
    api_error_window: int = 60  # seconds
    max_price_movement: float = 0.10  # 10%
    price_movement_window: int = 60  # seconds


@dataclass
class SystemState:
    """System state snapshot"""
    timestamp: datetime
    balance: float
    open_positions: int
    pending_orders: int
    daily_pnl: float
    daily_drawdown: float
    consecutive_losses: int
    api_error_rate: float
    recent_errors: List[str] = field(default_factory=list)


class KillSwitch:
    """Emergency kill switch for trading system"""
    
    def __init__(
        self,
        config: KillSwitchConfig,
        telegram_bot: Optional[object] = None
    ):
        """Initialize kill switch
        
        Args:
            config: Kill switch configuration
            telegram_bot: Telegram bot for alerts (optional)
        """
        self.config = config
        self.telegram_bot = telegram_bot
        
        # State
        self._activated = False
        self._activation_reason: Optional[KillSwitchReason] = None
        self._activation_time: Optional[datetime] = None
        self._system_state: Optional[SystemState] = None
        
        # Callbacks
        self._on_activated: Optional[Callable] = None
        
        # Monitoring data
        self._api_errors: List[datetime] = []
        self._price_history: List[tuple[datetime, float]] = []
        
    def set_callback(self, on_activated: Callable):
        """Set activation callback
        
        Args:
            on_activated: Callback function called when kill switch activates
        """
        self._on_activated = on_activated
        
    @property
    def is_activated(self) -> bool:
        """Check if kill switch is activated"""
        return self._activated
        
    @property
    def activation_reason(self) -> Optional[KillSwitchReason]:
        """Get activation reason"""
        return self._activation_reason
        
    async def check_daily_drawdown(
        self,
        current_balance: float,
        starting_balance: float
    ) -> bool:
        """Check daily drawdown threshold
        
        Args:
            current_balance: Current account balance
            starting_balance: Starting balance for the day
            
        Returns:
            True if threshold exceeded
        """
        if starting_balance <= 0:
            return False
            
        drawdown = (starting_balance - current_balance) / starting_balance
        
        if drawdown > self.config.max_daily_drawdown:
            logger.critical(
                f"Daily drawdown {drawdown*100:.2f}% exceeds threshold "
                f"{self.config.max_daily_drawdown*100:.2f}%"
            )
            
            await self._activate(
                reason=KillSwitchReason.DAILY_DRAWDOWN,
                system_state=SystemState(
                    timestamp=datetime.now(),
                    balance=current_balance,
                    open_positions=0,
                    pending_orders=0,
                    daily_pnl=current_balance - starting_balance,
                    daily_drawdown=drawdown,
                    consecutive_losses=0,
                    api_error_rate=0.0
                )
            )
            return True
            
        return False
        
    async def check_consecutive_losses(
        self,
        consecutive_losses: int
    ) -> bool:
        """Check consecutive losses threshold
        
        Args:
            consecutive_losses: Number of consecutive losing trades
            
        Returns:
            True if threshold exceeded
        """
        if consecutive_losses >= self.config.max_consecutive_losses:
            logger.critical(
                f"Consecutive losses {consecutive_losses} exceeds threshold "
                f"{self.config.max_consecutive_losses}"
            )
            
            await self._activate(
                reason=KillSwitchReason.CONSECUTIVE_LOSSES,
                system_state=SystemState(
                    timestamp=datetime.now(),
                    balance=0.0,
                    open_positions=0,
                    pending_orders=0,
                    daily_pnl=0.0,
                    daily_drawdown=0.0,
                    consecutive_losses=consecutive_losses,
                    api_error_rate=0.0
                )
            )
            return True
            
        return False
        
    def record_api_error(self, error_message: str):
        """Record API error for rate calculation
        
        Args:
            error_message: Error message
        """
        now = datetime.now()
        self._api_errors.append(now)
        
        # Clean old errors outside window
        cutoff = now.timestamp() - self.config.api_error_window
        self._api_errors = [
            t for t in self._api_errors 
            if t.timestamp() > cutoff
        ]
        
    async def check_api_error_rate(
        self,
        total_requests: int
    ) -> bool:
        """Check API error rate threshold
        
        Args:
            total_requests: Total API requests in window
            
        Returns:
            True if threshold exceeded
        """
        if total_requests == 0:
            return False
            
        error_count = len(self._api_errors)
        error_rate = error_count / total_requests
        
        if error_rate > self.config.max_api_error_rate:
            logger.critical(
                f"API error rate {error_rate*100:.2f}% exceeds threshold "
                f"{self.config.max_api_error_rate*100:.2f}% "
                f"({error_count}/{total_requests} errors)"
            )
            
            await self._activate(
                reason=KillSwitchReason.API_ERROR_RATE,
                system_state=SystemState(
                    timestamp=datetime.now(),
                    balance=0.0,
                    open_positions=0,
                    pending_orders=0,
                    daily_pnl=0.0,
                    daily_drawdown=0.0,
                    consecutive_losses=0,
                    api_error_rate=error_rate,
                    recent_errors=[str(t) for t in self._api_errors[-5:]]
                )
            )
            return True
            
        return False
        
    def record_price(self, price: float):
        """Record price for movement detection
        
        Args:
            price: Current price
        """
        now = datetime.now()
        self._price_history.append((now, price))
        
        # Clean old prices outside window
        cutoff = now.timestamp() - self.config.price_movement_window
        self._price_history = [
            (t, p) for t, p in self._price_history 
            if t.timestamp() > cutoff
        ]
        
    async def check_price_movement(self) -> bool:
        """Check abnormal price movement
        
        Returns:
            True if abnormal movement detected
        """
        if len(self._price_history) < 2:
            return False
            
        # Get oldest and newest prices in window
        oldest_price = self._price_history[0][1]
        newest_price = self._price_history[-1][1]
        
        # Calculate movement
        movement = abs(newest_price - oldest_price) / oldest_price
        
        if movement > self.config.max_price_movement:
            logger.critical(
                f"Price movement {movement*100:.2f}% exceeds threshold "
                f"{self.config.max_price_movement*100:.2f}% "
                f"(from {oldest_price:.2f} to {newest_price:.2f})"
            )
            
            await self._activate(
                reason=KillSwitchReason.ABNORMAL_PRICE_MOVEMENT,
                system_state=SystemState(
                    timestamp=datetime.now(),
                    balance=0.0,
                    open_positions=0,
                    pending_orders=0,
                    daily_pnl=0.0,
                    daily_drawdown=0.0,
                    consecutive_losses=0,
                    api_error_rate=0.0
                )
            )
            return True
            
        return False
        
    async def activate_manual(self, reason: str = "Manual activation"):
        """Manually activate kill switch
        
        Args:
            reason: Reason for manual activation
        """
        logger.warning(f"Kill switch manually activated: {reason}")
        
        await self._activate(
            reason=KillSwitchReason.MANUAL,
            system_state=SystemState(
                timestamp=datetime.now(),
                balance=0.0,
                open_positions=0,
                pending_orders=0,
                daily_pnl=0.0,
                daily_drawdown=0.0,
                consecutive_losses=0,
                api_error_rate=0.0
            )
        )
        
    async def _activate(
        self,
        reason: KillSwitchReason,
        system_state: SystemState
    ):
        """Activate kill switch
        
        Args:
            reason: Activation reason
            system_state: System state snapshot
        """
        if self._activated:
            logger.warning("Kill switch already activated")
            return
            
        self._activated = True
        self._activation_reason = reason
        self._activation_time = datetime.now()
        self._system_state = system_state
        
        # Log activation
        logger.critical(
            f"🚨 KILL SWITCH ACTIVATED 🚨\n"
            f"Reason: {reason.value}\n"
            f"Time: {self._activation_time}\n"
            f"State: {system_state}"
        )
        
        # Send Telegram alert
        if self.telegram_bot:
            try:
                await self._send_telegram_alert(reason, system_state)
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")
        
        # Call callback
        if self._on_activated:
            try:
                await self._on_activated(reason, system_state)
            except Exception as e:
                logger.error(f"Kill switch callback failed: {e}")
                
    async def _send_telegram_alert(
        self,
        reason: KillSwitchReason,
        system_state: SystemState
    ):
        """Send Telegram alert
        
        Args:
            reason: Activation reason
            system_state: System state snapshot
        """
        message = (
            "🚨 *KILL SWITCH ACTIVATED* 🚨\n\n"
            f"*Reason:* {reason.value}\n"
            f"*Time:* {self._activation_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"*System State:*\n"
            f"Balance: ${system_state.balance:.2f}\n"
            f"Open Positions: {system_state.open_positions}\n"
            f"Pending Orders: {system_state.pending_orders}\n"
        )
        
        if reason == KillSwitchReason.DAILY_DRAWDOWN:
            message += f"\nDaily Drawdown: {system_state.daily_drawdown*100:.2f}%"
        elif reason == KillSwitchReason.CONSECUTIVE_LOSSES:
            message += f"\nConsecutive Losses: {system_state.consecutive_losses}"
        elif reason == KillSwitchReason.API_ERROR_RATE:
            message += f"\nAPI Error Rate: {system_state.api_error_rate*100:.2f}%"
        
        message += "\n\n⚠️ *All trading stopped. Manual reset required.*"
        
        await self.telegram_bot.send_alert(message)
        
    def reset(self, manual_confirmation: bool = False):
        """Reset kill switch
        
        Args:
            manual_confirmation: Must be True to reset
            
        Raises:
            ValueError: If manual confirmation not provided
        """
        if not manual_confirmation:
            raise ValueError("Manual confirmation required to reset kill switch")
            
        if not self._activated:
            logger.warning("Kill switch not activated, nothing to reset")
            return
            
        logger.warning(
            f"Kill switch reset (was activated for {self._activation_reason.value})"
        )
        
        self._activated = False
        self._activation_reason = None
        self._activation_time = None
        self._system_state = None
        
        # Clear monitoring data
        self._api_errors.clear()
        self._price_history.clear()
        
    def get_status(self) -> Dict:
        """Get kill switch status
        
        Returns:
            Status dictionary
        """
        return {
            'activated': self._activated,
            'reason': self._activation_reason.value if self._activation_reason else None,
            'activation_time': self._activation_time.isoformat() if self._activation_time else None,
            'system_state': self._system_state
        }
