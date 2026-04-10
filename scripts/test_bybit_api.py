#!/usr/bin/env python3
"""
Test Bybit API Connection and Account Balance

This script tests the connection to Bybit Testnet API and retrieves account balance.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.connectors.bybit_rest import RESTClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_api_connection():
    """Test Bybit API connection and get account info"""
    
    # Get credentials
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    
    logger.info("="*60)
    logger.info("🧪 Testing Bybit API Connection")
    logger.info("="*60)
    logger.info(f"API Key: {api_key[:10]}...")
    logger.info(f"Testnet: {testnet}")
    logger.info("="*60)
    
    try:
        # Initialize REST client
        client = RESTClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )
        
        logger.info("✅ REST Client initialized")
        
        # Test 1: Get account balance
        logger.info("\n📊 Test 1: Getting account balance...")
        try:
            balance = await client.get_account_balance()
            logger.info(f"✅ Account Balance: {balance} USDT")
                
        except Exception as e:
            logger.error(f"❌ Failed to get balance: {e}")
            
        # Test 2: Get current positions
        logger.info("\n📊 Test 2: Getting current positions...")
        try:
            position = await client.get_position(symbol="BTCUSDT")
            logger.info(f"✅ Position response: {position}")
                
        except Exception as e:
            logger.error(f"❌ Failed to get positions: {e}")
            
        # Test 3: Get historical klines
        logger.info("\n📊 Test 3: Getting historical klines...")
        try:
            klines = await client.get_klines(
                symbol="BTCUSDT",
                interval="1",
                limit=5
            )
            logger.info(f"✅ Got {len(klines)} klines")
            if klines:
                latest = klines[-1]
                logger.info(f"  Latest kline: Open={latest['open']}, Close={latest['close']}, Volume={latest['volume']}")
        except Exception as e:
            logger.error(f"❌ Failed to get klines: {e}")
            
        logger.info("\n" + "="*60)
        logger.info("✅ API Connection Test Completed")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        

if __name__ == '__main__':
    asyncio.run(test_api_connection())
