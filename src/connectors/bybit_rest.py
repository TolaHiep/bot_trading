"""Bybit REST API Client

This module provides a REST API client for Bybit exchange operations.
"""

import asyncio
import hashlib
import hmac
import logging
import time
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

import aiohttp
import ujson

from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side enum"""
    BUY = "Buy"
    SELL = "Sell"


class OrderType(Enum):
    """Order type enum"""
    LIMIT = "Limit"
    MARKET = "Market"


class OrderStatus(Enum):
    """Order status enum"""
    PENDING = "New"
    FILLED = "Filled"
    PARTIALLY_FILLED = "PartiallyFilled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


class APIError(Exception):
    """Bybit API error"""
    pass


class RateLimitError(Exception):
    """Rate limit exceeded error"""
    pass


class RESTClient:
    """Bybit REST API client"""
    
    # API endpoints
    TESTNET_API = "https://api-testnet.bybit.com"
    MAINNET_API = "https://api.bybit.com"
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        max_requests: int = 600,
        window: int = 5
    ):
        """Initialize REST client
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet if True, mainnet if False
            max_requests: Max requests per window (default: 600)
            window: Time window in seconds (default: 5)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = self.TESTNET_API if testnet else self.MAINNET_API
        self.rate_limiter = RateLimiter(max_requests, window)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    def _generate_signature(self, params: Dict, timestamp: int) -> str:
        """Generate HMAC SHA256 signature
        
        Args:
            params: Request parameters
            timestamp: Request timestamp
            
        Returns:
            Signature string
        """
        # Sort parameters
        param_str = str(timestamp) + self.api_key + "5000"  # recv_window
        
        # Add parameters
        for key in sorted(params.keys()):
            param_str += f"{key}={params[key]}"
            
        # Generate signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
        
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict:
        """Make HTTP request to Bybit API
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            params: Request parameters
            signed: Whether request requires signature
            
        Returns:
            Response data
            
        Raises:
            APIError: If API returns error
            RateLimitError: If rate limit exceeded
        """
        if params is None:
            params = {}
            
        # Acquire rate limit permission
        await self.rate_limiter.acquire()
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add authentication if signed
        if signed:
            timestamp = int(time.time() * 1000)
            headers["X-BAPI-API-KEY"] = self.api_key
            headers["X-BAPI-TIMESTAMP"] = str(timestamp)
            headers["X-BAPI-RECV-WINDOW"] = "5000"
            headers["X-BAPI-SIGN"] = self._generate_signature(params, timestamp)
            
        url = f"{self.base_url}{endpoint}"
        
        # Retry logic with exponential backoff
        max_retries = 3
        retry_delays = [1, 2, 4]
        
        for attempt in range(max_retries):
            try:
                if self.session is None:
                    self.session = aiohttp.ClientSession()
                    
                if method == "GET":
                    async with self.session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        data = await response.text()
                        result = ujson.loads(data)
                        
                elif method == "POST":
                    async with self.session.post(
                        url,
                        json=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        data = await response.text()
                        result = ujson.loads(data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                    
                # Check response
                if result.get("retCode") != 0:
                    error_msg = result.get("retMsg", "Unknown error")
                    
                    # Check if rate limit error
                    if "rate limit" in error_msg.lower():
                        raise RateLimitError(error_msg)
                        
                    raise APIError(f"API error: {error_msg}")
                    
                return result.get("result", {})
                
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Max retries reached for {endpoint}")
                    raise APIError(f"Request failed after {max_retries} attempts: {e}")
                    
            except (APIError, RateLimitError):
                raise
            except Exception as e:
                logger.error(f"Unexpected error in request: {e}")
                raise APIError(f"Unexpected error: {e}")
                
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        qty: Decimal,
        price: Optional[Decimal] = None,
        time_in_force: str = "GTC"
    ) -> Dict:
        """Place an order
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: Order side (BUY or SELL)
            order_type: Order type (LIMIT or MARKET)
            qty: Order quantity
            price: Order price (required for LIMIT orders)
            time_in_force: Time in force (default: GTC)
            
        Returns:
            Order information
            
        Raises:
            APIError: If order placement fails
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side.value,
            "orderType": order_type.value,
            "qty": str(qty),
            "timeInForce": time_in_force
        }
        
        if order_type == OrderType.LIMIT:
            if price is None:
                raise ValueError("Price required for LIMIT orders")
            params["price"] = str(price)
            
        logger.info(
            f"Placing {order_type.value} {side.value} order: "
            f"{qty} {symbol} @ {price if price else 'MARKET'}"
        )
        
        result = await self._request("POST", "/v5/order/create", params, signed=True)
        
        logger.info(f"Order placed successfully: {result.get('orderId')}")
        return result
        
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id
        }
        
        logger.info(f"Cancelling order: {order_id}")
        
        try:
            await self._request("POST", "/v5/order/cancel", params, signed=True)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except APIError as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
            
    async def get_order(self, symbol: str, order_id: str) -> Dict:
        """Get order information
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
            
        Returns:
            Order information
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id
        }
        
        result = await self._request("GET", "/v5/order/realtime", params, signed=True)
        
        # Extract first order from list
        orders = result.get("list", [])
        if orders:
            return orders[0]
        return {}
        
    async def get_position(self, symbol: str) -> Dict:
        """Get position information
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position information
        """
        params = {
            "category": "linear",
            "symbol": symbol
        }
        
        result = await self._request("GET", "/v5/position/list", params, signed=True)
        
        # Extract first position from list
        positions = result.get("list", [])
        if positions:
            return positions[0]
        return {}
        
    async def get_account_balance(self) -> Decimal:
        """Get account balance
        
        Returns:
            Available balance in USDT
        """
        params = {
            "accountType": "UNIFIED"
        }
        
        result = await self._request("GET", "/v5/account/wallet-balance", params, signed=True)
        
        # Extract USDT balance
        accounts = result.get("list", [])
        if accounts:
            coins = accounts[0].get("coin", [])
            for coin in coins:
                if coin.get("coin") == "USDT":
                    return Decimal(coin.get("availableToWithdraw", "0"))
                    
        return Decimal("0")
        
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 200
    ) -> list:
        """Get historical klines
        
        Args:
            symbol: Trading symbol
            interval: Kline interval (1, 5, 15, 60 for minutes)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Number of klines to fetch (max 200)
            
        Returns:
            List of klines
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": str(limit)
        }
        
        if start_time:
            params["start"] = str(start_time)
        if end_time:
            params["end"] = str(end_time)
            
        result = await self._request("GET", "/v5/market/kline", params, signed=False)
        
        return result.get("list", [])
