"""
Order Manager - Quản lý vòng đời lệnh giao dịch

Implements order state machine và execution logic với retry mechanism.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, List
from uuid import uuid4

logger = logging.getLogger(__name__)


class OrderState(Enum):
    """Order state machine states"""
    PENDING = "PENDING"      # Order created, not yet submitted
    OPEN = "OPEN"           # Order submitted to exchange
    PARTIAL = "PARTIAL"     # Partially filled
    FILLED = "FILLED"       # Completely filled
    CANCELLED = "CANCELLED" # Cancelled by user or timeout
    REJECTED = "REJECTED"   # Rejected by exchange
    FAILED = "FAILED"       # Failed to submit


class OrderSide(Enum):
    """Order side"""
    BUY = "Buy"
    SELL = "Sell"


class OrderType(Enum):
    """Order type"""
    LIMIT = "Limit"
    MARKET = "Market"


@dataclass
class Order:
    """Order representation"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal]  # None for market orders
    state: OrderState
    filled_qty: Decimal = Decimal("0")
    avg_fill_price: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    exchange_order_id: Optional[str] = None
    reject_reason: Optional[str] = None
    retry_count: int = 0
    strategy_name: str = "main"
    
    def update_state(self, new_state: OrderState, reason: Optional[str] = None) -> None:
        """Update order state"""
        old_state = self.state
        self.state = new_state
        self.updated_at = datetime.now()
        
        if new_state == OrderState.REJECTED:
            self.reject_reason = reason
        
        logger.info(
            f"Order {self.order_id} state: {old_state.value} → {new_state.value}"
            + (f" (reason: {reason})" if reason else "")
        )
    
    def update_fill(self, filled_qty: Decimal, avg_price: Decimal) -> None:
        """Update fill information"""
        self.filled_qty = filled_qty
        self.avg_fill_price = avg_price
        self.updated_at = datetime.now()
        
        if self.filled_qty >= self.quantity:
            self.update_state(OrderState.FILLED)
        elif self.filled_qty > Decimal("0"):
            self.update_state(OrderState.PARTIAL)


@dataclass
class Position:
    """Trading position"""
    position_id: str
    symbol: str
    side: OrderSide
    entry_price: Decimal
    quantity: Decimal
    opened_at: datetime = field(default_factory=datetime.now)
    pnl: Decimal = Decimal("0")
    strategy_name: str = "main"
    margin_locked: Decimal = Decimal("0")  # Margin locked for this position
    leverage: Decimal = Decimal("1.0")  # Leverage used
    
    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L"""
        if self.side == OrderSide.BUY:
            self.pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - current_price) * self.quantity
        return self.pnl


class OrderManager:
    """
    Order Manager - Quản lý và thực thi orders
    
    Features:
    - State machine: PENDING → OPEN → PARTIAL → FILLED → CLOSED
    - Limit order with market fallback after timeout
    - Retry mechanism (up to 2 retries)
    - Order verification
    - Partial fill handling
    """
    
    def __init__(self, rest_client, max_retries: int = 2, limit_timeout: int = 5):
        """
        Initialize Order Manager
        
        Args:
            rest_client: Bybit REST client
            max_retries: Maximum retry attempts for failed orders
            limit_timeout: Timeout in seconds before falling back to market order
        """
        self.rest_client = rest_client
        self.max_retries = max_retries
        self.limit_timeout = limit_timeout
        
        # Order tracking
        self.pending_orders: Dict[str, Order] = {}
        self.filled_orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        
        logger.info(
            f"OrderManager initialized (max_retries={max_retries}, "
            f"limit_timeout={limit_timeout}s)"
        )
    
    async def execute_signal(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        limit_price: Optional[Decimal] = None
    ) -> Optional[Position]:
        """
        Execute trading signal
        
        Strategy:
        1. Place limit order at specified price (or best bid/ask)
        2. Wait for fill (timeout: 5 seconds)
        3. If not filled: cancel and place market order
        4. Verify execution via API query
        5. Retry up to 2 times on failure
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: Order side (BUY/SELL)
            quantity: Order quantity
            limit_price: Limit price (if None, use best bid/ask)
        
        Returns:
            Position if successful, None if failed
        """
        order_id = str(uuid4())
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=limit_price,
            state=OrderState.PENDING,
            strategy_name="main"
        )
        
        self.pending_orders[order_id] = order
        logger.info(
            f"Executing signal: {side.value} {quantity} {symbol} @ {limit_price}"
        )
        
        # Try limit order first
        position = await self._execute_with_retry(order)
        
        if position:
            self.positions[position.position_id] = position
            self.filled_orders[order_id] = order
            del self.pending_orders[order_id]
            logger.info(f"Position opened: {position.position_id}")
        else:
            logger.error(f"Failed to execute order {order_id}")
            if order_id in self.pending_orders:
                del self.pending_orders[order_id]
        
        return position
    
    async def _execute_with_retry(self, order: Order) -> Optional[Position]:
        """Execute order with retry logic"""
        for attempt in range(self.max_retries + 1):
            order.retry_count = attempt
            
            try:
                # Try limit order first
                position = await self._execute_limit_order(order)
                if position:
                    return position
                
                # If limit order failed/timeout, try market order
                if attempt < self.max_retries:
                    logger.warning(
                        f"Limit order failed, retrying with market order "
                        f"(attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    position = await self._execute_market_order(order)
                    if position:
                        return position
            
            except Exception as e:
                logger.error(f"Order execution error (attempt {attempt + 1}): {e}")
                if attempt >= self.max_retries:
                    order.update_state(OrderState.FAILED, str(e))
                    return None
                
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
        
        order.update_state(OrderState.FAILED, "Max retries exceeded")
        return None
    
    async def _execute_limit_order(self, order: Order) -> Optional[Position]:
        """Execute limit order with timeout fallback"""
        try:
            # Place limit order
            exchange_order_id = await self.place_limit_order(
                symbol=order.symbol,
                side=order.side,
                qty=order.quantity,
                price=order.price
            )
            
            if not exchange_order_id:
                order.update_state(OrderState.REJECTED, "Failed to place order")
                return None
            
            order.exchange_order_id = exchange_order_id
            order.update_state(OrderState.OPEN)
            
            # Wait for fill
            filled = await self.wait_for_fill(exchange_order_id, self.limit_timeout)
            
            if filled:
                # Verify execution
                verified_order = await self.verify_execution(exchange_order_id)
                if verified_order:
                    order.update_fill(
                        verified_order.filled_qty,
                        verified_order.avg_fill_price
                    )
                    return self._create_position(order)
            else:
                # Timeout - cancel and fallback to market
                logger.warning(
                    f"Limit order {exchange_order_id} not filled within "
                    f"{self.limit_timeout}s, cancelling..."
                )
                await self.cancel_order(exchange_order_id)
                order.update_state(OrderState.CANCELLED, "Timeout")
                return None
        
        except Exception as e:
            logger.error(f"Limit order execution error: {e}")
            order.update_state(OrderState.FAILED, str(e))
            return None
    
    async def _execute_market_order(self, order: Order) -> Optional[Position]:
        """Execute market order (fallback)"""
        try:
            # Update order type
            order.order_type = OrderType.MARKET
            order.price = None
            
            # Place market order
            exchange_order_id = await self.place_market_order(
                symbol=order.symbol,
                side=order.side,
                qty=order.quantity
            )
            
            if not exchange_order_id:
                order.update_state(OrderState.REJECTED, "Failed to place market order")
                return None
            
            order.exchange_order_id = exchange_order_id
            order.update_state(OrderState.OPEN)
            
            # Market orders fill immediately, verify execution
            await asyncio.sleep(0.5)  # Small delay for exchange processing
            verified_order = await self.verify_execution(exchange_order_id)
            
            if verified_order and verified_order.state == OrderState.FILLED:
                order.update_fill(
                    verified_order.filled_qty,
                    verified_order.avg_fill_price
                )
                return self._create_position(order)
            else:
                order.update_state(OrderState.FAILED, "Market order not filled")
                return None
        
        except Exception as e:
            logger.error(f"Market order execution error: {e}")
            order.update_state(OrderState.FAILED, str(e))
            return None
    
    async def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        price: Decimal
    ) -> Optional[str]:
        """
        Place limit order on exchange
        
        Returns:
            Exchange order ID if successful, None otherwise
        """
        try:
            response = await self.rest_client.place_order(
                category="linear",
                symbol=symbol,
                side=side.value,
                orderType=OrderType.LIMIT.value,
                qty=str(qty),
                price=str(price),
                timeInForce="GTC"
            )
            
            if response and response.get("retCode") == 0:
                order_id = response["result"]["orderId"]
                logger.info(f"Limit order placed: {order_id}")
                return order_id
            else:
                logger.error(f"Failed to place limit order: {response}")
                return None
        
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None
    
    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal
    ) -> Optional[str]:
        """
        Place market order on exchange
        
        Returns:
            Exchange order ID if successful, None otherwise
        """
        try:
            response = await self.rest_client.place_order(
                category="linear",
                symbol=symbol,
                side=side.value,
                orderType=OrderType.MARKET.value,
                qty=str(qty)
            )
            
            if response and response.get("retCode") == 0:
                order_id = response["result"]["orderId"]
                logger.info(f"Market order placed: {order_id}")
                return order_id
            else:
                logger.error(f"Failed to place market order: {response}")
                return None
        
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None
    
    async def cancel_order(self, exchange_order_id: str) -> bool:
        """Cancel order on exchange"""
        try:
            response = await self.rest_client.cancel_order(
                category="linear",
                orderId=exchange_order_id
            )
            
            if response and response.get("retCode") == 0:
                logger.info(f"Order cancelled: {exchange_order_id}")
                return True
            else:
                logger.error(f"Failed to cancel order: {response}")
                return False
        
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def wait_for_fill(self, exchange_order_id: str, timeout: int) -> bool:
        """
        Wait for order to be filled
        
        Args:
            exchange_order_id: Exchange order ID
            timeout: Timeout in seconds
        
        Returns:
            True if filled within timeout, False otherwise
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                order = await self.verify_execution(exchange_order_id)
                if order and order.state == OrderState.FILLED:
                    return True
                elif order and order.state in [OrderState.REJECTED, OrderState.CANCELLED]:
                    return False
                
                await asyncio.sleep(0.5)  # Poll every 500ms
            
            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                await asyncio.sleep(0.5)
        
        return False
    
    async def verify_execution(self, exchange_order_id: str) -> Optional[Order]:
        """
        Verify order execution via API query
        
        Returns:
            Order with updated status, or None if query failed
        """
        try:
            response = await self.rest_client.get_order_history(
                category="linear",
                orderId=exchange_order_id
            )
            
            if not response or response.get("retCode") != 0:
                logger.error(f"Failed to query order: {response}")
                return None
            
            order_data = response["result"]["list"][0]
            
            # Map exchange status to our OrderState
            status_map = {
                "New": OrderState.OPEN,
                "PartiallyFilled": OrderState.PARTIAL,
                "Filled": OrderState.FILLED,
                "Cancelled": OrderState.CANCELLED,
                "Rejected": OrderState.REJECTED
            }
            
            state = status_map.get(order_data["orderStatus"], OrderState.OPEN)
            filled_qty = Decimal(order_data.get("cumExecQty", "0"))
            avg_price = Decimal(order_data.get("avgPrice", "0"))
            
            # Create Order object from response
            order = Order(
                order_id=exchange_order_id,
                symbol=order_data["symbol"],
                side=OrderSide.BUY if order_data["side"] == "Buy" else OrderSide.SELL,
                order_type=OrderType.LIMIT if order_data["orderType"] == "Limit" else OrderType.MARKET,
                quantity=Decimal(order_data["qty"]),
                price=Decimal(order_data.get("price", "0")) if order_data.get("price") else None,
                state=state,
                filled_qty=filled_qty,
                avg_fill_price=avg_price,
                exchange_order_id=exchange_order_id,
                strategy_name="main" # Assuming it fetches from exchange, strategy inference is not trivial here
            )
            
            return order
        
        except Exception as e:
            logger.error(f"Error verifying execution: {e}")
            return None
    
    def _create_position(self, order: Order) -> Position:
        """Create position from filled order"""
        position = Position(
            position_id=str(uuid4()),
            symbol=order.symbol,
            side=order.side,
            entry_price=order.avg_fill_price,
            quantity=order.filled_qty,
            strategy_name=order.strategy_name
        )
        
        logger.info(
            f"Position created: {position.side.value} {position.quantity} "
            f"{position.symbol} @ {position.entry_price}"
        )
        
        return position
    
    def get_order_status(self, order_id: str) -> Optional[OrderState]:
        """Get current order status"""
        if order_id in self.pending_orders:
            return self.pending_orders[order_id].state
        elif order_id in self.filled_orders:
            return self.filled_orders[order_id].state
        return None
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID"""
        return self.positions.get(position_id)
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return list(self.positions.values())
