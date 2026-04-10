#!/usr/bin/env python3
"""
Run Testnet Trading Bot

This script runs the trading bot on Bybit Testnet with real WebSocket connections.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import yaml

# Import components
from src.connectors.bybit_ws import WebSocketManager
from src.connectors.bybit_rest import RESTClient
from src.data.stream_processor import StreamProcessor
from src.data.timescaledb_writer import TimescaleDBWriter
from src.alpha.signal_engine import SignalGenerator, SignalType
from src.execution.order_manager import OrderManager, OrderSide
from src.risk.position_sizing import PositionSizer
from src.risk.stop_loss import StopLossEngine, StopLossConfig, StopLossMode, PositionSide as StopLossPositionSide
from src.risk.kill_switch import KillSwitch, KillSwitchConfig
from src.monitoring.telegram_bot import TelegramBot
from src.monitoring.metrics_collector import MetricsCollector

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestnetTradingBot:
    """Testnet Trading Bot - Live trading on Bybit Testnet"""
    
    def __init__(self):
        """Initialize trading bot"""
        # Load configuration
        with open('config/config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbol = self.config['symbol']
        self.timeframes = self.config['timeframes']
        
        # API credentials
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        self.testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
        
        # Initialize components
        self.ws_manager = None
        self.rest_client = None
        self.db_writer = None
        self.stream_processor = None
        self.signal_generator = None
        self.order_manager = None
        self.position_sizer = None
        self.stop_loss_manager = None
        self.kill_switch = None
        self.telegram_bot = None
        self.metrics_collector = None
        
        # State
        self.running = False
        self.current_position = None
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("📊 Initializing components...")
        
        # 1. REST Client
        self.rest_client = RESTClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=self.testnet
        )
        logger.info("✅ REST Client initialized")
        
        # 2. Database Writer
        db_url = os.getenv('DATABASE_URL')
        self.db_writer = TimescaleDBWriter(db_url)
        await self.db_writer.connect()
        logger.info("✅ Database Writer connected")
        
        # 3. Stream Processor
        self.stream_processor = StreamProcessor(
            db_writer=self.db_writer
        )
        logger.info("✅ Stream Processor initialized")
        
        # 4. Signal Generator
        self.signal_generator = SignalGenerator(
            symbol=self.symbol,
            config_path='config/alpha_params.yaml'
        )
        logger.info("✅ Signal Generator initialized")
        
        # 5. Order Manager
        self.order_manager = OrderManager(
            rest_client=self.rest_client,
            max_retries=self.config['execution']['max_retries'],
            limit_timeout=self.config['execution']['limit_order_timeout']
        )
        logger.info("✅ Order Manager initialized")
        
        # 6. Position Sizer
        self.position_sizer = PositionSizer(
            max_risk_per_trade=self.config['risk']['max_risk_per_trade'],
            max_position_size=self.config['risk']['max_position_size']
        )
        self.initial_balance = Decimal(str(self.config['backtest']['initial_balance']))
        logger.info("✅ Position Sizer initialized")
        
        # 7. Stop Loss Engine
        stop_loss_config = StopLossConfig(
            mode=StopLossMode.FIXED_PERCENT,
            initial_stop_pct=self.config['risk']['initial_stop_loss_pct'],
            breakeven_profit_pct=self.config['risk']['breakeven_profit_pct'],
            trailing_activation_pct=self.config['risk']['trailing_activation_pct'],
            trailing_distance_pct=self.config['risk']['trailing_distance_pct']
        )
        self.stop_loss_manager = StopLossEngine(
            rest_client=self.rest_client,
            config=stop_loss_config
        )
        logger.info("✅ Stop Loss Engine initialized")
        
        # 8. Kill Switch
        kill_switch_config = KillSwitchConfig(
            max_daily_drawdown=self.config['risk']['kill_switch_daily_dd'],
            max_consecutive_losses=self.config['risk']['kill_switch_consecutive_losses']
        )
        self.kill_switch = KillSwitch(
            config=kill_switch_config
        )
        logger.info("✅ Kill Switch initialized")
        
        # 9. Metrics Collector
        self.metrics_collector = MetricsCollector()
        logger.info("✅ Metrics Collector initialized")
        
        # 10. Telegram Bot - Skip (running as separate service to avoid conflict)
        # Alerts will be logged only
        self.telegram_bot = None
        logger.info("⚠️  Telegram bot running as separate service")
        
        # 11. WebSocket Manager
        self.ws_manager = WebSocketManager(testnet=self.testnet)
        await self.ws_manager.connect()
        logger.info("✅ WebSocket connected")
        
        # Register callbacks
        self.ws_manager.register_callback('kline', self._handle_kline)
        self.ws_manager.register_callback('trade', self._handle_trade)
        
        # Subscribe to channels
        for timeframe in self.timeframes:
            await self.ws_manager.subscribe(f'kline.{timeframe}', self.symbol)
        await self.ws_manager.subscribe('trade', self.symbol)
        
        logger.info(f"✅ Subscribed to {len(self.timeframes)} timeframes + trades")
        
    async def _handle_kline(self, message: dict):
        """Handle kline data from WebSocket"""
        try:
            data = message['data'][0] if isinstance(message['data'], list) else message['data']
            
            # Extract kline data
            timeframe = message['topic'].split('.')[1]
            kline_data = {
                'symbol': data['symbol'],
                'timeframe': timeframe,
                'timestamp': int(data['start']),
                'open': float(data['open']),
                'high': float(data['high']),
                'low': float(data['low']),
                'close': float(data['close']),
                'volume': float(data['volume'])
            }
            
            # Process kline
            await self.stream_processor.process_kline(kline_data)
            
            # Update signal generator
            signal = self.signal_generator.add_kline(
                timeframe=timeframe,
                timestamp=kline_data['timestamp'],
                open_price=kline_data['open'],
                high=kline_data['high'],
                low=kline_data['low'],
                close=kline_data['close'],
                volume=kline_data['volume']
            )
            
            # Execute signal if generated
            if signal and not signal.suppressed:
                await self._execute_signal(signal)
                
        except Exception as e:
            logger.error(f"Error handling kline: {e}")
    
    async def _handle_trade(self, message: dict):
        """Handle trade data from WebSocket"""
        try:
            data = message['data'][0] if isinstance(message['data'], list) else message['data']
            
            # Extract trade data
            trade_data = {
                'symbol': data['s'],
                'timestamp': int(data['T']),
                'price': float(data['p']),
                'quantity': float(data['v']),
                'side': data['S'],
                'trade_id': data['i']
            }
            
            # Process trade
            await self.stream_processor.process_trade(trade_data)
            
            # Update signal generator (for order flow)
            for timeframe in self.timeframes:
                self.signal_generator.add_trade(
                    timeframe=timeframe,
                    timestamp=trade_data['timestamp'],
                    price=trade_data['price'],
                    quantity=trade_data['quantity'],
                    side=trade_data['side']
                )
                
        except Exception as e:
            logger.error(f"Error handling trade: {e}")
    
    async def _execute_signal(self, signal):
        """Execute trading signal"""
        try:
            # Check kill switch
            if self.kill_switch.is_activated:
                logger.warning("🚨 Kill switch active - signal ignored")
                if self.telegram_bot:
                    await self.telegram_bot.send_alert(
                        "🚨 Kill switch active - trading stopped",
                        priority="critical"
                    )
                return
            
            # Check if already in position
            if self.current_position:
                logger.info("Already in position - signal ignored")
                return
            
            logger.info(
                f"🎯 Signal: {signal.signal_type.value} at {signal.price:.2f}, "
                f"confidence: {signal.confidence:.1f}%"
            )
            
            # Calculate position size
            position_size_result = self.position_sizer.calculate_position_size(
                balance=float(self.initial_balance),
                entry_price=float(signal.price),
                stop_loss_price=float(signal.price * 0.98),  # 2% stop
                signal_confidence=signal.confidence
            )
            
            position_size = Decimal(str(position_size_result.quantity))
            
            if position_size <= 0:
                logger.warning("Position size too small - signal ignored")
                return
            
            # Determine order side
            side = OrderSide.BUY if signal.signal_type == SignalType.BUY else OrderSide.SELL
            
            # Log signal
            logger.info(
                f"🎯 Signal: {signal.signal_type.value} at {signal.price:.2f}, "
                f"confidence: {signal.confidence:.1f}%"
            )
            
            # Send Telegram alert (if bot available)
            if self.telegram_bot:
                await self.telegram_bot.send_alert(
                    f"🎯 *Signal Detected*\n"
                    f"Type: {signal.signal_type.value}\n"
                    f"Price: ${signal.price:,.2f}\n"
                    f"Confidence: {signal.confidence:.1f}%\n"
                    f"Reason: {signal.reason}",
                    priority="high"
                )
            
            # Execute order
            position = await self.order_manager.execute_signal(
                symbol=self.symbol,
                side=side,
                quantity=position_size,
                limit_price=Decimal(str(signal.price))
            )
            
            if position:
                self.current_position = position
                
                # Add position to stop loss manager
                stop_side = StopLossPositionSide.LONG if position.side == OrderSide.BUY else StopLossPositionSide.SHORT
                
                try:
                    stop_position = await self.stop_loss_manager.add_position(
                        symbol=self.symbol,
                        side=stop_side,
                        entry_price=float(position.entry_price),
                        quantity=float(position.quantity),
                        current_price=float(signal.price)
                    )
                    
                    logger.info(
                        f"✅ Position opened: {position.side.value} {position.quantity} "
                        f"@ {position.entry_price}, stop: {stop_position.stop_loss_price:.2f}"
                    )
                except Exception as e:
                    logger.error(f"Failed to set stop loss: {e}")
                    logger.info(
                        f"✅ Position opened: {position.side.value} {position.quantity} "
                        f"@ {position.entry_price} (no stop loss)"
                    )
                
                # Send Telegram alert (if bot available)
                if self.telegram_bot:
                    await self.telegram_bot.send_order_alert(
                        symbol=self.symbol,
                        side=position.side.value,
                        quantity=position.quantity,
                        price=position.entry_price,
                        state="FILLED"
                    )
            else:
                logger.error("❌ Failed to open position")
                
                # Send Telegram alert (if bot available)
                if self.telegram_bot:
                    await self.telegram_bot.send_alert(
                        f"❌ *Order Failed*\n"
                        f"Signal: {signal.signal_type.value}\n"
                        f"Price: ${signal.price:,.2f}",
                        priority="high"
                    )
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
    
    def _update_metrics(self, start_time: datetime):
        """Update metrics collector with current system state"""
        try:
            # Calculate uptime
            uptime_seconds = int((datetime.now() - start_time).total_seconds())
            
            # Update system metrics
            self.metrics_collector.update_system_metrics(
                api_status="healthy" if self.ws_manager.is_connected() else "down",
                db_status="healthy",  # Assume healthy if no errors
                last_tick_time=datetime.now(),
                error_rate=Decimal("0.0"),
                uptime_seconds=uptime_seconds,
                total_requests=0,  # TODO: Track actual requests
                failed_requests=0
            )
            
            # Update trading metrics
            current_balance = self.initial_balance
            open_positions = 1 if self.current_position else 0
            
            self.metrics_collector.update_trading_metrics(
                current_balance=current_balance,
                initial_balance=self.initial_balance,
                equity=current_balance,
                total_pnl=Decimal("0.0"),
                realized_pnl=Decimal("0.0"),
                unrealized_pnl=Decimal("0.0"),
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                open_positions=open_positions
            )
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    async def run(self):
        """Main trading loop"""
        self.running = True
        start_time = datetime.now()
        last_metrics_update = datetime.now()
        
        logger.info("="*60)
        logger.info("🚀 Testnet Trading Bot Running")
        logger.info("="*60)
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Timeframes: {', '.join(self.timeframes)}")
        logger.info(f"Testnet: {self.testnet}")
        logger.info(f"Balance: 10,000 USDT (Fake Money)")
        logger.info("="*60)
        logger.info("📱 Check Telegram for alerts")
        logger.info("📊 Dashboard: http://localhost:8501")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60)
        
        try:
            while self.running:
                # Check stop flag file
                if os.path.exists('/app/logs/stop_trading.flag'):
                    logger.info("Stop flag detected - shutting down...")
                    os.remove('/app/logs/stop_trading.flag')
                    break
                
                # Update metrics every 5 seconds
                now = datetime.now()
                if (now - last_metrics_update).total_seconds() >= 5:
                    self._update_metrics(start_time)
                    last_metrics_update = now
                
                # Monitor position and update stop loss
                if self.current_position:
                    # Get current price from signal generator
                    current_price = self.signal_generator.get_current_price()
                    
                    if current_price:
                        # Update stop loss based on current price
                        try:
                            await self.stop_loss_manager.update_stops(float(current_price))
                            
                            # Check if stop loss was triggered
                            if self.stop_loss_manager.check_stop_triggered(
                                symbol=self.symbol,
                                current_price=float(current_price)
                            ):
                                logger.info("🛑 Stop loss triggered - closing position")
                                
                                # Close position
                                # TODO: Implement position close logic
                                self.current_position = None
                                
                                if self.telegram_bot:
                                    await self.telegram_bot.send_alert(
                                        "🛑 Stop loss triggered - position closed",
                                        priority="high"
                                    )
                        except Exception as e:
                            logger.error(f"Error updating stop loss: {e}")
                
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown bot and cleanup"""
        logger.info("🛑 Shutting down...")
        
        self.running = False
        
        # Close position if open
        if self.current_position:
            logger.info("Closing open position...")
            # TODO: Close position
        
        # Disconnect WebSocket
        if self.ws_manager:
            await self.ws_manager.disconnect()
        
        # Telegram bot runs as separate service - don't stop it
        
        # Close database connection
        if self.db_writer:
            await self.db_writer.disconnect()
        
        logger.info("✅ Testnet Trading Bot stopped")


async def main():
    """Main function"""
    logger.info("="*60)
    logger.info("🤖 Testnet Trading Bot Starting")
    logger.info("="*60)
    
    # Check trading mode
    trading_mode = os.getenv('TRADING_MODE', 'paper')
    testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    
    logger.info(f"Trading Mode: {trading_mode}")
    logger.info(f"Bybit Testnet: {testnet}")
    
    if not testnet:
        logger.warning("⚠️  WARNING: BYBIT_TESTNET is set to 'false'")
        logger.warning("⚠️  This will place REAL orders with REAL money!")
        logger.warning("⚠️  Change to 'true' in .env for testnet trading")
        return
    
    # Create and run bot
    bot = TestnetTradingBot()
    
    try:
        await bot.initialize()
        await bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        if bot.telegram_bot:
            await bot.telegram_bot.send_alert(
                f"🚨 *Bot Crashed*\n\n{str(e)}",
                priority="critical"
            )
        raise


if __name__ == '__main__':
    asyncio.run(main())
