"""
Unit tests for Configuration Management
"""

import pytest
import yaml
from pathlib import Path

from src.config.config_manager import ConfigManager
from src.config.validator import ConfigValidator


class TestConfigManager:
    """Test ConfigManager"""
    
    def test_config_manager_initialization(self):
        """Test ConfigManager initializes correctly"""
        manager = ConfigManager("config/strategy_params.yaml")
        
        assert manager.config_path == Path("config/strategy_params.yaml")
        assert manager.config == {}
    
    def test_load_config(self):
        """Test loading configuration from file"""
        manager = ConfigManager("config/strategy_params.yaml")
        config = manager.load()
        
        assert "indicators" in config
        assert "risk" in config
        assert "execution" in config
    
    def test_get_config_value(self):
        """Test getting configuration value"""
        manager = ConfigManager("config/strategy_params.yaml")
        manager.load()
        
        # Test simple key
        indicators = manager.get("indicators")
        assert indicators is not None
        
        # Test nested key with dot notation
        rsi_period = manager.get("indicators.rsi.period")
        assert rsi_period == 14
    
    def test_get_config_value_default(self):
        """Test getting configuration value with default"""
        manager = ConfigManager("config/strategy_params.yaml")
        manager.load()
        
        # Non-existent key should return default
        value = manager.get("nonexistent.key", default=42)
        assert value == 42
    
    def test_set_config_value(self):
        """Test setting configuration value"""
        manager = ConfigManager("config/strategy_params.yaml")
        manager.load()
        
        # Set value
        manager.set("indicators.rsi.period", 20)
        
        # Verify
        assert manager.get("indicators.rsi.period") == 20
    
    def test_get_indicator_params(self):
        """Test getting indicator parameters"""
        manager = ConfigManager("config/strategy_params.yaml")
        manager.load()
        
        params = manager.get_indicator_params()
        
        assert "sma" in params
        assert "ema" in params
        assert "rsi" in params
    
    def test_get_risk_params(self):
        """Test getting risk parameters"""
        manager = ConfigManager("config/strategy_params.yaml")
        manager.load()
        
        params = manager.get_risk_params()
        
        assert "max_risk_per_trade" in params
        assert "max_position_size" in params
    
    def test_get_execution_params(self):
        """Test getting execution parameters"""
        manager = ConfigManager("config/strategy_params.yaml")
        manager.load()
        
        params = manager.get_execution_params()
        
        assert "max_slippage" in params
        assert "max_total_cost" in params
    
    def test_to_dict(self):
        """Test converting config to dictionary"""
        manager = ConfigManager("config/strategy_params.yaml")
        manager.load()
        
        config_dict = manager.to_dict()
        
        assert isinstance(config_dict, dict)
        assert "indicators" in config_dict


class TestConfigValidator:
    """Test ConfigValidator"""
    
    def test_validator_initialization(self):
        """Test ConfigValidator initializes correctly"""
        validator = ConfigValidator()
        
        assert validator.validation_rules is not None
        assert len(validator.validation_rules) > 0
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration"""
        validator = ConfigValidator()
        
        config = {
            "indicators": {
                "sma": {"periods": [9, 21, 50, 200]},
                "ema": {"periods": [9, 21, 50, 200]},
                "rsi": {"period": 14},
                "macd": {"fast": 12, "slow": 26, "signal": 9},
                "bollinger": {"period": 20, "std": 2.0}
            },
            "risk": {
                "max_risk_per_trade": 0.02,
                "max_position_size": 0.10,
                "stop_loss_pct": 0.02
            },
            "execution": {
                "max_slippage": 0.001,
                "max_total_cost": 0.002,
                "order_timeout": 5
            }
        }
        
        is_valid, errors = validator.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_missing_section(self):
        """Test validation fails for missing section"""
        validator = ConfigValidator()
        
        config = {
            "indicators": {},
            # Missing "risk" and "execution"
        }
        
        is_valid, errors = validator.validate(config)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("Missing required section" in error for error in errors)
    
    def test_validate_invalid_type(self):
        """Test validation fails for invalid type"""
        validator = ConfigValidator()
        
        config = {
            "indicators": {
                "rsi": {"period": "invalid"}  # Should be int
            },
            "risk": {},
            "execution": {}
        }
        
        is_valid, errors = validator.validate(config)
        
        assert is_valid is False
        assert len(errors) > 0
    
    def test_validate_out_of_range(self):
        """Test validation fails for out of range value"""
        validator = ConfigValidator()
        
        config = {
            "indicators": {
                "rsi": {"period": 1000}  # Max is 100
            },
            "risk": {},
            "execution": {}
        }
        
        is_valid, errors = validator.validate(config)
        
        assert is_valid is False
        assert any("maximum" in error.lower() for error in errors)
    
    def test_validate_macd_fast_slow(self):
        """Test validation of MACD fast < slow rule"""
        validator = ConfigValidator()
        
        config = {
            "indicators": {
                "macd": {"fast": 30, "slow": 20, "signal": 9}  # fast > slow (invalid)
            },
            "risk": {},
            "execution": {}
        }
        
        is_valid, errors = validator.validate(config)
        
        assert is_valid is False
        assert any("macd.fast" in error.lower() for error in errors)
    
    def test_validate_list_parameters(self):
        """Test validation of list parameters"""
        validator = ConfigValidator()
        
        config = {
            "indicators": {
                "sma": {"periods": [9, 21, 50, 1000]}  # 1000 > max (500)
            },
            "risk": {},
            "execution": {}
        }
        
        is_valid, errors = validator.validate(config)
        
        assert is_valid is False
        assert any("maximum" in error.lower() for error in errors)
    
    def test_get_nested_value(self):
        """Test getting nested value"""
        validator = ConfigValidator()
        
        config = {
            "indicators": {
                "rsi": {
                    "period": 14
                }
            }
        }
        
        value = validator._get_nested_value(config, "indicators.rsi.period")
        assert value == 14
        
        # Non-existent key
        value = validator._get_nested_value(config, "nonexistent.key")
        assert value is None


class TestConfigIntegration:
    """Test integration between ConfigManager and ConfigValidator"""
    
    def test_load_and_validate(self):
        """Test loading and validating configuration"""
        manager = ConfigManager("config/strategy_params.yaml")
        
        # Should not raise exception
        config = manager.load()
        
        assert config is not None
        assert "indicators" in config
    
    def test_invalid_config_raises_error(self, tmp_path):
        """Test that invalid config raises error"""
        # Create invalid config file
        invalid_config = {
            "indicators": {
                "rsi": {"period": 1000}  # Out of range
            },
            "risk": {},
            "execution": {}
        }
        
        config_file = tmp_path / "invalid_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        manager = ConfigManager(str(config_file))
        
        with pytest.raises(ValueError):
            manager.load()
