"""
Event bus implementation using asyncio.Queue for publish-subscribe pattern.

The event bus decouples modules by allowing them to publish events
and subscribe to event types without direct dependencies.
"""

import asyncio
import logging
from typing import Callable, Dict, List, Type
from src.core.events import Event


logger = logging.getLogger(__name__)


class EventBus:
    """
    Event bus for publish-subscribe pattern.
    
    Modules can publish events to the bus and subscribe to specific event types.
    The bus routes events to all registered subscribers asynchronously.
    """

    def __init__(self, queue_size: int = 1000):
        """
        Initialize the event bus.
        
        Args:
            queue_size: Maximum number of events in the queue
        """
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._subscribers: Dict[Type[Event], List[Callable]] = {}
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        logger.info(f"EventBus initialized with queue size {queue_size}")

    def subscribe(self, event_type: Type[Event], handler: Callable) -> None:
        """
        Subscribe a handler to a specific event type.
        
        Args:
            event_type: The event class to subscribe to
            handler: Async callable that will handle the event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed {handler.__name__} to {event_type.__name__}")

    def unsubscribe(self, event_type: Type[Event], handler: Callable) -> None:
        """
        Unsubscribe a handler from a specific event type.
        
        Args:
            event_type: The event class to unsubscribe from
            handler: The handler to remove
        """
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed {handler.__name__} from {event_type.__name__}")
                
                # Clean up empty subscriber lists
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]

    async def publish(self, event: Event) -> None:
        """
        Publish an event to the bus.
        
        Args:
            event: The event to publish
        """
        try:
            await self._queue.put(event)
            logger.debug(f"Published {event.event_type} (id: {event.event_id})")
        except asyncio.QueueFull:
            logger.error(f"Event queue full, dropping event {event.event_type}")

    async def start(self) -> None:
        """Start the event processor."""
        if self._running:
            logger.warning("EventBus already running")
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop the event processor."""
        if not self._running:
            return
        
        self._running = False
        
        # Wait for processor to finish
        if self._processor_task:
            await self._processor_task
        
        logger.info("EventBus stopped")

    async def _process_events(self) -> None:
        """
        Process events from the queue and dispatch to subscribers.
        
        This runs continuously until stop() is called.
        """
        logger.info("Event processor started")
        
        while self._running:
            try:
                # Wait for event with timeout to allow checking _running flag
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                # No event received, continue loop
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)

        # Process remaining events in queue
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                await self._dispatch_event(event)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error processing remaining event: {e}", exc_info=True)
        
        logger.info("Event processor stopped")

    async def _dispatch_event(self, event: Event) -> None:
        """
        Dispatch an event to all registered subscribers.
        
        Args:
            event: The event to dispatch
        """
        event_type = type(event)
        
        if event_type not in self._subscribers:
            logger.debug(f"No subscribers for {event.event_type}")
            return
        
        handlers = self._subscribers[event_type]
        logger.debug(f"Dispatching {event.event_type} to {len(handlers)} handlers")
        
        # Call all handlers concurrently
        tasks = []
        for handler in handlers:
            try:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating task for handler {handler.__name__}: {e}")
        
        # Wait for all handlers to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions from handlers
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    handler_name = handlers[i].__name__
                    logger.error(f"Handler {handler_name} raised exception: {result}", exc_info=result)

    def get_subscriber_count(self, event_type: Type[Event]) -> int:
        """
        Get the number of subscribers for an event type.
        
        Args:
            event_type: The event class
            
        Returns:
            Number of subscribers
        """
        return len(self._subscribers.get(event_type, []))

    def get_queue_size(self) -> int:
        """
        Get the current number of events in the queue.
        
        Returns:
            Number of events in queue
        """
        return self._queue.qsize()
