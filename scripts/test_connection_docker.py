"""
Test Bybit connection from Docker container
Run this inside the trading_bot container to verify API connection
"""
import os
from pybit.unified_trading import HTTP

def test_connection():
    print("=" * 60)
    print("Bybit Testnet Connection Test (Docker)")
    print("=" * 60)
    print()
    
    # Get credentials from environment
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    testnet = os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
    
    if not api_key or not api_secret:
        print("❌ Error: API credentials not found in environment variables")
        print("   Make sure .env file is properly configured")
        return False
    
    if api_key == 'your_testnet_api_key_here':
        print("❌ Error: Please update API credentials in .env file")
        return False
    
    try:
        # Initialize client
        session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        print("✅ Bybit client initialized")
        
        # Test 1: Get server time
        server_time = session.get_server_time()
        if server_time['retCode'] == 0:
            print(f"✅ Connected to Bybit {'Testnet' if testnet else 'Mainnet'}")
            print(f"   Server Time: {server_time['result']['timeSecond']}")
        else:
            print(f"❌ Server time check failed: {server_time['retMsg']}")
            return False
        
        # Test 2: Get account balance
        balance = session.get_wallet_balance(accountType="UNIFIED")
        if balance['retCode'] == 0:
            print("✅ Account Balance Retrieved")
            usdt_balance = None
            for coin in balance['result']['list'][0]['coin']:
                if coin['coin'] == 'USDT':
                    usdt_balance = float(coin['walletBalance'])
                    available = float(coin['availableToWithdraw'])
                    print(f"   USDT Balance: {usdt_balance}")
                    print(f"   Available: {available}")
                    break
            
            if usdt_balance is None:
                print("   ⚠️  No USDT found in Unified Trading Account")
                print("   Please transfer USDT from Spot Account to Unified Trading Account")
        else:
            print(f"❌ Balance check failed: {balance['retMsg']}")
            return False
        
        # Test 3: Get market data
        ticker = session.get_tickers(category="linear", symbol="BTCUSDT")
        if ticker['retCode'] == 0:
            print("✅ Market Data Retrieved")
            price = ticker['result']['list'][0]['lastPrice']
            print(f"   BTC Price: ${float(price):,.2f}")
        else:
            print(f"❌ Market data check failed: {ticker['retMsg']}")
            return False
        
        print()
        print("🎉 All tests passed! Your Bybit Testnet connection is working.")
        print("You are ready to start development!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your API credentials and network connection")
        return False

if __name__ == "__main__":
    success = test_connection()
    exit(0 if success else 1)
