"""
Paper Trading Simulator - Simulates order execution without real orders

Provides realistic simulation using real-time market data with slippage and commission.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import uuid4

from .order_manager import Order, OrderState, OrderSide, OrderType, Position
from .cost_filter import CostFilter, Orderbook

logger = logging.getLogger(__name__)


@dataclass
class SimulatedAccount:
    """Simulated trading account"""
    initial_balance: Decimal
    current_balance: Decimal
    equity: Decimal = field(default_factory=lambda: Decimal("0"))
    total_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    realized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    unrealized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    def update_equity(self, positions: List[Position], current_prices: Dict[str, Decimal]) -> None:
        """Update equity based on current positions and prices"""
        unrealized = Decimal("0")
        for position in positions:
            if position.symbol in current_prices:
                position.calculate_pnl(current_prices[position.symbol])
                unrealized += position.pnl
        
        self.unrealized_pnl = unrealized
        self.equity = self.current_balance + unrealized
        self.total_pnl = self.realized_pnl + unrealized


@dataclass
class SimulatedTrade:
    """Record of simulated trade"""
    trade_id: str
    timestamp: datetime
    symbol: str
    side: OrderSide
    entry_price: Decimal
    exit_price: Optional[Decimal]
    quantity: Decimal
    commission: Decimal
    slippage: Decimal
    pnl: Optional[Decimal]
    status: str  # "OPEN" or "CLOSED"
    entry_reason: str
    exit_reason: Optional[str] = None


class PaperTrader:
    """
    Paper Trading Simulator
    
    Features:
    - Simulates order execution without placing real orders
    - Uses real-time market data from Bybit
    - Applies realistic slippage and commission
    - Maintains simulated balance and positions
    - Logs all trades for analysis
    """
    
    def __init__(
        self,
        initial_balance: Decimal,
        commission_rate: Decimal = Decimal("0.0006"),  # Bybit taker fee
        cost_filter: Optional[CostFilter] = None
    ):
        """
        Initialize Paper Trader
        
        Args:
            initial_balance: Starting balance for simulation
            commission_rate: Commission rate (default: 0.06%)
            cost_filter: Cost filter for slippage calculation
        """
        self.account = SimulatedAccount(
            initial_balance=initial_balance,
            current_balance=initial_balance
        )
        self.commission_rate = commission_rate
        self.cost_filter = cost_filter or CostFilter(commission_rate=commission_rate * 100)
        
        # Tracking
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trade_history: List[SimulatedTrade] = []
        
        logger.info(
            f"PaperTrader initialized with balance: {initial_balance}, "
            f"commission: {commission_rate*100:.2f}%"
        )
    
    async def execute_signal(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        orderbook: Orderbook,
        reason: str = "Signal"
    ) -> Optional[Position]:
        """
        Execute trading signal in paper mode
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            orderbook: Current orderbook for slippage calculation
            reason: Entry reason for logging
        
        Returns:
            Simulated position if successful, None if rejected
        """
        # Analyze costs
        analysis = self.cost_filter.analyze_trade(orderbook, side.value, quantity)
        
        if analysis.should_reject:
            logger.warning(
                f"Paper trade rejected: {analysis.reject_reason}"
            )
            return None
        
        # Calculate entry price with slippage
        if side == OrderSide.BUY:
            entry_price = analysis.avg_fill_price
        else:
            entry_price = analysis.avg_fill_price
        
        # Calculate commission
        position_value = entry_price * quantity
        commission = position_value * self.commission_rate
        
        # Check if sufficient balance
        required_balance = position_value + commission
        if required_balance > self.account.current_balance:
            logger.warning(
                f"Insufficient balance: required={required_balance}, "
                f"available={self.account.current_balance}"
            )
            return None
        
        # Create simulated order
        order_id = str(uuid4())
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=entry_price,
            state=OrderState.FILLED,
            filled_qty=quantity,
            avg_fill_price=entry_price
        )
        
        self.orders[order_id] = order
        
        # Create simulated position
        position = Position(
            position_id=str(uuid4()),
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity
        )
        
        self.positions[position.position_id] = position
        
        # Update account balance
        self.account.current_balance -= required_balance
        
        # Record trade
        trade = SimulatedTrade(
            trade_id=position.position_id,
            timestamp=datetime.now(),
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            exit_price=None,
            quantity=quantity,
            commission=commission,
            slippage=analysis.expected_slippage,
            pnl=None,
            status="OPEN",
            entry_reason=reason
        )
        
        self.trade_history.append(trade)
        self.account.total_trades += 1
        
        logger.info(
            f"Paper trade executed: {side.value} {quantity} {symbol} @ {entry_price} "
            f"(slippage: {analysis.expected_slippage:.4f}%, commission: {commission:.2f})"
        )
        
        return position
    
    async def close_position(
        self,
        position_id: str,
        orderbook: Orderbook,
        reason: str = "Close"
    ) -> Optional[Decimal]:
        """
        Close simulated position
        
        Args:
            position_id: Position ID to close
            orderbook: Current orderbook for exit price
            reason: Exit reason for logging
        
        Returns:
            Realized P&L if successful, None if position not found
        """
        if position_id not in self.positions:
            logger.error(f"Position {position_id} not found")
            return None
        
        position = self.positions[position_id]
        
        # Determine exit side (opposite of entry)
        exit_side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
        
        # Calculate exit price with slippage
        analysis = self.cost_filter.analyze_trade(
            orderbook, exit_side.value, position.quantity
        )
        
        exit_price = analysis.avg_fill_price
        
        # Calculate P&L
        pnl = position.calculate_pnl(exit_price)
        
        # Calculate commission
        position_value = exit_price * position.quantity
        commission = position_value * self.commission_rate
        
        # Net P&L after commission
        net_pnl = pnl - commission
        
        # Update account
        self.account.current_balance += position_value + net_pnl
        self.account.realized_pnl += net_pnl
        
        if net_pnl > Decimal("0"):
            self.account.winning_trades += 1
        else:
            self.account.losing_trades += 1
        
        # Update trade record
        for trade in self.trade_history:
            if trade.trade_id == position_id:
                trade.exit_price = exit_price
                trade.pnl = net_pnl
                trade.status = "CLOSED"
                trade.exit_reason = reason
                trade.commission += commission
                break
        
        # Remove position
        del self.positions[position_id]
        
        logger.info(
            f"Paper position closed: {position.side.value} {position.quantity} "
            f"{position.symbol} @ {exit_price} (P&L: {net_pnl:.2f})"
        )
        
        return net_pnl
    
    def get_account_summary(self) -> Dict:
        """Get account summary"""
        win_rate = (
            self.account.winning_trades / self.account.total_trades * 100
            if self.account.total_trades > 0 else 0
        )
        
        return {
            "initial_balance": float(self.account.initial_balance),
            "current_balance": float(self.account.current_balance),
            "equity": float(self.account.equity),
            "total_pnl": float(self.account.total_pnl),
            "realized_pnl": float(self.account.realized_pnl),
            "unrealized_pnl": float(self.account.unrealized_pnl),
            "total_trades": self.account.total_trades,
            "winning_trades": self.account.winning_trades,
            "losing_trades": self.account.losing_trades,
            "win_rate": win_rate,
            "open_positions": len(self.positions)
        }
    
    def get_trade_history(self) -> List[Dict]:
        """Get trade history as list of dicts"""
        return [
            {
                "trade_id": trade.trade_id,
                "timestamp": trade.timestamp.isoformat(),
                "symbol": trade.symbol,
                "side": trade.side.value,
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price) if trade.exit_price else None,
                "quantity": float(trade.quantity),
                "commission": float(trade.commission),
                "slippage": float(trade.slippage),
                "pnl": float(trade.pnl) if trade.pnl else None,
                "status": trade.status,
                "entry_reason": trade.entry_reason,
                "exit_reason": trade.exit_reason
            }
            for trade in self.trade_history
        ]
    
    def export_trades_csv(self, filename: str) -> None:
        """Export trade history to CSV"""
        import csv
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'trade_id', 'timestamp', 'symbol', 'side',
                'entry_price', 'exit_price', 'quantity',
                'commission', 'slippage', 'pnl',
                'status', 'entry_reason', 'exit_reason'
            ])
            
            writer.writeheader()
            writer.writerows(self.get_trade_history())
        
        logger.info(f"Trade history exported to {filename}")
    
    def reset(self) -> None:
        """Reset paper trader to initial state"""
        self.account = SimulatedAccount(
            initial_balance=self.account.initial_balance,
            current_balance=self.account.initial_balance
        )
        self.positions.clear()
        self.orders.clear()
        self.trade_history.clear()
        
        logger.info("Paper trader reset to initial state")
