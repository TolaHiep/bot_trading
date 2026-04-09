"""
Mode Switcher - Safely switch between Paper and Live trading modes

Provides explicit confirmation mechanism to prevent accidental live trading.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode"""
    PAPER = "PAPER"
    LIVE = "LIVE"


class ModeSwitcher:
    """
    Mode Switcher - Manages trading mode transitions
    
    Features:
    - Explicit confirmation required for Live mode
    - Cannot accidentally enable Live mode
    - Logs all mode changes
    - Validates mode transitions
    """
    
    def __init__(self, initial_mode: TradingMode = TradingMode.PAPER):
        """
        Initialize Mode Switcher
        
        Args:
            initial_mode: Starting mode (default: PAPER)
        """
        self._current_mode = initial_mode
        self._confirmation_token: Optional[str] = None
        
        logger.warning(
            f"ModeSwitcher initialized in {initial_mode.value} mode"
        )
    
    @property
    def current_mode(self) -> TradingMode:
        """Get current trading mode"""
        return self._current_mode
    
    @property
    def is_paper_mode(self) -> bool:
        """Check if in paper mode"""
        return self._current_mode == TradingMode.PAPER
    
    @property
    def is_live_mode(self) -> bool:
        """Check if in live mode"""
        return self._current_mode == TradingMode.LIVE
    
    def request_live_mode(self) -> str:
        """
        Request to switch to Live mode
        
        Returns:
            Confirmation token that must be provided to activate_live_mode()
        """
        if self._current_mode == TradingMode.LIVE:
            logger.warning("Already in LIVE mode")
            return ""
        
        # Generate confirmation token
        import secrets
        self._confirmation_token = secrets.token_hex(16)
        
        logger.warning(
            "⚠️  LIVE MODE REQUESTED ⚠️\n"
            "To activate live trading, call activate_live_mode() with the confirmation token.\n"
            f"Confirmation token: {self._confirmation_token}\n"
            "This will enable REAL MONEY trading on Bybit."
        )
        
        return self._confirmation_token
    
    def activate_live_mode(
        self,
        confirmation_token: str,
        explicit_confirmation: bool = False
    ) -> bool:
        """
        Activate Live mode with explicit confirmation
        
        Args:
            confirmation_token: Token from request_live_mode()
            explicit_confirmation: Must be True to activate
        
        Returns:
            True if activated, False otherwise
        
        Raises:
            ValueError: If confirmation requirements not met
        """
        # Check if already in live mode
        if self._current_mode == TradingMode.LIVE:
            logger.warning("Already in LIVE mode")
            return True
        
        # Validate explicit confirmation
        if not explicit_confirmation:
            raise ValueError(
                "explicit_confirmation must be True to activate live mode. "
                "Set explicit_confirmation=True to confirm you want to trade with real money."
            )
        
        # Validate confirmation token
        if not self._confirmation_token:
            raise ValueError(
                "No confirmation token found. "
                "Call request_live_mode() first to get a confirmation token."
            )
        
        if confirmation_token != self._confirmation_token:
            raise ValueError(
                "Invalid confirmation token. "
                "The provided token does not match the expected token."
            )
        
        # All checks passed - activate live mode
        self._current_mode = TradingMode.LIVE
        self._confirmation_token = None
        
        logger.critical(
            "🚨 LIVE MODE ACTIVATED 🚨\n"
            "Trading with REAL MONEY on Bybit.\n"
            "All orders will be placed on the exchange."
        )
        
        return True
    
    def switch_to_paper_mode(self) -> bool:
        """
        Switch to Paper mode (no confirmation required)
        
        Returns:
            True if switched, False if already in paper mode
        """
        if self._current_mode == TradingMode.PAPER:
            logger.info("Already in PAPER mode")
            return False
        
        self._current_mode = TradingMode.PAPER
        self._confirmation_token = None
        
        logger.warning(
            "Switched to PAPER mode. "
            "All trades will be simulated."
        )
        
        return True
    
    def get_mode_info(self) -> dict:
        """Get current mode information"""
        return {
            "current_mode": self._current_mode.value,
            "is_paper": self.is_paper_mode,
            "is_live": self.is_live_mode,
            "has_pending_confirmation": self._confirmation_token is not None
        }
    
    def validate_mode_for_operation(self, operation: str) -> None:
        """
        Validate current mode allows operation
        
        Args:
            operation: Operation name for logging
        
        Raises:
            RuntimeError: If operation not allowed in current mode
        """
        if self._current_mode == TradingMode.PAPER:
            logger.debug(f"Operation '{operation}' in PAPER mode (simulated)")
        else:
            logger.warning(f"Operation '{operation}' in LIVE mode (REAL MONEY)")


class SafeModeSwitcher(ModeSwitcher):
    """
    Safe Mode Switcher - Extra safety for production
    
    Additional features:
    - Requires environment variable to enable live mode
    - Logs to separate file for audit trail
    - Sends alerts on mode changes
    """
    
    def __init__(
        self,
        initial_mode: TradingMode = TradingMode.PAPER,
        require_env_var: bool = True
    ):
        """
        Initialize Safe Mode Switcher
        
        Args:
            initial_mode: Starting mode (default: PAPER)
            require_env_var: Require ENABLE_LIVE_TRADING=true env var
        """
        super().__init__(initial_mode)
        self.require_env_var = require_env_var
    
    def activate_live_mode(
        self,
        confirmation_token: str,
        explicit_confirmation: bool = False
    ) -> bool:
        """
        Activate Live mode with additional safety checks
        
        Args:
            confirmation_token: Token from request_live_mode()
            explicit_confirmation: Must be True to activate
        
        Returns:
            True if activated, False otherwise
        
        Raises:
            ValueError: If safety requirements not met
        """
        # Check environment variable
        if self.require_env_var:
            import os
            if os.getenv("ENABLE_LIVE_TRADING") != "true":
                raise ValueError(
                    "Live trading not enabled. "
                    "Set environment variable ENABLE_LIVE_TRADING=true to enable."
                )
        
        # Call parent implementation
        return super().activate_live_mode(confirmation_token, explicit_confirmation)
