"""
Unit tests for Performance Analytics
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.backtest.analytics import PerformanceAnalytics


class TestPerformanceAnalytics:
    """Test PerformanceAnalytics"""
    
    def test_analytics_initialization(self):
        """Test analytics initializes correctly"""
        trades = [
            {"timestamp": "2024-01-01T10:00:00", "symbol": "BTCUSDT", "side": "BUY", "price": 50000, "quantity": 0.1}
        ]
        
        equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-01T11:00:00", "balance": 10100, "equity": 10100}
        ]
        
        analytics = PerformanceAnalytics(
            trades=trades,
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        assert analytics.initial_balance == Decimal("10000")
        assert len(analytics.trades) == 1
        assert len(analytics.equity_curve) == 2
    
    def test_calculate_total_return(self):
        """Test total return calculation"""
        equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-02T10:00:00", "balance": 11000, "equity": 11000}
        ]
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        total_return = analytics.calculate_total_return()
        
        # (11000 - 10000) / 10000 * 100 = 10%
        assert total_return == Decimal("10")
    
    def test_calculate_total_return_negative(self):
        """Test negative total return"""
        equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-02T10:00:00", "balance": 9000, "equity": 9000}
        ]
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        total_return = analytics.calculate_total_return()
        
        # (9000 - 10000) / 10000 * 100 = -10%
        assert total_return == Decimal("-10")
    
    def test_calculate_annualized_return(self):
        """Test annualized return calculation"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2025, 1, 1)  # 1 year
        
        equity_curve = [
            {"timestamp": start_date.isoformat(), "balance": 10000, "equity": 10000},
            {"timestamp": end_date.isoformat(), "balance": 12000, "equity": 12000}
        ]
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        annualized_return = analytics.calculate_annualized_return()
        
        # CAGR = ((12000/10000)^(1/1)) - 1 = 0.2 = 20%
        assert abs(annualized_return - Decimal("20")) < Decimal("0.1")
    
    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation"""
        # Create equity curve with consistent returns
        equity_curve = []
        base_equity = 10000
        
        for i in range(100):
            equity = base_equity * (1.01 ** i)  # 1% growth per period
            equity_curve.append({
                "timestamp": (datetime(2024, 1, 1) + timedelta(days=i)).isoformat(),
                "balance": equity,
                "equity": equity
            })
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        sharpe = analytics.calculate_sharpe_ratio()
        
        # Sharpe should be positive for positive returns
        assert sharpe > Decimal("0")
    
    def test_calculate_max_drawdown(self):
        """Test max drawdown calculation"""
        equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-02T10:00:00", "balance": 12000, "equity": 12000},  # Peak
            {"timestamp": "2024-01-03T10:00:00", "balance": 10800, "equity": 10800},  # -10% from peak
            {"timestamp": "2024-01-04T10:00:00", "balance": 11000, "equity": 11000}
        ]
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        max_dd, start_date, end_date = analytics.calculate_max_drawdown()
        
        # Max DD = (10800 - 12000) / 12000 = -10%
        assert abs(max_dd - Decimal("10")) < Decimal("0.1")
        assert start_date is not None
        assert end_date is not None
    
    def test_calculate_average_drawdown(self):
        """Test average drawdown calculation"""
        equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-02T10:00:00", "balance": 9500, "equity": 9500},   # -5%
            {"timestamp": "2024-01-03T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-04T10:00:00", "balance": 9800, "equity": 9800}    # -2%
        ]
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        avg_dd = analytics.calculate_average_drawdown()
        
        # Should be positive (absolute value)
        assert avg_dd > Decimal("0")
    
    def test_generate_metrics_summary(self):
        """Test metrics summary generation"""
        equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-02T10:00:00", "balance": 11000, "equity": 11000}
        ]
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        metrics = analytics.generate_metrics_summary()
        
        assert "total_return" in metrics
        assert "annualized_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert "total_trades" in metrics
        assert "initial_balance" in metrics
        assert "final_balance" in metrics
    
    def test_export_to_json(self, tmp_path):
        """Test JSON export"""
        import json
        
        equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000, "equity": 10000},
            {"timestamp": "2024-01-02T10:00:00", "balance": 11000, "equity": 11000}
        ]
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        json_file = tmp_path / "metrics.json"
        analytics.export_to_json(str(json_file))
        
        assert json_file.exists()
        
        # Verify JSON content
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        assert "total_return" in data
        assert "sharpe_ratio" in data
    
    def test_empty_equity_curve(self):
        """Test handling of empty equity curve"""
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=[],
            initial_balance=Decimal("10000")
        )
        
        total_return = analytics.calculate_total_return()
        assert total_return == Decimal("0")
        
        sharpe = analytics.calculate_sharpe_ratio()
        assert sharpe == Decimal("0")
        
        max_dd, _, _ = analytics.calculate_max_drawdown()
        assert max_dd == Decimal("0")
    
    def test_identify_best_period(self):
        """Test best period identification"""
        equity_curve = []
        for i in range(60):  # 60 days
            equity = 10000 + (i * 100)  # Linear growth
            equity_curve.append({
                "timestamp": (datetime(2024, 1, 1) + timedelta(days=i)).isoformat(),
                "balance": equity,
                "equity": equity
            })
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        best_period = analytics.identify_best_period(period_days=30)
        
        assert best_period["start_date"] is not None
        assert best_period["end_date"] is not None
        assert best_period["return_pct"] > Decimal("0")
    
    def test_identify_worst_period(self):
        """Test worst period identification"""
        equity_curve = []
        for i in range(60):  # 60 days
            # Create a dip in the middle
            if 20 <= i <= 40:
                equity = 10000 - ((i - 20) * 50)
            else:
                equity = 10000 + (i * 10)
            
            equity_curve.append({
                "timestamp": (datetime(2024, 1, 1) + timedelta(days=i)).isoformat(),
                "balance": equity,
                "equity": equity
            })
        
        analytics = PerformanceAnalytics(
            trades=[],
            equity_curve=equity_curve,
            initial_balance=Decimal("10000")
        )
        
        worst_period = analytics.identify_worst_period(period_days=30)
        
        assert worst_period["start_date"] is not None
        assert worst_period["end_date"] is not None
        assert worst_period["return_pct"] < Decimal("0")
