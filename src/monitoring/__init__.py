"""
Monitoring module - Dashboard and alerts
"""

from .metrics_collector import (
    MetricsCollector,
    SystemMetrics,
    TradingMetrics,
    SignalMetrics
)

# Build __all__ list dynamically based on available imports
__all__ = [
    "MetricsCollector",
    "SystemMetrics",
    "TradingMetrics",
    "SignalMetrics"
]

# Optional telegram bot import (requires python-telegram-bot)
try:
    from .telegram_bot import TelegramBot, AlertRateLimiter
    __all__.extend(["TelegramBot", "AlertRateLimiter"])
except ImportError:
    pass

# Optional dashboard import (requires streamlit)
try:
    from .dashboard import Dashboard, run_dashboard
    __all__.extend(["Dashboard", "run_dashboard"])
except ImportError:
    pass
