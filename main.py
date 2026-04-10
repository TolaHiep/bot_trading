"""
Trading Bot - Main Entry Point
Live trading with real Bybit API (Paper mode)
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point for live trading with 3 independent bots"""
    print("=" * 60)
    print("🤖 Trading Bot - 3 Bots Live Mode")
    print("=" * 60)
    print()
    
    try:
        # Load config
        import yaml
        from dotenv import load_dotenv
        
        load_dotenv()
        
        config_file = project_root / "config" / "config.yaml"
        if not config_file.exists():
            logger.error("Config file not found: config/config.yaml")
            print("❌ Config file not found!")
            return
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Get settings
        symbol = config.get('symbol', 'BTCUSDT')
        multi_symbol_enabled = config.get('multi_symbol', {}).get('enabled', False)
        scalping_enabled = config.get('scalping', {}).get('enabled', False)
        
        print(f"Symbol: {symbol}")
        print(f"Multi-Symbol: {'Enabled' if multi_symbol_enabled else 'Disabled'}")
        print(f"Scalping: {'Enabled' if scalping_enabled else 'Disabled'}")
        print()
        print("💰 3 Independent Bots:")
        print("  1. Wyckoff (Main): $100")
        print("  2. Scalping V1: $100")
        print("  3. Scalping V2: $100")
        print()
        
        # Initialize Multi-Bot Manager
        from src.core.multi_bot_manager import MultiBotManager
        
        bot_manager = MultiBotManager(config_path=str(config_file))
        logger.info("MultiBotManager initialized with 3 bots")
        
        # Import trading loops
        from src.core.trading_loop import TradingLoop
        from src.core.scalping_loop import ScalpingLoop
        from src.core.scalping_loop_v2 import ScalpingLoopV2
        
        # 1. Create Wyckoff (Main) trading loop
        wyckoff_loop = TradingLoop(
            symbol=symbol,
            initial_balance=Decimal("100"),
            testnet=False,  # Use mainnet (real API)
            config_path=str(config_file)
        )
        # Replace paper trader with bot manager's trader
        wyckoff_loop.paper_trader = bot_manager.get_wyckoff_trader()
        wyckoff_loop.account_monitor = bot_manager.get_wyckoff_monitor()
        
        logger.info("Wyckoff bot initialized")
        
        # 2. Create Scalping V1 loop if enabled
        scalp_v1_loop = None
        if scalping_enabled:
            scalping_symbols = config.get('scalping', {}).get('symbols', [])
            
            scalp_v1_loop = ScalpingLoop(
                paper_trader=bot_manager.get_scalp_trader(),
                symbols=scalping_symbols if scalping_symbols else [symbol],
                testnet=False
            )
            
            # Store reference for symbol sync
            if not scalping_symbols and multi_symbol_enabled:
                wyckoff_loop.scalping_loop = scalp_v1_loop
            
            logger.info("Scalping V1 bot initialized")
        
        # 3. Create Scalping V2 loop if enabled
        scalp_v2_loop = None
        if scalping_enabled:
            scalping_symbols = config.get('scalping', {}).get('symbols', [])
            
            scalp_v2_loop = ScalpingLoopV2(
                paper_trader=bot_manager.get_scalp_v2_trader(),
                symbols=scalping_symbols if scalping_symbols else [symbol],
                testnet=False
            )
            
            # Store reference for symbol sync
            if not scalping_symbols and multi_symbol_enabled:
                wyckoff_loop.scalping_loop_v2 = scalp_v2_loop
            
            logger.info("Scalping V2 bot initialized")
        
        # Store bot manager in wyckoff loop for metrics writing
        wyckoff_loop.bot_manager = bot_manager
        
        # Store scalp_v2_loop reference in bot_manager for targets
        if scalp_v2_loop:
            bot_manager.scalp_v2_loop = scalp_v2_loop
        
        # Start all bots concurrently
        tasks = [wyckoff_loop.start()]
        
        if scalp_v1_loop:
            tasks.append(scalp_v1_loop.start())
        
        if scalp_v2_loop:
            tasks.append(scalp_v2_loop.start())
        
        logger.info(f"Starting {len(tasks)} bots...")
        print(f"🚀 Starting {len(tasks)} bots...\n")
        
        await asyncio.gather(*tasks)
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        print("\n👋 All bots stopped by user")
    
    except Exception as e:
        logger.error(f"Error starting bots: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
