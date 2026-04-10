"""
Multi-Symbol Manager - Quản lý trading cùng lúc nhiều cặp giao dịch
"""

import asyncio
import logging
from typing import Dict, List, Optional
from decimal import Decimal

from src.connectors.bybit_ws import WebSocketManager
from src.alpha.signal_engine import SignalGenerator, SignalType
from src.execution.paper_trader import PaperTrader
from src.execution.cost_filter import CostFilter, Orderbook, OrderbookLevel
from src.execution.order_manager import OrderSide
from src.risk.position_manager import PositionManager

logger = logging.getLogger(__name__)

class MultiSymbolManager:
    """Manages multiple symbols for trading
    Handles:
    - Independent signal generators for each symbol
    - Subscription matrix
    - Position limits across portfolio
    """

    def __init__(
        self,
        ws_manager: WebSocketManager,
        paper_trader: PaperTrader,
        position_manager: PositionManager
    ):
        self.ws_manager = ws_manager
        self.paper_trader = paper_trader
        self.position_manager = position_manager
        
        self.active_symbols: List[str] = []
        self.signal_engines: Dict[str, SignalGenerator] = {}
        
        self.current_prices: Dict[str, float] = {}
        self.current_orderbooks: Dict[str, Orderbook] = {}
        
        # Register main callbacks to process multi symbol streams
        self.ws_manager.register_callback("kline", self._on_kline)
        self.ws_manager.register_callback("trade", self._on_trade)
        self.ws_manager.register_callback("orderbook", self._on_orderbook)

    def get_active_symbols(self) -> List[str]:
        return self.active_symbols

    def get_signal_engine(self, symbol: str) -> Optional[SignalGenerator]:
        return self.signal_engines.get(symbol)

    async def add_symbol(self, symbol: str) -> bool:
        """Add a new symbol to trading logic"""
        if symbol in self.active_symbols:
            return False
            
        logger.info(f"Adding multi-symbol monitoring for {symbol}")
        self.active_symbols.append(symbol)
        self.signal_engines[symbol] = SignalGenerator(symbol=symbol)
        
        await self.ws_manager.subscribe("kline.1", symbol)
        await self.ws_manager.subscribe("kline.5", symbol)
        await self.ws_manager.subscribe("kline.15", symbol)
        await self.ws_manager.subscribe("trade", symbol)
        await self.ws_manager.subscribe("orderbook.50", symbol)
        
        return True

    async def remove_symbol(self, symbol: str) -> bool:
        """Remove a symbol from monitoring"""
        if symbol not in self.active_symbols:
            return False
            
        logger.info(f"Removing multi-symbol monitoring for {symbol}")
        self.active_symbols.remove(symbol)
        if symbol in self.signal_engines:
            del self.signal_engines[symbol]
        if symbol in self.current_prices:
            del self.current_prices[symbol]
        if symbol in self.current_orderbooks:
            del self.current_orderbooks[symbol]
            
        # Try unsubscribe
        try:
            await self.ws_manager.unsubscribe("kline.1", symbol)
            await self.ws_manager.unsubscribe("kline.5", symbol)
            await self.ws_manager.unsubscribe("kline.15", symbol)
            await self.ws_manager.unsubscribe("trade", symbol)
            await self.ws_manager.unsubscribe("orderbook.50", symbol)
        except Exception as e:
            logger.debug(f"Unsubscribe ignored: {e}")
            
        return True

    async def _on_kline(self, message: dict) -> None:
        try:
            topic = message["topic"]
            data = message["data"][0]
            
            # topic = kline.1.BTCUSDT
            parts = topic.split(".")
            timeframe_raw = parts[1]
            timeframe = f"{timeframe_raw}m"
            symbol = parts[2]
            
            if symbol not in self.active_symbols:
                return
                
            timestamp = int(data["start"])
            open_price = float(data["open"])
            high = float(data["high"])
            low = float(data["low"])
            close = float(data["close"])
            volume = float(data["volume"])
            
            self.current_prices[symbol] = close
            
            engine = self.signal_engines.get(symbol)
            if engine:
                trading_signal = engine.add_kline(
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open_price=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume
                )
                
                if trading_signal and not trading_signal.suppressed:
                    await self._execute_signal(symbol, trading_signal)
                    
        except Exception as e:
            logger.error(f"MultiSymbol error processing kline: {e}")

    async def _on_trade(self, message: dict) -> None:
        try:
            topic = message["topic"]
            symbol = topic.split(".")[-1]
            
            if symbol not in self.active_symbols:
                return
                
            data = message["data"][0]
            timestamp = int(data["T"])
            price = float(data["p"])
            quantity = float(data["v"])
            side = data["S"]
            
            engine = self.signal_engines.get(symbol)
            if engine:
                engine.add_trade("1m", timestamp, price, quantity, side)
                
        except Exception as e:
            pass

    async def _on_orderbook(self, message: dict) -> None:
        try:
            import time
            topic = message["topic"]
            symbol = topic.split(".")[-1]
            
            if symbol not in self.active_symbols:
                return
                
            ts = message.get("ts", int(time.time() * 1000))
            data = message["data"]
            bids = [OrderbookLevel(price=Decimal(str(b[0])), quantity=Decimal(str(b[1]))) for b in data.get("b", [])]
            asks = [OrderbookLevel(price=Decimal(str(a[0])), quantity=Decimal(str(a[1]))) for a in data.get("a", [])]
            
            current_ob = self.current_orderbooks.get(symbol)
            if not current_ob or message.get("type") == "snapshot":
                self.current_orderbooks[symbol] = Orderbook(symbol=symbol, bids=bids, asks=asks, timestamp=ts)
            else:
                self.current_orderbooks[symbol] = Orderbook(
                    symbol=symbol,
                    bids=bids if bids else current_ob.bids,
                    asks=asks if asks else current_ob.asks,
                    timestamp=ts
                )
                
        except Exception as e:
            pass

    async def _execute_signal(self, symbol: str, trading_signal) -> None:
        try:
            orderbook = self.current_orderbooks.get(symbol)
            if not orderbook:
                logger.debug(f"[{symbol}] No orderbook data available to execute signal")
                return
                
            if trading_signal.signal_type == SignalType.BUY:
                side = OrderSide.BUY
            elif trading_signal.signal_type == SignalType.SELL:
                side = OrderSide.SELL
            else:
                return
                
            account_summary = self.paper_trader.get_account_summary()
            balance = Decimal(str(account_summary["current_balance"]))
            
            # Since max_position is handled by PositionManager internally via total equity limit,
            # we need to simulate a position value requested
            # Default risk config for multi-symbol
            max_pos_value = balance * self.position_manager.max_position_pct
            
            allowed, reason = self.position_manager.can_open_position(
                symbol=symbol,
                position_value=max_pos_value
            )
            
            if not allowed:
                logger.info(f"[{symbol}] Position rejected: {reason}")
                return
                
            max_quantity = max_pos_value / Decimal(str(trading_signal.price))
                
            position = await self.paper_trader.execute_signal(
                symbol=symbol,
                side=side,
                quantity=max_quantity,
                orderbook=orderbook,
                reason=f"MultiSymbol: {trading_signal.reason}"
            )
            
            if position:
                logger.info(f"✅ [{symbol}] Multi-position opened: {side.value} {position.quantity} @ {position.entry_price}")
                
        except Exception as e:
            logger.error(f"[{symbol}] Error executing multi-signal: {e}")
