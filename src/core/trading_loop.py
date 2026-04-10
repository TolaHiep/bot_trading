"""
Main Trading Loop - Kết nối tất cả modules thành hệ thống tự động

Luồng hoạt động:
1. WebSocket nhận kline/trade data từ Bybit
2. SignalGenerator phân tích và tạo tín hiệu
3. PaperTrader thực thi tín hiệu (paper mode)
4. Hiển thị balance, signals, trades realtime

Hỗ trợ 2 chế độ:
- Single-symbol mode: Trade 1 symbol (BTCUSDT)
- Multi-symbol mode: Scan và trade nhiều symbols đồng thời
"""

import asyncio
import json
import logging
import os
import signal
import sys
import psutil
import yaml
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pathlib import Path

from src.connectors.bybit_ws import WebSocketManager
from src.connectors.bybit_rest import RESTClient
from src.alpha.signal_engine import SignalGenerator, SignalType
from src.execution.paper_trader import PaperTrader
from src.execution.cost_filter import CostFilter, Orderbook, OrderbookLevel
from src.execution.order_manager import OrderSide, OrderType
from src.risk.position_sizing import PositionSizer
from src.risk.kill_switch import KillSwitch, KillSwitchConfig
from src.risk.stop_loss import StopLossEngine, StopLossConfig, StopLossMode, PositionSide as SLPositionSide
from src.monitoring.metrics_collector import MetricsCollector
from src.monitoring.account_monitor import AccountMonitor

logger = logging.getLogger(__name__)


class TradingLoop:
    """Main trading loop orchestrator
    
    Supports two modes:
    - Single-symbol mode: Trade one symbol (default: BTCUSDT)
    - Multi-symbol mode: Scan and trade multiple symbols simultaneously
    """
    
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        initial_balance: Decimal = Decimal("100"),
        testnet: bool = True,
        config_path: str = "config/config.yaml"
    ):
        """Initialize trading loop
        
        Args:
            symbol: Trading symbol (used in single-symbol mode)
            initial_balance: Initial paper trading balance
            testnet: Use testnet (True) or mainnet (False)
            config_path: Path to configuration file
        """
        self.symbol = symbol
        self.running = False
        self.testnet = testnet
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Determine mode
        self.multi_symbol_enabled = self.config.get("multi_symbol", {}).get("enabled", False)
        
        # Initialize components
        self.ws_manager = WebSocketManager(testnet=testnet)
        
        # Initialize Kill Switch first
        risk_config = self.config.get("risk", {})
        self.kill_switch = KillSwitch(
            config=KillSwitchConfig(
                max_daily_drawdown=risk_config.get("kill_switch_daily_dd", 0.05),
                max_consecutive_losses=risk_config.get("kill_switch_consecutive_losses", 5)
            )
        )
        logger.info(f"Kill Switch initialized: max_dd={risk_config.get('kill_switch_daily_dd', 0.05)*100}%, max_losses={risk_config.get('kill_switch_consecutive_losses', 5)}")
        
        # Initialize Stop Loss Engine
        # Get API credentials for REST client (needed for placing stop orders)
        api_key = os.getenv("BYBIT_API_KEY", "")
        api_secret = os.getenv("BYBIT_API_SECRET", "")
        rest_client = RESTClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
        
        stop_loss_config = StopLossConfig(
            mode=StopLossMode.TRAILING,  # Use trailing stop loss
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
                f"🛑 Stop Loss triggered for {position.symbol}! "
                f"Loss: ${loss:.2f}, closing position..."
            )
            
            # Get current orderbook
            if self.multi_symbol_enabled and self.multi_symbol_manager:
                orderbook = self.multi_symbol_manager.current_orderbooks.get(position.symbol)
            elif position.symbol == self.symbol:
                orderbook = self.current_orderbook
            else:
                orderbook = None
            
            if orderbook:
                # Close position
                await self.paper_trader.close_position_by_symbol(
                    symbol=position.symbol,
                    orderbook=orderbook,
                    reason=f"Stop Loss triggered (loss: ${loss:.2f})"
                )
                
                # Remove from stop loss engine
                await self.stop_loss_engine.remove_position(position.symbol)
            else:
                logger.error(f"No orderbook available for {position.symbol}, cannot close position")
        
        self.stop_loss_engine.set_callbacks(on_stop_triggered=on_stop_loss_triggered)
        
        logger.info(
            f"Stop Loss Engine initialized: mode={stop_loss_config.mode.value}, "
            f"initial_stop={stop_loss_config.initial_stop_pct*100}%, "
            f"breakeven_move={stop_loss_config.breakeven_profit_pct*100}%, "
            f"trailing_activation={stop_loss_config.trailing_activation_pct*100}%"
        )
        
        # Initialize PaperTrader with kill_switch
        self.paper_trader = PaperTrader(
            initial_balance=initial_balance,
            kill_switch=self.kill_switch
        )
        self.position_sizer = PositionSizer()
        self.metrics_collector = MetricsCollector()
        
        # Initialize Account Monitor
        self.account_monitor = AccountMonitor(
            paper_trader=self.paper_trader,
            initial_balance=initial_balance,
            liquidation_threshold=Decimal("5.0")  # Trigger when equity < $5
        )
        logger.info("Account Monitor initialized: will auto-reset if equity < $5")
        
        # Mode-specific initialization
        if self.multi_symbol_enabled:
            # Multi-symbol mode
            from src.core.symbol_scanner import SymbolScanner
            from src.core.multi_symbol_manager import MultiSymbolManager
            from src.risk.position_manager import PositionManager
            
            # Get API credentials from environment
            api_key = os.getenv("BYBIT_API_KEY", "")
            api_secret = os.getenv("BYBIT_API_SECRET", "")
            
            rest_client = RESTClient(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet
            )
            volume_threshold = self.config.get("multi_symbol", {}).get("volume_threshold", 10_000_000)
            filters_config = self.config.get("multi_symbol", {}).get("filters", {})
            
            self.symbol_scanner = SymbolScanner(
                rest_client=rest_client,
                volume_threshold=volume_threshold,
                filters_config=filters_config
            )
            
            max_position_pct = self.config.get("multi_symbol", {}).get("max_position_pct", 0.05)
            max_exposure_pct = self.config.get("multi_symbol", {}).get("max_total_exposure", 0.80)
            
            self.position_manager = PositionManager(
                initial_equity=initial_balance,
                max_position_pct=max_position_pct,
                max_exposure_pct=max_exposure_pct
            )
            
            self.multi_symbol_manager = MultiSymbolManager(
                ws_manager=self.ws_manager,
                paper_trader=self.paper_trader,
                position_manager=self.position_manager
            )
            
            self.signal_generator = None  # Not used in multi-symbol mode
            self.current_price = None
            self.current_orderbook = None
            
            logger.info(
                f"TradingLoop initialized in MULTI-SYMBOL mode: "
                f"volume_threshold=${volume_threshold:,.0f}, "
                f"max_position={max_position_pct*100:.1f}%, "
                f"max_exposure={max_exposure_pct*100:.1f}%"
            )
        else:
            # Single-symbol mode
            self.signal_generator = SignalGenerator(symbol=symbol)
            self.symbol_scanner = None
            self.multi_symbol_manager = None
            self.position_manager = None
            
            # Current market data
            self.current_price: Optional[float] = None
            self.current_orderbook: Optional[Orderbook] = None
            
            logger.info(
                f"TradingLoop initialized in SINGLE-SYMBOL mode: {symbol}"
            )
        
        # Track start time for uptime
        self.start_time = datetime.now()
        
        # Memory monitoring
        self.process = psutil.Process()
        self.memory_warning_threshold = 800 * 1024 * 1024  # 800MB in bytes
        self.last_memory_log_time = datetime.now()
        
        logger.info(
            f"balance={initial_balance} USDT, "
            f"mode={'testnet' if testnet else 'mainnet'}"
        )
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file
        
        Args:
            config_path: Path to config file
            
        Returns:
            Configuration dictionary
        """
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Configuration loaded from {config_path}")
                    return config or {}
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return {}
    
    async def start(self) -> None:
        """Start trading loop"""
        logger.info("Starting trading loop...")
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Connect WebSocket
            await self.ws_manager.connect()
            
            if self.multi_symbol_enabled:
                # Multi-symbol mode
                await self._start_multi_symbol_mode()
            else:
                # Single-symbol mode
                await self._start_single_symbol_mode()
        
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            raise
        finally:
            await self.stop()
    
    async def _start_single_symbol_mode(self) -> None:
        """Start single-symbol trading mode"""
        logger.info(f"Starting single-symbol mode for {self.symbol}")
        
        # Register callbacks
        self.ws_manager.register_callback("kline", self._on_kline)
        self.ws_manager.register_callback("trade", self._on_trade)
        self.ws_manager.register_callback("orderbook", self._on_orderbook)
        
        # Subscribe to channels
        await self.ws_manager.subscribe("kline.1", self.symbol)
        await self.ws_manager.subscribe("kline.5", self.symbol)
        await self.ws_manager.subscribe("kline.15", self.symbol)
        await self.ws_manager.subscribe("trade", self.symbol)
        await self.ws_manager.subscribe("orderbook.50", self.symbol)
        
        logger.info("Single-symbol mode started successfully")
        
        # Start stop loss monitoring
        await self.stop_loss_engine.start_monitoring()
        
        # Start memory monitoring task
        memory_task = asyncio.create_task(self._monitor_memory())
        
        # Print status every 10 seconds
        while self.running:
            await asyncio.sleep(10)
            self._print_status()
        
        # Stop stop loss monitoring
        await self.stop_loss_engine.stop_monitoring()
        
        # Cancel memory monitoring task
        memory_task.cancel()
        try:
            await memory_task
        except asyncio.CancelledError:
            pass
    
    async def _start_multi_symbol_mode(self) -> None:
        """Start multi-symbol trading mode"""
        logger.info("Starting multi-symbol mode")
        
        # Fetch initial symbols
        logger.info("Fetching symbols from Bybit...")
        symbols = await self.symbol_scanner.fetch_symbols()
        logger.info(f"Found {len(symbols)} symbols matching criteria")
        
        # Add symbols to multi-symbol manager
        for symbol in symbols:
            await self.multi_symbol_manager.add_symbol(symbol)
        
        logger.info(f"Multi-symbol mode started with {len(symbols)} symbols")
        
        # If scalping loop exists, add all symbols to it
        if hasattr(self, 'scalping_loop') and self.scalping_loop:
            logger.info(f"Adding {len(symbols)} symbols to scalping loop...")
            for symbol in symbols:
                await self.scalping_loop.add_symbol(symbol)
            logger.info(f"Scalping loop now monitoring {len(self.scalping_loop.symbols)} symbols")
        
        # If scalping loop V2 exists, add all symbols to it
        if hasattr(self, 'scalping_loop_v2') and self.scalping_loop_v2:
            logger.info(f"Adding {len(symbols)} symbols to scalping loop V2...")
            for symbol in symbols:
                await self.scalping_loop_v2.add_symbol(symbol)
            logger.info(f"Scalping loop V2 now monitoring {len(self.scalping_loop_v2.symbols)} symbols")
        
        # Start stop loss monitoring
        await self.stop_loss_engine.start_monitoring()
        
        # Start background tasks
        memory_task = asyncio.create_task(self._monitor_memory())
        refresh_task = asyncio.create_task(self._refresh_symbols_task())
        
        # Print status every 10 seconds
        while self.running:
            await asyncio.sleep(10)
            self._print_status()
        
        # Stop stop loss monitoring
        await self.stop_loss_engine.stop_monitoring()
        
        # Cancel background tasks
        memory_task.cancel()
        refresh_task.cancel()
        try:
            await memory_task
        except asyncio.CancelledError:
            pass
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
    
    async def stop(self) -> None:
        """Stop trading loop"""
        logger.info("Stopping trading loop...")
        self.running = False
        
        # Disconnect WebSocket
        await self.ws_manager.disconnect()
        
        # Print final summary
        self._print_summary()
        
        logger.info("Trading loop stopped")
    
    async def _on_kline(self, message: dict) -> None:
        """Handle kline data"""
        try:
            data = message["data"][0]
            topic = message["topic"]
            
            # Extract timeframe from topic (e.g., "kline.1.BTCUSDT" -> "1m")
            parts = topic.split(".")
            timeframe_raw = parts[1]
            timeframe = f"{timeframe_raw}m"
            
            # Parse kline data
            timestamp = int(data["start"])
            open_price = float(data["open"])
            high = float(data["high"])
            low = float(data["low"])
            close = float(data["close"])
            volume = float(data["volume"])
            
            # Update current price
            self.current_price = close
            
            # Update stop loss engine with current price
            if self.stop_loss_engine and self.symbol in self.stop_loss_engine.positions:
                await self.stop_loss_engine.update_position(self.symbol, close)
            
            # Feed to signal generator
            trading_signal = self.signal_generator.add_kline(
                timeframe=timeframe,
                timestamp=timestamp,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
            
            # Execute signal if generated
            if trading_signal and not trading_signal.suppressed:
                await self._execute_signal(trading_signal)
        
        except Exception as e:
            logger.error(f"Error processing kline: {e}")
    
    async def _on_trade(self, message: dict) -> None:
        """Handle trade data"""
        try:
            data = message["data"][0]
            
            timestamp = int(data["T"])
            price = float(data["p"])
            quantity = float(data["v"])
            side = data["S"]  # "Buy" or "Sell"
            
            # Feed to signal generator for order flow analysis
            # Use 1m timeframe for trade aggregation
            self.signal_generator.add_trade(
                timeframe="1m",
                timestamp=timestamp,
                price=price,
                quantity=quantity,
                side=side
            )
        
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
    
    async def _on_orderbook(self, message: dict) -> None:
        """Handle orderbook data"""
        try:
            import time
            ts = message.get("ts", int(time.time() * 1000))
            data = message["data"]
            # Bybit v5 returns actual prices, order levels
            bids = [OrderbookLevel(price=Decimal(str(b[0])), quantity=Decimal(str(b[1]))) for b in data.get("b", [])]
            asks = [OrderbookLevel(price=Decimal(str(a[0])), quantity=Decimal(str(a[1]))) for a in data.get("a", [])]
            
            if not self.current_orderbook or message.get("type", "") == "snapshot":
                self.current_orderbook = Orderbook(
                    symbol=self.symbol,
                    bids=bids,
                    asks=asks,
                    timestamp=ts
                )
        
        except Exception as e:
            logger.error(f"Error processing orderbook: {e}")
    
    async def _execute_signal(self, trading_signal) -> None:
        """Execute trading signal"""
        try:
            # Check Kill Switch FIRST
            if self.kill_switch.is_active():
                logger.error(
                    f"🚨 KILL SWITCH ACTIVE! Trading disabled. "
                    f"Reason: {self.kill_switch.get_status()['reason']}"
                )
                return
            
            logger.info(
                f"\n{'='*60}\n"
                f"SIGNAL DETECTED: {trading_signal.signal_type.value}\n"
                f"Price: {trading_signal.price:.2f}\n"
                f"Confidence: {trading_signal.confidence:.1f}%\n"
                f"Reason: {trading_signal.reason}\n"
                f"{'='*60}"
            )
            
            # Check if we have orderbook data
            if not self.current_orderbook:
                logger.warning("No orderbook data available, skipping signal")
                return
            
            # Determine order side
            if trading_signal.signal_type == SignalType.BUY:
                side = OrderSide.BUY
            elif trading_signal.signal_type == SignalType.SELL:
                side = OrderSide.SELL
            else:
                return  # NEUTRAL signal
            
            # Calculate position size
            # Get current prices for equity calculation
            if self.multi_symbol_enabled and self.multi_symbol_manager:
                current_prices_dict = {
                    symbol: Decimal(str(price)) 
                    for symbol, price in self.multi_symbol_manager.current_prices.items()
                }
            elif self.current_price:
                current_prices_dict = {self.symbol: Decimal(str(self.current_price))}
            else:
                current_prices_dict = {}
            
            account_summary = self.paper_trader.get_account_summary(current_prices_dict)
            
            # CROSS MARGIN: Use equity (balance + unrealized PnL) for position sizing
            available_margin = account_summary["available_margin"]
            
            # Simple position sizing: 2% risk with 2% stop loss
            stop_loss_pct = 0.02
            if side == OrderSide.BUY:
                stop_loss_price = trading_signal.price * (1 - stop_loss_pct)
            else:
                stop_loss_price = trading_signal.price * (1 + stop_loss_pct)
            
            position_size = self.position_sizer.calculate_position_size(
                balance=available_margin,  # Use equity instead of balance
                entry_price=trading_signal.price,
                stop_loss_price=stop_loss_price,
                signal_confidence=trading_signal.confidence
            )
            
            if position_size.quantity <= 0:
                logger.warning(f"Position size is zero: {position_size.reason}")
                return
            
            logger.info(
                f"Position size (CROSS): {position_size.quantity:.4f} {self.symbol} "
                f"(equity: {available_margin:.2f}, risk: {position_size.risk_percent*100:.2f}%)"
            )
            
            # Execute on paper trader
            position = await self.paper_trader.execute_signal(
                symbol=self.symbol,
                side=side,
                quantity=Decimal(str(position_size.quantity)),
                orderbook=self.current_orderbook,
                reason=f"Signal: {trading_signal.reason}"
            )
            
            if position:
                logger.info(
                    f"✅ Position opened: {side.value} {position.quantity} @ {position.entry_price}"
                )
                
                # Add position to Stop Loss Engine
                sl_side = SLPositionSide.LONG if side == OrderSide.BUY else SLPositionSide.SHORT
                await self.stop_loss_engine.add_position(
                    symbol=self.symbol,
                    side=sl_side,
                    entry_price=float(position.entry_price),
                    quantity=float(position.quantity),
                    current_price=float(position.entry_price)
                )
                logger.info(f"Stop loss added for {self.symbol} at {stop_loss_price:.2f}")
                
                # Update kill switch with successful trade
                self.kill_switch.record_trade(profit=0.0)  # Will update on close
            else:
                logger.warning("❌ Failed to open position")
        
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
    
    async def _monitor_memory(self) -> None:
        """Monitor memory usage every 60 seconds"""
        try:
            while self.running:
                await asyncio.sleep(60)
                
                # Get memory info
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                # Log memory usage
                logger.info(f"Memory usage: {memory_mb:.2f} MB")
                
                # Warn if exceeding threshold
                if memory_info.rss > self.memory_warning_threshold:
                    logger.warning(
                        f"⚠️  Memory usage ({memory_mb:.2f} MB) exceeds threshold "
                        f"({self.memory_warning_threshold / (1024 * 1024):.0f} MB)"
                    )
                
                # Log per-symbol memory if in multi-symbol mode (future enhancement)
                # This will be implemented when MultiSymbolManager is integrated
        
        except asyncio.CancelledError:
            logger.info("Memory monitoring stopped")
        except Exception as e:
            logger.error(f"Error in memory monitoring: {e}")
    
    async def _refresh_symbols_task(self) -> None:
        """Refresh symbol list every 6 hours"""
        try:
            refresh_interval = self.config.get("multi_symbol", {}).get("refresh_interval", 21600)  # 6 hours default
            
            while self.running:
                await asyncio.sleep(refresh_interval)
                
                logger.info("Refreshing symbol list...")
                
                try:
                    # Fetch current symbols
                    new_symbols = await self.symbol_scanner.refresh_symbols()
                    
                    # Get currently active symbols
                    active_symbols = self.multi_symbol_manager.get_active_symbols()
                    active_set = set(active_symbols)
                    new_set = set(new_symbols)  # new_symbols is already a list of strings
                    
                    # Find added and removed symbols
                    added = new_set - active_set
                    removed = active_set - new_set
                    
                    # Add new symbols
                    for symbol in added:
                        logger.info(f"Adding new symbol: {symbol}")
                        await self.multi_symbol_manager.add_symbol(symbol)
                        
                        # Also add to scalping loop if exists
                        if hasattr(self, 'scalping_loop') and self.scalping_loop:
                            await self.scalping_loop.add_symbol(symbol)
                        
                        # Also add to scalping loop V2 if exists
                        if hasattr(self, 'scalping_loop_v2') and self.scalping_loop_v2:
                            await self.scalping_loop_v2.add_symbol(symbol)
                    
                    # Remove old symbols
                    for symbol in removed:
                        logger.info(f"Removing symbol: {symbol} (no longer meets criteria)")
                        
                        # Close position if exists
                        if self.paper_trader.has_open_position(symbol):
                            position = self.paper_trader.get_position_by_symbol(symbol)
                            logger.info(f"Closing position for removed symbol {symbol}")
                            
                            # Get current orderbook for the symbol
                            signal_engine = self.multi_symbol_manager.get_signal_engine(symbol)
                            if signal_engine:
                                current_orderbook = self.multi_symbol_manager.current_orderbooks.get(symbol)
                                if current_orderbook:
                                    await self.paper_trader.close_position_by_symbol(
                                        symbol=symbol,
                                        orderbook=current_orderbook,
                                        reason="Symbol removed from scanner"
                                    )
                        
                        # Remove from manager
                        await self.multi_symbol_manager.remove_symbol(symbol)
                        
                        # Also remove from scalping loop if exists
                        if hasattr(self, 'scalping_loop') and self.scalping_loop:
                            await self.scalping_loop.remove_symbol(symbol)
                        
                        # Also remove from scalping loop V2 if exists
                        if hasattr(self, 'scalping_loop_v2') and self.scalping_loop_v2:
                            await self.scalping_loop_v2.remove_symbol(symbol)
                    
                    logger.info(
                        f"Symbol refresh complete: {len(added)} added, {len(removed)} removed, "
                        f"{len(new_set)} total active"
                    )
                
                except Exception as e:
                    logger.error(f"Error refreshing symbols: {e}")
        
        except asyncio.CancelledError:
            logger.info("Symbol refresh task stopped")
        except Exception as e:
            logger.error(f"Error in symbol refresh task: {e}")
    
    def _print_status(self) -> None:
        """Print current status and save metrics to file"""
        try:
            from decimal import Decimal
            
            # Prepare current prices for PnL calculation
            current_prices = {}
            if self.multi_symbol_enabled:
                # Multi-symbol mode: get prices from multi_symbol_manager
                current_prices = {
                    symbol: Decimal(str(price)) 
                    for symbol, price in self.multi_symbol_manager.current_prices.items()
                }
                logger.debug(f"Current prices for PnL: {len(current_prices)} symbols")
            elif self.current_price:
                # Single-symbol mode: use current_price
                current_prices = {self.symbol: Decimal(str(self.current_price))}
                logger.debug(f"Current price for {self.symbol}: {self.current_price}")
            
            # Get account summary with current prices for unrealized PnL
            account = self.paper_trader.get_account_summary(current_prices)
            
            # Update metrics collector
            from src.monitoring.metrics_collector import SystemMetrics, TradingMetrics
            
            # Update system metrics
            uptime_seconds = int((datetime.now() - self.start_time).total_seconds())
            self.metrics_collector.system_metrics = SystemMetrics(
                api_status="healthy",
                db_status="healthy",
                last_tick_time=datetime.now(),
                error_rate=Decimal("0"),
                uptime_seconds=uptime_seconds,
                total_requests=0,
                failed_requests=0
            )
            
            # Update trading metrics
            self.metrics_collector.trading_metrics = TradingMetrics(
                current_balance=account['current_balance'],
                initial_balance=account['initial_balance'],
                equity=account['equity'],
                total_pnl=account['total_pnl'],
                realized_pnl=account['realized_pnl'],
                unrealized_pnl=account['unrealized_pnl'],
                total_trades=account['total_trades'],
                winning_trades=account['winning_trades'],
                losing_trades=account['losing_trades'],
                open_positions=account['open_positions']
            )
            
            # Prepare metrics data
            metrics_data = {
                "timestamp": datetime.now().isoformat(),
                "mode": "multi_symbol" if self.multi_symbol_enabled else "single_symbol",
                "system": {
                    "status": "healthy",
                    "api_status": "healthy",
                    "db_status": "healthy",
                    "uptime_seconds": uptime_seconds,
                    "last_tick": datetime.now().isoformat()
                },
                "trading": {
                    "current_balance": float(account['current_balance']),
                    "initial_balance": float(account['initial_balance']),
                    "equity": float(account['equity']),
                    "total_pnl": float(account['total_pnl']),
                    "realized_pnl": float(account['realized_pnl']),
                    "unrealized_pnl": float(account['unrealized_pnl']),
                    "total_trades": account['total_trades'],
                    "winning_trades": account['winning_trades'],
                    "losing_trades": account['losing_trades'],
                    "win_rate": float(account['win_rate']),
                    "open_positions": account['open_positions']
                },
                "strategies": {
                    "scalp": self.paper_trader.get_strategy_summary("scalp"),
                    "main": self.paper_trader.get_strategy_summary("main")
                }
            }
            
            # Mode-specific status display
            if self.multi_symbol_enabled:
                # Multi-symbol mode
                active_symbols = self.multi_symbol_manager.get_active_symbols()
                all_positions = self.paper_trader.get_all_positions()
                
                metrics_data["multi_symbol"] = {
                    "monitored_symbols": len(active_symbols),
                    "active_symbols": active_symbols[:10]  # First 10 for brevity
                }
                
                print(f"\n{'='*60}")
                print(f"STATUS UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")
                print(f"Mode: MULTI-SYMBOL")
                print(f"Monitored Symbols: {len(active_symbols)}")
                print(f"Open Positions: {len(all_positions)}")
                
                print(f"\nPortfolio:")
                print(f"  Balance: {account['current_balance']:.2f} USDT")
                print(f"  Equity: {account['equity']:.2f} USDT")
                print(f"  Total P&L: {account['total_pnl']:.2f} USDT ({account['total_pnl']/account['initial_balance']*100:.2f}%)")
                print(f"  Realized P&L: {account['realized_pnl']:.2f} USDT")
                print(f"  Unrealized P&L: {account['unrealized_pnl']:.2f} USDT")
                
                if all_positions:
                    print(f"\nOpen Positions:")
                    positions_list = []
                    for pos in all_positions:
                        current_price = float(self.multi_symbol_manager.current_prices.get(pos.symbol, pos.entry_price))
                        entry_price = float(pos.entry_price)
                        if pos.side == OrderSide.BUY:
                            unrealized_pnl = (current_price - entry_price) * float(pos.quantity)
                        else:
                            unrealized_pnl = (entry_price - current_price) * float(pos.quantity)
                        
                        print(
                            f"  {pos.symbol}: {pos.side.value} {pos.quantity} @ {entry_price:.2f} "
                            f"(current: {current_price:.2f}, P&L: {unrealized_pnl:+.2f} USDT)"
                        )
                        
                        # Add to positions list for metrics
                        positions_list.append({
                            "symbol": pos.symbol,
                            "side": pos.side.value,
                            "quantity": float(pos.quantity),
                            "entry_price": float(pos.entry_price),
                            "current_price": float(current_price),
                            "unrealized_pnl": float(unrealized_pnl)
                        })
                    
                    # Add positions to metrics data
                    metrics_data["positions"] = positions_list
                
                print(f"\nTrades:")
                print(f"  Total: {account['total_trades']}")
                print(f"  Winning: {account['winning_trades']}")
                print(f"  Losing: {account['losing_trades']}")
                print(f"  Win Rate: {account['win_rate']:.1f}%")
                print(f"{'='*60}\n")
            else:
                # Single-symbol mode
                metrics_data["market"] = {
                    "symbol": self.symbol,
                    "current_price": float(self.current_price) if self.current_price else None
                }
                
                print(f"\n{'='*60}")
                print(f"STATUS UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")
                print(f"Mode: SINGLE-SYMBOL")
                print(f"Symbol: {self.symbol}")
                print(f"Current Price: {self.current_price:.2f}" if self.current_price else "Current Price: N/A")
                print(f"\nAccount:")
                print(f"  Balance: {account['current_balance']:.2f} USDT")
                print(f"  Equity: {account['equity']:.2f} USDT")
                print(f"  Total P&L: {account['total_pnl']:.2f} USDT ({account['total_pnl']/account['initial_balance']*100:.2f}%)")
                print(f"  Realized P&L: {account['realized_pnl']:.2f} USDT")
                print(f"  Unrealized P&L: {account['unrealized_pnl']:.2f} USDT")
                print(f"\nTrades:")
                print(f"  Total: {account['total_trades']}")
                print(f"  Winning: {account['winning_trades']}")
                print(f"  Losing: {account['losing_trades']}")
                print(f"  Win Rate: {account['win_rate']:.1f}%")
                print(f"  Open Positions: {account['open_positions']}")
                print(f"{'='*60}\n")
            
            # Write to shared file
            os.makedirs("logs", exist_ok=True)
            with open("logs/metrics.json", "w") as f:
                json.dump(metrics_data, f, indent=2)
            
            # Write bot-specific metrics if bot_manager exists
            if hasattr(self, 'bot_manager') and self.bot_manager:
                # Get current prices for all bots
                wyckoff_prices = current_prices.copy()
                scalp_prices = {}
                scalp_v2_prices = {}
                
                # Get scalp prices if scalping loops exist
                if hasattr(self, 'scalping_loop') and self.scalping_loop:
                    scalp_prices = {s: Decimal(str(p)) for s, p in self.scalping_loop.current_prices.items() if p}
                
                if hasattr(self, 'scalping_loop_v2') and self.scalping_loop_v2:
                    scalp_v2_prices = {s: Decimal(str(p)) for s, p in self.scalping_loop_v2.current_prices.items() if p}
                
                # Write metrics for all bots
                monitored = len(active_symbols) if self.multi_symbol_enabled else 1
                
                # Get scalp_v2 targets if available
                if hasattr(self.bot_manager, 'scalp_v2_loop') and self.bot_manager.scalp_v2_loop:
                    # Convert targets to serializable format
                    targets = {}
                    for symbol, target in self.bot_manager.scalp_v2_loop.position_targets.items():
                        targets[symbol] = {
                            "stop_loss": target.get("stop_loss", 0),
                            "take_profit1": target.get("take_profit1", 0),
                            "take_profit2": target.get("take_profit2", 0),
                            "entry_price": target.get("entry_price", 0),
                            "side": target.get("side", "")
                        }
                    self.bot_manager.scalp_v2_targets = targets
                
                self.bot_manager.write_all_metrics(
                    wyckoff_prices=wyckoff_prices,
                    scalp_prices=scalp_prices,
                    scalp_v2_prices=scalp_v2_prices,
                    monitored_symbols=monitored
                )
                
                # Check liquidations for all bots
                asyncio.create_task(
                    self.bot_manager.check_liquidations(
                        wyckoff_prices=wyckoff_prices,
                        scalp_prices=scalp_prices,
                        scalp_v2_prices=scalp_v2_prices
                    )
                )
            else:
                # Fallback: Check for account liquidation (old method)
                asyncio.create_task(self.account_monitor.check_and_handle_liquidation(current_prices))
        
        except Exception as e:
            logger.error(f"Error printing status: {e}")
    
    def _print_summary(self) -> None:
        """Print final summary"""
        try:
            from decimal import Decimal
            
            # Prepare current prices for final PnL calculation
            current_prices = {}
            if self.multi_symbol_enabled:
                current_prices = {
                    symbol: Decimal(str(price)) 
                    for symbol, price in self.multi_symbol_manager.current_prices.items()
                }
            elif self.current_price:
                current_prices = {self.symbol: Decimal(str(self.current_price))}
            
            account = self.paper_trader.get_account_summary(current_prices)
            trades = self.paper_trader.get_trade_history()
            
            print(f"\n{'='*60}")
            print(f"FINAL SUMMARY")
            print(f"{'='*60}")
            print(f"\nAccount Performance:")
            print(f"  Initial Balance: {account['initial_balance']:.2f} USDT")
            print(f"  Final Balance: {account['current_balance']:.2f} USDT")
            print(f"  Total P&L: {account['total_pnl']:.2f} USDT ({account['total_pnl']/account['initial_balance']*100:.2f}%)")
            print(f"\nTrading Statistics:")
            print(f"  Total Trades: {account['total_trades']}")
            print(f"  Winning Trades: {account['winning_trades']}")
            print(f"  Losing Trades: {account['losing_trades']}")
            print(f"  Win Rate: {account['win_rate']:.1f}%")
            
            if trades:
                print(f"\nRecent Trades:")
                for trade in trades[-5:]:  # Last 5 trades
                    print(f"  {trade['timestamp']}: {trade['side']} {trade['quantity']} @ {trade['entry_price']:.2f}")
                    if trade['exit_price']:
                        print(f"    Exit: {trade['exit_price']:.2f}, P&L: {trade['pnl']:.2f} USDT")
            
            print(f"{'='*60}\n")
        
        except Exception as e:
            logger.error(f"Error printing summary: {e}")
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False


async def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/trading.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Read configuration from environment
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    
    # Create and start trading loop
    loop = TradingLoop(
        symbol="BTCUSDT",
        initial_balance=Decimal("100"),
        testnet=testnet
    )
    
    from src.core.scalping_loop import ScalpingLoop
    scalp_loop = ScalpingLoop(
        paper_trader=loop.paper_trader,
        symbol="BTCUSDT",
        testnet=testnet
    )
    
    logger.info(f"Starting bot with {'TESTNET' if testnet else 'MAINNET (Live data)'} connection")
    
    # Check if Scalping is enabled in config
    if loop.config.get("scalping", {}).get("enabled", True):
        await asyncio.gather(loop.start(), scalp_loop.start())
    else:
        await loop.start()


if __name__ == "__main__":
    asyncio.run(main())
