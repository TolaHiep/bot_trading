#!/usr/bin/env python3
"""
Run Paper Trading with Mainnet Data

This script runs paper trading (simulated orders) using REAL market data from Bybit Mainnet.
- Uses REAL prices, volume, indicators from Mainnet
- Simulates order execution (NO REAL ORDERS)
- Calculates P&L based on real price movements
- 100% SAFE - No real money involved
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
from src.execution.paper_trader import PaperTrader  # Use PaperTrader instead of OrderManager
from src.execution.order_manager import OrderSide
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


class PaperTradingBot:
    """Paper Trading Bot - Simulated trading with REAL Mainnet data"""
    
    def __init__(self):
        """Initialize paper trading bot"""
        # Load configuration
        with open('config/config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbol = self.config['symbol']
        self.timeframes = self.config['timeframes']
        
        # Use MAINNET for real data (but no real orders)
        self.testnet = False  # FALSE = Mainnet data
        
        # Initialize components
        self.ws_manager = None
        self.rest_client = None
        self.db_writer = None
        self.stream_processor = None
        self.signal_generator = None
        self.paper_trader = None  # PaperTrader instead of OrderManager
        self.position_sizer = None
        self.stop_loss_manager = None
        self.kill_switch = None
        self.telegram_bot = None
        self.metrics_collector = None
        
        # State
        self.running = False
        self.current_position = None
        self.initial_balance = Decimal(str(self.config['backtest']['initial_balance']))
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("📊 Initializing components...")
        
        # 1. REST Client (NO API KEYS NEEDED for public data)
        self.rest_client = RESTClient(
            api_key="",  # Empty - not needed for public endpoints
            api_secret="",
            testnet=self.testnet
        )
        logger.info("✅ REST Client initialized (Mainnet - Public data only)")
        
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
        
        # 5. Paper Trader (Simulated orders)
        self.paper_trader = PaperTrader(
            initial_balance=self.initial_balance,
            commission_rate=Decimal(str(self.config['backtest']['commission_rate']))
            # Note: Slippage is handled by CostFilter internally
        )
        logger.info("✅ Paper Trader initialized (SIMULATED ORDERS ONLY)")
        
        # 6. Position Sizer
        self.position_sizer = PositionSizer(
            max_risk_per_trade=self.config['risk']['max_risk_per_trade'],
            max_position_size=self.config['risk']['max_position_size']
        )
        logger.info("✅ Position Sizer initialized")
        
        # 7. Kill Switch
        kill_switch_config = KillSwitchConfig(
            max_daily_drawdown=self.config['risk']['kill_switch_daily_dd'],
            max_consecutive_losses=self.config['risk']['kill_switch_consecutive_losses']
        )
        self.kill_switch = KillSwitch(
            config=kill_switch_config
        )
        logger.info("✅ Kill Switch initialized")
        
        # 8. Metrics Collector
        self.metrics_collector = MetricsCollector()
        logger.info("✅ Metrics Collector initialized")
        
        # 9. Telegram Bot - Skip (running as separate service)
        self.telegram_bot = None
        logger.info("⚠️  Telegram bot running as separate service")
        
        # 10. WebSocket Manager (MAINNET)
        self.ws_manager = WebSocketManager(testnet=self.testnet)
        await self.ws_manager.connect()
        logger.info("✅ WebSocket connected to MAINNET")
        
        # Register callbacks
        self.ws_manager.register_callback('kline', self._handle_kline)
        self.ws_manager.register_callback('trade', self._handle_trade)
        
        # Subscribe to channels
        for timeframe in self.timeframes:
            # Convert timeframe format: "1m" -> "1", "5m" -> "5", "1h" -> "60"
            if timeframe.endswith('m'):
                interval = timeframe[:-1]  # Remove 'm'
            elif timeframe.endswith('h'):
                hours = int(timeframe[:-1])
                interval = str(hours * 60)  # Convert hours to minutes
            else:
                interval = timeframe
            
            await self.ws_manager.subscribe(f'kline.{interval}', self.symbol)
        await self.ws_manager.subscribe('trade', self.symbol)
        
        logger.info(f"✅ Subscribed to {len(self.timeframes)} timeframes + trades")
        
    async def _handle_kline(self, message: dict):
        """Handle kline data from WebSocket"""
        try:
            data = message['data'][0] if isinstance(message['data'], list) else message['data']
            
            # Extract timeframe from topic: "kline.1.BTCUSDT" -> "1" (minutes)
            topic_parts = message['topic'].split('.')
            interval_minutes = topic_parts[1]  # "1", "5", "15", "60"
            symbol = topic_parts[2]  # "BTCUSDT"
            
            # Convert back to our format: "1" -> "1m", "60" -> "1h"
            if interval_minutes == "60":
                timeframe = "1h"
            elif interval_minutes == "240":
                timeframe = "4h"
            elif interval_minutes == "1440":
                timeframe = "1d"
            else:
                timeframe = f"{interval_minutes}m"
            
            # Extract kline data
            kline_data = {
                'symbol': symbol,  # Get from topic, not from data
                'timeframe': timeframe,
                'timestamp': int(data['start']),
                'open': float(data['open']),
                'high': float(data['high']),
                'low': float(data['low']),
                'close': float(data['close']),
                'volume': float(data['volume'])
            }
            
            logger.info(f"📊 Kline {timeframe}: Close={kline_data['close']:.2f}, Volume={kline_data['volume']:.2f}")
            
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
        """Execute trading signal (SIMULATED)"""
        try:
            # Check kill switch
            if self.kill_switch.is_activated:
                logger.warning("🚨 Kill switch active - signal ignored")
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
                balance=float(self.paper_trader.account.balance),
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
                f"🎯 SIMULATED ORDER: {signal.signal_type.value} {position_size} {self.symbol} "
                f"at {signal.price:.2f}"
            )
            
            # Execute SIMULATED order
            position = await self.paper_trader.execute_signal(
                symbol=self.symbol,
                side=side,
                quantity=position_size,
                limit_price=Decimal(str(signal.price))
            )
            
            if position:
                self.current_position = position
                
                logger.info(
                    f"✅ SIMULATED Position opened: {position.side.value} {position.quantity} "
                    f"@ {position.entry_price}"
                )
                logger.info(
                    f"💰 Account Balance: {self.paper_trader.account.balance:.2f} USDT, "
                    f"Equity: {self.paper_trader.account.equity:.2f} USDT"
                )
                
                # Send Telegram alert
                if self.telegram_bot:
                    await self.telegram_bot.send_alert(
                        f"🎯 *SIMULATED Position Opened*\n"
                        f"Type: {position.side.value}\n"
                        f"Size: {position.quantity}\n"
                        f"Price: ${position.entry_price:,.2f}\n"
                        f"Balance: ${self.paper_trader.account.balance:,.2f}",
                        priority="high"
                    )
            else:
                logger.error("❌ Failed to open simulated position")
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
    
    def _update_metrics(self, start_time: datetime):
        """Update metrics collector with current system state"""
        try:
            # Calculate uptime
            uptime_seconds = int((datetime.now() - start_time).total_seconds())
            
            # Get account summary
            account_summary = self.paper_trader.get_account_summary()
            
            # Update system metrics
            self.metrics_collector.update_system_metrics(
                api_status="healthy" if self.ws_manager.is_connected() else "down",
                db_status="healthy",
                last_tick_time=datetime.now(),
                error_rate=Decimal("0.0"),
                uptime_seconds=uptime_seconds,
                total_requests=0,
                failed_requests=0
            )
            
            # Update trading metrics
            self.metrics_collector.update_trading_metrics(
                current_balance=account_summary['balance'],
                initial_balance=self.initial_balance,
                equity=account_summary['equity'],
                total_pnl=account_summary['total_pnl'],
                realized_pnl=account_summary['realized_pnl'],
                unrealized_pnl=account_summary['unrealized_pnl'],
                total_trades=account_summary['total_trades'],
                winning_trades=account_summary['winning_trades'],
                losing_trades=account_summary['losing_trades'],
                open_positions=len(account_summary['open_positions'])
            )
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    async def run(self):
        """Main trading loop"""
        self.running = True
        start_time = datetime.now()
        last_metrics_update = datetime.now()
        last_summary_time = datetime.now()
        
        logger.info("="*60)
        logger.info("🚀 Paper Trading Bot Running (MAINNET DATA)")
        logger.info("="*60)
        logger.info(f"Symbol: {self.symbol}")
        logger.info(f"Timeframes: {', '.join(self.timeframes)}")
        logger.info(f"Data Source: Bybit MAINNET (Real prices)")
        logger.info(f"Order Execution: SIMULATED (No real orders)")
        logger.info(f"Initial Balance: {self.initial_balance:,.2f} USDT (Virtual)")
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
                
                # Print account summary every 60 seconds
                if (now - last_summary_time).total_seconds() >= 60:
                    summary = self.paper_trader.get_account_summary()
                    logger.info("="*60)
                    logger.info("📊 ACCOUNT SUMMARY")
                    logger.info(f"Balance: {summary['balance']:,.2f} USDT")
                    logger.info(f"Equity: {summary['equity']:,.2f} USDT")
                    logger.info(f"Total P&L: {summary['total_pnl']:,.2f} USDT ({summary['total_pnl_pct']:.2f}%)")
                    logger.info(f"Realized P&L: {summary['realized_pnl']:,.2f} USDT")
                    logger.info(f"Unrealized P&L: {summary['unrealized_pnl']:,.2f} USDT")
                    logger.info(f"Total Trades: {summary['total_trades']}")
                    logger.info(f"Win Rate: {summary['win_rate']:.1f}%")
                    logger.info(f"Open Positions: {len(summary['open_positions'])}")
                    logger.info("="*60)
                    last_summary_time = now
                
                # Monitor position and update P&L
                if self.current_position:
                    current_price = self.signal_generator.get_current_price()
                    
                    if current_price:
                        # Update position P&L
                        current_prices = {self.symbol: Decimal(str(current_price))}
                        self.paper_trader.account.update_equity(
                            [self.current_position],
                            current_prices
                        )
                        
                        # Check stop loss (simulated)
                        # TODO: Implement stop loss checking
                
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
        
        # Print final summary
        summary = self.paper_trader.get_account_summary()
        logger.info("="*60)
        logger.info("📊 FINAL SUMMARY")
        logger.info(f"Initial Balance: {self.initial_balance:,.2f} USDT")
        logger.info(f"Final Balance: {summary['balance']:,.2f} USDT")
        logger.info(f"Final Equity: {summary['equity']:,.2f} USDT")
        logger.info(f"Total P&L: {summary['total_pnl']:,.2f} USDT ({summary['total_pnl_pct']:.2f}%)")
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info(f"Winning Trades: {summary['winning_trades']}")
        logger.info(f"Losing Trades: {summary['losing_trades']}")
        logger.info(f"Win Rate: {summary['win_rate']:.1f}%")
        logger.info("="*60)
        
        # Export trades to CSV
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reports/paper_trades_{timestamp}.csv"
            self.paper_trader.export_trades_csv(filename)
            logger.info(f"✅ Trades exported to {filename}")
        except Exception as e:
            logger.error(f"Failed to export trades: {e}")
        
        # Disconnect WebSocket
        if self.ws_manager:
            await self.ws_manager.disconnect()
        
        # Close database connection
        if self.db_writer:
            await self.db_writer.disconnect()
        
        logger.info("✅ Paper Trading Bot stopped")


async def main():
    """Main function"""
    logger.info("="*60)
    logger.info("🤖 Paper Trading Bot Starting")
    logger.info("="*60)
    logger.info("⚠️  PAPER TRADING MODE")
    logger.info("⚠️  Using REAL Mainnet data")
    logger.info("⚠️  Orders are SIMULATED (No real money)")
    logger.info("="*60)
    
    # Create and run bot
    bot = PaperTradingBot()
    
    try:
        await bot.initialize()
        await bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    asyncio.run(main())
