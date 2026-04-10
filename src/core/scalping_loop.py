"""
Scalping Loop - Chạy chiến lược đánh siêu tốc 1m
Hỗ trợ multi-symbol scalping
"""

import asyncio
import logging
import os
from decimal import Decimal
from typing import Optional, Dict, List

from src.connectors.bybit_ws import WebSocketManager
from src.connectors.bybit_rest import RESTClient
from src.alpha.scalping_engine import ScalpingSignalGenerator
from src.alpha.signal_engine import SignalType
from src.execution.paper_trader import PaperTrader
from src.execution.cost_filter import Orderbook, OrderbookLevel
from src.execution.order_manager import OrderSide
from src.risk.stop_loss import StopLossEngine, StopLossConfig, StopLossMode, PositionSide as SLPositionSide

logger = logging.getLogger(__name__)

class ScalpingLoop:
    """Scalping trading loop (1m timeframe)
    Supports multi-symbol scalping
    """
    
    def __init__(
        self,
        paper_trader: PaperTrader,
        symbols: List[str] = None,
        testnet: bool = True,
        config_path: str = "config/config.yaml"
    ):
        self.symbols = symbols or ["BTCUSDT"]
        self.running = False
        self.testnet = testnet
        self.paper_trader = paper_trader
        
        # Load scalping config
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        scalping_config = config.get('scalping', {})
        self.risk_per_trade = scalping_config.get('risk_per_trade', 0.01)
        self.leverage = scalping_config.get('leverage', 1.0)  # Default 1x (no leverage)
        
        logger.info(f"Scalping config: risk={self.risk_per_trade*100}%, leverage={self.leverage}x")
        
        # WebSocket manager
        self.ws_manager = WebSocketManager(testnet=testnet)
        
        # Initialize Stop Loss Engine
        api_key = os.getenv("BYBIT_API_KEY", "")
        api_secret = os.getenv("BYBIT_API_SECRET", "")
        rest_client = RESTClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
        
        risk_config = config.get('risk', {})
        stop_loss_config = StopLossConfig(
            mode=StopLossMode.TRAILING,
            initial_stop_pct=risk_config.get("initial_stop_loss_pct", 0.02),
            breakeven_profit_pct=risk_config.get("breakeven_profit_pct", 0.01),
            trailing_activation_pct=risk_config.get("trailing_activation_pct", 0.02),
            trailing_distance_pct=risk_config.get("trailing_distance_pct", 0.01)
        )
        self.stop_loss_engine = StopLossEngine(
            rest_client=rest_client,
            config=stop_loss_config,
            monitor_interval=1.0
        )
        
        # Set callback to auto-close position when stop loss triggers
        async def on_stop_loss_triggered(position, loss):
            logger.warning(
                f"🛑 [SCALP] Stop Loss triggered for {position.symbol}! "
                f"Loss: ${loss:.2f}, closing position..."
            )
            
            # Get current orderbook
            orderbook = self.current_orderbooks.get(position.symbol)
            
            if orderbook:
                # Close position
                await self.paper_trader.close_position_by_symbol(
                    symbol=position.symbol,
                    orderbook=orderbook,
                    reason=f"Stop Loss triggered (loss: ${loss:.2f})",
                    strategy_name="scalp"
                )
                
                # Remove from stop loss engine
                await self.stop_loss_engine.remove_position(position.symbol)
            else:
                logger.error(f"[SCALP] No orderbook available for {position.symbol}, cannot close position")
        
        self.stop_loss_engine.set_callbacks(on_stop_triggered=on_stop_loss_triggered)
        
        logger.info(
            f"Scalping Stop Loss Engine initialized: mode={stop_loss_config.mode.value}, "
            f"initial_stop={stop_loss_config.initial_stop_pct*100}%, "
            f"breakeven_move={stop_loss_config.breakeven_profit_pct*100}%"
        )
        
        # Signal generators per symbol
        self.signal_generators: Dict[str, ScalpingSignalGenerator] = {}
        for symbol in self.symbols:
            self.signal_generators[symbol] = ScalpingSignalGenerator(symbol=symbol)
        
        # Current prices and orderbooks per symbol
        self.current_prices: Dict[str, float] = {}
        self.current_orderbooks: Dict[str, Orderbook] = {}

    async def start(self) -> None:
        """Start scalping loop"""
        logger.info(f"Starting ScalpingLoop for {len(self.symbols)} symbols: {', '.join(self.symbols[:5])}{'...' if len(self.symbols) > 5 else ''}")
        self.running = True
        
        try:
            await self.ws_manager.connect()
            
            # Register callbacks
            self.ws_manager.register_callback("kline", self._on_kline)
            self.ws_manager.register_callback("orderbook", self._on_orderbook)
            
            # Subscribe 1m kline and orderbook.50 for all symbols
            for symbol in self.symbols:
                await self.ws_manager.subscribe("kline.1", symbol)
                await self.ws_manager.subscribe("orderbook.50", symbol)
                logger.info(f"[SCALP] Subscribed to {symbol}")
            
            logger.info(f"ScalpingLoop started successfully with {len(self.symbols)} symbols")
            
            # Start stop loss monitoring
            await self.stop_loss_engine.start_monitoring()
            
            while self.running:
                await asyncio.sleep(1)
            
            # Stop stop loss monitoring
            await self.stop_loss_engine.stop_monitoring()
                
        except Exception as e:
            logger.error(f"Error in scalping loop: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop scalping loop"""
        logger.info("Stopping ScalpingLoop...")
        self.running = False
        await self.ws_manager.disconnect()
    
    async def add_symbol(self, symbol: str):
        """Add a new symbol to scalping
        
        Args:
            symbol: Trading symbol to add
        """
        if symbol in self.symbols:
            return
        
        logger.info(f"[SCALP] Adding new symbol: {symbol}")
        self.symbols.append(symbol)
        
        # Create signal generator
        self.signal_generators[symbol] = ScalpingSignalGenerator(symbol=symbol)
        
        # Subscribe to WebSocket
        if self.running:
            await self.ws_manager.subscribe("kline.1", symbol)
            await self.ws_manager.subscribe("orderbook.50", symbol)
            logger.info(f"[SCALP] Subscribed to {symbol}")
    
    async def remove_symbol(self, symbol: str):
        """Remove a symbol from scalping
        
        Args:
            symbol: Trading symbol to remove
        """
        if symbol not in self.symbols:
            return
        
        logger.info(f"[SCALP] Removing symbol: {symbol}")
        self.symbols.remove(symbol)
        
        # Remove signal generator
        if symbol in self.signal_generators:
            del self.signal_generators[symbol]
        
        # Remove orderbook
        if symbol in self.current_orderbooks:
            del self.current_orderbooks[symbol]
        
        # Remove price
        if symbol in self.current_prices:
            del self.current_prices[symbol]

    async def _on_kline(self, message: dict) -> None:
        try:
            data = message["data"][0]
            topic = message["topic"]
            
            # Extract symbol from topic (e.g., "kline.1.BTCUSDT" -> "BTCUSDT")
            parts = topic.split(".")
            symbol = parts[2] if len(parts) > 2 else parts[-1]
            
            if symbol not in self.signal_generators:
                return
            
            timestamp = int(data["start"])
            open_price = float(data["open"])
            high = float(data["high"])
            low = float(data["low"])
            close = float(data["close"])
            volume = float(data["volume"])
            
            self.current_prices[symbol] = close
            
            # Update stop loss engine with current price
            if symbol in self.stop_loss_engine.positions:
                await self.stop_loss_engine.update_position(symbol, close)
            
            trading_signal = self.signal_generators[symbol].add_kline(
                timeframe="1m",
                timestamp=timestamp,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
            
            if trading_signal:
                await self._execute_signal(symbol, trading_signal)
                
        except Exception as e:
            logger.error(f"Error processing scalping kline: {e}")

    async def _on_orderbook(self, message: dict) -> None:
        try:
            import time
            ts = message.get("ts", int(time.time() * 1000))
            data = message["data"]
            topic = message["topic"]
            
            # Extract symbol from topic (e.g., "orderbook.50.BTCUSDT" -> "BTCUSDT")
            parts = topic.split(".")
            symbol = parts[2] if len(parts) > 2 else parts[-1]
            
            if symbol not in self.symbols:
                return
            
            # Bybit v5 snapshot or delta
            bids = [OrderbookLevel(price=Decimal(str(b[0])), quantity=Decimal(str(b[1]))) for b in data.get("b", [])]
            asks = [OrderbookLevel(price=Decimal(str(a[0])), quantity=Decimal(str(a[1]))) for a in data.get("a", [])]
            
            if symbol not in self.current_orderbooks or message.get("type") == "snapshot":
                self.current_orderbooks[symbol] = Orderbook(
                    symbol=symbol,
                    bids=bids,
                    asks=asks,
                    timestamp=ts
                )
            else:
                # Update orderbook with new data
                prev_orderbook = self.current_orderbooks[symbol]
                self.current_orderbooks[symbol] = Orderbook(
                    symbol=symbol,
                    bids=bids if bids else prev_orderbook.bids,
                    asks=asks if asks else prev_orderbook.asks,
                    timestamp=ts
                )
        except Exception as e:
            logger.error(f"Error processing scalping orderbook: {e}")

    async def _execute_signal(self, symbol: str, trading_signal) -> None:
        """Execute scalping signal - Notification handled by PaperTrader"""
        try:
            # Kill switch disabled for scalping - only check paper trader's kill switch
            # (which is only for Wyckoff bot)
            
            logger.info(f"\n[SCALP] SIGNAL DETECTED for {symbol}: {trading_signal.signal_type.value}")

            if symbol not in self.current_orderbooks:
                logger.warning(f"[SCALP] No orderbook data available for {symbol}")
                return
            
            if trading_signal.signal_type == SignalType.BUY:
                side = OrderSide.BUY
            elif trading_signal.signal_type == SignalType.SELL:
                side = OrderSide.SELL
            else:
                return
            
            # Get current prices for PnL calculation
            current_prices = {s: Decimal(str(p)) for s, p in self.current_prices.items() if p}
            account_summary = self.paper_trader.get_account_summary(current_prices)
            
            # CROSS MARGIN: Use equity (balance + unrealized PnL) for position sizing
            available_margin = account_summary["available_margin"]
            
            # Use risk_per_trade from config (e.g., 5%) and leverage
            risk_pct = self.risk_per_trade
            leverage = self.leverage
            
            # Calculate quantity with leverage using available margin (equity)
            # Formula: quantity = (equity × risk_pct × leverage) / price
            quantity = (Decimal(str(available_margin)) * Decimal(str(risk_pct)) * Decimal(str(leverage))) / Decimal(str(trading_signal.price))
            
            logger.info(
                f"[SCALP] Position sizing (CROSS): equity=${available_margin:.2f} "
                f"(balance=${account_summary['current_balance']:.2f} + unrealized=${account_summary['unrealized_pnl']:.2f}), "
                f"risk={risk_pct*100}%, leverage={leverage}x, qty={quantity:.6f}"
            )
            
            # Thực thi mua / bán - PaperTrader sẽ tự động gửi notification
            position = await self.paper_trader.execute_signal(
                symbol=symbol,
                side=side,
                quantity=quantity,
                orderbook=self.current_orderbooks[symbol],
                reason=f"Scalping: {trading_signal.reason}",
                strategy_name="scalp",
                leverage=Decimal(str(leverage))
            )
            
            if position:
                logger.info(f"[SCALP] ✅ Position opened: {side.value} {position.quantity} {symbol} @ {position.entry_price}")
                
                # Add position to Stop Loss Engine
                sl_side = SLPositionSide.LONG if side == OrderSide.BUY else SLPositionSide.SHORT
                await self.stop_loss_engine.add_position(
                    symbol=symbol,
                    side=sl_side,
                    entry_price=float(position.entry_price),
                    quantity=float(position.quantity),
                    current_price=float(position.entry_price)
                )
                logger.info(f"[SCALP] Stop loss added for {symbol}")
            else:
                logger.warning(f"[SCALP] ❌ Failed to open position for {symbol}")
                
        except Exception as e:
            logger.error(f"Error executing scalping signal for {symbol}: {e}")
