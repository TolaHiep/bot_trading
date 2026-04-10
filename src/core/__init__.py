"""
Core infrastructure for the automated trading system.

This module provides the event bus, event types, and state persistence
for the event-driven architecture.
"""

from src.core.events import (
    Event,
    MarketDataEvent,
    SignalGeneratedEvent,
    OrderPlacedEvent,
    OrderFilledEvent,
    PositionOpenedEvent,
    PositionClosedEvent,
    KillSwitchActivatedEvent,
    SystemHealthEvent,
)
from src.core.event_bus import EventBus
# from src.core.state import SystemState, StatePersistence  # Commented out - requires aiofiles

__all__ = [
    "Event",
    "MarketDataEvent",
    "SignalGeneratedEvent",
    "OrderPlacedEvent",
    "OrderFilledEvent",
    "PositionOpenedEvent",
    "PositionClosedEvent",
    "KillSwitchActivatedEvent",
    "SystemHealthEvent",
    "EventBus",
    # "SystemState",
    # "StatePersistence",
]
