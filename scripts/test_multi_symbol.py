#!/usr/bin/env python3
"""
Test script to verify multi-symbol mode configuration
Run this in Docker to verify all components work
"""

import sys
import os
import yaml
from pathlib import Path

# Add /app to Python path for Docker
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_config():
    """Test configuration loading"""
    print("Testing configuration...")
    
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found")
        return False
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    if "multi_symbol" not in config:
        print("❌ multi_symbol section not found in config")
        return False
    
    multi_symbol = config["multi_symbol"]
    print(f"✅ Multi-symbol config found")
    print(f"   - Enabled: {multi_symbol.get('enabled', False)}")
    print(f"   - Volume threshold: ${multi_symbol.get('volume_threshold', 0):,}")
    print(f"   - Max symbols: {multi_symbol.get('max_symbols', 0)}")
    print(f"   - Refresh interval: {multi_symbol.get('refresh_interval', 0)}s")
    print(f"   - Max position %: {multi_symbol.get('max_position_pct', 0)*100:.1f}%")
    print(f"   - Max exposure %: {multi_symbol.get('max_total_exposure', 0)*100:.1f}%")
    
    return True

def test_imports():
    """Test all required imports"""
    print("\nTesting imports...")
    
    try:
        from src.core.symbol_scanner import SymbolScanner
        print("✅ SymbolScanner imported")
    except Exception as e:
        print(f"❌ Failed to import SymbolScanner: {e}")
        return False
    
    try:
        from src.core.multi_symbol_manager import MultiSymbolManager
        print("✅ MultiSymbolManager imported")
    except Exception as e:
        print(f"❌ Failed to import MultiSymbolManager: {e}")
        return False
    
    try:
        from src.risk.position_manager import PositionManager
        print("✅ PositionManager imported")
    except Exception as e:
        print(f"❌ Failed to import PositionManager: {e}")
        return False
    
    try:
        import psutil
        print("✅ psutil imported")
    except Exception as e:
        print(f"❌ Failed to import psutil: {e}")
        return False
    
    return True

def test_trading_loop():
    """Test TradingLoop instantiation"""
    print("\nTesting TradingLoop...")
    
    try:
        from src.core.trading_loop import TradingLoop
        from decimal import Decimal
        
        # Test single-symbol mode
        loop = TradingLoop(
            symbol="BTCUSDT",
            initial_balance=Decimal("100"),
            testnet=True
        )
        
        mode = "multi-symbol" if loop.multi_symbol_enabled else "single-symbol"
        print(f"✅ TradingLoop instantiated successfully")
        print(f"   - Mode: {mode}")
        print(f"   - Symbol: {loop.symbol}")
        print(f"   - Testnet: {loop.testnet}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to instantiate TradingLoop: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("Multi-Symbol Scanner - Docker Compatibility Test")
    print("="*60)
    
    results = []
    
    results.append(("Configuration", test_config()))
    results.append(("Imports", test_imports()))
    results.append(("TradingLoop", test_trading_loop()))
    
    print("\n" + "="*60)
    print("Test Results:")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("✅ All tests passed! Multi-symbol mode is ready.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
