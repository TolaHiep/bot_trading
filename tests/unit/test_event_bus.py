"""
Unit tests for the EventBus implementation.

Tests the publish-subscribe pattern, event dispatching, and queue management.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock
from src.core.event_bus import EventBus
from src.core.events import (
    Event,
    MarketDataEvent,
    SignalGeneratedEvent,
    OrderPlacedEvent,
)


@pytest.fixture
def event_bus():
    """Create an EventBus instance for testing."""
    return EventBus(queue_size=100)


@pytest.mark.asyncio
async def test_event_bus_initialization(event_bus):
    """Test that EventBus initializes correctly."""
    assert event_bus._queue.maxsize == 100
    assert event_bus._subscribers == {}
    assert not event_bus._running


@pytest.mark.asyncio
async def test_subscribe_handler(event_bus):
    """Test subscribing a handler to an event type."""
    handler = AsyncMock()
    
    event_bus.subscribe(MarketDataEvent, handler)
    
    assert MarketDataEvent in event_bus._subscribers
    assert handler in event_bus._subscribers[MarketDataEvent]
    assert event_bus.get_subscriber_count(MarketDataEvent) == 1


@pytest.mark.asyncio
async def test_subscribe_multiple_handlers(event_bus):
    """Test subscribing multiple handlers to the same event type."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    
    event_bus.subscribe(MarketDataEvent, handler1)
    event_bus.subscribe(MarketDataEvent, handler2)
    
    assert event_bus.get_subscriber_count(MarketDataEvent) == 2


@pytest.mark.asyncio
async def test_subscribe_duplicate_handler(event_bus):
    """Test that subscribing the same handler twice doesn't duplicate it."""
    handler = AsyncMock()
    
    event_bus.subscribe(MarketDataEvent, handler)
    event_bus.subscribe(MarketDataEvent, handler)
    
    assert event_bus.get_subscriber_count(MarketDataEvent) == 1


@pytest.mark.asyncio
async def test_unsubscribe_handler(event_bus):
    """Test unsubscribing a handler from an event type."""
    handler = AsyncMock()
    
    event_bus.subscribe(MarketDataEvent, handler)
    event_bus.unsubscribe(MarketDataEvent, handler)
    
    assert MarketDataEvent not in event_bus._subscribers


@pytest.mark.asyncio
async def test_unsubscribe_one_of_multiple_handlers(event_bus):
    """Test unsubscribing one handler when multiple are subscribed."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    
    event_bus.subscribe(MarketDataEvent, handler1)
    event_bus.subscribe(MarketDataEvent, handler2)
    event_bus.unsubscribe(MarketDataEvent, handler1)
    
    assert event_bus.get_subscriber_count(MarketDataEvent) == 1
    assert handler2 in event_bus._subscribers[MarketDataEvent]


@pytest.mark.asyncio
async def test_publish_event(event_bus):
    """Test publishing an event to the queue."""
    event = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    
    await event_bus.publish(event)
    
    assert event_bus.get_queue_size() == 1


@pytest.mark.asyncio
async def test_publish_multiple_events(event_bus):
    """Test publishing multiple events."""
    event1 = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    event2 = SignalGeneratedEvent(symbol="BTCUSDT")
    
    await event_bus.publish(event1)
    await event_bus.publish(event2)
    
    assert event_bus.get_queue_size() == 2


@pytest.mark.asyncio
async def test_event_dispatch_to_handler(event_bus):
    """Test that events are dispatched to subscribed handlers."""
    handler = AsyncMock()
    event = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    
    event_bus.subscribe(MarketDataEvent, handler)
    await event_bus.start()
    await event_bus.publish(event)
    
    # Wait for event to be processed
    await asyncio.sleep(0.2)
    
    await event_bus.stop()
    
    handler.assert_called_once()
    call_args = handler.call_args[0][0]
    assert isinstance(call_args, MarketDataEvent)
    assert call_args.symbol == "BTCUSDT"


@pytest.mark.asyncio
async def test_event_dispatch_to_multiple_handlers(event_bus):
    """Test that events are dispatched to all subscribed handlers."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    event = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    
    event_bus.subscribe(MarketDataEvent, handler1)
    event_bus.subscribe(MarketDataEvent, handler2)
    await event_bus.start()
    await event_bus.publish(event)
    
    # Wait for event to be processed
    await asyncio.sleep(0.2)
    
    await event_bus.stop()
    
    handler1.assert_called_once()
    handler2.assert_called_once()


@pytest.mark.asyncio
async def test_event_not_dispatched_to_wrong_type(event_bus):
    """Test that events are only dispatched to handlers for their type."""
    market_handler = AsyncMock()
    signal_handler = AsyncMock()
    event = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    
    event_bus.subscribe(MarketDataEvent, market_handler)
    event_bus.subscribe(SignalGeneratedEvent, signal_handler)
    await event_bus.start()
    await event_bus.publish(event)
    
    # Wait for event to be processed
    await asyncio.sleep(0.2)
    
    await event_bus.stop()
    
    market_handler.assert_called_once()
    signal_handler.assert_not_called()


@pytest.mark.asyncio
async def test_start_and_stop(event_bus):
    """Test starting and stopping the event bus."""
    await event_bus.start()
    assert event_bus._running
    assert event_bus._processor_task is not None
    
    await event_bus.stop()
    assert not event_bus._running


@pytest.mark.asyncio
async def test_start_when_already_running(event_bus):
    """Test that starting an already running bus doesn't create issues."""
    await event_bus.start()
    await event_bus.start()  # Should log warning but not fail
    
    assert event_bus._running
    
    await event_bus.stop()


@pytest.mark.asyncio
async def test_handler_exception_doesnt_stop_processing(event_bus):
    """Test that an exception in one handler doesn't stop event processing."""
    failing_handler = AsyncMock(side_effect=Exception("Handler error"))
    working_handler = AsyncMock()
    event = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    
    event_bus.subscribe(MarketDataEvent, failing_handler)
    event_bus.subscribe(MarketDataEvent, working_handler)
    await event_bus.start()
    await event_bus.publish(event)
    
    # Wait for event to be processed
    await asyncio.sleep(0.2)
    
    await event_bus.stop()
    
    # Both handlers should be called despite one failing
    failing_handler.assert_called_once()
    working_handler.assert_called_once()


@pytest.mark.asyncio
async def test_queue_full_drops_event(event_bus):
    """Test that events are dropped when queue is full."""
    small_bus = EventBus(queue_size=2)
    
    event1 = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    event2 = MarketDataEvent(symbol="ETHUSDT", timeframe="1m", data_type="kline")
    event3 = MarketDataEvent(symbol="SOLUSDT", timeframe="1m", data_type="kline")
    
    await small_bus.publish(event1)
    await small_bus.publish(event2)
    await small_bus.publish(event3)  # Should be dropped
    
    # Queue should be full (2 events)
    assert small_bus.get_queue_size() == 2


@pytest.mark.asyncio
async def test_process_remaining_events_on_stop(event_bus):
    """Test that remaining events in queue are processed when stopping."""
    handler = AsyncMock()
    event1 = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    event2 = MarketDataEvent(symbol="ETHUSDT", timeframe="1m", data_type="kline")
    
    event_bus.subscribe(MarketDataEvent, handler)
    await event_bus.start()
    await event_bus.publish(event1)
    await event_bus.publish(event2)
    
    # Stop immediately without waiting
    await event_bus.stop()
    
    # Both events should be processed
    assert handler.call_count == 2


@pytest.mark.asyncio
async def test_get_subscriber_count_for_unsubscribed_type(event_bus):
    """Test getting subscriber count for an event type with no subscribers."""
    count = event_bus.get_subscriber_count(OrderPlacedEvent)
    assert count == 0


@pytest.mark.asyncio
async def test_event_id_is_unique(event_bus):
    """Test that each event gets a unique ID."""
    event1 = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    event2 = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    
    assert event1.event_id != event2.event_id


@pytest.mark.asyncio
async def test_event_type_is_set_correctly(event_bus):
    """Test that event_type is set based on class name."""
    market_event = MarketDataEvent(symbol="BTCUSDT", timeframe="1m", data_type="kline")
    signal_event = SignalGeneratedEvent(symbol="BTCUSDT")
    
    assert market_event.event_type == "MarketDataEvent"
    assert signal_event.event_type == "SignalGeneratedEvent"
