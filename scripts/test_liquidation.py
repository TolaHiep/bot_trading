"""Test liquidation detection and reporting"""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.execution.paper_trader import PaperTrader
from src.execution.order_manager import OrderSide
from src.execution.cost_filter import Orderbook, OrderbookLevel
from src.monitoring.account_monitor import AccountMonitor


async def test_liquidation():
    """Test liquidation scenario"""
    print("=" * 60)
    print("Testing Liquidation Detection and Reporting")
    print("=" * 60)
    
    # Create paper trader with $100
    paper_trader = PaperTrader(initial_balance=Decimal("100"))
    
    # Create account monitor
    account_monitor = AccountMonitor(
        paper_trader=paper_trader,
        initial_balance=Decimal("100"),
        liquidation_threshold=Decimal("5.0")
    )
    
    # Create fake orderbook
    orderbook = Orderbook(
        symbol="BTCUSDT",
        bids=[
            OrderbookLevel(price=Decimal("70000"), quantity=Decimal("1.0")),
            OrderbookLevel(price=Decimal("69990"), quantity=Decimal("2.0"))
        ],
        asks=[
            OrderbookLevel(price=Decimal("70010"), quantity=Decimal("1.0")),
            OrderbookLevel(price=Decimal("70020"), quantity=Decimal("2.0"))
        ],
        timestamp=1234567890
    )
    
    print("\n1. Opening multiple losing positions...")
    
    # Simulate multiple losing trades with bigger losses
    for i in range(20):  # Increased to 20 trades
        # Open position
        position = await paper_trader.execute_signal(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.001"),
            orderbook=orderbook,
            reason=f"Test trade {i+1}",
            strategy_name="scalp",
            leverage=Decimal("20.0")
        )
        
        if position:
            print(f"   Trade {i+1}: Opened BUY position @ 70010")
            
            # Simulate bigger price drop (bigger loss)
            exit_orderbook = Orderbook(
                symbol="BTCUSDT",
                bids=[
                    OrderbookLevel(price=Decimal("65000"), quantity=Decimal("1.0")),  # Bigger drop
                    OrderbookLevel(price=Decimal("64990"), quantity=Decimal("2.0"))
                ],
                asks=[
                    OrderbookLevel(price=Decimal("65010"), quantity=Decimal("1.0")),
                    OrderbookLevel(price=Decimal("65020"), quantity=Decimal("2.0"))
                ],
                timestamp=1234567890
            )
            
            # Close with loss
            pnl = await paper_trader.close_position(
                position_id=position.position_id,
                orderbook=exit_orderbook,
                reason="Stop loss"
            )
            
            if pnl:
                print(f"   Trade {i+1}: Closed with P&L: ${pnl:.2f}")
            
            # Check account
            account = paper_trader.get_account_summary()
            print(f"   Balance: ${account['current_balance']:.2f}, Equity: ${account['equity']:.2f}")
            
            # Check if liquidated
            current_prices = {"BTCUSDT": Decimal("65000")}
            liquidated = await account_monitor.check_and_handle_liquidation(current_prices)
            
            if liquidated:
                print("\n" + "=" * 60)
                print("LIQUIDATION DETECTED AND HANDLED!")
                print("=" * 60)
                
                # Check new balance
                account = paper_trader.get_account_summary()
                print(f"\nNew balance after reset: ${account['current_balance']:.2f}")
                
                # Show liquidation stats
                stats = account_monitor.get_liquidation_stats()
                print(f"Total liquidations: {stats['total_liquidations']}")
                print(f"Last liquidation: {stats['last_liquidation']}")
                
                break
        else:
            print(f"   Trade {i+1}: Failed to open position")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    print("\nCheck reports/liquidations/ for detailed report")


if __name__ == "__main__":
    asyncio.run(test_liquidation())
