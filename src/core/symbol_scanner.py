"""Symbol Scanner Module

This module implements the SymbolScanner component that fetches and filters
tradeable symbols from Bybit based on volume, spread, volatility, and other criteria.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from src.connectors.bybit_rest import RESTClient

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """Information about a tradeable symbol"""
    symbol: str
    status: str
    base_currency: str
    quote_currency: str
    volume_24h_usd: Decimal
    bid_price: Decimal
    ask_price: Decimal
    spread_pct: float
    price_scale: int
    qty_scale: int
    min_order_qty: Decimal
    max_order_qty: Decimal
    launch_time: Optional[int]
    last_updated: datetime


@dataclass
class FiltersConfig:
    """Configuration for symbol filtering"""
    volume_threshold: Decimal
    max_spread_pct: float = 0.1
    min_atr_multiplier: float = 0.5
    min_listing_age_hours: int = 48
    blacklist: Set[str] = None
    
    def __post_init__(self):
        if self.blacklist is None:
            self.blacklist = set()


class SymbolScanner:
    """Scans and filters tradeable symbols from Bybit exchange"""
    
    def __init__(
        self,
        rest_client: RESTClient,
        volume_threshold: Decimal,
        filters_config: Optional[FiltersConfig] = None
    ):
        """Initialize SymbolScanner
        
        Args:
            rest_client: Bybit REST API client
            volume_threshold: Minimum 24h volume in USD (e.g., 10000000 for $10M)
            filters_config: Optional filters configuration
        """
        self.rest_client = rest_client
        self.volume_threshold = volume_threshold
        
        if filters_config is None:
            filters_config = FiltersConfig(volume_threshold=volume_threshold)
        self.filters_config = filters_config
        
        # Cache for symbol information
        self._symbol_cache: Dict[str, SymbolInfo] = {}
        self._filtered_symbols: Set[str] = set()
        self._last_refresh: Optional[datetime] = None
        
        logger.info(
            f"SymbolScanner initialized with volume threshold: ${volume_threshold:,.0f}"
        )
    
    async def fetch_symbols(self) -> List[str]:
        """Fetch and filter tradeable symbols from Bybit
        
        This method performs multi-step filtering:
        1. Query /v5/market/instruments-info with cursor-based pagination
        2. Query /v5/market/tickers to get volume and spread data
        3. Apply filters: volume, status, spread, volatility, listing age, blacklist
        
        Returns:
            List of filtered symbol names
        """
        logger.info("Fetching symbols from Bybit...")
        
        # Step 1: Fetch all instruments with pagination
        instruments = await self._fetch_all_instruments()
        logger.info(f"Fetched {len(instruments)} total instruments")
        
        # Step 2: Fetch ticker data for volume and spread
        tickers = await self._fetch_tickers()
        logger.info(f"Fetched ticker data for {len(tickers)} symbols")
        
        # Step 3: Apply filters
        filtered_symbols = []
        filter_stats = {
            "total": len(instruments),
            "status": 0,
            "volume": 0,
            "spread": 0,
            "listing_age": 0,
            "blacklist": 0,
            "missing_ticker": 0,
            "passed": 0
        }
        
        for instrument in instruments:
            symbol = instrument.get("symbol")
            if not symbol:
                continue
            
            # Filter: Status must be "Trading"
            status = instrument.get("status")
            if status != "Trading":
                filter_stats["status"] += 1
                logger.debug(f"Excluded {symbol}: status={status}")
                continue
            
            # Filter: Blacklist
            blacklist = self.filters_config.get("blacklist", [])
            if symbol in blacklist:
                filter_stats["blacklist"] += 1
                logger.debug(f"Excluded {symbol}: in blacklist")
                continue
            
            # Filter: Listing age (must be > 48 hours)
            launch_time = instrument.get("launchTime")
            if launch_time:
                launch_time_ms = int(launch_time)
                listing_age_hours = (time.time() * 1000 - launch_time_ms) / (1000 * 3600)
                min_listing_age = self.filters_config.get("min_listing_age_hours", 48)
                if listing_age_hours < min_listing_age:
                    filter_stats["listing_age"] += 1
                    logger.debug(
                        f"Excluded {symbol}: listing age {listing_age_hours:.1f}h "
                        f"< {min_listing_age}h"
                    )
                    continue
            
            # Get ticker data
            ticker = tickers.get(symbol)
            if not ticker:
                filter_stats["missing_ticker"] += 1
                logger.debug(f"Excluded {symbol}: no ticker data")
                continue
            
            # Filter: Volume (turnover24h in USD)
            turnover_24h = ticker.get("turnover24h", "0")
            try:
                volume_usd = Decimal(turnover_24h)
            except (ValueError, TypeError):
                filter_stats["missing_ticker"] += 1
                logger.debug(f"Excluded {symbol}: invalid turnover24h")
                continue
            
            if volume_usd < self.volume_threshold:
                filter_stats["volume"] += 1
                logger.debug(
                    f"Excluded {symbol}: volume ${volume_usd:,.0f} "
                    f"< ${self.volume_threshold:,.0f}"
                )
                continue
            
            # Filter: Spread (< 0.1%)
            bid_price_str = ticker.get("bid1Price", "0")
            ask_price_str = ticker.get("ask1Price", "0")
            
            try:
                bid_price = Decimal(bid_price_str)
                ask_price = Decimal(ask_price_str)
            except (ValueError, TypeError):
                filter_stats["missing_ticker"] += 1
                logger.debug(f"Excluded {symbol}: invalid bid/ask prices")
                continue
            
            if bid_price <= 0 or ask_price <= 0:
                filter_stats["missing_ticker"] += 1
                logger.debug(f"Excluded {symbol}: zero bid/ask prices")
                continue
            
            mid_price = (bid_price + ask_price) / 2
            spread_pct = float((ask_price - bid_price) / mid_price * 100)
            
            max_spread = self.filters_config.get("max_spread_pct", 0.001) * 100  # Convert to percentage
            if spread_pct > max_spread:
                filter_stats["spread"] += 1
                logger.debug(
                    f"Excluded {symbol}: spread {spread_pct:.3f}% "
                    f"> {max_spread}%"
                )
                continue
            
            # Symbol passed all filters
            filter_stats["passed"] += 1
            filtered_symbols.append(symbol)
            
            # Cache symbol info
            self._symbol_cache[symbol] = SymbolInfo(
                symbol=symbol,
                status=status,
                base_currency=instrument.get("baseCoin", ""),
                quote_currency=instrument.get("quoteCoin", ""),
                volume_24h_usd=volume_usd,
                bid_price=bid_price,
                ask_price=ask_price,
                spread_pct=spread_pct,
                price_scale=int(instrument.get("priceScale", 2)),
                qty_scale=int(instrument.get("qtyScale", 4)),
                min_order_qty=Decimal(instrument.get("lotSizeFilter", {}).get("minOrderQty", "0")),
                max_order_qty=Decimal(instrument.get("lotSizeFilter", {}).get("maxOrderQty", "0")),
                launch_time=int(launch_time) if launch_time else None,
                last_updated=datetime.now()
            )
        
        # Update filtered symbols cache
        self._filtered_symbols = set(filtered_symbols)
        self._last_refresh = datetime.now()
        
        # Log filter statistics
        logger.info(
            f"Symbol filtering complete: {filter_stats['passed']}/{filter_stats['total']} passed"
        )
        logger.info(
            f"Filter exclusions: "
            f"status={filter_stats['status']}, "
            f"volume={filter_stats['volume']}, "
            f"spread={filter_stats['spread']}, "
            f"listing_age={filter_stats['listing_age']}, "
            f"blacklist={filter_stats['blacklist']}, "
            f"missing_ticker={filter_stats['missing_ticker']}"
        )
        
        return sorted(filtered_symbols)
    
    async def refresh_symbols(self) -> Tuple[List[str], List[str]]:
        """Refresh symbol list and detect changes
        
        This method fetches the latest symbol list and compares it with
        the cached list to identify newly added and removed symbols.
        Should be called every 6 hours.
        
        Returns:
            Tuple of (added_symbols, removed_symbols)
        """
        logger.info("Refreshing symbol list...")
        
        # Store old symbols
        old_symbols = self._filtered_symbols.copy()
        
        # Fetch new symbols
        new_symbols = set(await self.fetch_symbols())
        
        # Detect changes
        added = sorted(new_symbols - old_symbols)
        removed = sorted(old_symbols - new_symbols)
        
        if added:
            logger.info(f"Added {len(added)} symbols: {', '.join(added)}")
        if removed:
            logger.info(f"Removed {len(removed)} symbols: {', '.join(removed)}")
        if not added and not removed:
            logger.info("No symbol changes detected")
        
        return added, removed
    
    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """Get cached information for a symbol
        
        Args:
            symbol: Symbol name (e.g., "BTCUSDT")
        
        Returns:
            SymbolInfo if found, None otherwise
        """
        return self._symbol_cache.get(symbol)
    
    def get_filtered_symbols(self) -> List[str]:
        """Get current list of filtered symbols
        
        Returns:
            List of symbol names
        """
        return sorted(self._filtered_symbols)
    
    def get_last_refresh_time(self) -> Optional[datetime]:
        """Get timestamp of last symbol refresh
        
        Returns:
            Datetime of last refresh, or None if never refreshed
        """
        return self._last_refresh
    
    async def _fetch_all_instruments(self) -> List[Dict]:
        """Fetch all instruments using cursor-based pagination
        
        Returns:
            List of instrument dictionaries
        """
        instruments = []
        cursor = None
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
        
        while True:
            params = {
                "category": "linear",
                "limit": "1000"
            }
            
            if cursor:
                params["cursor"] = cursor
            
            # Retry logic with exponential backoff
            for attempt in range(max_retries):
                try:
                    result = await self.rest_client._request(
                        "GET",
                        "/v5/market/instruments-info",
                        params,
                        signed=False
                    )
                    
                    # Validate response
                    if not isinstance(result, dict):
                        logger.error(f"Invalid response type: {type(result)}, expected dict. Response: {result}")
                        raise ValueError(f"Invalid response type: {type(result)}")
                    
                    # Extract instruments
                    batch = result.get("list", [])
                    instruments.extend(batch)
                    
                    # Check for next page
                    cursor = result.get("nextPageCursor")
                    if not cursor:
                        return instruments
                    
                    # Success, break retry loop
                    break
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch instruments (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.info(f"Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries reached for instruments-info. "
                            f"Returning {len(instruments)} instruments fetched so far."
                        )
                        return instruments
        
        return instruments
    
    async def _fetch_tickers(self) -> Dict[str, Dict]:
        """Fetch ticker data for all symbols
        
        Returns:
            Dictionary mapping symbol to ticker data
        """
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
        
        params = {
            "category": "linear"
        }
        
        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                result = await self.rest_client._request(
                    "GET",
                    "/v5/market/tickers",
                    params,
                    signed=False
                )
                
                # Convert list to dictionary keyed by symbol
                tickers = {}
                for ticker in result.get("list", []):
                    symbol = ticker.get("symbol")
                    if symbol:
                        tickers[symbol] = ticker
                
                return tickers
                
            except Exception as e:
                logger.warning(
                    f"Failed to fetch tickers (attempt {attempt + 1}/{max_retries}): {e}"
                )
                
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries reached for tickers. Returning empty dict.")
                    return {}
        
        return {}
