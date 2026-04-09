"""
Grid Search Optimization Script

Performs parallel grid search optimization of strategy parameters.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any
from itertools import product
from concurrent.futures import ProcessPoolExecutor
import yaml
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GridSearchOptimizer:
    """
    Grid Search Optimizer
    
    Features:
    - Parallel execution across multiple cores
    - Parameter grid definition
    - Performance metric optimization
    - Result ranking and export
    """
    
    def __init__(
        self,
        base_config_path: str = "config/strategy_params.yaml",
        n_workers: int = 4
    ):
        """
        Initialize Grid Search Optimizer
        
        Args:
            base_config_path: Path to base configuration
            n_workers: Number of parallel workers
        """
        self.base_config_path = base_config_path
        self.n_workers = n_workers
        
        # Load base configuration
        with open(base_config_path, 'r') as f:
            self.base_config = yaml.safe_load(f)
        
        logger.info(f"GridSearchOptimizer initialized with {n_workers} workers")
    
    def define_parameter_grid(self) -> Dict[str, List[Any]]:
        """
        Define parameter grid for optimization
        
        Returns:
            Dictionary of parameter names to value lists
        """
        grid = {
            # Indicator parameters
            "indicators.rsi.period": [10, 14, 20],
            "indicators.macd.fast": [10, 12, 15],
            "indicators.macd.slow": [24, 26, 30],
            "indicators.bollinger.std": [1.5, 2.0, 2.5],
            
            # Risk parameters
            "risk.max_risk_per_trade": [0.01, 0.02, 0.03],
            "risk.stop_loss_pct": [0.015, 0.02, 0.025],
            
            # Signal parameters
            "signal.min_confidence": [50, 60, 70],
            "signal.volume_multiplier": [1.3, 1.5, 1.7]
        }
        
        return grid
    
    def generate_configurations(self, grid: Dict[str, List[Any]]) -> List[Dict]:
        """
        Generate all parameter combinations
        
        Args:
            grid: Parameter grid
        
        Returns:
            List of configuration dictionaries
        """
        # Get parameter names and values
        param_names = list(grid.keys())
        param_values = list(grid.values())
        
        # Generate all combinations
        combinations = list(product(*param_values))
        
        logger.info(f"Generated {len(combinations)} parameter combinations")
        
        # Create configuration for each combination
        configs = []
        for combo in combinations:
            config = self.base_config.copy()
            
            # Apply parameters
            for param_name, param_value in zip(param_names, combo):
                self._set_nested_value(config, param_name, param_value)
            
            configs.append(config)
        
        return configs
    
    def _set_nested_value(self, config: Dict, key: str, value: Any) -> None:
        """
        Set nested value in config using dot notation
        
        Args:
            config: Configuration dictionary
            key: Key with dot notation
            value: Value to set
        """
        keys = key.split('.')
        current = config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def run_backtest(self, config: Dict) -> Dict:
        """
        Run backtest with given configuration
        
        Args:
            config: Configuration dictionary
        
        Returns:
            Performance metrics dictionary
        """
        # This is a placeholder - would integrate with actual backtest engine
        # For now, return dummy metrics
        
        import random
        import time
        
        # Simulate backtest execution
        time.sleep(0.1)
        
        # Generate random metrics (placeholder)
        metrics = {
            "total_return": random.uniform(-20, 50),
            "sharpe_ratio": random.uniform(-1, 3),
            "max_drawdown": random.uniform(5, 30),
            "win_rate": random.uniform(30, 70),
            "profit_factor": random.uniform(0.5, 3.0),
            "total_trades": random.randint(50, 500),
            "config": config
        }
        
        return metrics
    
    def optimize(
        self,
        objective: str = "sharpe_ratio",
        minimize: bool = False
    ) -> List[Dict]:
        """
        Run grid search optimization
        
        Args:
            objective: Metric to optimize (e.g., "sharpe_ratio", "total_return")
            minimize: Whether to minimize (True) or maximize (False) the objective
        
        Returns:
            List of results sorted by objective
        """
        logger.info(f"Starting grid search optimization (objective: {objective})")
        
        # Define parameter grid
        grid = self.define_parameter_grid()
        
        # Generate configurations
        configs = self.generate_configurations(grid)
        
        logger.info(f"Running {len(configs)} backtests on {self.n_workers} workers...")
        
        # Run backtests in parallel
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            results = list(executor.map(self.run_backtest, configs))
        
        # Sort results by objective
        results.sort(
            key=lambda x: x[objective],
            reverse=not minimize
        )
        
        logger.info("Grid search optimization complete")
        
        return results
    
    def export_results(
        self,
        results: List[Dict],
        filename: str = "optimization_results.json"
    ) -> None:
        """
        Export optimization results to JSON
        
        Args:
            results: List of result dictionaries
            filename: Output filename
        """
        # Convert to serializable format
        serializable_results = []
        for result in results:
            serializable_result = {
                "total_return": result["total_return"],
                "sharpe_ratio": result["sharpe_ratio"],
                "max_drawdown": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "profit_factor": result["profit_factor"],
                "total_trades": result["total_trades"],
                "config": result["config"]
            }
            serializable_results.append(serializable_result)
        
        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        logger.info(f"Results exported to {filename}")
    
    def print_top_results(self, results: List[Dict], n: int = 10) -> None:
        """
        Print top N results
        
        Args:
            results: List of result dictionaries
            n: Number of top results to print
        """
        print(f"\n{'='*80}")
        print(f"Top {n} Configurations")
        print(f"{'='*80}\n")
        
        for i, result in enumerate(results[:n], 1):
            print(f"Rank {i}:")
            print(f"  Total Return: {result['total_return']:.2f}%")
            print(f"  Sharpe Ratio: {result['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown: {result['max_drawdown']:.2f}%")
            print(f"  Win Rate: {result['win_rate']:.2f}%")
            print(f"  Profit Factor: {result['profit_factor']:.2f}")
            print(f"  Total Trades: {result['total_trades']}")
            print()


def main():
    """Main optimization script"""
    # Initialize optimizer
    optimizer = GridSearchOptimizer(
        base_config_path="config/strategy_params.yaml",
        n_workers=4
    )
    
    # Run optimization
    results = optimizer.optimize(objective="sharpe_ratio")
    
    # Print top results
    optimizer.print_top_results(results, n=10)
    
    # Export results
    optimizer.export_results(results, filename="optimization_results.json")
    
    # Save best configuration
    best_config = results[0]["config"]
    with open("config/best_params.yaml", 'w') as f:
        yaml.dump(best_config, f, default_flow_style=False, sort_keys=False)
    
    logger.info("Best configuration saved to config/best_params.yaml")


if __name__ == "__main__":
    main()
