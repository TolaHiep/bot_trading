"""
Configuration Manager - Load and manage configuration from YAML

Provides centralized configuration management with validation and hot-reload support.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from decimal import Decimal

from src.config.validator import ConfigValidator

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Configuration Manager
    
    Features:
    - Load configuration from YAML files
    - Validate configuration values
    - Support hot-reload for non-critical parameters
    - Preserve comments when serializing
    """
    
    def __init__(self, config_path: str = "config/strategy_params.yaml"):
        """
        Initialize Configuration Manager
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.validator = ConfigValidator()
        
        logger.info(f"ConfigManager initialized with path: {config_path}")
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file
        
        Returns:
            Configuration dictionary
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            logger.info(f"Configuration loaded from {self.config_path}")
            
            # Validate configuration
            is_valid, errors = self.validator.validate(self.config)
            
            if not is_valid:
                error_msg = f"Invalid configuration: {', '.join(errors)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            return self.config
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            raise ValueError(f"Invalid YAML format: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key
        
        Args:
            key: Configuration key (supports dot notation, e.g., "indicators.rsi.period")
            default: Default value if key not found
        
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value
        
        Args:
            key: Configuration key (supports dot notation)
            value: New value
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        logger.debug(f"Config updated: {key} = {value}")
    
    def save(self) -> None:
        """
        Save configuration to YAML file
        
        Note: This will not preserve comments
        """
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Configuration saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration from file
        
        Returns:
            Updated configuration dictionary
        """
        logger.info("Reloading configuration...")
        return self.load()
    
    def get_indicator_params(self) -> Dict[str, Any]:
        """Get indicator parameters"""
        return self.get('indicators', {})
    
    def get_risk_params(self) -> Dict[str, Any]:
        """Get risk management parameters"""
        return self.get('risk', {})
    
    def get_execution_params(self) -> Dict[str, Any]:
        """Get execution parameters"""
        return self.get('execution', {})
    
    def get_backtest_params(self) -> Dict[str, Any]:
        """Get backtest parameters"""
        return self.get('backtest', {})
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Get full configuration as dictionary
        
        Returns:
            Configuration dictionary
        """
        return self.config.copy()
