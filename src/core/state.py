"""
System state persistence for recovery after restarts.

The system state includes current mode, balance, positions, orders,
and kill switch status.
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import List, Optional
import aiofiles


logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode types."""
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"


@dataclass
class Position:
    """Position data for state persistence."""
    position_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    entry_price: str  # Stored as string to preserve precision
    quantity: str  # Stored as string to preserve precision
    opened_at: str  # ISO format timestamp
    stop_loss: Optional[str] = None
    trailing_stop: Optional[str] = None
    unrealized_pnl: str = "0"


@dataclass
class Order:
    """Order data for state persistence."""
    order_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "LIMIT" or "MARKET"
    quantity: str  # Stored as string to preserve precision
    price: Optional[str] = None
    state: str = "PENDING"
    exchange_order_id: Optional[str] = None


@dataclass
class SystemState:
    """
    Complete system state for persistence.
    
    This state is saved to disk and can be restored after system restart.
    """
    mode: str  # "paper", "testnet", or "live"
    balance: str  # Stored as string to preserve precision
    open_positions: List[Position] = field(default_factory=list)
    pending_orders: List[Order] = field(default_factory=list)
    daily_starting_balance: str = "0"
    consecutive_losses: int = 0
    kill_switch_active: bool = False
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class StatePersistence:
    """
    Handles saving and loading system state to/from disk.
    
    State is stored as JSON for human readability and easy debugging.
    """

    def __init__(self, state_file: str = "data/system_state.json"):
        """
        Initialize state persistence.
        
        Args:
            state_file: Path to the state file
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"StatePersistence initialized with file: {self.state_file}")

    async def save_state(self, state: SystemState) -> None:
        """
        Save system state to disk.
        
        Args:
            state: The system state to save
        """
        try:
            # Update last_updated timestamp
            state.last_updated = datetime.utcnow().isoformat()
            
            # Convert to dict
            state_dict = asdict(state)
            
            # Write to file atomically (write to temp file, then rename)
            temp_file = self.state_file.with_suffix('.tmp')
            
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(json.dumps(state_dict, indent=2, cls=DecimalEncoder))
            
            # Atomic rename
            temp_file.replace(self.state_file)
            
            logger.info(f"System state saved successfully")
            logger.debug(f"State: mode={state.mode}, balance={state.balance}, "
                        f"positions={len(state.open_positions)}, "
                        f"orders={len(state.pending_orders)}")
        
        except Exception as e:
            logger.error(f"Failed to save system state: {e}", exc_info=True)
            raise

    async def load_state(self) -> Optional[SystemState]:
        """
        Load system state from disk.
        
        Returns:
            SystemState if file exists and is valid, None otherwise
        """
        if not self.state_file.exists():
            logger.info("No saved state file found")
            return None
        
        try:
            async with aiofiles.open(self.state_file, 'r') as f:
                content = await f.read()
                state_dict = json.loads(content)
            
            # Convert positions
            positions = [Position(**p) for p in state_dict.get('open_positions', [])]
            
            # Convert orders
            orders = [Order(**o) for o in state_dict.get('pending_orders', [])]
            
            # Create SystemState
            state = SystemState(
                mode=state_dict['mode'],
                balance=state_dict['balance'],
                open_positions=positions,
                pending_orders=orders,
                daily_starting_balance=state_dict.get('daily_starting_balance', '0'),
                consecutive_losses=state_dict.get('consecutive_losses', 0),
                kill_switch_active=state_dict.get('kill_switch_active', False),
                last_updated=state_dict.get('last_updated', datetime.utcnow().isoformat())
            )
            
            logger.info(f"System state loaded successfully")
            logger.debug(f"State: mode={state.mode}, balance={state.balance}, "
                        f"positions={len(state.open_positions)}, "
                        f"orders={len(state.pending_orders)}")
            
            return state
        
        except Exception as e:
            logger.error(f"Failed to load system state: {e}", exc_info=True)
            return None

    async def clear_state(self) -> None:
        """
        Clear the saved state file.
        
        This is useful for starting fresh or after a mode switch.
        """
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.info("System state cleared")
            else:
                logger.debug("No state file to clear")
        
        except Exception as e:
            logger.error(f"Failed to clear system state: {e}", exc_info=True)
            raise

    def state_exists(self) -> bool:
        """
        Check if a saved state file exists.
        
        Returns:
            True if state file exists, False otherwise
        """
        return self.state_file.exists()
