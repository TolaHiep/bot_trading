"""
Equity Curve Generator - Generate interactive equity curve visualization

Provides Plotly-based interactive charts for equity curve analysis.
"""

import logging
from typing import List, Dict
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

logger = logging.getLogger(__name__)


class EquityCurveGenerator:
    """
    Equity Curve Generator
    
    Features:
    - Interactive Plotly charts
    - Equity curve with drawdown
    - Trade markers
    - Performance annotations
    """
    
    def __init__(self, equity_curve: List[Dict], trades: List[Dict] = None):
        """
        Initialize Equity Curve Generator
        
        Args:
            equity_curve: List of equity snapshots
            trades: Optional list of trades for markers
        """
        self.equity_df = pd.DataFrame(equity_curve) if equity_curve else pd.DataFrame()
        self.trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        
        if not self.equity_df.empty and 'timestamp' in self.equity_df.columns:
            self.equity_df['timestamp'] = pd.to_datetime(self.equity_df['timestamp'])
            self.equity_df = self.equity_df.sort_values('timestamp')
        
        if not self.trades_df.empty and 'timestamp' in self.trades_df.columns:
            self.trades_df['timestamp'] = pd.to_datetime(self.trades_df['timestamp'])
        
        logger.info(f"EquityCurveGenerator initialized with {len(equity_curve)} points")
    
    def generate_equity_curve(self, title: str = "Equity Curve") -> go.Figure:
        """
        Generate basic equity curve
        
        Args:
            title: Chart title
        
        Returns:
            Plotly Figure
        """
        if self.equity_df.empty:
            logger.warning("No equity data to plot")
            return go.Figure()
        
        fig = go.Figure()
        
        # Add equity line
        fig.add_trace(go.Scatter(
            x=self.equity_df['timestamp'],
            y=self.equity_df['equity'],
            mode='lines',
            name='Equity',
            line=dict(color='blue', width=2),
            hovertemplate='<b>Date</b>: %{x}<br><b>Equity</b>: $%{y:,.2f}<extra></extra>'
        ))
        
        # Add trade markers if available
        if not self.trades_df.empty:
            buy_trades = self.trades_df[self.trades_df['side'] == 'BUY']
            sell_trades = self.trades_df[self.trades_df['side'] == 'SELL']
            
            if not buy_trades.empty:
                fig.add_trace(go.Scatter(
                    x=buy_trades['timestamp'],
                    y=[self.equity_df[self.equity_df['timestamp'] <= t]['equity'].iloc[-1] 
                       if not self.equity_df[self.equity_df['timestamp'] <= t].empty 
                       else 0 for t in buy_trades['timestamp']],
                    mode='markers',
                    name='Buy',
                    marker=dict(color='green', size=10, symbol='triangle-up'),
                    hovertemplate='<b>Buy</b><br>Date: %{x}<br>Price: %{text}<extra></extra>',
                    text=[f"${p:,.2f}" for p in buy_trades['price']]
                ))
            
            if not sell_trades.empty:
                fig.add_trace(go.Scatter(
                    x=sell_trades['timestamp'],
                    y=[self.equity_df[self.equity_df['timestamp'] <= t]['equity'].iloc[-1] 
                       if not self.equity_df[self.equity_df['timestamp'] <= t].empty 
                       else 0 for t in sell_trades['timestamp']],
                    mode='markers',
                    name='Sell',
                    marker=dict(color='red', size=10, symbol='triangle-down'),
                    hovertemplate='<b>Sell</b><br>Date: %{x}<br>Price: %{text}<extra></extra>',
                    text=[f"${p:,.2f}" for p in sell_trades['price']]
                ))
        
        fig.update_layout(
            title=title,
            xaxis_title='Date',
            yaxis_title='Equity ($)',
            hovermode='x unified',
            template='plotly_white',
            height=600
        )
        
        return fig
    
    def generate_equity_with_drawdown(self, title: str = "Equity Curve with Drawdown") -> go.Figure:
        """
        Generate equity curve with drawdown subplot
        
        Args:
            title: Chart title
        
        Returns:
            Plotly Figure with subplots
        """
        if self.equity_df.empty:
            logger.warning("No equity data to plot")
            return go.Figure()
        
        # Calculate drawdown
        equity_series = self.equity_df['equity'].values
        running_max = pd.Series(equity_series).expanding().max().values
        drawdown = ((equity_series - running_max) / running_max) * 100
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=('Equity', 'Drawdown (%)'),
            row_heights=[0.7, 0.3]
        )
        
        # Add equity curve
        fig.add_trace(
            go.Scatter(
                x=self.equity_df['timestamp'],
                y=self.equity_df['equity'],
                mode='lines',
                name='Equity',
                line=dict(color='blue', width=2),
                hovertemplate='<b>Equity</b>: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Add drawdown
        fig.add_trace(
            go.Scatter(
                x=self.equity_df['timestamp'],
                y=drawdown,
                mode='lines',
                name='Drawdown',
                line=dict(color='red', width=2),
                fill='tozeroy',
                fillcolor='rgba(255, 0, 0, 0.2)',
                hovertemplate='<b>Drawdown</b>: %{y:.2f}%<extra></extra>'
            ),
            row=2, col=1
        )
        
        fig.update_xaxes(title_text='Date', row=2, col=1)
        fig.update_yaxes(title_text='Equity ($)', row=1, col=1)
        fig.update_yaxes(title_text='Drawdown (%)', row=2, col=1)
        
        fig.update_layout(
            title=title,
            hovermode='x unified',
            template='plotly_white',
            height=800,
            showlegend=True
        )
        
        return fig
    
    def save_html(self, fig: go.Figure, filename: str) -> None:
        """
        Save figure to HTML file
        
        Args:
            fig: Plotly figure
            filename: Output filename
        """
        fig.write_html(filename)
        logger.info(f"Chart saved to {filename}")
    
    def save_png(self, fig: go.Figure, filename: str) -> None:
        """
        Save figure to PNG file
        
        Args:
            fig: Plotly figure
            filename: Output filename
        """
        try:
            fig.write_image(filename)
            logger.info(f"Chart saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save PNG (requires kaleido): {e}")
