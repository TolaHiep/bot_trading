"""Rate Limiter Module

This module implements a token bucket rate limiter to control API request rates.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests"""
    
    def __init__(self, max_requests: int, window: int):
        """Initialize rate limiter
        
        Args:
            max_requests: Maximum number of requests allowed (e.g., 600)
            window: Time window in seconds (e.g., 5)
        """
        self.max_requests = max_requests
        self.window = window
        self.requests: Deque[float] = deque()
        self._lock = asyncio.Lock()
        
    async def acquire(self) -> None:
        """Acquire permission to make a request
        
        This method will block if the rate limit has been reached,
        waiting until a request slot becomes available.
        """
        async with self._lock:
            now = time.time()
            
            # Remove requests outside the current window
            while self.requests and self.requests[0] <= now - self.window:
                self.requests.popleft()
                
            # If at limit, wait until oldest request expires
            if len(self.requests) >= self.max_requests:
                oldest_request = self.requests[0]
                wait_time = (oldest_request + self.window) - now
                
                if wait_time > 0:
                    logger.debug(
                        f"Rate limit reached. Waiting {wait_time:.2f}s. "
                        f"Queue size: {len(self.requests)}/{self.max_requests}"
                    )
                    await asyncio.sleep(wait_time)
                    
                    # Clean up again after waiting
                    now = time.time()
                    while self.requests and self.requests[0] <= now - self.window:
                        self.requests.popleft()
                        
            # Record this request
            self.requests.append(now)
            
    def get_remaining_quota(self) -> int:
        """Get remaining request quota in current window
        
        Returns:
            Number of requests that can be made without waiting
        """
        now = time.time()
        
        # Remove expired requests
        while self.requests and self.requests[0] <= now - self.window:
            self.requests.popleft()
            
        remaining = self.max_requests - len(self.requests)
        return max(0, remaining)
        
    def get_current_usage(self) -> int:
        """Get current number of requests in window
        
        Returns:
            Number of requests made in current window
        """
        now = time.time()
        
        # Remove expired requests
        while self.requests and self.requests[0] <= now - self.window:
            self.requests.popleft()
            
        return len(self.requests)
