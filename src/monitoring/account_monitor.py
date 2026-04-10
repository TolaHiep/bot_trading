"""Account Monitor - Theo dõi tài khoản và xử lý khi cháy

Tính năng:
- Phát hiện khi equity <= 0 hoặc < threshold
- Tạo báo cáo chi tiết về các lệnh, lỗi, nguyên nhân
- Gửi báo cáo qua Telegram
- Tự động reset tài khoản về initial balance
"""

import logging
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AccountMonitor:
    """Monitor account balance and handle liquidation"""
    
    def __init__(
        self,
        paper_trader,
        initial_balance: Decimal,
        liquidation_threshold: Decimal = Decimal("5.0"),  # $5 threshold
        report_dir: str = "reports/liquidations"
    ):
        """Initialize account monitor
        
        Args:
            paper_trader: PaperTrader instance
            initial_balance: Initial balance to reset to
            liquidation_threshold: Balance threshold to trigger liquidation report
            report_dir: Directory to save liquidation reports
        """
        self.paper_trader = paper_trader
        self.initial_balance = initial_balance
        self.liquidation_threshold = liquidation_threshold
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        self.liquidation_count = 0
        self.last_liquidation_time: Optional[datetime] = None
        
        logger.info(
            f"AccountMonitor initialized: threshold=${liquidation_threshold}, "
            f"reset_balance=${initial_balance}"
        )
    
    async def check_and_handle_liquidation(
        self,
        current_prices: Dict[str, Decimal]
    ) -> bool:
        """Check if account is liquidated and handle it
        
        Args:
            current_prices: Current prices for all symbols
            
        Returns:
            True if liquidation occurred and was handled
        """
        # Get account summary with current prices
        account = self.paper_trader.get_account_summary(current_prices)
        equity = Decimal(str(account['equity']))
        
        # Check if liquidated
        if equity <= self.liquidation_threshold:
            logger.critical(
                f"🚨 ACCOUNT LIQUIDATED! Equity: ${equity:.2f} <= ${self.liquidation_threshold:.2f}"
            )
            
            # Generate report
            report = await self._generate_liquidation_report(account, current_prices)
            
            # Save report to file
            report_file = await self._save_report(report)
            
            # Send Telegram notification
            await self._send_telegram_report(report, report_file)
            
            # Reset account
            await self._reset_account()
            
            self.liquidation_count += 1
            self.last_liquidation_time = datetime.now()
            
            return True
        
        return False
    
    async def _generate_liquidation_report(
        self,
        account: Dict,
        current_prices: Dict[str, Decimal]
    ) -> Dict:
        """Generate detailed liquidation report
        
        Args:
            account: Account summary
            current_prices: Current prices
            
        Returns:
            Report dictionary
        """
        logger.info("Generating liquidation report...")
        
        # Get all trade history
        trades = self.paper_trader.get_trade_history()
        
        # Analyze trades
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get('pnl') and float(t['pnl']) > 0]
        losing_trades = [t for t in trades if t.get('pnl') and float(t['pnl']) < 0]
        
        # Calculate statistics
        total_profit = sum(float(t['pnl']) for t in winning_trades)
        total_loss = sum(float(t['pnl']) for t in losing_trades)
        
        # Find worst trades
        worst_trades = sorted(
            [t for t in trades if t.get('pnl')],
            key=lambda x: float(x['pnl'])
        )[:10]  # Top 10 worst
        
        # Find best trades
        best_trades = sorted(
            [t for t in trades if t.get('pnl')],
            key=lambda x: float(x['pnl']),
            reverse=True
        )[:10]  # Top 10 best
        
        # Analyze by symbol
        symbol_stats = {}
        for trade in trades:
            symbol = trade['symbol']
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    'trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_pnl': 0.0
                }
            
            symbol_stats[symbol]['trades'] += 1
            if trade.get('pnl'):
                pnl = float(trade['pnl'])
                symbol_stats[symbol]['total_pnl'] += pnl
                if pnl > 0:
                    symbol_stats[symbol]['wins'] += 1
                else:
                    symbol_stats[symbol]['losses'] += 1
        
        # Sort symbols by worst performance
        worst_symbols = sorted(
            symbol_stats.items(),
            key=lambda x: x[1]['total_pnl']
        )[:10]
        
        # Analyze by strategy
        strategy_stats = {}
        for trade in trades:
            strategy = trade.get('strategy_name', 'main')
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_pnl': 0.0
                }
            
            strategy_stats[strategy]['trades'] += 1
            if trade.get('pnl'):
                pnl = float(trade['pnl'])
                strategy_stats[strategy]['total_pnl'] += pnl
                if pnl > 0:
                    strategy_stats[strategy]['wins'] += 1
                else:
                    strategy_stats[strategy]['losses'] += 1
        
        # Get open positions (if any)
        open_positions = self.paper_trader.get_all_positions()
        
        # Create report
        report = {
            'timestamp': datetime.now().isoformat(),
            'liquidation_number': self.liquidation_count + 1,
            'account': {
                'initial_balance': account['initial_balance'],
                'final_equity': account['equity'],
                'total_loss': account['initial_balance'] - account['equity'],
                'loss_percentage': ((account['initial_balance'] - account['equity']) / account['initial_balance'] * 100),
                'realized_pnl': account['realized_pnl'],
                'unrealized_pnl': account['unrealized_pnl']
            },
            'trading_summary': {
                'total_trades': total_trades,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0,
                'total_profit': total_profit,
                'total_loss': total_loss,
                'net_pnl': total_profit + total_loss,
                'average_win': total_profit / len(winning_trades) if winning_trades else 0,
                'average_loss': total_loss / len(losing_trades) if losing_trades else 0
            },
            'worst_trades': worst_trades,
            'best_trades': best_trades,
            'symbol_performance': dict(worst_symbols),
            'strategy_performance': strategy_stats,
            'open_positions': [
                {
                    'symbol': pos.symbol,
                    'side': pos.side.value,
                    'entry_price': float(pos.entry_price),
                    'quantity': float(pos.quantity),
                    'current_price': float(current_prices.get(pos.symbol, pos.entry_price)),
                    'unrealized_pnl': float(pos.calculate_pnl(current_prices.get(pos.symbol, pos.entry_price)))
                }
                for pos in open_positions
            ],
            'analysis': self._analyze_failure_reasons(trades, symbol_stats, strategy_stats)
        }
        
        return report
    
    def _analyze_failure_reasons(
        self,
        trades: List[Dict],
        symbol_stats: Dict,
        strategy_stats: Dict
    ) -> Dict:
        """Analyze reasons for account liquidation
        
        Args:
            trades: All trades
            symbol_stats: Statistics by symbol
            strategy_stats: Statistics by strategy
            
        Returns:
            Analysis dictionary
        """
        reasons = []
        
        # Check for consecutive losses
        consecutive_losses = 0
        max_consecutive_losses = 0
        for trade in trades:
            if trade.get('pnl') and float(trade['pnl']) < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0
        
        if max_consecutive_losses >= 5:
            reasons.append(f"Consecutive losses: {max_consecutive_losses} trades in a row")
        
        # Check for overtrading specific symbols
        for symbol, stats in symbol_stats.items():
            if stats['trades'] > 20 and stats['total_pnl'] < -10:
                reasons.append(f"Overtrading {symbol}: {stats['trades']} trades, ${stats['total_pnl']:.2f} loss")
        
        # Check for poor strategy performance
        for strategy, stats in strategy_stats.items():
            if stats['trades'] > 10:
                win_rate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
                if win_rate < 30:
                    reasons.append(f"Poor {strategy} strategy: {win_rate:.1f}% win rate")
        
        # Check for large single losses
        large_losses = [t for t in trades if t.get('pnl') and float(t['pnl']) < -5]
        if large_losses:
            reasons.append(f"Large losses: {len(large_losses)} trades with >$5 loss each")
        
        # Check average loss vs average win
        winning_trades = [t for t in trades if t.get('pnl') and float(t['pnl']) > 0]
        losing_trades = [t for t in trades if t.get('pnl') and float(t['pnl']) < 0]
        
        if winning_trades and losing_trades:
            avg_win = sum(float(t['pnl']) for t in winning_trades) / len(winning_trades)
            avg_loss = sum(float(t['pnl']) for t in losing_trades) / len(losing_trades)
            
            if abs(avg_loss) > avg_win * 2:
                reasons.append(f"Poor risk/reward: Avg loss ${abs(avg_loss):.2f} > 2x avg win ${avg_win:.2f}")
        
        return {
            'reasons': reasons,
            'max_consecutive_losses': max_consecutive_losses,
            'recommendations': self._generate_recommendations(reasons, symbol_stats, strategy_stats)
        }
    
    def _generate_recommendations(
        self,
        reasons: List[str],
        symbol_stats: Dict,
        strategy_stats: Dict
    ) -> List[str]:
        """Generate recommendations based on failure analysis
        
        Args:
            reasons: Failure reasons
            symbol_stats: Symbol statistics
            strategy_stats: Strategy statistics
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # General recommendations
        recommendations.append("Reduce leverage from 20x to 5-10x")
        recommendations.append("Reduce risk per trade from 5% to 2-3%")
        recommendations.append("Implement stricter stop loss (0.5-1% instead of 2%)")
        
        # Specific recommendations based on reasons
        if any('Consecutive losses' in r for r in reasons):
            recommendations.append("Add kill switch for 3 consecutive losses (currently 5)")
            recommendations.append("Take break after 2 consecutive losses")
        
        if any('Overtrading' in r for r in reasons):
            recommendations.append("Limit trades per symbol to 5 per day")
            recommendations.append("Increase signal confidence threshold")
        
        if any('Poor' in r and 'strategy' in r for r in reasons):
            recommendations.append("Review and optimize strategy parameters")
            recommendations.append("Consider disabling underperforming strategies")
        
        if any('Large losses' in r for r in reasons):
            recommendations.append("Implement maximum loss per trade ($2-3)")
            recommendations.append("Use tighter stop loss for high volatility symbols")
        
        if any('risk/reward' in r for r in reasons):
            recommendations.append("Increase take profit targets (3-5% instead of current)")
            recommendations.append("Use trailing take profit to lock in gains")
        
        return recommendations
    
    async def _save_report(self, report: Dict) -> Path:
        """Save report to file
        
        Args:
            report: Report dictionary
            
        Returns:
            Path to saved report
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"liquidation_{timestamp}_#{report['liquidation_number']}.json"
        filepath = self.report_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Liquidation report saved: {filepath}")
        return filepath
    
    async def _send_telegram_report(self, report: Dict, report_file: Path):
        """Send liquidation report via Telegram
        
        Args:
            report: Report dictionary
            report_file: Path to report file
        """
        try:
            from src.monitoring.notifier import send_telegram_alert
            
            # Create summary message
            acc = report['account']
            summary = report['trading_summary']
            analysis = report['analysis']
            
            message = (
                f"🚨 <b>ACCOUNT LIQUIDATED #{report['liquidation_number']}</b> 🚨\n\n"
                f"<b>Account Summary:</b>\n"
                f"Initial: <code>${acc['initial_balance']:.2f}</code>\n"
                f"Final: <code>${acc['final_equity']:.2f}</code>\n"
                f"Loss: <code>${acc['total_loss']:.2f}</code> ({acc['loss_percentage']:.1f}%)\n\n"
                f"<b>Trading Summary:</b>\n"
                f"Total Trades: {summary['total_trades']}\n"
                f"Win Rate: {summary['win_rate']:.1f}%\n"
                f"Wins: {summary['winning_trades']} (${summary['total_profit']:.2f})\n"
                f"Losses: {summary['losing_trades']} (${summary['total_loss']:.2f})\n"
                f"Avg Win: <code>${summary['average_win']:.2f}</code>\n"
                f"Avg Loss: <code>${summary['average_loss']:.2f}</code>\n\n"
                f"<b>Failure Analysis:</b>\n"
            )
            
            # Add top 3 reasons
            for i, reason in enumerate(analysis['reasons'][:3], 1):
                message += f"{i}. {reason}\n"
            
            message += f"\n<b>Top Recommendations:</b>\n"
            for i, rec in enumerate(analysis['recommendations'][:3], 1):
                message += f"{i}. {rec}\n"
            
            message += f"\n📄 Full report: {report_file.name}"
            message += f"\n\n✅ Account reset to <code>${self.initial_balance}</code>"
            
            await send_telegram_alert(message)
            
            logger.info("Liquidation report sent via Telegram")
            
        except Exception as e:
            logger.error(f"Failed to send Telegram report: {e}")
    
    async def _reset_account(self):
        """Reset paper trading account to initial balance"""
        logger.warning(f"Resetting account to ${self.initial_balance}...")
        
        # Close all open positions
        open_positions = self.paper_trader.get_all_positions()
        for position in open_positions:
            logger.info(f"Force closing position: {position.symbol}")
        
        # Reset paper trader
        self.paper_trader.reset()
        
        logger.info(f"✅ Account reset complete. New balance: ${self.initial_balance}")
    
    def get_liquidation_stats(self) -> Dict:
        """Get liquidation statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            'total_liquidations': self.liquidation_count,
            'last_liquidation': self.last_liquidation_time.isoformat() if self.last_liquidation_time else None
        }
