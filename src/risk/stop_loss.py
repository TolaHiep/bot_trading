"""Stop-Loss Engine

This module manages stop-loss orders with multiple modes:
- Fixed %: Static stop-loss at fixed percentage
- Trailing: Dynamic stop-loss that follows price
- ATR-based: Stop-loss based on Average True Range
"""

import logging
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class StopLossMode(Enum):
    """Stop-loss modes"""
    FIXED_PERCENT = "FIXED_PERCENT"
    TRAILING = "TRAILING"
    ATR_BASED = "ATR_BASED"


class PositionSide(Enum):
    """Position side"""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Position:
    """Position information"""
    symbol: str
    side: PositionSide
    entry_price: float
    quantity: float
    current_price: float
    stop_loss_price: Optional[float] = None
    stop_loss_order_id: Optional[str] = None
    breakeven_moved: bool = False
    trailing_activated: bool = False
    highest_price: Optional[float] = None  # For long positions
    lowest_price: Optional[float] = None   # For short positions


@dataclass
class StopLossConfig:
    """Stop-loss configuration"""
    mode: StopLossMode
    initial_stop_pct: float = 0.02  # 2%
    breakeven_profit_pct: float = 0.01  # 1%
    trailing_activation_pct: float = 0.02  # 2%
    trailing_distance_pct: float = 0.01  # 1%
    atr_multiplier: float = 2.0
    atr_adjustment_threshold: float = 0.20  # 20%


class StopLossEngine:
    """Manage stop-loss orders with multiple modes"""
    
    def __init__(
        self,
        rest_client,
        config: StopLossConfig,
        monitor_interval: float = 1.0
    ):
        """Initialize stop-loss engine
        
        Args:
            rest_client: Bybit REST client for placing orders
            config: Stop-loss configuration
            monitor_interval: Position monitoring interval in seconds
        """
        self.rest_client = rest_client
        self.config = config
        self.monitor_interval = monitor_interval
        
        # Track positions
        self.positions: Dict[str, Position] = {}
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks
        self._on_stop_triggered: Optional[Callable] = None
        self._on_emergency_close: Optional[Callable] = None
        
        # ATR tracking
        self._atr_values: Dict[str, float] = {}
        
    def set_callbacks(
        self,
        on_stop_triggered: Optional[Callable] = None,
        on_emergency_close: Optional[Callable] = None
    ):
        """Set callback functions
        
        Args:
            on_stop_triggered: Called when stop-loss is triggered
            on_emergency_close: Called when emergency close is executed
        """
        self._on_stop_triggered = on_stop_triggered
        self._on_emergency_close = on_emergency_close
        
    async def add_position(
        self,
        symbol: str,
        side: PositionSide,
        entry_price: float,
        quantity: float,
        current_price: float,
        atr: Optional[float] = None
    ) -> Position:
        """Add position and place initial stop-loss
        
        Args:
            symbol: Trading symbol
            side: Position side (LONG/SHORT)
            entry_price: Entry price
            quantity: Position quantity
            current_price: Current market price
            atr: Average True Range (required for ATR mode)
            
        Returns:
            Position object
        """
        # Calculate initial stop-loss price
        stop_loss_price = self._calculate_initial_stop_loss(
            entry_price=entry_price,
            side=side,
            atr=atr
        )
        
        # Create position
        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            current_price=current_price,
            stop_loss_price=stop_loss_price,
            highest_price=current_price if side == PositionSide.LONG else None,
            lowest_price=current_price if side == PositionSide.SHORT else None
        )
        
        # Place stop-loss order on exchange
        try:
            order_id = await self._place_stop_loss_order(position)
            position.stop_loss_order_id = order_id
            
            logger.info(
                f"Initial stop-loss placed for {symbol} {side.value} at "
                f"{stop_loss_price:.2f} (order: {order_id})"
            )
        except Exception as e:
            logger.error(f"Failed to place initial stop-loss: {e}")
            # Continue without stop-loss order (will use emergency close if needed)
        
        # Store position
        self.positions[symbol] = position
        
        # Store ATR if provided
        if atr is not None:
            self._atr_values[symbol] = atr
        
        return position
        
    def _calculate_initial_stop_loss(
        self,
        entry_price: float,
        side: PositionSide,
        atr: Optional[float] = None
    ) -> float:
        """Calculate initial stop-loss price
        
        Args:
            entry_price: Entry price
            side: Position side
            atr: Average True Range (for ATR mode)
            
        Returns:
            Stop-loss price
        """
        if self.config.mode == StopLossMode.ATR_BASED:
            if atr is None:
                raise ValueError("ATR required for ATR_BASED mode")
            
            stop_distance = atr * self.config.atr_multiplier
            
            if side == PositionSide.LONG:
                return entry_price - stop_distance
            else:
                return entry_price + stop_distance
        else:
            # Fixed % or Trailing (both start with fixed %)
            if side == PositionSide.LONG:
                return entry_price * (1 - self.config.initial_stop_pct)
            else:
                return entry_price * (1 + self.config.initial_stop_pct)
                
    async def _place_stop_loss_order(self, position: Position) -> str:
        """Place stop-loss order on exchange
        
        Args:
            position: Position object
            
        Returns:
            Order ID
        """
        # Cancel existing stop-loss order if any
        if position.stop_loss_order_id:
            try:
                await self.rest_client.cancel_order(
                    symbol=position.symbol,
                    order_id=position.stop_loss_order_id
                )
            except Exception as e:
                logger.warning(f"Failed to cancel existing stop-loss: {e}")
        
        # Determine order side (opposite of position)
        order_side = "Sell" if position.side == PositionSide.LONG else "Buy"
        
        # Place stop-loss order
        response = await self.rest_client.place_order(
            symbol=position.symbol,
            side=order_side,
            order_type="Market",
            qty=position.quantity,
            stop_loss=position.stop_loss_price,
            reduce_only=True
        )
        
        return response['orderId']
        
    async def update_position(
        self,
        symbol: str,
        current_price: float,
        atr: Optional[float] = None
    ):
        """Update position with current price and adjust stop-loss
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            atr: Current ATR (for ATR mode)
        """
        if symbol not in self.positions:
            return
            
        position = self.positions[symbol]
        position.current_price = current_price
        
        # Update highest/lowest price
        if position.side == PositionSide.LONG:
            if position.highest_price is None or current_price > position.highest_price:
                position.highest_price = current_price
        else:
            if position.lowest_price is None or current_price < position.lowest_price:
                position.lowest_price = current_price
        
        # Update ATR if provided
        if atr is not None:
            old_atr = self._atr_values.get(symbol)
            self._atr_values[symbol] = atr
            
            # Check if ATR changed significantly
            if old_atr and self.config.mode == StopLossMode.ATR_BASED:
                atr_change = abs(atr - old_atr) / old_atr
                if atr_change > self.config.atr_adjustment_threshold:
                    logger.info(
                        f"ATR changed {atr_change*100:.1f}% for {symbol}, "
                        f"adjusting stop-loss"
                    )
                    await self._adjust_stop_loss(position, atr)
                    return
        
        # Calculate profit percentage
        profit_pct = self._calculate_profit_pct(position)
        
        # Update trailing stop if active (highest priority)
        if position.trailing_activated:
            await self._update_trailing_stop(position)
            return
        
        # Check for trailing stop activation (priority in TRAILING mode)
        if (self.config.mode == StopLossMode.TRAILING and 
            not position.trailing_activated and 
            profit_pct >= self.config.trailing_activation_pct):
            await self._activate_trailing_stop(position)
            return
        
        # Check for breakeven move
        if not position.breakeven_moved and profit_pct >= self.config.breakeven_profit_pct:
            await self._move_to_breakeven(position)
            return
            
    def _calculate_profit_pct(self, position: Position) -> float:
        """Calculate profit percentage
        
        Args:
            position: Position object
            
        Returns:
            Profit percentage (0.01 = 1%)
        """
        if position.side == PositionSide.LONG:
            return (position.current_price - position.entry_price) / position.entry_price
        else:
            return (position.entry_price - position.current_price) / position.entry_price
            
    async def _move_to_breakeven(self, position: Position):
        """Move stop-loss to breakeven
        
        Args:
            position: Position object
        """
        old_stop = position.stop_loss_price
        position.stop_loss_price = position.entry_price
        position.breakeven_moved = True
        
        try:
            order_id = await self._place_stop_loss_order(position)
            position.stop_loss_order_id = order_id
            
            logger.info(
                f"Stop-loss moved to breakeven for {position.symbol} "
                f"(from {old_stop:.2f} to {position.stop_loss_price:.2f})"
            )
        except Exception as e:
            logger.error(f"Failed to move stop-loss to breakeven: {e}")
            # Revert
            position.stop_loss_price = old_stop
            position.breakeven_moved = False
            
    async def _activate_trailing_stop(self, position: Position):
        """Activate trailing stop
        
        Args:
            position: Position object
        """
        position.trailing_activated = True
        
        # Calculate trailing stop price
        await self._update_trailing_stop(position)
        
        logger.info(f"Trailing stop activated for {position.symbol}")
        
    async def _update_trailing_stop(self, position: Position):
        """Update trailing stop price
        
        Args:
            position: Position object
        """
        # Calculate new stop-loss price based on highest/lowest
        if position.side == PositionSide.LONG:
            new_stop = position.highest_price * (1 - self.config.trailing_distance_pct)
        else:
            new_stop = position.lowest_price * (1 + self.config.trailing_distance_pct)
        
        # Only move stop-loss in favorable direction
        if position.side == PositionSide.LONG:
            if new_stop > position.stop_loss_price:
                old_stop = position.stop_loss_price
                position.stop_loss_price = new_stop
                
                try:
                    order_id = await self._place_stop_loss_order(position)
                    position.stop_loss_order_id = order_id
                    
                    logger.info(
                        f"Trailing stop updated for {position.symbol} "
                        f"(from {old_stop:.2f} to {new_stop:.2f})"
                    )
                except Exception as e:
                    logger.error(f"Failed to update trailing stop: {e}")
                    position.stop_loss_price = old_stop
        else:
            if new_stop < position.stop_loss_price:
                old_stop = position.stop_loss_price
                position.stop_loss_price = new_stop
                
                try:
                    order_id = await self._place_stop_loss_order(position)
                    position.stop_loss_order_id = order_id
                    
                    logger.info(
                        f"Trailing stop updated for {position.symbol} "
                        f"(from {old_stop:.2f} to {new_stop:.2f})"
                    )
                except Exception as e:
                    logger.error(f"Failed to update trailing stop: {e}")
                    position.stop_loss_price = old_stop
                    
    async def _adjust_stop_loss(self, position: Position, atr: float):
        """Adjust stop-loss based on new ATR
        
        Args:
            position: Position object
            atr: New ATR value
        """
        # Calculate new stop-loss price
        stop_distance = atr * self.config.atr_multiplier
        
        if position.side == PositionSide.LONG:
            new_stop = position.current_price - stop_distance
        else:
            new_stop = position.current_price + stop_distance
        
        old_stop = position.stop_loss_price
        position.stop_loss_price = new_stop
        
        try:
            order_id = await self._place_stop_loss_order(position)
            position.stop_loss_order_id = order_id
            
            logger.info(
                f"ATR-based stop-loss adjusted for {position.symbol} "
                f"(from {old_stop:.2f} to {new_stop:.2f})"
            )
        except Exception as e:
            logger.error(f"Failed to adjust ATR-based stop-loss: {e}")
            position.stop_loss_price = old_stop
            
    async def check_stop_loss_triggered(self, symbol: str) -> bool:
        """Check if stop-loss was triggered
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if stop-loss was triggered
        """
        if symbol not in self.positions:
            return False
            
        position = self.positions[symbol]
        
        # Check if price hit stop-loss
        if position.side == PositionSide.LONG:
            triggered = position.current_price <= position.stop_loss_price
        else:
            triggered = position.current_price >= position.stop_loss_price
        
        if triggered:
            # Calculate loss
            if position.side == PositionSide.LONG:
                loss = (position.entry_price - position.current_price) * position.quantity
            else:
                loss = (position.current_price - position.entry_price) * position.quantity
            
            logger.warning(
                f"Stop-loss triggered for {symbol} at {position.current_price:.2f} "
                f"(stop: {position.stop_loss_price:.2f}, loss: ${loss:.2f})"
            )
            
            # Call callback
            if self._on_stop_triggered:
                await self._on_stop_triggered(position, loss)
            
            # Check if stop-loss order exists
            if not position.stop_loss_order_id:
                logger.error(f"No stop-loss order for {symbol}, executing emergency close")
                await self._emergency_close(position, loss)
            
            return True
            
        return False
        
    async def _emergency_close(self, position: Position, loss: float):
        """Emergency close position at market
        
        Args:
            position: Position object
            loss: Calculated loss amount
        """
        try:
            # Determine order side
            order_side = "Sell" if position.side == PositionSide.LONG else "Buy"
            
            # Place market order
            response = await self.rest_client.place_order(
                symbol=position.symbol,
                side=order_side,
                order_type="Market",
                qty=position.quantity,
                reduce_only=True
            )
            
            logger.warning(
                f"Emergency close executed for {position.symbol} "
                f"(order: {response['orderId']}, loss: ${loss:.2f})"
            )
            
            # Call callback
            if self._on_emergency_close:
                await self._on_emergency_close(position, loss)
                
        except Exception as e:
            logger.critical(f"Emergency close failed for {position.symbol}: {e}")
            
    async def remove_position(self, symbol: str):
        """Remove position from tracking
        
        Args:
            symbol: Trading symbol
        """
        if symbol in self.positions:
            position = self.positions[symbol]
            
            # Cancel stop-loss order
            if position.stop_loss_order_id:
                try:
                    await self.rest_client.cancel_order(
                        symbol=symbol,
                        order_id=position.stop_loss_order_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to cancel stop-loss order: {e}")
            
            del self.positions[symbol]
            
            if symbol in self._atr_values:
                del self._atr_values[symbol]
                
            logger.info(f"Position removed: {symbol}")
            
    async def start_monitoring(self):
        """Start monitoring positions"""
        if self._running:
            logger.warning("Monitoring already running")
            return
            
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Stop-loss monitoring started")
        
    async def stop_monitoring(self):
        """Stop monitoring positions"""
        if not self._running:
            return
            
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Stop-loss monitoring stopped")
        
    async def _monitor_loop(self):
        """Monitor positions continuously"""
        while self._running:
            try:
                # Check all positions
                for symbol in list(self.positions.keys()):
                    await self.check_stop_loss_triggered(symbol)
                    
                await asyncio.sleep(self.monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.monitor_interval)
                
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position object or None
        """
        return self.positions.get(symbol)
        
    def get_all_positions(self) -> Dict[str, Position]:
        """Get all positions
        
        Returns:
            Dictionary of positions
        """
        return self.positions.copy()
    
    async def update_stops(self, current_price: float):
        """Update all stop losses with current price
        
        Args:
            current_price: Current market price
        """
        for symbol in list(self.positions.keys()):
            await self.update_position(symbol, current_price)
    
    def check_stop_triggered(self, symbol: str, current_price: float) -> bool:
        """Check if stop loss was triggered (alias for check_stop_loss_triggered)
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            
        Returns:
            True if stop loss triggered
        """
        if symbol in self.positions:
            self.positions[symbol].current_price = current_price
        
        return asyncio.run(self.check_stop_loss_triggered(symbol))
