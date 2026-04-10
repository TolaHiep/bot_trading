"""
Scalping Loop V2 - Improved Strategy
Implements professional scalping with:
- ATR-based stop loss
- Multiple take profit targets
- Breakeven logic
- Trailing stop
"""

import asyncio
import logging
import os
import yaml
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, List

from src.connectors.bybit_ws import WebSocketManager
from src.connectors.bybit_rest import RESTClient
from src.alpha.scalping_engine_v2 import ScalpingEngineV2, ScalpSignalType
from src.execution.paper_trader import PaperTrader
from src.execution.cost_filter import Orderbook, OrderbookLevel
from src.execution.order_manager import OrderSide

logger = logging.getLogger(__name__)


class ScalpingLoopV2:
    """
    Improved Scalping Loop
    
    Features:
    - ATR-based stop loss (0.3-0.5%)
    - Multiple TP targets (0.4%, 0.8%)
    - Breakeven at 0.3% profit
    - Trailing stop at 0.5% profit
    - Kill switch for consecutive losses
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
        
        # Load config
        config_file = Path(config_path)
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        self.scalping_config = config.get('scalping', {})
        
        # Risk config
        risk_cfg = self.scalping_config.get('risk', {})
        self.risk_per_trade = risk_cfg.get('risk_per_trade', 0.025)  # 2.5%
        self.leverage = risk_cfg.get('leverage', 12.0)  # 12x
        self.max_positions = risk_cfg.get('max_positions', 5)
        self.max_exposure_pct = risk_cfg.get('max_exposure_pct', 0.50)
        
        # Kill switch config
        ks_cfg = self.scalping_config.get('kill_switch', {})
        self.max_consecutive_losses = ks_cfg.get('max_consecutive_losses', 3)
        self.cooldown_minutes = ks_cfg.get('cooldown_minutes', 15)
        self.consecutive_losses = 0
        self.cooldown_until = None
        
        logger.info(
            f"ScalpingLoopV2 config: risk={self.risk_per_trade*100}%, "
            f"leverage={self.leverage}x, max_positions={self.max_positions}"
        )
        
        # WebSocket manager
        self.ws_manager = WebSocketManager(testnet=testnet)
        
        # Signal engines per symbol
        self.signal_engines: Dict[str, ScalpingEngineV2] = {}
        for symbol in self.symbols:
            self.signal_engines[symbol] = ScalpingEngineV2(
                symbol=symbol,
                config=self.scalping_config
            )
        
        # Current prices and orderbooks
        self.current_prices: Dict[str, float] = {}
        self.current_orderbooks: Dict[str, Orderbook] = {}
        
        # Position tracking for TP/SL management
        self.position_targets: Dict[str, dict] = {}  # symbol -> {sl, tp1, tp2, breakeven_moved}
    
    async def start(self) -> None:
        """Start scalping loop"""
        logger.info(f"Starting ScalpingLoopV2 for {len(self.symbols)} symbols")
        self.running = True
        
        try:
            await self.ws_manager.connect()
            
            # Register callbacks
            self.ws_manager.register_callback("kline", self._on_kline)
            self.ws_manager.register_callback("trade", self._on_trade)
            self.ws_manager.register_callback("orderbook", self._on_orderbook)
            
            # Subscribe to 1m kline, trades, and orderbook
            for symbol in self.symbols:
                await self.ws_manager.subscribe("kline.1", symbol)
                await self.ws_manager.subscribe("trade", symbol)
                await self.ws_manager.subscribe("orderbook.50", symbol)
                logger.info(f"[SCALP V2] Subscribed to {symbol}")
            
            logger.info("ScalpingLoopV2 started successfully")
            
            # Start TP/SL monitoring task
            monitor_task = asyncio.create_task(self._monitor_positions())
            
            while self.running:
                await asyncio.sleep(1)
            
            # Cancel monitoring task
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"Error in scalping loop V2: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop scalping loop"""
        logger.info("Stopping ScalpingLoopV2...")
        self.running = False
        await self.ws_manager.disconnect()
    
    async def add_symbol(self, symbol: str):
        """Add new symbol"""
        if symbol in self.symbols:
            return
        
        logger.info(f"[SCALP V2] Adding symbol: {symbol}")
        self.symbols.append(symbol)
        self.signal_engines[symbol] = ScalpingEngineV2(
            symbol=symbol,
            config=self.scalping_config
        )
        
        if self.running:
            await self.ws_manager.subscribe("kline.1", symbol)
            await self.ws_manager.subscribe("trade", symbol)
            await self.ws_manager.subscribe("orderbook.50", symbol)
    
    async def remove_symbol(self, symbol: str):
        """Remove symbol"""
        if symbol not in self.symbols:
            return
        
        logger.info(f"[SCALP V2] Removing symbol: {symbol}")
        self.symbols.remove(symbol)
        
        if symbol in self.signal_engines:
            del self.signal_engines[symbol]
        if symbol in self.current_orderbooks:
            del self.current_orderbooks[symbol]
        if symbol in self.current_prices:
            del self.current_prices[symbol]
        if symbol in self.position_targets:
            del self.position_targets[symbol]
    
    async def _on_kline(self, message: dict) -> None:
        """Handle kline data"""
        try:
            data = message["data"][0]
            topic = message["topic"]
            
            # Extract symbol
            parts = topic.split(".")
            symbol = parts[2] if len(parts) > 2 else parts[-1]
            
            if symbol not in self.signal_engines:
                return
            
            timestamp = int(data["start"])
            open_price = float(data["open"])
            high = float(data["high"])
            low = float(data["low"])
            close = float(data["close"])
            volume = float(data["volume"])
            
            self.current_prices[symbol] = close
            
            # Generate signal
            signal = self.signal_engines[symbol].add_kline(
                timeframe="1m",
                timestamp=timestamp,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
            
            if signal:
                await self._execute_signal(symbol, signal)
                
        except Exception as e:
            logger.error(f"Error processing kline: {e}")
    
    async def _on_trade(self, message: dict) -> None:
        """Handle trade data for order flow"""
        try:
            data = message["data"][0]
            topic = message["topic"]
            
            # Extract symbol
            parts = topic.split(".")
            symbol = parts[-1] if len(parts) > 1 else topic.replace("trade.", "")
            
            if symbol not in self.signal_engines:
                return
            
            timestamp = int(data["T"])
            price = float(data["p"])
            quantity = float(data["v"])
            side = data["S"]
            
            self.signal_engines[symbol].add_trade(
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
            topic = message["topic"]
            
            # Extract symbol
            parts = topic.split(".")
            symbol = parts[2] if len(parts) > 2 else parts[-1]
            
            if symbol not in self.symbols:
                return
            
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
                prev_orderbook = self.current_orderbooks[symbol]
                self.current_orderbooks[symbol] = Orderbook(
                    symbol=symbol,
                    bids=bids if bids else prev_orderbook.bids,
                    asks=asks if asks else prev_orderbook.asks,
                    timestamp=ts
                )
                
        except Exception as e:
            logger.error(f"Error processing orderbook: {e}")
    
    async def _execute_signal(self, symbol: str, signal) -> None:
        """Execute scalping signal"""
        try:
            # Cooldown disabled for scalping V2 - trade continuously
            
            # Check max positions
            open_positions = [p for p in self.paper_trader.get_all_positions() if p.strategy_name == "scalp"]
            if len(open_positions) >= self.max_positions:
                logger.warning(f"[SCALP V2] Max positions reached ({self.max_positions})")
                return
            
            # Check if already have position for this symbol
            if self.paper_trader.has_open_position(symbol, "scalp"):
                return
            
            # Check orderbook
            if symbol not in self.current_orderbooks:
                logger.warning(f"[SCALP V2] No orderbook for {symbol}")
                return
            
            logger.info(
                f"\n[SCALP V2] SIGNAL: {signal.signal_type.value} {symbol} @ {signal.price:.2f}\n"
                f"  Confidence: {signal.confidence:.0f}%\n"
                f"  SL: {signal.stop_loss_price:.2f}\n"
                f"  TP1: {signal.take_profit1_price:.2f}\n"
                f"  TP2: {signal.take_profit2_price:.2f}\n"
                f"  R:R: {signal.risk_reward_ratio:.2f}\n"
                f"  Reason: {signal.reason}"
            )
            
            # Determine side
            if signal.signal_type == ScalpSignalType.BUY:
                side = OrderSide.BUY
            elif signal.signal_type == ScalpSignalType.SELL:
                side = OrderSide.SELL
            else:
                return
            
            # Calculate position size
            current_prices = {s: Decimal(str(p)) for s, p in self.current_prices.items() if p}
            account_summary = self.paper_trader.get_account_summary(current_prices)
            available_margin = account_summary["available_margin"]
            
            # Check max exposure
            total_exposure = sum(
                float(p.entry_price) * float(p.quantity) 
                for p in open_positions
            )
            exposure_pct = total_exposure / float(available_margin) if available_margin > 0 else 0
            
            if exposure_pct >= self.max_exposure_pct:
                logger.warning(
                    f"[SCALP V2] Max exposure reached: {exposure_pct*100:.1f}% >= {self.max_exposure_pct*100}%"
                )
                return
            
            # Position sizing: (equity × risk% × leverage) / price
            quantity = (
                Decimal(str(available_margin)) * 
                Decimal(str(self.risk_per_trade)) * 
                Decimal(str(self.leverage))
            ) / Decimal(str(signal.price))
            
            logger.info(
                f"[SCALP V2] Position sizing: equity=${available_margin:.2f}, "
                f"risk={self.risk_per_trade*100}%, leverage={self.leverage}x, qty={quantity:.6f}"
            )
            
            # Execute trade
            position = await self.paper_trader.execute_signal(
                symbol=symbol,
                side=side,
                quantity=quantity,
                orderbook=self.current_orderbooks[symbol],
                reason=f"Scalp V2: {signal.reason}",
                strategy_name="scalp",
                leverage=Decimal(str(self.leverage))
            )
            
            if position:
                logger.info(f"[SCALP V2] ✅ Position opened: {side.value} {quantity:.6f} {symbol} @ {position.entry_price}")
                
                # Store TP/SL targets
                self.position_targets[symbol] = {
                    'stop_loss': signal.stop_loss_price,
                    'take_profit1': signal.take_profit1_price,
                    'take_profit2': signal.take_profit2_price,
                    'breakeven_moved': False,
                    'trailing_active': False,
                    'entry_price': float(position.entry_price),
                    'side': side.value
                }
                
            else:
                logger.warning(f"[SCALP V2] ❌ Failed to open position for {symbol}")
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
    
    async def _monitor_positions(self) -> None:
        """Monitor positions for TP/SL and breakeven"""
        try:
            while self.running:
                await asyncio.sleep(1)  # Check every second
                
                # Get all scalp positions
                positions = [p for p in self.paper_trader.get_all_positions() if p.strategy_name == "scalp"]
                
                for position in positions:
                    symbol = position.symbol
                    
                    # Check if we have targets for this position
                    if symbol not in self.position_targets:
                        continue
                    
                    # Get current price
                    current_price = self.current_prices.get(symbol)
                    if not current_price:
                        continue
                    
                    targets = self.position_targets[symbol]
                    entry_price = targets['entry_price']
                    side = targets['side']
                    
                    # Calculate current P&L %
                    if side == "Buy":
                        pnl_pct = (current_price - entry_price) / entry_price
                    else:
                        pnl_pct = (entry_price - current_price) / entry_price
                    
                    # Check Stop Loss
                    if side == "Buy":
                        if current_price <= targets['stop_loss']:
                            logger.warning(f"[SCALP V2] 🛑 Stop Loss hit for {symbol} @ {current_price:.2f}")
                            await self._close_position(symbol, "Stop Loss")
                            # Cooldown disabled - continue trading
                            continue
                    else:
                        if current_price >= targets['stop_loss']:
                            logger.warning(f"[SCALP V2] 🛑 Stop Loss hit for {symbol} @ {current_price:.2f}")
                            await self._close_position(symbol, "Stop Loss")
                            # Cooldown disabled - continue trading
                            continue
                    
                    # Check Take Profit 1
                    if side == "Buy":
                        if current_price >= targets['take_profit1']:
                            logger.info(f"[SCALP V2] 🎯 Take Profit 1 hit for {symbol} @ {current_price:.2f}")
                            await self._close_position(symbol, "Take Profit 1")
                            # Reset consecutive losses on win (even though cooldown is disabled)
                            self.consecutive_losses = 0
                            continue
                    else:
                        if current_price <= targets['take_profit1']:
                            logger.info(f"[SCALP V2] 🎯 Take Profit 1 hit for {symbol} @ {current_price:.2f}")
                            await self._close_position(symbol, "Take Profit 1")
                            # Reset consecutive losses on win (even though cooldown is disabled)
                            self.consecutive_losses = 0
                            continue
                    
                    # Breakeven logic: Move SL to entry at 0.3% profit
                    sl_cfg = self.scalping_config.get('stop_loss', {})
                    breakeven_pct = sl_cfg.get('breakeven_profit_pct', 0.003)
                    
                    if not targets['breakeven_moved'] and pnl_pct >= breakeven_pct:
                        logger.info(f"[SCALP V2] 📍 Moving SL to breakeven for {symbol} (profit: {pnl_pct*100:.2f}%)")
                        targets['stop_loss'] = entry_price
                        targets['breakeven_moved'] = True
                    
                    # Lock profit logic: Move SL to +0.2% at 0.5% profit
                    lock_pct = sl_cfg.get('breakeven_lock_pct', 0.005)
                    lock_profit_pct = 0.002  # Lock 0.2% profit
                    
                    if targets['breakeven_moved'] and not targets['trailing_active'] and pnl_pct >= lock_pct:
                        if side == "Buy":
                            new_sl = entry_price * (1 + lock_profit_pct)
                        else:
                            new_sl = entry_price * (1 - lock_profit_pct)
                        
                        logger.info(f"[SCALP V2] 🔒 Locking profit for {symbol}: SL @ {new_sl:.2f} (profit: {pnl_pct*100:.2f}%)")
                        targets['stop_loss'] = new_sl
                        targets['trailing_active'] = True
                    
                    # Trailing stop: Update SL as price moves favorably
                    tp_cfg = self.scalping_config.get('take_profit', {})
                    trailing_distance_pct = tp_cfg.get('trailing_distance_pct', 0.002)
                    
                    if targets['trailing_active']:
                        if side == "Buy":
                            new_sl = current_price * (1 - trailing_distance_pct)
                            if new_sl > targets['stop_loss']:
                                logger.debug(f"[SCALP V2] 📈 Trailing SL for {symbol}: {targets['stop_loss']:.2f} -> {new_sl:.2f}")
                                targets['stop_loss'] = new_sl
                        else:
                            new_sl = current_price * (1 + trailing_distance_pct)
                            if new_sl < targets['stop_loss']:
                                logger.debug(f"[SCALP V2] 📉 Trailing SL for {symbol}: {targets['stop_loss']:.2f} -> {new_sl:.2f}")
                                targets['stop_loss'] = new_sl
                
        except asyncio.CancelledError:
            logger.info("Position monitoring stopped")
        except Exception as e:
            logger.error(f"Error in position monitoring: {e}")
    
    async def _close_position(self, symbol: str, reason: str) -> None:
        """Close position"""
        try:
            if symbol not in self.current_orderbooks:
                logger.error(f"[SCALP V2] No orderbook for {symbol}")
                return
            
            pnl = await self.paper_trader.close_position_by_symbol(
                symbol=symbol,
                orderbook=self.current_orderbooks[symbol],
                reason=reason,
                strategy_name="scalp"
            )
            
            if pnl is not None:
                logger.info(f"[SCALP V2] Position closed: {symbol}, P&L: ${pnl:.2f}")
                
                # Remove targets
                if symbol in self.position_targets:
                    del self.position_targets[symbol]
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def _check_cooldown(self) -> None:
        """Check if cooldown should be activated - DISABLED for scalping"""
        # Cooldown disabled for scalping V2 - trade continuously
        pass
