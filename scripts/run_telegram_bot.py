#!/usr/bin/env python3
"""
Run Telegram Bot

This script starts the Telegram bot for receiving commands and sending alerts.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.monitoring.telegram_bot import TelegramBot
from src.monitoring.metrics_collector import MetricsCollector

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
    # Get configuration from environment
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_ids_str = os.getenv('TELEGRAM_CHAT_IDS', '')
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment")
        logger.error("Please set TELEGRAM_BOT_TOKEN in .env file")
        return
    
    if not chat_ids_str:
        logger.error("TELEGRAM_CHAT_IDS not found in environment")
        logger.error("Please set TELEGRAM_CHAT_IDS in .env file")
        return
    
    # Parse chat IDs
    try:
        chat_ids = [int(id.strip()) for id in chat_ids_str.split(',') if id.strip()]
    except ValueError:
        logger.error("Invalid TELEGRAM_CHAT_IDS format. Use comma-separated integers.")
        return
    
    if not chat_ids:
        logger.error("No valid chat IDs found")
        return
    
    logger.info(f"Starting Telegram bot with {len(chat_ids)} allowed chat IDs")
    logger.info(f"Allowed chat IDs: {chat_ids}")
    
    # Create metrics collector
    metrics_collector = MetricsCollector()
    
    # Create bot
    bot = TelegramBot(
        bot_token=bot_token,
        allowed_chat_ids=chat_ids,
        metrics_collector=metrics_collector
    )
    
    try:
        # Start bot
        await bot.start()
        logger.info("✅ Telegram bot is running")
        logger.info("📱 Send /start to your bot on Telegram to test")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        await bot.stop()
        logger.info("Telegram bot stopped")


if __name__ == '__main__':
    asyncio.run(main())
