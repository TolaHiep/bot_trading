"""Download Historical Data Script

This script downloads historical market data from Bybit and stores it in TimescaleDB.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from tqdm import tqdm

from src.connectors.bybit_rest import RESTClient
from src.data.timescaledb_writer import TimescaleDBWriter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def download_historical_klines(
    rest_client: RESTClient,
    db_writer: TimescaleDBWriter,
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime
) -> int:
    """Download historical klines for a symbol and timeframe
    
    Args:
        rest_client: Bybit REST client
        db_writer: TimescaleDB writer
        symbol: Trading symbol (e.g., 'BTCUSDT')
        timeframe: Timeframe (e.g., '1m', '5m', '15m', '1h')
        start_date: Start date
        end_date: End date
        
    Returns:
        Number of klines downloaded
    """
    # Convert timeframe to Bybit interval format
    interval_map = {
        '1m': '1',
        '5m': '5',
        '15m': '15',
        '1h': '60',
        '4h': '240',
        '1d': 'D'
    }
    
    interval = interval_map.get(timeframe)
    if not interval:
        logger.error(f"Unsupported timeframe: {timeframe}")
        return 0
    
    # Calculate total expected candles for progress bar
    timeframe_minutes = {
        '1m': 1,
        '5m': 5,
        '15m': 15,
        '1h': 60,
        '4h': 240,
        '1d': 1440
    }
    total_minutes = int((end_date - start_date).total_seconds() / 60)
    expected_candles = total_minutes // timeframe_minutes[timeframe]
    
    print(f"\n📊 Downloading {symbol} {timeframe}")
    print(f"   Period: {start_date.date()} to {end_date.date()}")
    print(f"   Expected: ~{expected_candles:,} candles")
    
    # Convert to milliseconds
    start_time = int(start_date.timestamp() * 1000)
    end_time = int(end_date.timestamp() * 1000)
    
    total_klines = 0
    current_start = start_time
    
    # Progress bar
    pbar = tqdm(total=expected_candles, desc=f"{symbol} {timeframe}", unit="candles", ncols=100)
    
    while current_start < end_time:
        try:
            # Fetch batch (max 200 records)
            klines = await rest_client.get_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_time,
                limit=200
            )
            
            if not klines:
                break
            
            # Bybit returns klines in reverse chronological order
            klines.reverse()
            
            # Convert to our format
            kline_dicts = []
            for kline in klines:
                # Bybit kline format: [timestamp, open, high, low, close, volume, turnover]
                kline_dict = {
                    'timestamp': int(kline[0]),
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'open': kline[1],
                    'high': kline[2],
                    'low': kline[3],
                    'close': kline[4],
                    'volume': kline[5]
                }
                kline_dicts.append(kline_dict)
            
            # Batch write to database
            await db_writer.batch_write_klines(kline_dicts)
            
            total_klines += len(kline_dicts)
            pbar.update(len(kline_dicts))
            
            # Update start time for next batch
            current_start = int(klines[-1][0]) + 1
            
            # Small delay to respect rate limits
            await asyncio.sleep(0.2)
            
        except Exception as e:
            logger.error(f"Error downloading klines: {e}")
            # Continue with next batch
            await asyncio.sleep(1)
            current_start += 200 * 60 * 1000  # Skip ahead
    
    pbar.close()
    print(f"✅ Completed: {total_klines:,} candles")
    
    return total_klines


async def main():
    """Main function"""
    # Configuration
    SYMBOL = os.getenv('SYMBOL', 'BTCUSDT')
    TIMEFRAMES = ['1m', '5m', '15m', '1h']
    
    # Download last 6 months of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    # Get API credentials
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    database_url = os.getenv('DATABASE_URL')
    
    if not all([api_key, api_secret, database_url]):
        logger.error("Missing required environment variables")
        logger.error("Required: BYBIT_API_KEY, BYBIT_API_SECRET, DATABASE_URL")
        return
    
    print("\n" + "="*60)
    print("📥 Historical Data Download")
    print("="*60)
    print(f"Symbol: {SYMBOL}")
    print(f"Period: {start_date.date()} to {end_date.date()} (6 months)")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"Mode: {'Testnet' if testnet else 'Mainnet'}")
    print("="*60 + "\n")
    
    # Initialize clients
    rest_client = RESTClient(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )
    
    db_writer = TimescaleDBWriter(database_url)
    
    try:
        # Connect to database
        await db_writer.connect()
        logger.info("Connected to TimescaleDB")
        
        # Download data for each timeframe
        total_downloaded = 0
        start_time = datetime.now()
        
        for i, timeframe in enumerate(TIMEFRAMES, 1):
            print(f"\n[{i}/{len(TIMEFRAMES)}] Processing {timeframe}...")
            count = await download_historical_klines(
                rest_client=rest_client,
                db_writer=db_writer,
                symbol=SYMBOL,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            total_downloaded += count
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "="*60)
        print("✅ Download Complete!")
        print("="*60)
        print(f"Total candles: {total_downloaded:,}")
        print(f"Time elapsed: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"Average speed: {total_downloaded/elapsed:.0f} candles/sec")
        print("="*60 + "\n")
        
        # Show buffer status
        buffer_status = db_writer.get_buffer_status()
        logger.info(f"Buffer status: {buffer_status}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    
    finally:
        # Cleanup
        await db_writer.disconnect()
        if rest_client.session:
            await rest_client.session.close()
        
        logger.info("Cleanup complete")


if __name__ == '__main__':
    asyncio.run(main())
