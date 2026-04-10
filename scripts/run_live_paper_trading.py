#!/usr/bin/env python3
"""
Run Live Paper Trading - Chạy paper trading với dữ liệu thực từ Bybit

Sử dụng:
    python scripts/run_live_paper_trading.py
    
Hoặc với Docker:
    docker-compose up trading-bot
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.trading_loop import main

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║         QUANTITATIVE TRADING BOT - PAPER TRADING MODE        ║
╚══════════════════════════════════════════════════════════════╝

Starting live paper trading with 100 USDT initial balance...
Press Ctrl+C to stop gracefully.

""")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)
