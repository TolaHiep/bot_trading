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
from ..risk.position_manager import PositionManager
from ..risk.drawdown_monitor import DrawdownMonitor

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
    strategy_name: str = "main"


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
        cost_filter: Optional[CostFilter] = None,
        position_manager: Optional[PositionManager] = None,
        kill_switch = None
    ):
        """
        Initialize Paper Trader
        
        Args:
            initial_balance: Starting balance for simulation
            commission_rate: Commission rate (default: 0.06%)
            cost_filter: Cost filter for slippage calculation
            position_manager: Position manager for capital allocation (optional)
            kill_switch: Kill switch for emergency stop (optional)
        """
        self.account = SimulatedAccount(
            initial_balance=initial_balance,
            current_balance=initial_balance
        )
        self.commission_rate = commission_rate
        self.cost_filter = cost_filter or CostFilter(commission_rate=commission_rate * 100)
        self.position_manager = position_manager
        self.kill_switch = kill_switch
        
        # Drawdown monitoring
        self.drawdown_monitor = DrawdownMonitor(float(initial_balance))
        
        # Tracking
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        self.orders: Dict[str, Order] = {}
        self.trade_history: List[SimulatedTrade] = []
        
        logger.info(
            f"PaperTrader initialized with balance: {initial_balance}, "
            f"commission: {commission_rate*100:.2f}%"
        )
    
    def has_open_position(self, symbol: str, strategy_name: str = "main") -> bool:
        """
        Check if there is an open position for the given symbol and strategy
        
        Args:
            symbol: Trading symbol to check
            strategy_name: Strategy name
        
        Returns:
            True if position exists for symbol and strategy, False otherwise
        """
        return any(pos.symbol == symbol and pos.strategy_name == strategy_name for pos in self.positions.values())
    
    def get_position_by_symbol(self, symbol: str, strategy_name: str = "main") -> Optional[Position]:
        """
        Get the open position for a specific symbol and strategy
        
        Args:
            symbol: Trading symbol
            strategy_name: Strategy name
        
        Returns:
            Position object if found, None otherwise
        """
        for position in self.positions.values():
            if position.symbol == symbol and position.strategy_name == strategy_name:
                return position
        return None
    
    def get_all_positions(self) -> List[Position]:
        """
        Get all open positions
        
        Returns:
            List of all Position objects
        """
        return list(self.positions.values())
    
    async def close_position_by_symbol(
        self,
        symbol: str,
        orderbook: Orderbook,
        reason: str = "Close",
        strategy_name: str = "main"
    ) -> Optional[Decimal]:
        """
        Close position by symbol
        
        Args:
            symbol: Trading symbol
            orderbook: Current orderbook for exit price
            reason: Exit reason for logging
        
        Returns:
            Realized P&L if successful, None if position not found
        """
        position = self.get_position_by_symbol(symbol, strategy_name)
        if position is None:
            logger.error(f"No open position found for symbol {symbol} strategy {strategy_name}")
            return None
        
        return await self.close_position(position.position_id, orderbook, reason)
    
    async def execute_signal(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        orderbook: Orderbook,
        reason: str = "Signal",
        strategy_name: str = "main",
        leverage: Decimal = Decimal("1.0")
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
        # Check if position already exists for this symbol and strategy
        if self.has_open_position(symbol, strategy_name):
            logger.warning(
                f"Paper trade rejected: Position already exists for {symbol} ({strategy_name})"
            )
            return None
        
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
        
        # Check capital allocation with PositionManager if available
        if self.position_manager is not None:
            can_open, allocation_reason = self.position_manager.can_open_position(
                symbol, position_value
            )
            if not can_open:
                logger.warning(
                    f"Paper trade rejected by PositionManager: {allocation_reason}"
                )
                return None
        
        # Check if sufficient balance (with leverage)
        # CROSS MARGIN: Use equity (balance + unrealized PnL) instead of just balance
        # This allows unrealized profit to be used as margin for new positions
        
        # Calculate current equity (balance + unrealized PnL from all positions)
        current_prices_for_equity = {pos.symbol: Decimal(str(pos.entry_price)) for pos in self.positions.values()}
        self.account.update_equity(list(self.positions.values()), current_prices_for_equity)
        available_margin = self.account.equity  # Use equity instead of current_balance
        
        # Margin required = position_value / leverage
        margin_required = position_value / leverage if leverage > Decimal("1.0") else position_value
        required_balance = margin_required + commission
        
        if required_balance > available_margin:
            logger.warning(
                f"Insufficient margin (CROSS): required={required_balance:.2f} (margin={margin_required:.2f} + commission={commission:.2f}), "
                f"available={available_margin:.2f} (balance={self.account.current_balance:.2f} + unrealized={self.account.unrealized_pnl:.2f}), "
                f"leverage={leverage}x"
            )
            return None
        
        logger.info(
            f"Opening position with CROSS margin: "
            f"required={required_balance:.2f}, available={available_margin:.2f}, "
            f"balance={self.account.current_balance:.2f}, unrealized_pnl={self.account.unrealized_pnl:.2f}"
        )
        
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
            avg_fill_price=entry_price,
            strategy_name=strategy_name
        )
        
        self.orders[order_id] = order
        
        # Create simulated position
        position = Position(
            position_id=str(uuid4()),
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            strategy_name=strategy_name,
            margin_locked=required_balance,  # Store locked margin + commission
            leverage=leverage
        )
        
        self.positions[position.position_id] = position
        
        # Add position to PositionManager if available
        if self.position_manager is not None:
            success = self.position_manager.add_position(
                symbol, quantity, entry_price
            )
            if not success:
                # Rollback position creation
                del self.positions[position.position_id]
                del self.orders[order_id]
                logger.error(
                    f"Failed to add position to PositionManager for {symbol}"
                )
                return None
        
        # Update account balance (deduct margin + commission)
        self.account.current_balance -= required_balance
        
        # Update drawdown monitor
        self.drawdown_monitor.update_balance(float(self.account.current_balance))
        
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
            entry_reason=reason,
            strategy_name=strategy_name
        )
        
        self.trade_history.append(trade)
        self.account.total_trades += 1
        
        logger.info(
            f"Paper trade executed: {side.value} {quantity} {symbol} @ {entry_price} "
            f"(slippage: {analysis.expected_slippage:.4f}%, commission: {commission:.2f})"
        )
        
        # Telegram notification disabled - use /scalp, /scalp_v2, /wyckoff commands for reports
        
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
        
        # Update account: Return locked margin + net P&L
        # When we opened: balance -= margin_locked (which included entry commission)
        # When we close: balance += margin_locked + net_pnl
        self.account.current_balance += position.margin_locked + net_pnl
        self.account.realized_pnl += net_pnl
        
        # Update drawdown monitor
        self.drawdown_monitor.update_balance(float(self.account.current_balance))
        
        # Track win/loss
        if net_pnl > Decimal("0"):
            self.account.winning_trades += 1
        else:
            self.account.losing_trades += 1
        
        # Update kill switch if available
        if self.kill_switch:
            self.kill_switch.record_trade(profit=float(net_pnl))
            drawdown_metrics = self.drawdown_monitor.get_metrics()
            self.kill_switch.update_state(
                balance=float(self.account.current_balance),
                daily_drawdown=drawdown_metrics.daily_drawdown
            )
        
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
        
        # Remove position from PositionManager if available
        if self.position_manager is not None:
            self.position_manager.remove_position(position.symbol)
        
        logger.info(
            f"Paper position closed: {position.side.value} {position.quantity} "
            f"{position.symbol} @ {exit_price} (P&L: {net_pnl:.2f})"
        )
        
        # Telegram notification disabled - use /scalp, /scalp_v2, /wyckoff commands for reports
        
        return net_pnl
    
    def get_account_summary(self, current_prices: Optional[Dict[str, Decimal]] = None) -> Dict:
        """Get account summary with updated equity
        
        Args:
            current_prices: Dict of symbol -> current price for unrealized PnL calculation
        """
        # Always update equity if we have positions
        if self.positions:
            if current_prices:
                # Update with provided prices
                self.account.update_equity(list(self.positions.values()), current_prices)
            else:
                # If no prices provided, try to use last known prices from positions
                # This ensures equity is at least calculated with entry prices
                last_prices = {pos.symbol: pos.entry_price for pos in self.positions.values()}
                self.account.update_equity(list(self.positions.values()), last_prices)
        else:
            # No positions, equity = balance
            self.account.equity = self.account.current_balance
            self.account.unrealized_pnl = Decimal("0")
        
        win_rate = (
            self.account.winning_trades / self.account.total_trades * 100
            if self.account.total_trades > 0 else 0
        )
        
        return {
            "initial_balance": float(self.account.initial_balance),
            "current_balance": float(self.account.current_balance),
            "equity": float(self.account.equity),
            "available_margin": float(self.account.equity),  # CROSS MARGIN: equity is available margin
            "total_pnl": float(self.account.total_pnl),
            "realized_pnl": float(self.account.realized_pnl),
            "unrealized_pnl": float(self.account.unrealized_pnl),
            "total_trades": self.account.total_trades,
            "winning_trades": self.account.winning_trades,
            "losing_trades": self.account.losing_trades,
            "win_rate": win_rate,
            "open_positions": len(self.positions)
        }
    
    def get_strategy_summary(self, strategy_name: str) -> Dict:
        """Get summary string specifically for a strategy"""
        trades = [t for t in self.trade_history if t.strategy_name == strategy_name]
        pos = [p for p in self.positions.values() if p.strategy_name == strategy_name]
        
        total_trades = len(trades)
        winning = len([t for t in trades if getattr(t, 'pnl', 0) is not None and float(getattr(t, 'pnl', 0) or 0) > 0])
        losing = len([t for t in trades if getattr(t, 'pnl', 0) is not None and float(getattr(t, 'pnl', 0) or 0) < 0])
        total_pnl = sum([float(getattr(t, 'pnl', 0) or 0) for t in trades if getattr(t, 'pnl', 0) is not None])
        
        # Calculate unrealized pnl roughly, wait PaperTrader calculate_pnl needs exit_price. 
        # But we just return what we can since telegram bot usually requests it globally.
        return {
            "total_trades": total_trades,
            "winning_trades": winning,
            "losing_trades": losing,
            "win_rate": (winning / total_trades * 100) if total_trades > 0 else 0,
            "realized_pnl": total_pnl,
            "open_positions": len(pos)
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
                "exit_reason": trade.exit_reason,
                "strategy_name": trade.strategy_name
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
                'status', 'entry_reason', 'exit_reason', 'strategy_name'
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
