"""
Performance Reporter - Tạo báo cáo hiệu suất giao dịch

Tính toán metrics và export reports
"""

import logging
import json
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    # Time period
    start_date: str
    end_date: str
    period_days: int
    
    # Returns
    initial_balance: float
    final_balance: float
    total_return: float
    total_return_pct: float
    annualized_return_pct: float
    
    # Risk metrics
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    avg_drawdown_pct: float
    recovery_factor: float
    
    # Trading metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_trade: float
    
    # Position metrics
    avg_holding_time_hours: float
    max_position_size: float
    avg_position_size: float


class PerformanceReporter:
    """Generate performance reports"""
    
    def __init__(self):
        """Initialize performance reporter"""
        pass
    
    def calculate_metrics(
        self,
        initial_balance: float,
        final_balance: float,
        trades: List[Dict],
        equity_curve: List[Dict],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> PerformanceMetrics:
        """Calculate performance metrics
        
        Args:
            initial_balance: Initial account balance
            final_balance: Final account balance
            trades: List of trade dictionaries
            equity_curve: List of equity snapshots
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            PerformanceMetrics object
        """
        # Determine time period
        if not start_date and trades:
            start_date = datetime.fromisoformat(trades[0]['timestamp'])
        if not end_date and trades:
            end_date = datetime.fromisoformat(trades[-1]['timestamp'])
        
        if not start_date:
            start_date = datetime.now() - timedelta(days=1)
        if not end_date:
            end_date = datetime.now()
        
        period_days = max(1, (end_date - start_date).days)
        
        # Returns
        total_return = final_balance - initial_balance
        total_return_pct = (total_return / initial_balance * 100) if initial_balance > 0 else 0
        annualized_return_pct = (total_return_pct / period_days * 365) if period_days > 0 else 0
        
        # Trading metrics
        closed_trades = [t for t in trades if t['status'] == 'CLOSED' and t['pnl'] is not None]
        total_trades = len(closed_trades)
        
        if total_trades > 0:
            winning_trades = len([t for t in closed_trades if t['pnl'] > 0])
            losing_trades = len([t for t in closed_trades if t['pnl'] < 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            wins = [t['pnl'] for t in closed_trades if t['pnl'] > 0]
            losses = [abs(t['pnl']) for t in closed_trades if t['pnl'] < 0]
            
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0
            avg_trade = np.mean([t['pnl'] for t in closed_trades])
            
            gross_profit = sum(wins) if wins else 0
            gross_loss = sum(losses) if losses else 0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        else:
            winning_trades = 0
            losing_trades = 0
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            avg_trade = 0
            profit_factor = 0
        
        # Risk metrics
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
        max_dd, max_dd_pct = self._calculate_max_drawdown(equity_curve, initial_balance)
        avg_dd_pct = self._calculate_avg_drawdown(equity_curve, initial_balance)
        recovery_factor = (total_return / abs(max_dd)) if max_dd != 0 else 0
        
        # Position metrics
        avg_holding_time = self._calculate_avg_holding_time(closed_trades)
        max_position_size = max([abs(t['quantity'] * t['entry_price']) for t in trades]) if trades else 0
        avg_position_size = np.mean([abs(t['quantity'] * t['entry_price']) for t in trades]) if trades else 0
        
        return PerformanceMetrics(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            period_days=period_days,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            avg_drawdown_pct=avg_dd_pct,
            recovery_factor=recovery_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade=avg_trade,
            avg_holding_time_hours=avg_holding_time,
            max_position_size=max_position_size,
            avg_position_size=avg_position_size
        )
    
    def _calculate_sharpe_ratio(
        self,
        equity_curve: List[Dict],
        risk_free_rate: float = 0.0
    ) -> float:
        """Calculate Sharpe ratio"""
        if len(equity_curve) < 2:
            return 0.0
        
        # Calculate daily returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1]['equity']
            curr_equity = equity_curve[i]['equity']
            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                returns.append(daily_return)
        
        if not returns:
            return 0.0
        
        # Calculate Sharpe ratio
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        sharpe = (mean_return - risk_free_rate) / std_return * np.sqrt(252)  # Annualized
        return sharpe
    
    def _calculate_max_drawdown(
        self,
        equity_curve: List[Dict],
        initial_balance: float
    ) -> tuple:
        """Calculate maximum drawdown"""
        if not equity_curve:
            return 0.0, 0.0
        
        peak = initial_balance
        max_dd = 0.0
        max_dd_pct = 0.0
        
        for snapshot in equity_curve:
            equity = snapshot['equity']
            
            if equity > peak:
                peak = equity
            
            dd = peak - equity
            dd_pct = (dd / peak * 100) if peak > 0 else 0
            
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        
        return max_dd, max_dd_pct
    
    def _calculate_avg_drawdown(
        self,
        equity_curve: List[Dict],
        initial_balance: float
    ) -> float:
        """Calculate average drawdown"""
        if not equity_curve:
            return 0.0
        
        peak = initial_balance
        drawdowns = []
        
        for snapshot in equity_curve:
            equity = snapshot['equity']
            
            if equity > peak:
                peak = equity
            
            dd_pct = ((peak - equity) / peak * 100) if peak > 0 else 0
            if dd_pct > 0:
                drawdowns.append(dd_pct)
        
        return np.mean(drawdowns) if drawdowns else 0.0
    
    def _calculate_avg_holding_time(self, trades: List[Dict]) -> float:
        """Calculate average holding time in hours"""
        if not trades:
            return 0.0
        
        holding_times = []
        for trade in trades:
            if trade['status'] == 'CLOSED':
                entry_time = datetime.fromisoformat(trade['timestamp'])
                # Assume exit time is now if not provided
                exit_time = datetime.now()
                holding_time = (exit_time - entry_time).total_seconds() / 3600
                holding_times.append(holding_time)
        
        return np.mean(holding_times) if holding_times else 0.0
    
    def export_to_json(
        self,
        metrics: PerformanceMetrics,
        filepath: str
    ) -> None:
        """Export metrics to JSON"""
        with open(filepath, 'w') as f:
            json.dump(asdict(metrics), f, indent=2)
        
        logger.info(f"Performance metrics exported to {filepath}")
    
    def export_to_csv(
        self,
        metrics: PerformanceMetrics,
        filepath: str
    ) -> None:
        """Export metrics to CSV"""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            
            for key, value in asdict(metrics).items():
                writer.writerow([key, value])
        
        logger.info(f"Performance metrics exported to {filepath}")
    
    def generate_summary_report(
        self,
        metrics: PerformanceMetrics
    ) -> str:
        """Generate text summary report"""
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║              PERFORMANCE REPORT                              ║
╚══════════════════════════════════════════════════════════════╝

Period: {metrics.start_date} to {metrics.end_date} ({metrics.period_days} days)

═══════════════════════════════════════════════════════════════
RETURNS
═══════════════════════════════════════════════════════════════
Initial Balance:      ${metrics.initial_balance:,.2f}
Final Balance:        ${metrics.final_balance:,.2f}
Total Return:         ${metrics.total_return:,.2f} ({metrics.total_return_pct:+.2f}%)
Annualized Return:    {metrics.annualized_return_pct:+.2f}%

═══════════════════════════════════════════════════════════════
RISK METRICS
═══════════════════════════════════════════════════════════════
Sharpe Ratio:         {metrics.sharpe_ratio:.2f}
Max Drawdown:         ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)
Avg Drawdown:         {metrics.avg_drawdown_pct:.2f}%
Recovery Factor:      {metrics.recovery_factor:.2f}

═══════════════════════════════════════════════════════════════
TRADING STATISTICS
═══════════════════════════════════════════════════════════════
Total Trades:         {metrics.total_trades}
Winning Trades:       {metrics.winning_trades}
Losing Trades:        {metrics.losing_trades}
Win Rate:             {metrics.win_rate:.1f}%
Profit Factor:        {metrics.profit_factor:.2f}

Average Win:          ${metrics.avg_win:,.2f}
Average Loss:         ${metrics.avg_loss:,.2f}
Average Trade:        ${metrics.avg_trade:,.2f}

═══════════════════════════════════════════════════════════════
POSITION METRICS
═══════════════════════════════════════════════════════════════
Avg Holding Time:     {metrics.avg_holding_time_hours:.1f} hours
Max Position Size:    ${metrics.max_position_size:,.2f}
Avg Position Size:    ${metrics.avg_position_size:,.2f}

═══════════════════════════════════════════════════════════════
"""
        return report
    
    def print_summary(self, metrics: PerformanceMetrics) -> None:
        """Print summary report to console"""
        print(self.generate_summary_report(metrics))
