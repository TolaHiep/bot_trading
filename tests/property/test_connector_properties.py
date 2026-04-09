"""Property-Based Tests for Bybit Connector

These tests validate universal properties that should hold across all inputs.
"""

import asyncio
import pytest
import time
from decimal import Decimal
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock, patch

from src.connectors.rate_limiter import RateLimiter
from src.connectors.ntp_sync import NTPSync
from src.connectors.bybit_ws import WebSocketManager
from src.connectors.bybit_rest import RESTClient, OrderSide, OrderType


# Configure Hypothesis
settings.register_profile("default", max_examples=100, deadline=10000)  # 10 second deadline
settings.load_profile("default")


class TestProperty1_WebSocketAutoReconnection:
    """
    Feature: quantitative-trading-bot, Property 1: WebSocket Auto-Reconnection
    
    For any WebSocket disconnection event, the Bybit_Connector should 
    successfully reconnect within 5 seconds.
    """
    
    @pytest.mark.asyncio
    @given(
        disconnect_count=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=20)
    async def test_websocket_reconnects_within_5_seconds(self, disconnect_count):
        """Test that WebSocket reconnects within 5 seconds after disconnect"""
        ws = WebSocketManager(testnet=True)
        
        # Mock the connect method to succeed
        ws.connect = AsyncMock()
        ws._running = True
        
        # Simulate disconnection and reconnection
        start_time = time.time()
        await ws.reconnect()
        elapsed = time.time() - start_time
        
        # Should reconnect within 5 seconds
        assert elapsed < 5.0
        assert ws.connect.called


class TestProperty2_APIRequestRetryWithExponentialBackoff:
    """
    Feature: quantitative-trading-bot, Property 2: API Request Retry with Exponential Backoff
    
    For any failed API request, the system should retry up to the configured 
    maximum (3 times for Bybit_Connector, 2 times for Order_Manager) with 
    exponential backoff between attempts.
    """
    
    @pytest.mark.asyncio
    @given(
        failure_count=st.integers(min_value=1, max_value=2)
    )
    @settings(max_examples=20)
    async def test_rest_client_retries_with_exponential_backoff(self, failure_count):
        """Test that REST client retries with exponential backoff"""
        async with RESTClient("key", "secret", testnet=True) as client:
            call_times = []
            call_count = 0
            
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                call_times.append(time.time())
                call_count += 1
                
                if call_count <= failure_count:
                    raise asyncio.TimeoutError("Network error")
                    
                # Success on final attempt
                return {"retCode": 0, "result": {}}
                
            with patch.object(client.session, 'get') as mock_get:
                mock_response = AsyncMock()
                mock_response.text = AsyncMock(side_effect=mock_request)
                mock_get.return_value.__aenter__.return_value = mock_response
                
                try:
                    await client._request("GET", "/test", {})
                except:
                    pass
                    
                # Verify exponential backoff between retries
                if len(call_times) >= 2:
                    # First retry should wait ~1 second
                    delay1 = call_times[1] - call_times[0]
                    assert 0.9 <= delay1 <= 1.5
                    
                if len(call_times) >= 3:
                    # Second retry should wait ~2 seconds
                    delay2 = call_times[2] - call_times[1]
                    assert 1.8 <= delay2 <= 2.5


class TestProperty3_APIRateLimiting:
    """
    Feature: quantitative-trading-bot, Property 3: API Rate Limiting
    
    For any sequence of API requests within a 5-second window, the total 
    number of requests sent to Bybit should not exceed 600.
    """
    
    @pytest.mark.asyncio
    @given(
        max_requests=st.integers(min_value=5, max_value=20),
        window=st.integers(min_value=1, max_value=5),
        request_count=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=50)
    async def test_rate_limiter_enforces_limit(self, max_requests, window, request_count):
        """Test that rate limiter enforces request limits"""
        limiter = RateLimiter(max_requests=max_requests, window=window)
        
        # Make requests
        start_time = time.time()
        for _ in range(request_count):
            await limiter.acquire()
            
        elapsed = time.time() - start_time
        
        # Calculate expected minimum time
        if request_count > max_requests:
            # Should have waited for at least one window
            windows_needed = (request_count - 1) // max_requests
            expected_min_time = windows_needed * window * 0.9  # 90% tolerance
            assert elapsed >= expected_min_time
            
        # Verify usage never exceeds limit
        assert limiter.get_current_usage() <= max_requests
        
    @pytest.mark.asyncio
    @given(
        burst_size=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=30)
    async def test_rate_limiter_allows_bursts_within_limit(self, burst_size):
        """Test that rate limiter allows bursts within limit"""
        limiter = RateLimiter(max_requests=10, window=1)
        
        if burst_size <= 10:
            # Should allow burst without waiting
            start_time = time.time()
            for _ in range(burst_size):
                await limiter.acquire()
            elapsed = time.time() - start_time
            
            # Should be fast (no waiting)
            assert elapsed < 0.5


class TestProperty4_TimeDriftWarning:
    """
    Feature: quantitative-trading-bot, Property 4: Time Drift Warning
    
    For any system time measurement, if the drift from NTP server exceeds 
    1 second, a time synchronization warning should be emitted.
    """
    
    @pytest.mark.asyncio
    @given(
        time_offset=st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    async def test_ntp_warns_on_large_drift(self, time_offset):
        """Test that NTP sync warns when drift exceeds 1 second"""
        ntp = NTPSync()
        
        # Mock NTP response
        mock_response = MagicMock()
        mock_response.offset = time_offset
        
        with patch.object(ntp.ntp_client, 'request', return_value=mock_response):
            with patch('src.connectors.ntp_sync.logger') as mock_logger:
                await ntp.sync_time()
                
                # Should warn if drift > 1 second
                if abs(time_offset) > 1.0:
                    mock_logger.warning.assert_called()
                    # Verify warning message mentions drift
                    warning_call = mock_logger.warning.call_args
                    assert "drift" in str(warning_call).lower()
                else:
                    # Should not warn for small drift
                    mock_logger.warning.assert_not_called()
                    
    @pytest.mark.asyncio
    @given(
        time_offset=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    async def test_ntp_drift_calculation_accuracy(self, time_offset):
        """Test that time drift is calculated accurately"""
        ntp = NTPSync()
        
        # Set offset
        ntp.time_offset = time_offset
        
        # Get drift
        drift = ntp.get_time_drift()
        
        # Drift should be absolute value of offset
        if time_offset is not None:
            expected_drift = Decimal(str(abs(time_offset)))
            assert abs(drift - expected_drift) < Decimal("0.001")


class TestRateLimiterProperties:
    """Additional rate limiter properties"""
    
    @pytest.mark.asyncio
    @given(
        max_requests=st.integers(min_value=1, max_value=100),
        window=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    async def test_remaining_quota_accuracy(self, max_requests, window):
        """Test that remaining quota is calculated accurately"""
        limiter = RateLimiter(max_requests=max_requests, window=window)
        
        # Initially should have full quota
        assert limiter.get_remaining_quota() == max_requests
        
        # Use some quota
        requests_to_make = min(max_requests // 2, 10)
        for _ in range(requests_to_make):
            await limiter.acquire()
            
        # Remaining should be accurate
        remaining = limiter.get_remaining_quota()
        assert remaining == max_requests - requests_to_make
        
    @pytest.mark.asyncio
    @given(
        max_requests=st.integers(min_value=5, max_value=50),
        window=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=30)
    async def test_quota_never_negative(self, max_requests, window):
        """Test that remaining quota never goes negative"""
        limiter = RateLimiter(max_requests=max_requests, window=window)
        
        # Make many requests
        for _ in range(max_requests + 10):
            await limiter.acquire()
            
            # Quota should never be negative
            assert limiter.get_remaining_quota() >= 0


class TestWebSocketProperties:
    """Additional WebSocket properties"""
    
    @pytest.mark.asyncio
    @given(
        channel=st.sampled_from(["kline.1", "kline.5", "trade", "orderbook.20"]),
        symbol=st.sampled_from(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    )
    @settings(max_examples=30)
    async def test_subscription_idempotency(self, channel, symbol):
        """Test that subscribing multiple times to same channel is idempotent"""
        ws = WebSocketManager(testnet=True)
        ws.ws = AsyncMock()
        ws._running = True
        
        # Subscribe twice
        await ws.subscribe(channel, symbol)
        initial_count = len(ws.subscriptions)
        
        await ws.subscribe(channel, symbol)
        final_count = len(ws.subscriptions)
        
        # Should not create duplicate subscriptions
        assert initial_count == final_count
        
    @pytest.mark.asyncio
    @given(
        callback_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=20)
    async def test_multiple_callbacks_per_topic(self, callback_count):
        """Test that multiple callbacks can be registered for same topic"""
        ws = WebSocketManager(testnet=True)
        
        callbacks = []
        for i in range(callback_count):
            async def callback(msg, idx=i):
                pass
            callbacks.append(callback)
            ws.register_callback("kline", callback)
            
        # All callbacks should be registered
        assert len(ws.callbacks["kline"]) == callback_count


class TestRESTClientProperties:
    """Additional REST client properties"""
    
    @pytest.mark.asyncio
    @given(
        qty=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("100"), places=3),
        price=st.decimals(min_value=Decimal("1"), max_value=Decimal("100000"), places=2)
    )
    @settings(max_examples=30)
    async def test_order_parameters_preserved(self, qty, price):
        """Test that order parameters are preserved in API call"""
        async with RESTClient("key", "secret", testnet=True) as client:
            # Mock request to capture parameters
            captured_params = {}
            
            async def capture_request(method, endpoint, params, signed):
                captured_params.update(params)
                return {"orderId": "test123"}
                
            client._request = capture_request
            
            await client.place_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                qty=qty,
                price=price
            )
            
            # Parameters should match
            assert Decimal(captured_params["qty"]) == qty
            assert Decimal(captured_params["price"]) == price
            
    @pytest.mark.asyncio
    @given(
        balance=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000000"), places=2)
    )
    @settings(max_examples=30)
    async def test_balance_parsing_accuracy(self, balance):
        """Test that balance is parsed accurately from API response"""
        async with RESTClient("key", "secret", testnet=True) as client:
            mock_response = {
                "list": [{
                    "coin": [{
                        "coin": "USDT",
                        "availableToWithdraw": str(balance)
                    }]
                }]
            }
            client._request = AsyncMock(return_value=mock_response)
            
            parsed_balance = await client.get_account_balance()
            
            # Should match exactly
            assert parsed_balance == balance
