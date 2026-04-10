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
    """Main entry point for live trading"""
    print("=" * 60)
    print("🤖 Trading Bot - Live Mode")
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
        initial_balance = Decimal(str(config.get('initial_balance', 100)))
        multi_symbol_enabled = config.get('multi_symbol', {}).get('enabled', False)
        scalping_enabled = config.get('scalping', {}).get('enabled', False)
        
        print(f"Symbol: {symbol}")
        print(f"Initial Balance: {initial_balance} USDT")
        print(f"Multi-Symbol: {'Enabled' if multi_symbol_enabled else 'Disabled'}")
        print(f"Scalping: {'Enabled' if scalping_enabled else 'Disabled'}")
        print()
        
        # Import trading loop
        from src.core.trading_loop import TradingLoop
        
        # Create trading loop
        trading_loop = TradingLoop(
            symbol=symbol,
            initial_balance=initial_balance,
            testnet=False,  # Use mainnet (real API)
            config_path=str(config_file)
        )
        
        # Start scalping loop if enabled
        scalping_loop = None
        if scalping_enabled:
            from src.core.scalping_loop import ScalpingLoop
            
            # Get scalping symbols from config
            scalping_symbols = config.get('scalping', {}).get('symbols', [])
            
            # If empty, use multi_symbol scanner results
            if not scalping_symbols:
                if multi_symbol_enabled and hasattr(trading_loop, 'multi_symbol_manager'):
                    # Get all symbols from multi_symbol_manager after it's initialized
                    # We'll start scalping loop after trading_loop starts
                    logger.info("Scalping will use all symbols from multi-symbol scanner")
                    scalping_symbols = []  # Will be populated dynamically
                else:
                    scalping_symbols = [symbol]
                    logger.info(f"Scalping using single symbol: {symbol}")
            else:
                logger.info(f"Scalping using {len(scalping_symbols)} configured symbols")
            
            scalping_loop = ScalpingLoop(
                paper_trader=trading_loop.paper_trader,
                symbols=scalping_symbols if scalping_symbols else [symbol],
                testnet=False
            )
            
            # If using multi-symbol, we'll update symbols after scanner runs
            if not scalping_symbols and multi_symbol_enabled:
                trading_loop.scalping_loop = scalping_loop  # Store reference
            
            asyncio.create_task(scalping_loop.start())
            logger.info(f"Scalping loop started")
        
        # Start main trading loop
        await trading_loop.start()
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        print("\n👋 Bot stopped by user")
    
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
