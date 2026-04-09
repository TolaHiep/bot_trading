"""
Configuration Validator - Validate configuration values

Provides validation rules for all configuration parameters.
"""

import logging
from typing import Dict, Any, List, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class ConfigValidator:
    """
    Configuration Validator
    
    Features:
    - Validate indicator parameters
    - Validate risk parameters
    - Validate execution parameters
    - Check value ranges
    """
    
    def __init__(self):
        """Initialize Configuration Validator"""
        self.validation_rules = self._define_validation_rules()
        logger.info("ConfigValidator initialized")
    
    def _define_validation_rules(self) -> Dict[str, Dict]:
        """
        Define validation rules for all parameters
        
        Returns:
            Dictionary of validation rules
        """
        return {
            # Indicator parameters
            "indicators.sma.periods": {
                "type": list,
                "min_length": 1,
                "item_type": int,
                "item_min": 1,
                "item_max": 500
            },
            "indicators.ema.periods": {
                "type": list,
                "min_length": 1,
                "item_type": int,
                "item_min": 1,
                "item_max": 500
            },
            "indicators.rsi.period": {
                "type": int,
                "min": 2,
                "max": 100
            },
            "indicators.macd.fast": {
                "type": int,
                "min": 2,
                "max": 50
            },
            "indicators.macd.slow": {
                "type": int,
                "min": 10,
                "max": 100
            },
            "indicators.macd.signal": {
                "type": int,
                "min": 2,
                "max": 50
            },
            "indicators.bollinger.period": {
                "type": int,
                "min": 5,
                "max": 100
            },
            "indicators.bollinger.std": {
                "type": (int, float),
                "min": 0.5,
                "max": 5.0
            },
            
            # Risk parameters
            "risk.max_risk_per_trade": {
                "type": (int, float),
                "min": 0.001,
                "max": 0.1  # Max 10%
            },
            "risk.max_position_size": {
                "type": (int, float),
                "min": 0.01,
                "max": 1.0  # Max 100%
            },
            "risk.stop_loss_pct": {
                "type": (int, float),
                "min": 0.001,
                "max": 0.2  # Max 20%
            },
            "risk.trailing_stop_distance": {
                "type": (int, float),
                "min": 0.001,
                "max": 0.1  # Max 10%
            },
            "risk.max_daily_drawdown": {
                "type": (int, float),
                "min": 0.01,
                "max": 0.5  # Max 50%
            },
            "risk.max_consecutive_losses": {
                "type": int,
                "min": 1,
                "max": 20
            },
            
            # Execution parameters
            "execution.max_slippage": {
                "type": (int, float),
                "min": 0.0001,
                "max": 0.05  # Max 5%
            },
            "execution.max_total_cost": {
                "type": (int, float),
                "min": 0.0001,
                "max": 0.1  # Max 10%
            },
            "execution.order_timeout": {
                "type": int,
                "min": 1,
                "max": 60  # Max 60 seconds
            },
            "execution.max_retries": {
                "type": int,
                "min": 0,
                "max": 5
            },
            
            # Signal parameters
            "signal.min_confidence": {
                "type": int,
                "min": 0,
                "max": 100
            },
            "signal.volume_multiplier": {
                "type": (int, float),
                "min": 1.0,
                "max": 10.0
            },
            
            # Backtest parameters
            "backtest.initial_balance": {
                "type": (int, float),
                "min": 100,
                "max": 10000000
            },
            "backtest.commission_rate": {
                "type": (int, float),
                "min": 0.0,
                "max": 0.01  # Max 1%
            }
        }
    
    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration
        
        Args:
            config: Configuration dictionary
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check required sections
        required_sections = ['indicators', 'risk', 'execution']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        if errors:
            return False, errors
        
        # Validate each parameter
        for key, rules in self.validation_rules.items():
            value = self._get_nested_value(config, key)
            
            if value is None:
                # Parameter is optional
                continue
            
            # Validate type
            if "type" in rules:
                expected_type = rules["type"]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"{key}: Expected type {expected_type}, got {type(value)}"
                    )
                    continue
            
            # Validate list parameters
            if isinstance(value, list):
                if "min_length" in rules and len(value) < rules["min_length"]:
                    errors.append(
                        f"{key}: List length {len(value)} < minimum {rules['min_length']}"
                    )
                
                if "item_type" in rules:
                    for i, item in enumerate(value):
                        if not isinstance(item, rules["item_type"]):
                            errors.append(
                                f"{key}[{i}]: Expected type {rules['item_type']}, got {type(item)}"
                            )
                
                if "item_min" in rules:
                    for i, item in enumerate(value):
                        if item < rules["item_min"]:
                            errors.append(
                                f"{key}[{i}]: Value {item} < minimum {rules['item_min']}"
                            )
                
                if "item_max" in rules:
                    for i, item in enumerate(value):
                        if item > rules["item_max"]:
                            errors.append(
                                f"{key}[{i}]: Value {item} > maximum {rules['item_max']}"
                            )
            
            # Validate numeric parameters
            if isinstance(value, (int, float)):
                if "min" in rules and value < rules["min"]:
                    errors.append(
                        f"{key}: Value {value} < minimum {rules['min']}"
                    )
                
                if "max" in rules and value > rules["max"]:
                    errors.append(
                        f"{key}: Value {value} > maximum {rules['max']}"
                    )
        
        # Custom validations
        errors.extend(self._validate_custom_rules(config))
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("Configuration validation passed")
        else:
            logger.warning(f"Configuration validation failed: {len(errors)} errors")
        
        return is_valid, errors
    
    def _validate_custom_rules(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate custom business rules
        
        Args:
            config: Configuration dictionary
        
        Returns:
            List of error messages
        """
        errors = []
        
        # MACD: fast < slow
        macd_fast = self._get_nested_value(config, "indicators.macd.fast")
        macd_slow = self._get_nested_value(config, "indicators.macd.slow")
        
        if macd_fast and macd_slow and macd_fast >= macd_slow:
            errors.append("indicators.macd.fast must be < indicators.macd.slow")
        
        # Risk: max_risk_per_trade <= max_position_size
        max_risk = self._get_nested_value(config, "risk.max_risk_per_trade")
        max_position = self._get_nested_value(config, "risk.max_position_size")
        
        if max_risk and max_position and max_risk > max_position:
            errors.append("risk.max_risk_per_trade must be <= risk.max_position_size")
        
        return errors
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """
        Get nested value from config using dot notation
        
        Args:
            config: Configuration dictionary
            key: Key with dot notation
        
        Returns:
            Value or None if not found
        """
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
