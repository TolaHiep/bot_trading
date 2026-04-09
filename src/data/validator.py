"""Data Validator Module

This module validates market data for completeness and correctness.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of data validation"""
    is_valid: bool
    errors: List[str]


class DataValidator:
    """Validate market data completeness and correctness"""
    
    def validate_kline(self, kline: dict) -> ValidationResult:
        """Validate kline data
        
        Checks:
            - Required fields: open, high, low, close, volume, timestamp, symbol, timeframe
            - Price constraints: high >= low, high >= open, high >= close, low <= open, low <= close
            - Volume >= 0
            - All prices > 0
            - Timestamp is valid
        
        Args:
            kline: Kline data dictionary
            
        Returns:
            ValidationResult with is_valid flag and error list
        """
        errors = []
        
        # Check required fields
        required_fields = ['open', 'high', 'low', 'close', 'volume', 'timestamp', 'symbol', 'timeframe']
        for field in required_fields:
            if field not in kline or kline[field] is None:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        try:
            # Convert to Decimal for precise comparison
            open_price = Decimal(str(kline['open']))
            high = Decimal(str(kline['high']))
            low = Decimal(str(kline['low']))
            close = Decimal(str(kline['close']))
            volume = Decimal(str(kline['volume']))
            
            # Check price > 0
            if open_price <= 0:
                errors.append(f"Invalid open price: {open_price} (must be > 0)")
            if high <= 0:
                errors.append(f"Invalid high price: {high} (must be > 0)")
            if low <= 0:
                errors.append(f"Invalid low price: {low} (must be > 0)")
            if close <= 0:
                errors.append(f"Invalid close price: {close} (must be > 0)")
            
            # Check volume >= 0
            if volume < 0:
                errors.append(f"Invalid volume: {volume} (must be >= 0)")
            
            # Check OHLC constraints
            if high < low:
                errors.append(f"Invalid OHLC: high ({high}) < low ({low})")
            if high < open_price:
                errors.append(f"Invalid OHLC: high ({high}) < open ({open_price})")
            if high < close:
                errors.append(f"Invalid OHLC: high ({high}) < close ({close})")
            if low > open_price:
                errors.append(f"Invalid OHLC: low ({low}) > open ({open_price})")
            if low > close:
                errors.append(f"Invalid OHLC: low ({low}) > close ({close})")
            
            # Check timestamp is valid integer
            timestamp = kline['timestamp']
            if not isinstance(timestamp, (int, float)) or timestamp <= 0:
                errors.append(f"Invalid timestamp: {timestamp}")
                
        except (ValueError, TypeError, KeyError) as e:
            errors.append(f"Data type error: {e}")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Kline validation failed for {kline.get('symbol', 'UNKNOWN')}: {errors}")
        
        return ValidationResult(is_valid=is_valid, errors=errors)
    
    def validate_trade(self, trade: dict) -> ValidationResult:
        """Validate trade data
        
        Checks:
            - Required fields: price, quantity, side, timestamp, symbol, trade_id
            - Price > 0
            - Quantity > 0
            - Side is 'Buy' or 'Sell'
            - Timestamp is valid
        
        Args:
            trade: Trade data dictionary
            
        Returns:
            ValidationResult with is_valid flag and error list
        """
        errors = []
        
        # Check required fields
        required_fields = ['price', 'quantity', 'side', 'timestamp', 'symbol', 'trade_id']
        for field in required_fields:
            if field not in trade or trade[field] is None:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        try:
            # Convert to Decimal
            price = Decimal(str(trade['price']))
            quantity = Decimal(str(trade['quantity']))
            
            # Check price > 0
            if price <= 0:
                errors.append(f"Invalid price: {price} (must be > 0)")
            
            # Check quantity > 0
            if quantity <= 0:
                errors.append(f"Invalid quantity: {quantity} (must be > 0)")
            
            # Check side
            side = trade['side']
            if side not in ['Buy', 'Sell']:
                errors.append(f"Invalid side: {side} (must be 'Buy' or 'Sell')")
            
            # Check timestamp
            timestamp = trade['timestamp']
            if not isinstance(timestamp, (int, float)) or timestamp <= 0:
                errors.append(f"Invalid timestamp: {timestamp}")
                
        except (ValueError, TypeError, KeyError) as e:
            errors.append(f"Data type error: {e}")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Trade validation failed for {trade.get('symbol', 'UNKNOWN')}: {errors}")
        
        return ValidationResult(is_valid=is_valid, errors=errors)
    
    def validate_orderbook(self, orderbook: dict) -> ValidationResult:
        """Validate orderbook data
        
        Checks:
            - Required fields: bids, asks, timestamp, symbol
            - Bids and asks are lists
            - At least 20 levels on each side
            - Each level has price and quantity
            - Prices and quantities > 0
            - Bids sorted descending, asks sorted ascending
        
        Args:
            orderbook: Orderbook data dictionary
            
        Returns:
            ValidationResult with is_valid flag and error list
        """
        errors = []
        
        # Check required fields
        required_fields = ['bids', 'asks', 'timestamp', 'symbol']
        for field in required_fields:
            if field not in orderbook or orderbook[field] is None:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return ValidationResult(is_valid=False, errors=errors)
        
        try:
            bids = orderbook['bids']
            asks = orderbook['asks']
            
            # Check bids and asks are lists
            if not isinstance(bids, list):
                errors.append(f"Bids must be a list, got {type(bids)}")
            if not isinstance(asks, list):
                errors.append(f"Asks must be a list, got {type(asks)}")
            
            if errors:
                return ValidationResult(is_valid=False, errors=errors)
            
            # Check depth requirement (at least 20 levels)
            if len(bids) < 20:
                errors.append(f"Insufficient bid depth: {len(bids)} (need >= 20)")
            if len(asks) < 20:
                errors.append(f"Insufficient ask depth: {len(asks)} (need >= 20)")
            
            # Validate bid levels
            for i, bid in enumerate(bids[:20]):  # Check first 20 levels
                if not isinstance(bid, (list, tuple)) or len(bid) < 2:
                    errors.append(f"Invalid bid format at level {i}: {bid}")
                    continue
                
                try:
                    price = Decimal(str(bid[0]))
                    quantity = Decimal(str(bid[1]))
                    
                    if price <= 0:
                        errors.append(f"Invalid bid price at level {i}: {price}")
                    if quantity <= 0:
                        errors.append(f"Invalid bid quantity at level {i}: {quantity}")
                    
                    # Check descending order
                    if i > 0 and len(bids[i-1]) >= 2:
                        prev_price = Decimal(str(bids[i-1][0]))
                        if price > prev_price:
                            errors.append(f"Bids not sorted descending at level {i}: {price} > {prev_price}")
                            
                except (ValueError, TypeError) as e:
                    errors.append(f"Bid data type error at level {i}: {e}")
            
            # Validate ask levels
            for i, ask in enumerate(asks[:20]):  # Check first 20 levels
                if not isinstance(ask, (list, tuple)) or len(ask) < 2:
                    errors.append(f"Invalid ask format at level {i}: {ask}")
                    continue
                
                try:
                    price = Decimal(str(ask[0]))
                    quantity = Decimal(str(ask[1]))
                    
                    if price <= 0:
                        errors.append(f"Invalid ask price at level {i}: {price}")
                    if quantity <= 0:
                        errors.append(f"Invalid ask quantity at level {i}: {quantity}")
                    
                    # Check ascending order
                    if i > 0 and len(asks[i-1]) >= 2:
                        prev_price = Decimal(str(asks[i-1][0]))
                        if price < prev_price:
                            errors.append(f"Asks not sorted ascending at level {i}: {price} < {prev_price}")
                            
                except (ValueError, TypeError) as e:
                    errors.append(f"Ask data type error at level {i}: {e}")
            
            # Check timestamp
            timestamp = orderbook['timestamp']
            if not isinstance(timestamp, (int, float)) or timestamp <= 0:
                errors.append(f"Invalid timestamp: {timestamp}")
                
        except (ValueError, TypeError, KeyError) as e:
            errors.append(f"Data error: {e}")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Orderbook validation failed for {orderbook.get('symbol', 'UNKNOWN')}: {errors}")
        
        return ValidationResult(is_valid=is_valid, errors=errors)
