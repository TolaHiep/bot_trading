"""
Streamlit Dashboard - Real-time monitoring dashboard

Hiển thị metrics, signals, positions và system health.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
import time

from .metrics_collector import MetricsCollector


class Dashboard:
    """
    Real-time Monitoring Dashboard
    
    Features:
    - Display current balance và open positions
    - Display recent signals với confidence scores
    - Display current Wyckoff phase và order flow delta
    - Display equity curve last 30 days
    - Display key metrics (win rate, profit factor, Sharpe ratio)
    - Display system health (API, DB, error rate)
    - Auto-refresh every 5 seconds
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        """
        Initialize Dashboard
        
        Args:
            metrics_collector: MetricsCollector instance
        """
        self.metrics_collector = metrics_collector
        
        # Configure Streamlit page
        st.set_page_config(
            page_title="Trading Bot Dashboard",
            page_icon="📈",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def render(self) -> None:
        """Render dashboard UI"""
        # Title
        st.title("📈 Quantitative Trading Bot Dashboard")
        st.markdown("---")
        
        # Auto-refresh every 5 seconds
        st_autorefresh = st.empty()
        with st_autorefresh:
            st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Auto-refresh: 5s)")
        
        # Main layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_trading_metrics()
            self._render_equity_curve()
            self._render_recent_signals()
        
        with col2:
            self._render_system_health()
            self._render_current_phase()
            self._render_recent_errors()
        
        # Auto-refresh
        time.sleep(5)
        st.rerun()
    
    def _render_trading_metrics(self) -> None:
        """Render trading performance metrics"""
        st.subheader("💰 Trading Performance")
        
        metrics = self.metrics_collector.get_trading_summary()
        
        if metrics.get("status") == "no_data":
            st.warning("No trading data available yet")
            return
        
        # Key metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Current Balance",
                value=f"${metrics['current_balance']:,.2f}",
                delta=f"${metrics['total_pnl']:,.2f}"
            )
        
        with col2:
            st.metric(
                label="Total Return",
                value=f"{metrics['total_return']:.2f}%",
                delta=f"{metrics['realized_pnl']:,.2f}"
            )
        
        with col3:
            st.metric(
                label="Win Rate",
                value=f"{metrics['win_rate']:.1f}%",
                delta=f"{metrics['winning_trades']}/{metrics['total_trades']} wins"
            )
        
        with col4:
            st.metric(
                label="Open Positions",
                value=metrics['open_positions'],
                delta=f"${metrics['unrealized_pnl']:,.2f}"
            )
        
        # Detailed metrics
        with st.expander("📊 Detailed Metrics"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**Account**")
                st.write(f"Initial Balance: ${metrics['initial_balance']:,.2f}")
                st.write(f"Equity: ${metrics['equity']:,.2f}")
                st.write(f"Realized P&L: ${metrics['realized_pnl']:,.2f}")
                st.write(f"Unrealized P&L: ${metrics['unrealized_pnl']:,.2f}")
            
            with col2:
                st.write("**Trades**")
                st.write(f"Total Trades: {metrics['total_trades']}")
                st.write(f"Winning Trades: {metrics['winning_trades']}")
                st.write(f"Losing Trades: {metrics['losing_trades']}")
                st.write(f"Win Rate: {metrics['win_rate']:.2f}%")
            
            with col3:
                st.write("**Performance**")
                st.write(f"Total Return: {metrics['total_return']:.2f}%")
                st.write(f"Total P&L: ${metrics['total_pnl']:,.2f}")
                # Placeholder for future metrics
                st.write(f"Profit Factor: N/A")
                st.write(f"Sharpe Ratio: N/A")
    
    def _render_equity_curve(self) -> None:
        """Render equity curve chart"""
        st.subheader("📈 Equity Curve (Last 30 Days)")
        
        equity_data = self.metrics_collector.get_equity_curve(days=30)
        
        if not equity_data:
            st.info("No equity data available yet. Start trading to see equity curve.")
            return
        
        # Create plotly chart
        fig = make_subplots(
            rows=2, cols=1,
            row_heights=[0.7, 0.3],
            subplot_titles=("Equity & Balance", "P&L"),
            vertical_spacing=0.1
        )
        
        timestamps = [point["timestamp"] for point in equity_data]
        equity = [point["equity"] for point in equity_data]
        balance = [point["balance"] for point in equity_data]
        pnl = [point["pnl"] for point in equity_data]
        
        # Equity and Balance
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=equity,
                name="Equity",
                line=dict(color="blue", width=2)
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=timestamps,
                y=balance,
                name="Balance",
                line=dict(color="green", width=2, dash="dash")
            ),
            row=1, col=1
        )
        
        # P&L
        colors = ["green" if p >= 0 else "red" for p in pnl]
        fig.add_trace(
            go.Bar(
                x=timestamps,
                y=pnl,
                name="P&L",
                marker_color=colors
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            height=500,
            showlegend=True,
            hovermode="x unified"
        )
        
        fig.update_xaxes(title_text="Time", row=2, col=1)
        fig.update_yaxes(title_text="USD", row=1, col=1)
        fig.update_yaxes(title_text="P&L (USD)", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_recent_signals(self) -> None:
        """Render recent trading signals"""
        st.subheader("🎯 Recent Signals")
        
        signals = self.metrics_collector.get_recent_signals(limit=10)
        
        if not signals:
            st.info("No signals generated yet")
            return
        
        # Display signals in table
        for signal in reversed(signals):  # Most recent first
            timestamp = datetime.fromisoformat(signal["timestamp"])
            signal_type = signal["signal_type"]
            confidence = signal["confidence"]
            
            # Color based on signal type
            if signal_type == "BUY":
                color = "🟢"
                bg_color = "#d4edda"
            elif signal_type == "SELL":
                color = "🔴"
                bg_color = "#f8d7da"
            else:
                color = "⚪"
                bg_color = "#e2e3e5"
            
            with st.container():
                st.markdown(
                    f"""
                    <div style="background-color: {bg_color}; padding: 10px; border-radius: 5px; margin-bottom: 5px;">
                        <b>{color} {signal_type}</b> {signal['symbol']} 
                        | Confidence: <b>{confidence}%</b>
                        | Phase: {signal['wyckoff_phase']}
                        | Delta: {signal['order_flow_delta']:.2f}
                        | {timestamp.strftime('%H:%M:%S')}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    
    def _render_system_health(self) -> None:
        """Render system health status"""
        st.subheader("🏥 System Health")
        
        status = self.metrics_collector.get_system_status()
        
        if status.get("status") == "unknown":
            st.warning("System status unknown")
            return
        
        # Overall status
        if status["status"] == "healthy":
            st.success("✅ System Healthy")
        else:
            st.error("⚠️ System Degraded")
        
        # Component status
        st.write("**Components:**")
        
        # API Status
        api_status = status["api_status"]
        if api_status == "healthy":
            st.write("🟢 API: Connected")
        elif api_status == "degraded":
            st.write("🟡 API: Degraded")
        else:
            st.write("🔴 API: Down")
        
        # DB Status
        db_status = status["db_status"]
        if db_status == "healthy":
            st.write("🟢 Database: Connected")
        elif db_status == "degraded":
            st.write("🟡 Database: Degraded")
        else:
            st.write("🔴 Database: Down")
        
        # Metrics
        st.write("**Metrics:**")
        st.write(f"Error Rate: {status['error_rate']:.2f}%")
        st.write(f"Uptime: {status['uptime_hours']:.1f} hours")
        st.write(f"Total Requests: {status['total_requests']:,}")
        st.write(f"Failed Requests: {status['failed_requests']:,}")
        
        if status["last_tick"]:
            last_tick = datetime.fromisoformat(status["last_tick"])
            seconds_ago = (datetime.now() - last_tick).total_seconds()
            st.write(f"Last Tick: {seconds_ago:.0f}s ago")
    
    def _render_current_phase(self) -> None:
        """Render current market phase"""
        st.subheader("📊 Current Market Phase")
        
        signals = self.metrics_collector.get_recent_signals(limit=1)
        
        if not signals:
            st.info("No phase data available")
            return
        
        latest = signals[0]
        
        # Wyckoff Phase
        phase = latest["wyckoff_phase"]
        st.write(f"**Wyckoff Phase:** {phase}")
        
        # Phase description
        phase_descriptions = {
            "ACCUMULATION": "📦 Smart money accumulating",
            "MARKUP": "🚀 Uptrend in progress",
            "DISTRIBUTION": "📤 Smart money distributing",
            "MARKDOWN": "📉 Downtrend in progress",
            "UNKNOWN": "❓ Phase unclear"
        }
        
        st.info(phase_descriptions.get(phase, "Unknown phase"))
        
        # Order Flow Delta
        delta = latest["order_flow_delta"]
        st.write(f"**Order Flow Delta:** {delta:.2f}")
        
        if delta > 0:
            st.success("🟢 Buying pressure dominant")
        elif delta < 0:
            st.error("🔴 Selling pressure dominant")
        else:
            st.warning("⚪ Neutral order flow")
    
    def _render_recent_errors(self) -> None:
        """Render recent errors"""
        st.subheader("⚠️ Recent Errors")
        
        errors = self.metrics_collector.get_recent_errors(limit=5)
        
        if not errors:
            st.success("No recent errors")
            return
        
        for error in reversed(errors):  # Most recent first
            timestamp = datetime.fromisoformat(error["timestamp"])
            with st.expander(f"{error['type']} - {timestamp.strftime('%H:%M:%S')}"):
                st.code(error["message"])


def run_dashboard(metrics_collector: MetricsCollector) -> None:
    """
    Run Streamlit dashboard
    
    Args:
        metrics_collector: MetricsCollector instance
    
    Usage:
        streamlit run src/monitoring/dashboard.py
    """
    dashboard = Dashboard(metrics_collector)
    dashboard.render()


if __name__ == "__main__":
    # For standalone testing
    from .metrics_collector import MetricsCollector
    
    # Create mock metrics collector
    collector = MetricsCollector()
    
    # Add some mock data
    collector.update_system_metrics(
        api_status="healthy",
        db_status="healthy",
        last_tick_time=datetime.now(),
        error_rate=Decimal("0.5"),
        uptime_seconds=3600,
        total_requests=1000,
        failed_requests=5
    )
    
    collector.update_trading_metrics(
        current_balance=Decimal("10500"),
        initial_balance=Decimal("10000"),
        equity=Decimal("10500"),
        total_pnl=Decimal("500"),
        realized_pnl=Decimal("500"),
        unrealized_pnl=Decimal("0"),
        total_trades=10,
        winning_trades=7,
        losing_trades=3,
        open_positions=0
    )
    
    collector.add_signal(
        symbol="BTCUSDT",
        signal_type="BUY",
        confidence=75,
        wyckoff_phase="MARKUP",
        order_flow_delta=Decimal("150.5")
    )
    
    run_dashboard(collector)
