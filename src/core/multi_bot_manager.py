"""
Multi-Bot Manager - Quản lý 3 bot với ví riêng biệt
- Wyckoff (Main): $100
- Scalping V1: $100
- Scalping V2: $100
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict

from src.execution.paper_trader import PaperTrader
from src.monitoring.account_monitor import AccountMonitor

logger = logging.getLogger(__name__)


class BotMetricsWriter:
    """Write metrics for individual bot"""
    
    def __init__(self, bot_name: str, metrics_file: str):
        self.bot_name = bot_name
        self.metrics_file = metrics_file
        os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
    
    def write_metrics(
        self,
        paper_trader: PaperTrader,
        current_prices: Dict[str, Decimal],
        config: dict,
        extra_stats: dict = None
    ) -> None:
        """Write metrics to file
        
        Args:
            paper_trader: PaperTrader instance
            current_prices: Current prices for PnL calculation
            config: Bot configuration
            extra_stats: Extra statistics (e.g., monitored_symbols)
        """
        try:
            # Get account summary
            account = paper_trader.get_account_summary(current_prices)
            
            # Get positions
            positions = paper_trader.get_all_positions()
            
            # Prepare metrics data
            data = {
                "timestamp": datetime.now().isoformat(),
                "bot_name": self.bot_name,
                "account": {
                    "initial_balance": account['initial_balance'],
                    "balance": account['current_balance'],
                    "equity": account['equity'],
                    "realized_pnl": account['realized_pnl'],
                    "unrealized_pnl": account['unrealized_pnl']
                },
                "stats": {
                    "total_trades": account['total_trades'],
                    "winning_trades": account['winning_trades'],
                    "losing_trades": account['losing_trades'],
                    "win_rate": account['win_rate'],
                    "open_positions": len(positions)
                },
                "config": config
            }
            
            # Add extra stats if provided
            if extra_stats:
                data["stats"].update(extra_stats)
            
            # Write to file
            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error writing metrics for {self.bot_name}: {e}")


class MultiBotManager:
    """
    Manage multiple trading bots with separate wallets
    
    Features:
    - 3 independent bots with $100 each
    - Separate metrics files
    - Auto-reset on liquidation
    - Cross margin for each bot
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize multi-bot manager
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        
        # Load config
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize paper traders (one per bot)
        self.wyckoff_trader = PaperTrader(
            initial_balance=Decimal("100"),
            kill_switch=None  # Will be set by trading_loop
        )
        
        self.scalp_trader = PaperTrader(
            initial_balance=Decimal("100"),
            kill_switch=None  # Will be set by scalping_loop
        )
        
        self.scalp_v2_trader = PaperTrader(
            initial_balance=Decimal("100"),
            kill_switch=None  # Will be set by scalping_loop_v2
        )
        
        # Initialize account monitors
        self.wyckoff_monitor = AccountMonitor(
            paper_trader=self.wyckoff_trader,
            initial_balance=Decimal("100"),
            liquidation_threshold=Decimal("5.0"),
            report_dir="reports/liquidations/wyckoff"
        )
        
        self.scalp_monitor = AccountMonitor(
            paper_trader=self.scalp_trader,
            initial_balance=Decimal("100"),
            liquidation_threshold=Decimal("5.0"),
            report_dir="reports/liquidations/scalp"
        )
        
        self.scalp_v2_monitor = AccountMonitor(
            paper_trader=self.scalp_v2_trader,
            initial_balance=Decimal("100"),
            liquidation_threshold=Decimal("5.0"),
            report_dir="reports/liquidations/scalp_v2"
        )
        
        # Initialize metrics writers
        self.wyckoff_metrics = BotMetricsWriter(
            bot_name="wyckoff",
            metrics_file="logs/metrics_wyckoff.json"
        )
        
        self.scalp_metrics = BotMetricsWriter(
            bot_name="scalp",
            metrics_file="logs/metrics_scalp.json"
        )
        
        self.scalp_v2_metrics = BotMetricsWriter(
            bot_name="scalp_v2",
            metrics_file="logs/metrics_scalp_v2.json"
        )
        
        logger.info("MultiBotManager initialized with 3 independent bots")
    
    def get_wyckoff_trader(self) -> PaperTrader:
        """Get Wyckoff paper trader"""
        return self.wyckoff_trader
    
    def get_scalp_trader(self) -> PaperTrader:
        """Get Scalp V1 paper trader"""
        return self.scalp_trader
    
    def get_scalp_v2_trader(self) -> PaperTrader:
        """Get Scalp V2 paper trader"""
        return self.scalp_v2_trader
    
    def get_wyckoff_monitor(self) -> AccountMonitor:
        """Get Wyckoff account monitor"""
        return self.wyckoff_monitor
    
    def get_scalp_monitor(self) -> AccountMonitor:
        """Get Scalp V1 account monitor"""
        return self.scalp_monitor
    
    def get_scalp_v2_monitor(self) -> AccountMonitor:
        """Get Scalp V2 account monitor"""
        return self.scalp_v2_monitor
    
    async def check_liquidations(
        self,
        wyckoff_prices: Dict[str, Decimal],
        scalp_prices: Dict[str, Decimal],
        scalp_v2_prices: Dict[str, Decimal]
    ) -> None:
        """Check all bots for liquidation
        
        Args:
            wyckoff_prices: Current prices for Wyckoff bot
            scalp_prices: Current prices for Scalp V1 bot
            scalp_v2_prices: Current prices for Scalp V2 bot
        """
        # Check Wyckoff
        liquidated = await self.wyckoff_monitor.check_and_handle_liquidation(wyckoff_prices)
        if liquidated:
            logger.critical("🚨 Wyckoff bot liquidated and reset!")
        
        # Check Scalp V1
        liquidated = await self.scalp_monitor.check_and_handle_liquidation(scalp_prices)
        if liquidated:
            logger.critical("🚨 Scalp V1 bot liquidated and reset!")
        
        # Check Scalp V2
        liquidated = await self.scalp_v2_monitor.check_and_handle_liquidation(scalp_v2_prices)
        if liquidated:
            logger.critical("🚨 Scalp V2 bot liquidated and reset!")
    
    def write_all_metrics(
        self,
        wyckoff_prices: Dict[str, Decimal],
        scalp_prices: Dict[str, Decimal],
        scalp_v2_prices: Dict[str, Decimal],
        monitored_symbols: int = 0
    ) -> None:
        """Write metrics for all bots
        
        Args:
            wyckoff_prices: Current prices for Wyckoff bot
            scalp_prices: Current prices for Scalp V1 bot
            scalp_v2_prices: Current prices for Scalp V2 bot
            monitored_symbols: Number of monitored symbols (for Wyckoff)
        """
        # Wyckoff metrics
        self.wyckoff_metrics.write_metrics(
            paper_trader=self.wyckoff_trader,
            current_prices=wyckoff_prices,
            config={
                "mode": "multi_symbol" if self.config.get("multi_symbol", {}).get("enabled") else "single_symbol"
            },
            extra_stats={"monitored_symbols": monitored_symbols}
        )
        
        # Scalp V1 metrics
        scalp_config = self.config.get("scalping", {})
        risk_cfg = scalp_config.get("risk", {})
        self.scalp_metrics.write_metrics(
            paper_trader=self.scalp_trader,
            current_prices=scalp_prices,
            config={
                "risk_per_trade": risk_cfg.get("risk_per_trade", 0.05),
                "leverage": risk_cfg.get("leverage", 20.0)
            }
        )
        
        # Scalp V2 metrics
        sl_cfg = scalp_config.get("stop_loss", {})
        tp_cfg = scalp_config.get("take_profit", {})
        self.scalp_v2_metrics.write_metrics(
            paper_trader=self.scalp_v2_trader,
            current_prices=scalp_v2_prices,
            config={
                "risk_per_trade": risk_cfg.get("risk_per_trade", 0.025),
                "leverage": risk_cfg.get("leverage", 12.0),
                "sl_method": sl_cfg.get("method", "atr"),
                "tp1_pct": tp_cfg.get("target1_pct", 0.004),
                "tp2_pct": tp_cfg.get("target2_pct", 0.008)
            }
        )
        
        # Write positions separately for Telegram commands
        self._write_positions_files(wyckoff_prices, scalp_prices, scalp_v2_prices)
    
    def _write_positions_files(
        self,
        wyckoff_prices: Dict[str, Decimal],
        scalp_prices: Dict[str, Decimal],
        scalp_v2_prices: Dict[str, Decimal]
    ) -> None:
        """Write positions to separate files for Telegram
        
        Args:
            wyckoff_prices: Current prices for Wyckoff bot
            scalp_prices: Current prices for Scalp V1 bot
            scalp_v2_prices: Current prices for Scalp V2 bot
        """
        try:
            import json
            from datetime import datetime
            
            # Wyckoff positions
            wyckoff_positions = self.wyckoff_trader.get_all_positions()
            wyckoff_account = self.wyckoff_trader.get_account_summary(wyckoff_prices)
            
            wyckoff_pos_data = {
                "timestamp": datetime.now().isoformat(),
                "bot_name": "wyckoff",
                "account": {
                    "balance": wyckoff_account['current_balance'],
                    "equity": wyckoff_account['equity'],
                    "unrealized_pnl": wyckoff_account['unrealized_pnl']
                },
                "positions": [
                    {
                        "symbol": pos.symbol,
                        "side": pos.side.value,
                        "entry_price": float(pos.entry_price),
                        "current_price": float(wyckoff_prices.get(pos.symbol, pos.entry_price)),
                        "quantity": float(pos.quantity),
                        "unrealized_pnl": float(pos.calculate_pnl(wyckoff_prices.get(pos.symbol, pos.entry_price)))
                    }
                    for pos in wyckoff_positions
                ]
            }
            
            with open("logs/metrics_wyckoff_positions.json", "w") as f:
                json.dump(wyckoff_pos_data, f, indent=2)
            
            # Scalp V1 positions
            scalp_positions = self.scalp_trader.get_all_positions()
            scalp_account = self.scalp_trader.get_account_summary(scalp_prices)
            
            scalp_pos_data = {
                "timestamp": datetime.now().isoformat(),
                "bot_name": "scalp",
                "account": {
                    "balance": scalp_account['current_balance'],
                    "equity": scalp_account['equity'],
                    "unrealized_pnl": scalp_account['unrealized_pnl']
                },
                "positions": [
                    {
                        "symbol": pos.symbol,
                        "side": pos.side.value,
                        "entry_price": float(pos.entry_price),
                        "current_price": float(scalp_prices.get(pos.symbol, pos.entry_price)),
                        "quantity": float(pos.quantity),
                        "unrealized_pnl": float(pos.calculate_pnl(scalp_prices.get(pos.symbol, pos.entry_price)))
                    }
                    for pos in scalp_positions
                ]
            }
            
            with open("logs/metrics_scalp_positions.json", "w") as f:
                json.dump(scalp_pos_data, f, indent=2)
            
            # Scalp V2 positions (with targets)
            scalp_v2_positions = self.scalp_v2_trader.get_all_positions()
            scalp_v2_account = self.scalp_v2_trader.get_account_summary(scalp_v2_prices)
            
            # Get targets from scalping_loop_v2 if available (will be set by main.py)
            targets = {}
            if hasattr(self, 'scalp_v2_targets'):
                targets = self.scalp_v2_targets
            
            scalp_v2_pos_data = {
                "timestamp": datetime.now().isoformat(),
                "bot_name": "scalp_v2",
                "account": {
                    "balance": scalp_v2_account['current_balance'],
                    "equity": scalp_v2_account['equity'],
                    "unrealized_pnl": scalp_v2_account['unrealized_pnl']
                },
                "positions": [
                    {
                        "symbol": pos.symbol,
                        "side": pos.side.value,
                        "entry_price": float(pos.entry_price),
                        "current_price": float(scalp_v2_prices.get(pos.symbol, pos.entry_price)),
                        "quantity": float(pos.quantity),
                        "unrealized_pnl": float(pos.calculate_pnl(scalp_v2_prices.get(pos.symbol, pos.entry_price)))
                    }
                    for pos in scalp_v2_positions
                ],
                "targets": targets
            }
            
            with open("logs/metrics_scalp_v2_positions.json", "w") as f:
                json.dump(scalp_v2_pos_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error writing positions files: {e}")
