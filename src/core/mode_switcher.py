"""
Mode Switcher - Chuyển đổi giữa Paper, Testnet và Live mode

An toàn và dễ dàng switch mode
"""

import logging
import os
from enum import Enum
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading modes"""
    PAPER = "paper"      # Paper trading với live data (An toàn 100%)
    TESTNET = "testnet"  # Testnet trading với fake money
    LIVE = "live"        # Live trading với real money (NGUY HIỂM)


@dataclass
class ModeConfig:
    """Mode configuration"""
    mode: TradingMode
    use_testnet_api: bool
    use_paper_trader: bool
    require_api_keys: bool
    description: str
    risk_level: str


class ModeSwitcher:
    """Switch between trading modes safely"""
    
    # Mode configurations
    MODE_CONFIGS = {
        TradingMode.PAPER: ModeConfig(
            mode=TradingMode.PAPER,
            use_testnet_api=False,
            use_paper_trader=True,
            require_api_keys=False,
            description="Paper trading với dữ liệu thực từ Bybit Mainnet. An toàn 100%, không cần API keys.",
            risk_level="SAFE"
        ),
        TradingMode.TESTNET: ModeConfig(
            mode=TradingMode.TESTNET,
            use_testnet_api=True,
            use_paper_trader=False,
            require_api_keys=True,
            description="Testnet trading với tiền giả trên Bybit Testnet. Cần Testnet API keys.",
            risk_level="LOW"
        ),
        TradingMode.LIVE: ModeConfig(
            mode=TradingMode.LIVE,
            use_testnet_api=False,
            use_paper_trader=False,
            require_api_keys=True,
            description="Live trading với tiền thật trên Bybit Mainnet. NGUY HIỂM! Cần Mainnet API keys.",
            risk_level="HIGH"
        )
    }
    
    def __init__(self):
        """Initialize mode switcher"""
        self.current_mode: Optional[TradingMode] = None
    
    def get_mode_from_env(self) -> TradingMode:
        """Get trading mode from environment variable
        
        Returns:
            TradingMode enum
        """
        mode_str = os.getenv('TRADING_MODE', 'paper').lower()
        
        mode_map = {
            'paper': TradingMode.PAPER,
            'testnet': TradingMode.TESTNET,
            'live': TradingMode.LIVE
        }
        
        mode = mode_map.get(mode_str, TradingMode.PAPER)
        logger.info(f"Trading mode from environment: {mode.value}")
        
        return mode
    
    def validate_mode(self, mode: TradingMode) -> tuple[bool, Optional[str]]:
        """Validate if mode can be activated
        
        Args:
            mode: Trading mode to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        config = self.MODE_CONFIGS[mode]
        
        # Check API keys if required
        if config.require_api_keys:
            api_key = os.getenv('BYBIT_API_KEY')
            api_secret = os.getenv('BYBIT_API_SECRET')
            
            if not api_key or not api_secret:
                return False, f"API keys required for {mode.value} mode but not found in environment"
            
            # Validate API key format
            if len(api_key) < 10 or len(api_secret) < 10:
                return False, f"Invalid API key format for {mode.value} mode"
        
        # Additional validation for LIVE mode
        if mode == TradingMode.LIVE:
            # Check if user explicitly confirmed
            live_confirmed = os.getenv('LIVE_TRADING_CONFIRMED', 'false').lower()
            if live_confirmed != 'true':
                return False, (
                    "LIVE mode requires explicit confirmation. "
                    "Set LIVE_TRADING_CONFIRMED=true in .env file. "
                    "⚠️ WARNING: This will trade with REAL MONEY!"
                )
            
            # Check minimum balance requirement
            min_balance = float(os.getenv('MIN_LIVE_BALANCE', '100'))
            # Note: Actual balance check would require API call
            logger.warning(
                f"LIVE mode activated. Minimum balance requirement: ${min_balance}"
            )
        
        return True, None
    
    def switch_mode(
        self,
        new_mode: TradingMode,
        force: bool = False
    ) -> tuple[bool, Optional[str]]:
        """Switch to new trading mode
        
        Args:
            new_mode: New trading mode
            force: Force switch without validation (dangerous)
            
        Returns:
            Tuple of (success, error_message)
        """
        # Validate new mode
        if not force:
            is_valid, error_msg = self.validate_mode(new_mode)
            if not is_valid:
                logger.error(f"Mode validation failed: {error_msg}")
                return False, error_msg
        
        # Get configuration
        config = self.MODE_CONFIGS[new_mode]
        
        # Log mode switch
        if self.current_mode:
            logger.warning(
                f"Switching mode: {self.current_mode.value} → {new_mode.value}"
            )
        else:
            logger.info(f"Activating mode: {new_mode.value}")
        
        # Print mode information
        self._print_mode_info(config)
        
        # Update current mode
        self.current_mode = new_mode
        
        return True, None
    
    def _print_mode_info(self, config: ModeConfig) -> None:
        """Print mode information"""
        risk_colors = {
            "SAFE": "🟢",
            "LOW": "🟡",
            "HIGH": "🔴"
        }
        
        risk_emoji = risk_colors.get(config.risk_level, "⚪")
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    TRADING MODE ACTIVATED                    ║
╚══════════════════════════════════════════════════════════════╝

Mode: {config.mode.value.upper()}
Risk Level: {risk_emoji} {config.risk_level}

{config.description}

Configuration:
  • Use Testnet API: {config.use_testnet_api}
  • Use Paper Trader: {config.use_paper_trader}
  • Require API Keys: {config.require_api_keys}

{'⚠️  WARNING: LIVE TRADING MODE - REAL MONEY AT RISK!' if config.mode == TradingMode.LIVE else ''}
{'✅ SAFE MODE - No real money involved' if config.mode == TradingMode.PAPER else ''}

╚══════════════════════════════════════════════════════════════╝
""")
    
    def get_config(self, mode: Optional[TradingMode] = None) -> ModeConfig:
        """Get configuration for mode
        
        Args:
            mode: Trading mode (uses current mode if None)
            
        Returns:
            ModeConfig object
        """
        if mode is None:
            mode = self.current_mode or TradingMode.PAPER
        
        return self.MODE_CONFIGS[mode]
    
    def is_safe_mode(self) -> bool:
        """Check if current mode is safe (paper trading)"""
        return self.current_mode == TradingMode.PAPER
    
    def is_live_mode(self) -> bool:
        """Check if current mode is live trading"""
        return self.current_mode == TradingMode.LIVE
    
    def get_websocket_endpoint(self) -> str:
        """Get WebSocket endpoint for current mode"""
        if not self.current_mode:
            return "wss://stream.bybit.com/v5/public/linear"  # Default mainnet
        
        config = self.get_config()
        
        if config.use_testnet_api:
            return "wss://stream-testnet.bybit.com/v5/public/linear"
        else:
            return "wss://stream.bybit.com/v5/public/linear"
    
    def get_rest_endpoint(self) -> str:
        """Get REST API endpoint for current mode"""
        if not self.current_mode:
            return "https://api.bybit.com"  # Default mainnet
        
        config = self.get_config()
        
        if config.use_testnet_api:
            return "https://api-testnet.bybit.com"
        else:
            return "https://api.bybit.com"
    
    @staticmethod
    def print_mode_comparison():
        """Print comparison of all modes"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║                   TRADING MODE COMPARISON                    ║
╚══════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────┐
│ 1. PAPER TRADING (Khuyến nghị)                              │
├──────────────────────────────────────────────────────────────┤
│ Risk Level:    🟢 SAFE (An toàn 100%)                       │
│ Data Source:   Bybit Mainnet (Real-time)                    │
│ Execution:     Simulated (No real orders)                   │
│ Balance:       100 USDT (Fake money)                        │
│ API Keys:      Not required                                 │
│ Use Case:      Test strategy safely                         │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 2. TESTNET TRADING                                           │
├──────────────────────────────────────────────────────────────┤
│ Risk Level:    🟡 LOW (Tiền giả)                            │
│ Data Source:   Bybit Testnet                                │
│ Execution:     Real orders (Testnet)                        │
│ Balance:       10,000 USDT (Fake money)                     │
│ API Keys:      Testnet keys required                        │
│ Use Case:      Test API integration                         │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 3. LIVE TRADING ⚠️                                           │
├──────────────────────────────────────────────────────────────┤
│ Risk Level:    🔴 HIGH (NGUY HIỂM!)                         │
│ Data Source:   Bybit Mainnet                                │
│ Execution:     Real orders (Mainnet)                        │
│ Balance:       Your real money                              │
│ API Keys:      Mainnet keys required                        │
│ Use Case:      Production trading (After thorough testing)  │
└──────────────────────────────────────────────────────────────┘

Khuyến nghị:
1. Bắt đầu với PAPER TRADING để test chiến lược
2. Chuyển sang TESTNET để test API integration
3. Chỉ dùng LIVE sau khi đã test kỹ và hiểu rõ rủi ro

╚══════════════════════════════════════════════════════════════╝
""")


# Example usage
if __name__ == "__main__":
    # Print comparison
    ModeSwitcher.print_mode_comparison()
    
    # Create switcher
    switcher = ModeSwitcher()
    
    # Get mode from environment
    mode = switcher.get_mode_from_env()
    
    # Switch to mode
    success, error = switcher.switch_mode(mode)
    
    if success:
        print(f"\n✅ Mode activated successfully: {mode.value}")
        print(f"WebSocket: {switcher.get_websocket_endpoint()}")
        print(f"REST API: {switcher.get_rest_endpoint()}")
    else:
        print(f"\n❌ Failed to activate mode: {error}")
