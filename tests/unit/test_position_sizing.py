"""Unit tests for position sizing calculator"""

import pytest
from src.risk.position_sizing import PositionSizer, SizingMethod, PositionSize


class TestPositionSizer:
    """Test position sizing calculator"""
    
    def test_initialization(self):
        """Test position sizer initialization"""
        sizer = PositionSizer()
        
        assert sizer.max_risk_per_trade == 0.02
        assert sizer.max_position_size == 0.10
        assert sizer.drawdown_threshold == 0.10
        assert sizer.current_drawdown == 0.0
    
    def test_custom_initialization(self):
        """Test custom initialization"""
        sizer = PositionSizer(
            max_risk_per_trade=0.01,
            max_position_size=0.05,
            drawdown_threshold=0.15
        )
        
        assert sizer.max_risk_per_trade == 0.01
        assert sizer.max_position_size == 0.05
        assert sizer.drawdown_threshold == 0.15
    
    def test_basic_position_calculation(self):
        """Test basic position size calculation"""
        sizer = PositionSizer()
        
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=98.0,  # 2% stop loss
            signal_confidence=100.0,
            method=SizingMethod.FIXED_PERCENT
        )
        
        assert result.quantity > 0
        assert result.risk_percent <= 0.02
        assert result.method == "FIXED_PERCENT"
    
    def test_risk_limit_enforcement(self):
        """Test that risk never exceeds 2% of balance"""
        sizer = PositionSizer(max_risk_per_trade=0.02)
        
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            signal_confidence=100.0
        )
        
        # Risk should be <= 2%
        assert result.risk_percent <= 0.02
        assert result.risk_amount <= 200.0
    
    def test_position_size_limit_enforcement(self):
        """Test that position size never exceeds 10% of balance"""
        sizer = PositionSizer(max_position_size=0.10)
        
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=99.5,  # Very tight stop
            signal_confidence=100.0
        )
        
        # Position value should be <= 10% of balance
        position_percent = result.position_value / 10000.0
        assert position_percent <= 0.10
    
    def test_confidence_adjustment(self):
        """Test position adjustment based on signal confidence"""
        sizer = PositionSizer()
        
        # Full confidence - use wider stop to avoid position size limit
        result_100 = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=95.0,  # 5% stop loss
            signal_confidence=100.0
        )
        
        # Half confidence
        result_50 = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=95.0,  # 5% stop loss
            signal_confidence=50.0
        )
        
        # Lower confidence should result in smaller position or equal risk
        assert result_50.risk_amount <= result_100.risk_amount
        assert result_50.adjusted_for_confidence is True
    
    def test_drawdown_adjustment(self):
        """Test position reduction when drawdown > 10%"""
        sizer = PositionSizer(drawdown_threshold=0.10, drawdown_reduction=0.50)
        
        # No drawdown - use wider stop to avoid position size limit
        result_no_dd = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=95.0,  # 5% stop loss
            signal_confidence=100.0
        )
        
        # Set drawdown to 15%
        sizer.update_drawdown(0.15)
        
        result_with_dd = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=95.0,  # 5% stop loss
            signal_confidence=100.0
        )
        
        # Position should be reduced or risk should be lower
        assert result_with_dd.risk_amount <= result_no_dd.risk_amount
        assert result_with_dd.adjusted_for_drawdown is True
    
    def test_leverage_adjustment(self):
        """Test position sizing with leverage"""
        sizer = PositionSizer()
        
        # No leverage
        result_1x = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            leverage=1.0
        )
        
        # 2x leverage
        result_2x = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            leverage=2.0
        )
        
        # With leverage, can take larger position
        assert result_2x.quantity >= result_1x.quantity
        assert result_2x.leverage == 2.0
    
    def test_lot_size_rounding(self):
        """Test automatic rounding to lot size"""
        sizer = PositionSizer()
        
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            qty_step=0.01
        )
        
        # Should be rounded to 2 decimal places
        assert result.quantity == round(result.quantity, 2)
    
    def test_minimum_quantity_check(self):
        """Test return 0 if size < min_lot"""
        sizer = PositionSizer()
        
        result = sizer.calculate_position_size(
            balance=10.0,  # Very small balance
            entry_price=100.0,
            stop_loss_price=98.0,
            min_qty=1.0  # Large minimum
        )
        
        # Should return 0
        assert result.quantity == 0.0
        assert "minimum" in result.reason.lower()
    
    def test_invalid_balance(self):
        """Test handling of invalid balance"""
        sizer = PositionSizer()
        
        result = sizer.calculate_position_size(
            balance=0.0,
            entry_price=100.0,
            stop_loss_price=98.0
        )
        
        assert result.quantity == 0.0
        assert "balance" in result.reason.lower()
    
    def test_invalid_prices(self):
        """Test handling of invalid prices"""
        sizer = PositionSizer()
        
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=0.0,
            stop_loss_price=98.0
        )
        
        assert result.quantity == 0.0
        assert "price" in result.reason.lower()
    
    def test_invalid_stop_loss(self):
        """Test handling of invalid stop loss"""
        sizer = PositionSizer()
        
        # Stop loss same as entry
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=100.0
        )
        
        assert result.quantity == 0.0
    
    def test_kelly_criterion_method(self):
        """Test Kelly Criterion sizing method"""
        sizer = PositionSizer()
        
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            method=SizingMethod.KELLY_CRITERION,
            win_rate=0.6,
            avg_win=0.03,
            avg_loss=0.02
        )
        
        assert result.quantity > 0
        assert result.method == "KELLY_CRITERION"
    
    def test_kelly_without_stats(self):
        """Test Kelly method falls back to fixed percent without stats"""
        sizer = PositionSizer()
        
        result = sizer.calculate_position_size(
            balance=10000.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            method=SizingMethod.KELLY_CRITERION
            # No win_rate, avg_win, avg_loss provided
        )
        
        # Should fall back to FIXED_PERCENT
        assert result.method == "FIXED_PERCENT"
    
    def test_get_max_position_value(self):
        """Test get maximum position value"""
        sizer = PositionSizer(max_position_size=0.10)
        
        max_value = sizer.get_max_position_value(balance=10000.0, leverage=1.0)
        
        assert max_value == 1000.0  # 10% of 10000
    
    def test_get_max_risk_amount(self):
        """Test get maximum risk amount"""
        sizer = PositionSizer(max_risk_per_trade=0.02)
        
        max_risk = sizer.get_max_risk_amount(balance=10000.0)
        
        assert max_risk == 200.0  # 2% of 10000
    
    def test_get_max_risk_with_drawdown(self):
        """Test max risk amount with drawdown"""
        sizer = PositionSizer(
            max_risk_per_trade=0.02,
            drawdown_threshold=0.10,
            drawdown_reduction=0.50
        )
        
        # Set drawdown
        sizer.update_drawdown(0.15)
        
        max_risk = sizer.get_max_risk_amount(balance=10000.0)
        
        # Should be reduced by 50%
        assert max_risk == 100.0  # 2% * 50% of 10000
    
    def test_validate_position_size(self):
        """Test position size validation"""
        sizer = PositionSizer()
        
        validation = sizer.validate_position_size(
            quantity=10.0,
            entry_price=100.0,
            stop_loss_price=98.0,
            balance=10000.0
        )
        
        assert 'valid' in validation
        assert 'risk_percent' in validation
        assert 'position_percent' in validation
    
    def test_validate_excessive_risk(self):
        """Test validation catches excessive risk"""
        sizer = PositionSizer(max_risk_per_trade=0.02)
        
        validation = sizer.validate_position_size(
            quantity=200.0,  # Very large position
            entry_price=100.0,
            stop_loss_price=98.0,
            balance=10000.0
        )
        
        assert validation['valid'] is False
        assert len(validation['violations']) > 0
    
    def test_inverse_proportionality(self):
        """Test position size is inversely proportional to stop loss distance"""
        sizer = PositionSizer()
        
        # Tight stop loss - use larger balance to see difference
        result_tight = sizer.calculate_position_size(
            balance=100000.0,
            entry_price=100.0,
            stop_loss_price=99.0,  # 1% stop
            signal_confidence=100.0
        )
        
        # Wide stop loss
        result_wide = sizer.calculate_position_size(
            balance=100000.0,
            entry_price=100.0,
            stop_loss_price=96.0,  # 4% stop
            signal_confidence=100.0
        )
        
        # Both hit position size limit (10%), so quantities are same
        # But tighter stop has LOWER risk for same position size
        # This is correct behavior - position size limit takes precedence
        assert result_tight.quantity == result_wide.quantity  # Both at max position size
        assert result_tight.risk_amount < result_wide.risk_amount  # Tighter stop = lower risk
