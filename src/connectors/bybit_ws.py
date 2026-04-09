"""Bybit WebSocket Manager

This module manages WebSocket connections to Bybit for real-time market data.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set

import aiohttp
import ujson

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections to Bybit"""
    
    # Bybit WebSocket endpoints
    TESTNET_WS = "wss://stream-testnet.bybit.com/v5/public/linear"
    MAINNET_WS = "wss://stream.bybit.com/v5/public/linear"
    
    def __init__(self, testnet: bool = True):
        """Initialize WebSocket manager
        
        Args:
            testnet: Use testnet endpoint if True, mainnet if False
        """
        self.endpoint = self.TESTNET_WS if testnet else self.MAINNET_WS
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.subscriptions: Set[str] = set()
        self.callbacks: Dict[str, List[Callable]] = {}
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._last_message_time: Optional[float] = None
        
    async def connect(self) -> None:
        """Establish WebSocket connection"""
        try:
            if self.session is None:
                self.session = aiohttp.ClientSession()
                
            logger.info(f"Connecting to Bybit WebSocket: {self.endpoint}")
            self.ws = await self.session.ws_connect(
                self.endpoint,
                heartbeat=20,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            self._running = True
            self._last_message_time = asyncio.get_event_loop().time()
            
            # Start receive task
            self._receive_task = asyncio.create_task(self._receive_messages())
            
            # Start ping task
            self._ping_task = asyncio.create_task(self._send_pings())
            
            logger.info("WebSocket connected successfully")
            
            # Resubscribe to channels if reconnecting
            if self.subscriptions:
                await self._resubscribe()
                
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            raise
            
    async def disconnect(self) -> None:
        """Close WebSocket connection"""
        self._running = False
        
        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
            
        # Close WebSocket
        if self.ws and not self.ws.closed:
            await self.ws.close()
            
        # Close session
        if self.session and not self.session.closed:
            await self.session.close()
            
        logger.info("WebSocket disconnected")
        
    async def subscribe(self, channel: str, symbol: str) -> None:
        """Subscribe to a channel for a specific symbol
        
        Args:
            channel: Channel name (e.g., "kline.1", "trade", "orderbook.20")
            symbol: Trading symbol (e.g., "BTCUSDT")
        """
        topic = f"{channel}.{symbol}"
        
        if topic in self.subscriptions:
            logger.debug(f"Already subscribed to {topic}")
            return
            
        subscribe_msg = {
            "op": "subscribe",
            "args": [topic]
        }
        
        try:
            await self.ws.send_str(ujson.dumps(subscribe_msg))
            self.subscriptions.add(topic)
            logger.info(f"Subscribed to {topic}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {topic}: {e}")
            raise
            
    async def unsubscribe(self, channel: str, symbol: str) -> None:
        """Unsubscribe from a channel
        
        Args:
            channel: Channel name
            symbol: Trading symbol
        """
        topic = f"{channel}.{symbol}"
        
        if topic not in self.subscriptions:
            return
            
        unsubscribe_msg = {
            "op": "unsubscribe",
            "args": [topic]
        }
        
        try:
            await self.ws.send_str(ujson.dumps(unsubscribe_msg))
            self.subscriptions.remove(topic)
            logger.info(f"Unsubscribed from {topic}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {topic}: {e}")
            
    def register_callback(self, topic: str, callback: Callable) -> None:
        """Register a callback for a specific topic
        
        Args:
            topic: Topic pattern (e.g., "kline", "trade", "orderbook")
            callback: Async callback function to handle messages
        """
        if topic not in self.callbacks:
            self.callbacks[topic] = []
        self.callbacks[topic].append(callback)
        logger.debug(f"Registered callback for topic: {topic}")
        
    async def _receive_messages(self) -> None:
        """Receive and process WebSocket messages"""
        while self._running:
            try:
                msg = await self.ws.receive()
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._last_message_time = asyncio.get_event_loop().time()
                    await self._handle_message(msg.data)
                    
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket connection closed by server")
                    await self._handle_disconnect()
                    break
                    
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self.ws.exception()}")
                    await self._handle_disconnect()
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                await self._handle_disconnect()
                break
                
    async def _handle_message(self, data: str) -> None:
        """Handle incoming WebSocket message
        
        Args:
            data: Raw message data
        """
        try:
            message = ujson.loads(data)
            
            # Handle pong response
            if message.get("op") == "pong":
                logger.debug("Received pong")
                return
                
            # Handle subscription confirmation
            if message.get("op") == "subscribe":
                logger.debug(f"Subscription confirmed: {message}")
                return
                
            # Handle data messages
            if "topic" in message and "data" in message:
                topic = message["topic"]
                data = message["data"]
                
                # Extract base topic (e.g., "kline" from "kline.1.BTCUSDT")
                base_topic = topic.split(".")[0]
                
                # Call registered callbacks
                if base_topic in self.callbacks:
                    for callback in self.callbacks[base_topic]:
                        try:
                            await callback(message)
                        except Exception as e:
                            logger.error(f"Error in callback for {topic}: {e}")
                            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            
    async def _send_pings(self) -> None:
        """Send periodic ping messages to keep connection alive"""
        while self._running:
            try:
                await asyncio.sleep(20)
                
                if self.ws and not self.ws.closed:
                    ping_msg = {"op": "ping"}
                    await self.ws.send_str(ujson.dumps(ping_msg))
                    logger.debug("Sent ping")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending ping: {e}")
                
    async def _handle_disconnect(self) -> None:
        """Handle WebSocket disconnection and trigger reconnection"""
        if not self._running:
            return
            
        logger.warning("WebSocket disconnected, attempting to reconnect...")
        
        # Cancel existing tasks
        if self._receive_task:
            self._receive_task.cancel()
        if self._ping_task:
            self._ping_task.cancel()
            
        # Start reconnection
        self._reconnect_task = asyncio.create_task(self.reconnect())
        
    async def reconnect(self) -> None:
        """Reconnect to WebSocket with exponential backoff"""
        max_retries = 5
        retry_delays = [1, 2, 4, 8, 16]  # Exponential backoff
        
        for attempt in range(max_retries):
            try:
                delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                logger.info(f"Reconnection attempt {attempt + 1}/{max_retries} in {delay}s")
                
                await asyncio.sleep(delay)
                
                # Close old connection
                if self.ws and not self.ws.closed:
                    await self.ws.close()
                    
                # Establish new connection
                await self.connect()
                
                logger.info("Reconnection successful")
                return
                
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                
                if attempt == max_retries - 1:
                    logger.critical("Max reconnection attempts reached. Giving up.")
                    self._running = False
                    raise
                    
    async def _resubscribe(self) -> None:
        """Resubscribe to all channels after reconnection"""
        logger.info(f"Resubscribing to {len(self.subscriptions)} channels")
        
        # Create a copy to avoid modification during iteration
        subscriptions_copy = list(self.subscriptions)
        self.subscriptions.clear()
        
        for topic in subscriptions_copy:
            # Parse topic back to channel and symbol
            parts = topic.split(".")
            if len(parts) >= 2:
                channel = ".".join(parts[:-1])
                symbol = parts[-1]
                await self.subscribe(channel, symbol)
                
    def is_connected(self) -> bool:
        """Check if WebSocket is connected
        
        Returns:
            True if connected, False otherwise
        """
        return self.ws is not None and not self.ws.closed and self._running
