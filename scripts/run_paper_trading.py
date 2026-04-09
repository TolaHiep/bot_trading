#!/usr/bin/env python3
"""
Run Paper Trading Bot

This script runs the trading bot in paper trading mode.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function"""
    logger.info("="*60)
    logger.info("🤖 Paper Trading Bot Starting")
    logger.info("="*60)
    
    # Check trading mode
    trading_mode = os.getenv('TRADING_MODE', 'paper')
    logger.info(f"Trading Mode: {trading_mode}")
    
    if trading_mode == 'live':
        logger.warning("⚠️  WARNING: TRADING_MODE is set to 'live'")
        logger.warning("⚠️  This will place REAL orders with REAL money!")
        logger.warning("⚠️  Change to 'paper' in .env for paper trading")
        response = input("Continue with LIVE trading? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Aborted by user")
            return
    
    logger.info("📊 Initializing components...")
    
    # TODO: Initialize trading bot components
    # - Data stream processor
    # - Signal engine
    # - Order manager
    # - Risk manager
    
    logger.info("✅ Paper Trading Bot is running")
    logger.info("📱 Check Telegram for alerts")
    logger.info("📊 Check Dashboard: http://localhost:8501")
    logger.info("Press Ctrl+C to stop")
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
            # TODO: Main trading loop
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        logger.info("Paper Trading Bot stopped")


if __name__ == '__main__':
    asyncio.run(main())
