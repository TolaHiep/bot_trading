"""
Simulated Exchange - Simulate order execution trong backtest

Provides realistic order execution simulation với slippage và commission.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, List
from dataclasses import dataclass

from src.backtest.slippage_model import SlippageModel

logger = logging.getLogger(__name__)


@dataclass
class SimulatedOrder:
    """Simulated order"""
    order_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "LIMIT" or "MARKET"
    quantity: Decimal
    price: Optional[Decimal]  # None for market orders
    timestamp: datetime
    
    # Execution results
    filled: bool = False
    fill_price: Optional[Decimal] = None
    fill_timestamp: Optional[datetime] = None
    commission: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")


@dataclass
class SimulatedPosition:
    """Simulated position"""
    symbol: str
    side: str
    entry_price: Decimal
    quantity: Decimal
    opened_at: datetime
    
    def get_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L"""
        if self.side == "BUY":
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity


class SimulatedExchange:
    """
    Simulate order execution trong backtest
    
    Features:
    - Realistic slippage simulation based on orderbook
    - Commission application (Bybit fee structure)
    - Balance and position tracking
    - Market and limit order support
    """
    
    def __init__(
        self,
        initial_balance: Decimal,
        commission_rate: Decimal = Decimal("0.0006")  # Bybit taker fee 0.06%
    ):
        """
        Initialize Simulated Exchange
        
        Args:
            initial_balance: Starting balance
            commission_rate: Commission rate (default: 0.06%)
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_rate = commission_rate
        
        # State
        self.positions: Dict[str, SimulatedPosition] = {}
        self.orders: Dict[str, SimulatedOrder] = {}
        self.order_counter = 0
        
        # Slippage model
        self.slippage_model = SlippageModel()
        
        # Orderbook history for slippage calculation
        self.orderbook_history: Dict[datetime, Dict] = {}
        
        logger.info(
            f"SimulatedExchange initialized with balance: {initial_balance}, "
            f"commission: {commission_rate*100:.2f}%"
        )
    
    def update_orderbook(self, timestamp: datetime, orderbook: Dict) -> None:
        """
        Update orderbook snapshot for slippage calculation
        
        Args:
            timestamp: Orderbook timestamp
            orderbook: Orderbook data with bids and asks
        """
        self.orderbook_history[timestamp] = orderbook
    
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal],
        current_timestamp: datetime
    ) -> SimulatedOrder:
        """
        Place order on simulated exchange
        
        Args:
            symbol: Trading symbol
            side: "BUY" or "SELL"
            order_type: "LIMIT" or "MARKET"
            quantity: Order quantity
            price: Limit price (None for market orders)
            current_timestamp: Current backtest timestamp
        
        Returns:
            SimulatedOrder
        """
        self.order_counter += 1
        order_id = f"SIM_{self.order_counter}"
        
        order = SimulatedOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            timestamp=current_timestamp
        )
        
        self.orders[order_id] = order
        
        logger.debug(
            f"Order placed: {order_id} {side} {quantity} {symbol} "
            f"@ {price if price else 'MARKET'}"
        )
        
        return order
    
    def execute_order(
        self,
        order: SimulatedOrder,
        current_price: Decimal,
        current_timestamp: datetime
    ) -> bool:
        """
        Execute order with realistic slippage
        
        Args:
            order: Order to execute
            current_price: Current market price
            current_timestamp: Current backtest timestamp
        
        Returns:
            True if executed, False otherwise
        
        Algorithm:
            1. Get orderbook at current_timestamp
            2. Calculate realistic slippage
            3. Apply commission
            4. Update balance and positions
        """
        # Get orderbook for slippage calculation
        orderbook = self.orderbook_history.get(current_timestamp)
        
        # Calculate slippage
        if orderbook:
            slippage_pct = self.slippage_model.calculate_slippage(
                orderbook=orderbook,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type
            )
        else:
            # Fallback: use default slippage
            slippage_pct = Decimal("0.0005") if order.order_type == "MARKET" else Decimal("0")
        
        # Calculate fill price
        if order.side == "BUY":
            fill_price = current_price * (Decimal("1") + slippage_pct)
        else:
            fill_price = current_price * (Decimal("1") - slippage_pct)
        
        # Calculate position value and commission
        position_value = fill_price * order.quantity
        commission = position_value * self.commission_rate
        
        # Check if sufficient balance
        if order.side == "BUY":
            total_cost = position_value + commission
            if self.balance < total_cost:
                logger.warning(
                    f"Insufficient balance for order {order.order_id}: "
                    f"need {total_cost}, have {self.balance}"
                )
                return False
        
        # Execute order
        order.filled = True
        order.fill_price = fill_price
        order.fill_timestamp = current_timestamp
        order.commission = commission
        order.slippage = slippage_pct
        
        # Update balance
        if order.side == "BUY":
            self.balance -= (position_value + commission)
        else:
            self.balance += (position_value - commission)
        
        # Update positions
        self._update_position(order)
        
        logger.debug(
            f"Order executed: {order.order_id} filled @ {fill_price} "
            f"(slippage: {slippage_pct*100:.3f}%, commission: {commission:.2f})"
        )
        
        return True
    
    def _update_position(self, order: SimulatedOrder) -> None:
        """Update position after order execution"""
        symbol = order.symbol
        
        if symbol not in self.positions:
            # Open new position
            self.positions[symbol] = SimulatedPosition(
                symbol=symbol,
                side=order.side,
                entry_price=order.fill_price,
                quantity=order.quantity,
                opened_at=order.fill_timestamp
            )
        else:
            # Close or modify existing position
            position = self.positions[symbol]
            
            if position.side != order.side:
                # Closing position
                if order.quantity >= position.quantity:
                    # Full close or reverse
                    del self.positions[symbol]
                    
                    if order.quantity > position.quantity:
                        # Reverse position
                        remaining_qty = order.quantity - position.quantity
                        self.positions[symbol] = SimulatedPosition(
                            symbol=symbol,
                            side=order.side,
                            entry_price=order.fill_price,
                            quantity=remaining_qty,
                            opened_at=order.fill_timestamp
                        )
                else:
                    # Partial close
                    position.quantity -= order.quantity
            else:
                # Adding to position (average entry price)
                total_value = (position.entry_price * position.quantity + 
                              order.fill_price * order.quantity)
                total_quantity = position.quantity + order.quantity
                position.entry_price = total_value / total_quantity
                position.quantity = total_quantity
    
    def close_position(
        self,
        symbol: str,
        current_price: Decimal,
        current_timestamp: datetime
    ) -> Optional[Decimal]:
        """
        Close position at market price
        
        Args:
            symbol: Symbol to close
            current_price: Current market price
            current_timestamp: Current timestamp
        
        Returns:
            Realized P&L if position exists, None otherwise
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Calculate P&L
        pnl = position.get_unrealized_pnl(current_price)
        
        # Place closing order
        close_side = "SELL" if position.side == "BUY" else "BUY"
        order = self.place_order(
            symbol=symbol,
            side=close_side,
            order_type="MARKET",
            quantity=position.quantity,
            price=None,
            current_timestamp=current_timestamp
        )
        
        # Execute order
        self.execute_order(order, current_price, current_timestamp)
        
        logger.info(
            f"Position closed: {symbol} {position.side} "
            f"P&L: {pnl:.2f}"
        )
        
        return pnl
    
    def get_balance(self) -> Decimal:
        """Get current balance"""
        return self.balance
    
    def get_equity(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """
        Calculate total equity (balance + unrealized P&L)
        
        Args:
            current_prices: Dict of symbol -> current price
        
        Returns:
            Total equity
        """
        equity = self.balance
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                unrealized_pnl = position.get_unrealized_pnl(current_prices[symbol])
                equity += unrealized_pnl
        
        return equity
    
    def get_positions(self) -> Dict[str, SimulatedPosition]:
        """Get all open positions"""
        return self.positions.copy()
    
    def get_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """Get order by ID"""
        return self.orders.get(order_id)
