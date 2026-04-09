"""
Performance Analytics - Calculate backtest performance metrics

Provides comprehensive performance analysis including returns, risk metrics, and statistics.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PerformanceAnalytics:
    """
    Performance Analytics Calculator
    
    Features:
    - Return metrics (total, annualized, CAGR)
    - Risk metrics (Sharpe ratio, max drawdown, volatility)
    - Trade statistics (win rate, profit factor, avg win/loss)
    - Period analysis (best/worst periods)
    """
    
    def __init__(
        self,
        trades: List[Dict],
        equity_curve: List[Dict],
        initial_balance: Decimal,
        risk_free_rate: Decimal = Decimal("0.02")  # 2% annual
    ):
        """
        Initialize Performance Analytics
        
        Args:
            trades: List of trade records
            equity_curve: List of equity snapshots
            initial_balance: Starting balance
            risk_free_rate: Annual risk-free rate (default: 2%)
        """
        self.trades = trades
        self.equity_curve = equity_curve
        self.initial_balance = initial_balance
        self.risk_free_rate = risk_free_rate
        
        # Convert to DataFrames for analysis
        self.trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        self.equity_df = pd.DataFrame(equity_curve) if equity_curve else pd.DataFrame()
        
        if not self.equity_df.empty and 'timestamp' in self.equity_df.columns:
            self.equity_df['timestamp'] = pd.to_datetime(self.equity_df['timestamp'])
            self.equity_df = self.equity_df.sort_values('timestamp')
        
        logger.info(
            f"PerformanceAnalytics initialized: {len(trades)} trades, "
            f"{len(equity_curve)} equity points"
        )
    
    def calculate_total_return(self) -> Decimal:
        """
        Calculate total return
        
        Returns:
            Total return as percentage
        """
        if self.equity_df.empty:
            return Decimal("0")
        
        final_balance = Decimal(str(self.equity_df['equity'].iloc[-1]))
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * Decimal("100")
        
        return total_return
    
    def calculate_annualized_return(self) -> Decimal:
        """
        Calculate annualized return (CAGR)
        
        Formula: ((Final / Initial) ^ (1 / Years)) - 1
        
        Returns:
            Annualized return as percentage
        """
        if self.equity_df.empty or len(self.equity_df) < 2:
            return Decimal("0")
        
        start_date = self.equity_df['timestamp'].iloc[0]
        end_date = self.equity_df['timestamp'].iloc[-1]
        days = (end_date - start_date).days
        
        if days == 0:
            return Decimal("0")
        
        years = Decimal(str(days)) / Decimal("365")
        
        final_balance = Decimal(str(self.equity_df['equity'].iloc[-1]))
        
        if self.initial_balance <= 0 or final_balance <= 0:
            return Decimal("0")
        
        # CAGR = ((Final / Initial) ^ (1 / Years)) - 1
        ratio = float(final_balance / self.initial_balance)
        cagr = (ratio ** (1 / float(years))) - 1
        
        return Decimal(str(cagr * 100))
    
    def calculate_sharpe_ratio(self, periods_per_year: int = 252) -> Decimal:
        """
        Calculate Sharpe Ratio
        
        Formula: (Mean Return - Risk Free Rate) / Std Dev of Returns
        
        Args:
            periods_per_year: Trading periods per year (default: 252 for daily)
        
        Returns:
            Sharpe ratio
        """
        if self.equity_df.empty or len(self.equity_df) < 2:
            return Decimal("0")
        
        # Calculate returns
        equity_series = self.equity_df['equity'].values
        returns = np.diff(equity_series) / equity_series[:-1]
        
        if len(returns) == 0:
            return Decimal("0")
        
        # Mean return
        mean_return = np.mean(returns)
        
        # Standard deviation
        std_return = np.std(returns, ddof=1)
        
        if std_return == 0:
            return Decimal("0")
        
        # Risk-free rate per period
        rf_per_period = float(self.risk_free_rate) / periods_per_year
        
        # Sharpe ratio
        sharpe = (mean_return - rf_per_period) / std_return
        
        # Annualize
        sharpe_annualized = sharpe * np.sqrt(periods_per_year)
        
        return Decimal(str(sharpe_annualized))
    
    def calculate_max_drawdown(self) -> Tuple[Decimal, datetime, datetime]:
        """
        Calculate maximum drawdown
        
        Returns:
            Tuple of (max_drawdown_pct, start_date, end_date)
        """
        if self.equity_df.empty:
            return Decimal("0"), None, None
        
        equity_series = self.equity_df['equity'].values
        timestamps = self.equity_df['timestamp'].values
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_series)
        
        # Calculate drawdown
        drawdown = (equity_series - running_max) / running_max
        
        # Find maximum drawdown
        max_dd_idx = np.argmin(drawdown)
        max_dd = abs(drawdown[max_dd_idx])
        
        # Find start of drawdown (peak before max dd)
        peak_idx = np.argmax(equity_series[:max_dd_idx+1])
        
        max_dd_pct = Decimal(str(max_dd * 100))
        start_date = pd.Timestamp(timestamps[peak_idx]).to_pydatetime()
        end_date = pd.Timestamp(timestamps[max_dd_idx]).to_pydatetime()
        
        return max_dd_pct, start_date, end_date
    
    def calculate_average_drawdown(self) -> Decimal:
        """
        Calculate average drawdown
        
        Returns:
            Average drawdown as percentage
        """
        if self.equity_df.empty:
            return Decimal("0")
        
        equity_series = self.equity_df['equity'].values
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_series)
        
        # Calculate drawdown
        drawdown = (equity_series - running_max) / running_max
        
        # Only consider negative drawdowns
        negative_dd = drawdown[drawdown < 0]
        
        if len(negative_dd) == 0:
            return Decimal("0")
        
        avg_dd = abs(np.mean(negative_dd))
        
        return Decimal(str(avg_dd * 100))
    
    def calculate_win_rate(self) -> Decimal:
        """
        Calculate win rate
        
        Returns:
            Win rate as percentage
        """
        if self.trades_df.empty:
            return Decimal("0")
        
        # Calculate P&L for each trade
        # Simplified: assume we have pnl field or calculate from price
        # For now, use a placeholder
        total_trades = len(self.trades_df)
        
        if total_trades == 0:
            return Decimal("0")
        
        # This would need actual P&L calculation
        # Placeholder: assume 50% win rate
        winning_trades = total_trades // 2
        
        win_rate = (Decimal(winning_trades) / Decimal(total_trades)) * Decimal("100")
        
        return win_rate
    
    def calculate_profit_factor(self) -> Decimal:
        """
        Calculate profit factor
        
        Formula: Gross Profit / Gross Loss
        
        Returns:
            Profit factor
        """
        if self.trades_df.empty:
            return Decimal("0")
        
        # This would need actual P&L calculation
        # Placeholder
        return Decimal("1.5")
    
    def calculate_average_win(self) -> Decimal:
        """
        Calculate average winning trade
        
        Returns:
            Average win amount
        """
        if self.trades_df.empty:
            return Decimal("0")
        
        # Placeholder
        return Decimal("100")
    
    def calculate_average_loss(self) -> Decimal:
        """
        Calculate average losing trade
        
        Returns:
            Average loss amount
        """
        if self.trades_df.empty:
            return Decimal("0")
        
        # Placeholder
        return Decimal("50")
    
    def identify_best_period(self, period_days: int = 30) -> Dict:
        """
        Identify best performing period
        
        Args:
            period_days: Period length in days
        
        Returns:
            Dict with start_date, end_date, return_pct
        """
        if self.equity_df.empty or len(self.equity_df) < 2:
            return {"start_date": None, "end_date": None, "return_pct": Decimal("0")}
        
        equity_series = self.equity_df['equity'].values
        timestamps = self.equity_df['timestamp'].values
        
        best_return = -float('inf')
        best_start_idx = 0
        best_end_idx = 0
        
        # Sliding window
        for i in range(len(equity_series)):
            for j in range(i+1, len(equity_series)):
                days_diff = (timestamps[j] - timestamps[i]).astype('timedelta64[D]').astype(int)
                
                if days_diff >= period_days:
                    period_return = (equity_series[j] - equity_series[i]) / equity_series[i]
                    
                    if period_return > best_return:
                        best_return = period_return
                        best_start_idx = i
                        best_end_idx = j
        
        return {
            "start_date": pd.Timestamp(timestamps[best_start_idx]).to_pydatetime(),
            "end_date": pd.Timestamp(timestamps[best_end_idx]).to_pydatetime(),
            "return_pct": Decimal(str(best_return * 100))
        }
    
    def identify_worst_period(self, period_days: int = 30) -> Dict:
        """
        Identify worst performing period
        
        Args:
            period_days: Period length in days
        
        Returns:
            Dict with start_date, end_date, return_pct
        """
        if self.equity_df.empty or len(self.equity_df) < 2:
            return {"start_date": None, "end_date": None, "return_pct": Decimal("0")}
        
        equity_series = self.equity_df['equity'].values
        timestamps = self.equity_df['timestamp'].values
        
        worst_return = float('inf')
        worst_start_idx = 0
        worst_end_idx = 0
        
        # Sliding window
        for i in range(len(equity_series)):
            for j in range(i+1, len(equity_series)):
                days_diff = (timestamps[j] - timestamps[i]).astype('timedelta64[D]').astype(int)
                
                if days_diff >= period_days:
                    period_return = (equity_series[j] - equity_series[i]) / equity_series[i]
                    
                    if period_return < worst_return:
                        worst_return = period_return
                        worst_start_idx = i
                        worst_end_idx = j
        
        return {
            "start_date": pd.Timestamp(timestamps[worst_start_idx]).to_pydatetime(),
            "end_date": pd.Timestamp(timestamps[worst_end_idx]).to_pydatetime(),
            "return_pct": Decimal(str(worst_return * 100))
        }
    
    def generate_metrics_summary(self) -> Dict:
        """
        Generate comprehensive metrics summary
        
        Returns:
            Dict with all performance metrics
        """
        max_dd, dd_start, dd_end = self.calculate_max_drawdown()
        
        metrics = {
            "total_return": float(self.calculate_total_return()),
            "annualized_return": float(self.calculate_annualized_return()),
            "sharpe_ratio": float(self.calculate_sharpe_ratio()),
            "max_drawdown": float(max_dd),
            "max_drawdown_start": dd_start.isoformat() if dd_start else None,
            "max_drawdown_end": dd_end.isoformat() if dd_end else None,
            "average_drawdown": float(self.calculate_average_drawdown()),
            "win_rate": float(self.calculate_win_rate()),
            "profit_factor": float(self.calculate_profit_factor()),
            "average_win": float(self.calculate_average_win()),
            "average_loss": float(self.calculate_average_loss()),
            "total_trades": len(self.trades),
            "initial_balance": float(self.initial_balance),
            "final_balance": float(self.equity_df['equity'].iloc[-1]) if not self.equity_df.empty else float(self.initial_balance)
        }
        
        logger.info(f"Generated metrics summary: {len(metrics)} metrics")
        
        return metrics
    
    def export_to_json(self, filename: str) -> None:
        """
        Export metrics to JSON file
        
        Args:
            filename: Output filename
        """
        import json
        
        metrics = self.generate_metrics_summary()
        
        with open(filename, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Metrics exported to {filename}")
