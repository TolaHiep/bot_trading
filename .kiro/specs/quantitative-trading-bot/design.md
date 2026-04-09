# Design Document - Quantitative Trading Bot

## Overview

### Mục đích hệ thống

Quantitative Trading Bot là một hệ thống giao dịch tự động định lượng được thiết kế để hoạt động trên sàn Bybit. Hệ thống tự động hóa toàn bộ quy trình giao dịch từ thu thập dữ liệu, phân tích thị trường, tạo tín hiệu, quản trị rủi ro đến thực thi lệnh. Hệ thống áp dụng các lý thuyết phân tích kỹ thuật tiên tiến (Dow Theory, Wyckoff Method, Order Flow Analysis) kết hợp với quản trị rủi ro Six Sigma để đạt được hiệu suất giao dịch ổn định và có thể mở rộng.

### Nguyên tắc thiết kế

1. **Event-Driven Architecture**: Hệ thống hoạt động theo mô hình sự kiện, cho phép xử lý bất đồng bộ và khả năng mở rộng cao
2. **Separation of Concerns**: Tách biệt rõ ràng giữa các module: Data, Alpha, Risk, Execution
3. **Performance-First**: Tối ưu hóa latency < 100ms cho toàn bộ pipeline từ nhận data đến ra quyết định
4. **Testability**: Thiết kế hỗ trợ property-based testing với Hypothesis và backtesting event-driven
5. **Fail-Safe**: Cơ chế Kill Switch và error handling đảm bảo an toàn vốn
6. **Observability**: Logging, monitoring và alerting toàn diện qua Dashboard và Telegram

### Công nghệ sử dụng

- **Language**: Python 3.11+ (asyncio, type hints)
- **Exchange API**: pybit v5 (WebSocket + REST)
- **Database**: TimescaleDB (time-series optimization)
- **Indicators**: pandas-ta, numpy (vectorized operations)
- **JSON Parsing**: ujson (high performance)
- **Testing**: Hypothesis (property-based testing), pytest
- **Monitoring**: Custom dashboard, Telegram Bot API
- **Configuration**: YAML (pyyaml)


## Architecture

### High-Level Architecture

Hệ thống được tổ chức theo kiến trúc phân tầng với luồng dữ liệu một chiều:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Bybit Exchange                          │
│                    (WebSocket + REST API)                       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONNECTOR LAYER                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Bybit Connector (src/connectors/)                       │  │
│  │  - WebSocket Manager (klines, trades, orderbook)         │  │
│  │  - REST Client (orders, account)                         │  │
│  │  - Rate Limiter (600 req/5s)                             │  │
│  │  - Auto-reconnect & Retry Logic                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Pipeline (src/data/)                               │  │
│  │  - Stream Processor (< 100ms latency)                    │  │
│  │  - Data Validator & Deduplicator                         │  │
│  │  - Gap Detector & Filler                                 │  │
│  │  - TimescaleDB Writer (hypertables)                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ALPHA LAYER                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Alpha Model (src/alpha/)                                │  │
│  │  - Indicator Engine (pandas-ta + numpy)                  │  │
│  │  - Order Flow Analyzer (delta, footprint)                │  │
│  │  - Wyckoff Detector (phase recognition)                  │  │
│  │  - Signal Generator (multi-timeframe)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RISK LAYER                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Risk Model (src/risk/)                                  │  │
│  │  - Position Sizer (2% max risk per trade)                │  │
│  │  - Stop-Loss Engine (trailing, breakeven)                │  │
│  │  - Kill Switch (5% daily DD, 5 consecutive losses)       │  │
│  │  - Drawdown Monitor                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Execution Model (src/execution/)                        │  │
│  │  - Order Manager (limit → market fallback)               │  │
│  │  - Cost Filter (slippage < 0.1%, total cost < 0.2%)      │  │
│  │  - Order Tracker & Verifier                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  MONITORING & CONTROL                           │
│  ┌────────────────────────┬────────────────────────────────┐   │
│  │  Dashboard             │  Telegram Bot                  │   │
│  │  (src/monitoring/)     │  (src/monitoring/)             │   │
│  │  - Real-time metrics   │  - Trade alerts                │   │
│  │  - Equity curve        │  - Commands (/status, /pnl)    │   │
│  │  - System health       │  - Error notifications         │   │
│  └────────────────────────┴────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    BACKTESTING ENGINE                           │
│  (src/backtest/)                                                │
│  - Event-driven replay                                          │
│  - Realistic slippage simulation                                │
│  - Look-ahead bias prevention                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

**Trading Flow (Live Mode)**:
1. Bybit Connector nhận market data qua WebSocket
2. Data Pipeline validate, deduplicate và lưu vào TimescaleDB (< 100ms)
3. Alpha Model tính indicators, phân tích order flow, nhận diện Wyckoff phase
4. Alpha Model tạo signal (BUY/SELL/NEUTRAL) với confidence score
5. Risk Model tính position size và đặt stop-loss
6. Kill Switch kiểm tra điều kiện dừng khẩn cấp
7. Execution Model thực thi lệnh với cost filtering
8. Monitoring gửi alert qua Telegram và cập nhật Dashboard

**Backtesting Flow**:
1. Backtesting Engine load historical data từ TimescaleDB
2. Replay data theo chronological order (prevent look-ahead bias)
3. Alpha Model xử lý data giống như live mode
4. Risk Model áp dụng cùng rules như live mode
5. Execution Model simulate order với realistic slippage
6. Performance Analytics tính metrics và generate reports


## Components and Interfaces

### 1. Bybit Connector (src/connectors/)

**Trách nhiệm**: Quản lý kết nối với Bybit API, xử lý WebSocket streams và REST requests.

**Subcomponents**:

#### 1.1 WebSocketManager
```python
class WebSocketManager:
    """Quản lý WebSocket connections đến Bybit"""
    
    async def connect(self, endpoint: str, channels: List[str]) -> None:
        """Kết nối WebSocket và subscribe channels
        
        Args:
            endpoint: Bybit WebSocket endpoint (testnet/mainnet)
            channels: List các channels cần subscribe (kline, trade, orderbook)
        """
    
    async def subscribe(self, channel: str, symbol: str) -> None:
        """Subscribe một channel cho symbol cụ thể"""
    
    async def on_message(self, message: dict) -> None:
        """Callback xử lý message từ WebSocket
        
        Emit events:
            - KlineReceived(symbol, timeframe, kline_data)
            - TradeReceived(symbol, trade_data)
            - OrderbookReceived(symbol, orderbook_data)
        """
    
    async def reconnect(self) -> None:
        """Auto-reconnect khi connection bị đứt (< 5s)"""
```

#### 1.2 RESTClient
```python
class RESTClient:
    """Client cho Bybit REST API"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.rate_limiter = RateLimiter(max_requests=600, window=5)
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        qty: Decimal,
        price: Optional[Decimal] = None
    ) -> Order:
        """Đặt lệnh giao dịch
        
        Returns:
            Order object với order_id, status, filled_qty
        
        Raises:
            RateLimitError: Khi vượt quá 600 req/5s
            APIError: Khi Bybit API trả về lỗi
        """
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Hủy lệnh"""
    
    async def get_position(self, symbol: str) -> Position:
        """Query vị thế hiện tại"""
    
    async def get_account_balance(self) -> Decimal:
        """Query số dư tài khoản"""
```

#### 1.3 RateLimiter
```python
class RateLimiter:
    """Giới hạn API request rate"""
    
    def __init__(self, max_requests: int, window: int):
        """
        Args:
            max_requests: Số request tối đa (600)
            window: Cửa sổ thời gian (5 giây)
        """
    
    async def acquire(self) -> None:
        """Chờ cho đến khi có thể gửi request
        
        Nếu đã đạt limit, queue request và chờ
        """
    
    def get_remaining_quota(self) -> int:
        """Trả về số request còn lại trong window hiện tại"""
```

**Interfaces**:
- Input: Bybit WebSocket/REST API
- Output: Events (KlineReceived, TradeReceived, OrderbookReceived)
- Dependencies: asyncio, pybit, ujson

---

### 2. Data Pipeline (src/data/)

**Trách nhiệm**: Thu thập, validate, deduplicate và lưu trữ market data vào TimescaleDB.

**Subcomponents**:

#### 2.1 StreamProcessor
```python
class StreamProcessor:
    """Xử lý real-time data streams"""
    
    async def process_kline(self, event: KlineReceived) -> None:
        """Xử lý kline data trong < 100ms
        
        Steps:
            1. Validate data (price > 0, volume >= 0)
            2. Deduplicate based on (symbol, timestamp, timeframe)
            3. Store to TimescaleDB
            4. Emit KlineProcessed event
        """
    
    async def process_trade(self, event: TradeReceived) -> None:
        """Xử lý trade data"""
    
    async def process_orderbook(self, event: OrderbookReceived) -> None:
        """Xử lý orderbook snapshot"""
```

#### 2.2 DataValidator
```python
class DataValidator:
    """Validate tính hợp lệ của market data"""
    
    def validate_kline(self, kline: dict) -> ValidationResult:
        """Kiểm tra kline data
        
        Checks:
            - Required fields: open, high, low, close, volume, timestamp
            - Price constraints: high >= low, high >= open, high >= close
            - Volume >= 0
            - Timestamp is valid Unix timestamp
        
        Returns:
            ValidationResult(is_valid: bool, errors: List[str])
        """
    
    def validate_trade(self, trade: dict) -> ValidationResult:
        """Kiểm tra trade data"""
    
    def validate_orderbook(self, orderbook: dict) -> ValidationResult:
        """Kiểm tra orderbook data"""
```

#### 2.3 GapDetector
```python
class GapDetector:
    """Phát hiện và fill gaps trong time-series data"""
    
    def detect_gap(
        self,
        symbol: str,
        timeframe: str,
        last_timestamp: int,
        current_timestamp: int
    ) -> Optional[TimeGap]:
        """Phát hiện gap bằng cách so sánh timestamps
        
        Returns:
            TimeGap nếu gap > 1 timeframe period, None otherwise
        """
    
    async def fill_gap(self, gap: TimeGap) -> List[Kline]:
        """Fill gap bằng cách gọi Bybit REST API lấy historical data
        
        Steps:
            1. Call GET /v5/market/kline với start_time và end_time
            2. Validate fetched data
            3. Store to TimescaleDB
            4. Recalculate affected indicators
            5. Emit DataGapFilled event
        """
```

#### 2.4 TimescaleDBWriter
```python
class TimescaleDBWriter:
    """Write data vào TimescaleDB"""
    
    async def write_kline(self, kline: Kline) -> None:
        """Insert kline vào hypertable klines
        
        Schema:
            - timestamp (TIMESTAMPTZ, primary key)
            - symbol (TEXT)
            - timeframe (TEXT)
            - open, high, low, close (NUMERIC)
            - volume (NUMERIC)
        """
    
    async def write_trade(self, trade: Trade) -> None:
        """Insert trade vào hypertable trades"""
    
    async def write_orderbook(self, orderbook: Orderbook) -> None:
        """Insert orderbook snapshot vào hypertable orderbooks"""
    
    async def buffer_write(self, records: List[Any]) -> None:
        """Buffer writes khi DB connection fails (max 10000 records)"""
```

**Interfaces**:
- Input: Events từ Bybit Connector
- Output: Stored data in TimescaleDB, Events (KlineProcessed, DataGapFilled)
- Dependencies: asyncpg, TimescaleDB

---

### 3. Alpha Model (src/alpha/)

**Trách nhiệm**: Phân tích thị trường và tạo trading signals.

**Subcomponents**:

#### 3.1 IndicatorEngine
```python
class IndicatorEngine:
    """Tính toán technical indicators"""
    
    def __init__(self):
        self.cache = {}  # Cache indicator values
    
    def calculate_indicators(self, df: pd.DataFrame) -> IndicatorSet:
        """Tính toán tất cả indicators trong < 50ms
        
        Uses vectorized operations (numpy, pandas-ta)
        
        Indicators:
            - SMA: periods [9, 21, 50, 200]
            - EMA: periods [9, 21, 50, 200]
            - RSI: period 14
            - MACD: (12, 26, 9)
            - Bollinger Bands: (20, 2)
            - Volume Profile: 24h window
        
        Returns:
            IndicatorSet với tất cả indicator values
        """
    
    def update_incremental(self, new_kline: Kline) -> IndicatorSet:
        """Update indicators incrementally khi có kline mới
        
        Optimization: Chỉ recalculate affected values thay vì toàn bộ
        """
```

#### 3.2 OrderFlowAnalyzer
```python
class OrderFlowAnalyzer:
    """Phân tích order flow từ trade data"""
    
    def __init__(self, window_size: int = 1000):
        self.trades_window = deque(maxlen=window_size)
    
    def add_trade(self, trade: Trade) -> None:
        """Thêm trade vào rolling window"""
    
    def calculate_cumulative_delta(self) -> Decimal:
        """Tính cumulative delta (buy volume - sell volume)
        
        Algorithm:
            delta = sum(qty if side == BUY else -qty for trade in window)
        """
    
    def create_footprint(self, price_levels: int = 50) -> FootprintChart:
        """Tạo footprint chart data
        
        Aggregate delta by price levels:
            - Group trades by price buckets
            - Calculate buy/sell volume per bucket
            - Identify imbalance zones (delta > 70% one direction)
        
        Returns:
            FootprintChart với delta per price level
        """
    
    def detect_delta_divergence(self, price_data: pd.Series) -> bool:
        """Phát hiện divergence giữa price và cumulative delta
        
        Returns:
            True nếu price tăng nhưng delta giảm (bearish divergence)
            hoặc price giảm nhưng delta tăng (bullish divergence)
        """
    
    def find_imbalance_zones(self) -> List[PriceLevel]:
        """Tìm các vùng imbalance (delta > 70% một chiều)"""
```

#### 3.3 WyckoffDetector
```python
class WyckoffDetector:
    """Nhận diện Wyckoff phases"""
    
    def detect_phase(
        self,
        price_data: pd.DataFrame,
        volume_data: pd.Series
    ) -> WyckoffPhase:
        """Nhận diện phase hiện tại
        
        Phases:
            - ACCUMULATION: Price range contraction + volume decrease
            - MARKUP: Higher highs + higher lows + volume increase
            - DISTRIBUTION: Price range expansion + volume increase
            - MARKDOWN: Lower highs + lower lows + volume increase
        
        Algorithm:
            1. Calculate price range (high - low) over rolling window
            2. Detect range contraction/expansion
            3. Analyze volume patterns
            4. Identify swing highs/lows
            5. Classify phase based on patterns
        
        Returns:
            WyckoffPhase enum
        """
    
    def detect_spring(self, phase: WyckoffPhase) -> bool:
        """Phát hiện Spring event trong Accumulation phase
        
        Spring: False breakdown below support followed by quick reversal
        """
    
    def detect_upthrust(self, phase: WyckoffPhase) -> bool:
        """Phát hiện Upthrust event trong Distribution phase
        
        Upthrust: False breakout above resistance followed by quick reversal
        """
```

#### 3.4 SignalGenerator
```python
class SignalGenerator:
    """Tổng hợp phân tích và tạo trading signals"""
    
    def generate_signal(
        self,
        indicators: IndicatorSet,
        order_flow: OrderFlowAnalysis,
        wyckoff_phase: WyckoffPhase,
        multi_timeframe_data: Dict[str, pd.DataFrame]
    ) -> Signal:
        """Tạo signal với confidence score
        
        BUY Signal Conditions:
            - Wyckoff phase == MARKUP
            - Cumulative delta > 0
            - Price breaks above resistance
            - Volume > 1.5x average (confirmation)
            - Alignment across timeframes (1m, 5m, 15m)
        
        SELL Signal Conditions:
            - Wyckoff phase == MARKDOWN
            - Cumulative delta < 0
            - Price breaks below support
            - Volume > 1.5x average (confirmation)
            - Alignment across timeframes
        
        Confidence Score Calculation:
            - Base: 40 points
            - Wyckoff alignment: +20 points
            - Order flow alignment: +20 points
            - Volume confirmation: +10 points
            - Multi-timeframe alignment: +10 points
        
        Returns:
            Signal(direction, confidence, timestamp, reasons)
        
        Note: Suppress signal if confidence < 60
        """
```

**Interfaces**:
- Input: Market data từ TimescaleDB, Events (KlineProcessed)
- Output: Events (SignalGenerated)
- Dependencies: pandas, pandas-ta, numpy


---

### 4. Risk Model (src/risk/)

**Trách nhiệm**: Quản trị rủi ro, tính position size, quản lý stop-loss và kill switch.

**Subcomponents**:

#### 4.1 PositionSizer
```python
class PositionSizer:
    """Tính toán kích thước vị thế"""
    
    def __init__(self, account_balance: Decimal, max_risk_per_trade: Decimal = Decimal("0.02")):
        self.account_balance = account_balance
        self.max_risk_per_trade = max_risk_per_trade  # 2%
        self.peak_balance = account_balance
    
    def calculate_position_size(
        self,
        signal: Signal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        leverage: int = 1
    ) -> Decimal:
        """Tính position size dựa trên risk management
        
        Algorithm:
            1. risk_amount = account_balance * max_risk_per_trade
            2. stop_loss_distance = abs(entry_price - stop_loss_price)
            3. position_size = risk_amount / stop_loss_distance
            4. Adjust by signal confidence: position_size *= (confidence / 100)
            5. Apply max position limit: min(position_size, account_balance * 0.1)
            6. Apply drawdown adjustment: if DD > 10%, reduce by 50%
            7. Account for leverage
            8. Round to Bybit min order quantity
        
        Returns:
            Position size in base currency
        """
    
    def adjust_for_drawdown(self, current_balance: Decimal) -> None:
        """Điều chỉnh position size khi drawdown > 10%
        
        If current_balance < peak_balance * 0.9:
            max_risk_per_trade = 0.01  # Reduce to 1%
        """
```

#### 4.2 StopLossEngine
```python
class StopLossEngine:
    """Quản lý stop-loss cho positions"""
    
    def __init__(self, rest_client: RESTClient):
        self.rest_client = rest_client
        self.active_stops = {}  # position_id -> stop_loss_order
    
    async def set_initial_stop(
        self,
        position: Position,
        stop_loss_price: Decimal
    ) -> str:
        """Đặt initial stop-loss khi mở position
        
        Stop-loss distance: 2% from entry price
        
        Returns:
            stop_loss_order_id
        """
    
    async def move_to_breakeven(self, position: Position) -> None:
        """Move stop-loss to breakeven khi profit >= 1%
        
        Steps:
            1. Cancel existing stop-loss order
            2. Place new stop-loss at entry price
        """
    
    async def activate_trailing_stop(
        self,
        position: Position,
        trail_distance: Decimal = Decimal("0.01")
    ) -> None:
        """Activate trailing stop khi profit >= 2%
        
        Trailing distance: 1% from current price
        
        Algorithm:
            - For LONG: stop_price = current_price * (1 - trail_distance)
            - For SHORT: stop_price = current_price * (1 + trail_distance)
            - Update stop_price every 1 second if price moves favorably
        """
    
    async def monitor_stops(self) -> None:
        """Monitor stop-loss orders mỗi 1 giây
        
        Checks:
            - Stop-loss order still active on exchange
            - If cancelled/rejected: close position immediately at market
        """
```

#### 4.3 KillSwitch
```python
class KillSwitch:
    """Cơ chế dừng giao dịch khẩn cấp"""
    
    def __init__(self, telegram_bot: TelegramBot):
        self.is_active = False
        self.activation_reason = None
        self.telegram_bot = telegram_bot
    
    async def check_conditions(
        self,
        daily_drawdown: Decimal,
        consecutive_losses: int,
        api_error_rate: float,
        price_movement: Decimal
    ) -> None:
        """Kiểm tra điều kiện kích hoạt kill switch
        
        Activation Conditions:
            1. daily_drawdown > 5%
            2. consecutive_losses >= 5
            3. api_error_rate > 20% over 1 minute
            4. price_movement > 10% in 1 minute (abnormal)
        
        If any condition met:
            - Set is_active = True
            - Close all open positions
            - Stop accepting new signals
            - Send Telegram alert
            - Log activation reason and system state
        """
    
    async def activate(self, reason: str) -> None:
        """Kích hoạt kill switch"""
    
    async def reset(self) -> None:
        """Reset kill switch (manual only)
        
        Requires explicit confirmation from user
        """
```

#### 4.4 DrawdownMonitor
```python
class DrawdownMonitor:
    """Theo dõi drawdown"""
    
    def __init__(self):
        self.peak_balance = Decimal("0")
        self.current_drawdown = Decimal("0")
        self.max_drawdown = Decimal("0")
    
    def update(self, current_balance: Decimal) -> None:
        """Update drawdown metrics
        
        Algorithm:
            if current_balance > peak_balance:
                peak_balance = current_balance
            current_drawdown = (peak_balance - current_balance) / peak_balance
            max_drawdown = max(max_drawdown, current_drawdown)
        """
    
    def get_daily_drawdown(self) -> Decimal:
        """Tính drawdown từ đầu ngày"""
```

**Interfaces**:
- Input: Events (SignalGenerated, PositionOpened)
- Output: Events (StopLossPlaced, KillSwitchActivated)
- Dependencies: Bybit Connector, Telegram Bot

---

### 5. Execution Model (src/execution/)

**Trách nhiệm**: Thực thi lệnh giao dịch với cost optimization.

**Subcomponents**:

#### 5.1 OrderManager
```python
class OrderManager:
    """Quản lý và thực thi orders"""
    
    def __init__(self, rest_client: RESTClient):
        self.rest_client = rest_client
        self.pending_orders = {}
        self.filled_orders = {}
    
    async def execute_signal(
        self,
        signal: Signal,
        position_size: Decimal,
        orderbook: Orderbook
    ) -> Optional[Position]:
        """Thực thi signal
        
        Strategy:
            1. Calculate expected slippage from orderbook
            2. If slippage > 0.1%: reject trade
            3. Place limit order at best bid/ask
            4. Wait 5 seconds for fill
            5. If not filled: cancel and place market order
            6. Verify execution via API query
            7. Retry up to 2 times on failure
        
        Returns:
            Position if successful, None if rejected/failed
        """
    
    async def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal,
        price: Decimal
    ) -> str:
        """Đặt limit order
        
        Returns:
            order_id
        """
    
    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: Decimal
    ) -> str:
        """Đặt market order (fallback)"""
    
    async def wait_for_fill(self, order_id: str, timeout: int = 5) -> bool:
        """Chờ order được fill trong timeout giây"""
    
    async def verify_execution(self, order_id: str) -> Order:
        """Verify order execution qua API query"""
```

#### 5.2 CostFilter
```python
class CostFilter:
    """Filter trades dựa trên cost analysis"""
    
    def calculate_expected_slippage(
        self,
        orderbook: Orderbook,
        side: OrderSide,
        qty: Decimal
    ) -> Decimal:
        """Tính expected slippage từ orderbook
        
        Algorithm:
            1. Simulate market order execution
            2. Walk through orderbook levels
            3. Calculate weighted average fill price
            4. slippage = abs(avg_fill_price - best_price) / best_price
        
        Returns:
            Slippage as percentage
        """
    
    def calculate_total_cost(
        self,
        position_value: Decimal,
        slippage: Decimal,
        commission_rate: Decimal = Decimal("0.0006")  # Bybit taker fee
    ) -> Decimal:
        """Tính total trading cost
        
        total_cost = commission + slippage + spread
        
        Returns:
            Total cost as percentage of position value
        """
    
    def should_reject_trade(
        self,
        slippage: Decimal,
        total_cost: Decimal
    ) -> bool:
        """Quyết định có reject trade không
        
        Reject if:
            - slippage > 0.1%
            - total_cost > 0.2%
        """
```

**Interfaces**:
- Input: Events (SignalGenerated), Orderbook data
- Output: Events (OrderPlaced, OrderFilled, PositionOpened)
- Dependencies: Bybit Connector

---

### 6. Backtesting Engine (src/backtest/)

**Trách nhiệm**: Kiểm thử chiến lược trên historical data.

**Subcomponents**:

#### 6.1 EventEngine
```python
class EventEngine:
    """Event-driven backtesting engine"""
    
    def __init__(self):
        self.event_queue = asyncio.Queue()
        self.handlers = {}  # event_type -> List[handler]
    
    def register_handler(self, event_type: Type, handler: Callable) -> None:
        """Đăng ký handler cho event type"""
    
    async def emit(self, event: Event) -> None:
        """Emit event vào queue"""
    
    async def process_events(self) -> None:
        """Process events từ queue"""
```

#### 6.2 HistoricalDataReplayer
```python
class HistoricalDataReplayer:
    """Replay historical data chronologically"""
    
    def __init__(self, db_connection, start_date: datetime, end_date: datetime):
        self.db = db_connection
        self.start_date = start_date
        self.end_date = end_date
        self.current_timestamp = start_date
    
    async def replay(self, event_engine: EventEngine) -> None:
        """Replay data theo chronological order
        
        Algorithm:
            1. Query data từ TimescaleDB trong date range
            2. Sort by timestamp (prevent look-ahead bias)
            3. For each data point:
                - Emit corresponding event (KlineReceived, TradeReceived)
                - Wait for event processing
                - Advance current_timestamp
        
        Performance: Process >= 1000 candles/second
        """
```

#### 6.3 SimulatedExchange
```python
class SimulatedExchange:
    """Simulate order execution trong backtest"""
    
    def __init__(self, initial_balance: Decimal):
        self.balance = initial_balance
        self.positions = {}
        self.orderbook_history = {}  # timestamp -> orderbook
    
    async def place_order(
        self,
        order: Order,
        current_timestamp: datetime
    ) -> Order:
        """Simulate order execution
        
        Algorithm:
            1. Get orderbook at current_timestamp
            2. Calculate realistic slippage:
                - Analyze orderbook depth within 0.5% of price
                - Simulate market impact
            3. Apply commission (Bybit fee structure)
            4. Update balance and positions
        
        Returns:
            Filled order with actual fill price
        """
    
    def calculate_realistic_slippage(
        self,
        orderbook: Orderbook,
        order: Order
    ) -> Decimal:
        """Tính slippage dựa trên orderbook liquidity
        
        Walk through orderbook levels to simulate fill
        """
```

#### 6.4 BacktestRunner
```python
class BacktestRunner:
    """Orchestrate backtest execution"""
    
    async def run(
        self,
        strategy_config: dict,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """Chạy backtest
        
        Steps:
            1. Initialize EventEngine
            2. Initialize all components (Alpha, Risk, Execution)
            3. Register event handlers
            4. Start HistoricalDataReplayer
            5. Collect results
            6. Generate performance metrics
        
        Returns:
            BacktestResult với trades, equity curve, metrics
        """
```

**Interfaces**:
- Input: Historical data từ TimescaleDB, Strategy config
- Output: BacktestResult, Performance metrics
- Dependencies: TimescaleDB, Alpha Model, Risk Model

---

### 7. Monitoring (src/monitoring/)

**Trách nhiệm**: Dashboard và Telegram alerts.

#### 7.1 Dashboard
```python
class Dashboard:
    """Real-time monitoring dashboard"""
    
    def get_system_status(self) -> SystemStatus:
        """Trả về system health status
        
        Metrics:
            - API connection status
            - Database connection status
            - Error rate (last 1 hour)
            - Latency (p50, p95, p99)
        """
    
    def get_trading_metrics(self) -> TradingMetrics:
        """Trả về trading metrics
        
        Metrics:
            - Current balance
            - Open positions
            - Daily P&L
            - Win rate
            - Profit factor
            - Sharpe ratio
        """
    
    def get_recent_signals(self, limit: int = 10) -> List[Signal]:
        """Trả về recent signals với confidence scores"""
```

#### 7.2 TelegramBot
```python
class TelegramBot:
    """Telegram bot cho alerts và commands"""
    
    def __init__(self, bot_token: str, allowed_chat_ids: List[int]):
        self.bot_token = bot_token
        self.allowed_chat_ids = allowed_chat_ids
        self.alert_rate_limiter = RateLimiter(max_alerts=10, window=3600)
    
    async def send_alert(self, message: str) -> None:
        """Gửi alert message
        
        Rate limit: Max 10 alerts/hour
        Message format: [TIMESTAMP] [SYMBOL] message
        """
    
    async def handle_command(self, command: str, chat_id: int) -> str:
        """Xử lý user commands
        
        Commands:
            /status - System status và connection health
            /positions - Open positions và unrealized P&L
            /pnl - Daily, weekly, total P&L
        
        Authentication: Check chat_id in allowed_chat_ids
        """
```

**Interfaces**:
- Input: System events, Trading events
- Output: Dashboard UI, Telegram messages
- Dependencies: Telegram Bot API


## Data Models

### Core Domain Models

#### Market Data Models

```python
@dataclass
class Kline:
    """Candlestick data"""
    symbol: str
    timeframe: str  # "1m", "5m", "15m", "1h"
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    
    def __post_init__(self):
        assert self.high >= self.low
        assert self.high >= self.open
        assert self.high >= self.close
        assert self.volume >= 0

@dataclass
class Trade:
    """Individual trade"""
    symbol: str
    timestamp: datetime
    price: Decimal
    quantity: Decimal
    side: OrderSide  # BUY or SELL
    trade_id: str
    
    def is_buyer_initiated(self) -> bool:
        return self.side == OrderSide.BUY

@dataclass
class OrderbookLevel:
    """Single orderbook level"""
    price: Decimal
    quantity: Decimal

@dataclass
class Orderbook:
    """Orderbook snapshot"""
    symbol: str
    timestamp: datetime
    bids: List[OrderbookLevel]  # Sorted descending by price
    asks: List[OrderbookLevel]  # Sorted ascending by price
    
    def get_best_bid(self) -> Decimal:
        return self.bids[0].price if self.bids else Decimal("0")
    
    def get_best_ask(self) -> Decimal:
        return self.asks[0].price if self.asks else Decimal("0")
    
    def get_spread(self) -> Decimal:
        return self.get_best_ask() - self.get_best_bid()
```

#### Analysis Models

```python
@dataclass
class IndicatorSet:
    """Collection of technical indicators"""
    timestamp: datetime
    sma_9: Decimal
    sma_21: Decimal
    sma_50: Decimal
    sma_200: Decimal
    ema_9: Decimal
    ema_21: Decimal
    ema_50: Decimal
    ema_200: Decimal
    rsi_14: Decimal
    macd: Decimal
    macd_signal: Decimal
    macd_histogram: Decimal
    bb_upper: Decimal
    bb_middle: Decimal
    bb_lower: Decimal
    volume_profile: Dict[Decimal, Decimal]  # price -> volume

@dataclass
class OrderFlowAnalysis:
    """Order flow analysis results"""
    timestamp: datetime
    cumulative_delta: Decimal
    footprint: Dict[Decimal, Decimal]  # price level -> delta
    imbalance_zones: List[Decimal]  # price levels with >70% imbalance
    has_delta_divergence: bool

class WyckoffPhase(Enum):
    """Wyckoff market phases"""
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"

@dataclass
class Signal:
    """Trading signal"""
    timestamp: datetime
    symbol: str
    direction: SignalDirection  # BUY, SELL, NEUTRAL
    confidence: int  # 0-100
    reasons: List[str]  # Contributing factors
    indicators: IndicatorSet
    order_flow: OrderFlowAnalysis
    wyckoff_phase: WyckoffPhase
    
    def is_actionable(self) -> bool:
        return self.confidence >= 60 and self.direction != SignalDirection.NEUTRAL
```

#### Trading Models

```python
class OrderSide(Enum):
    BUY = "Buy"
    SELL = "Sell"

class OrderType(Enum):
    LIMIT = "Limit"
    MARKET = "Market"

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

@dataclass
class Order:
    """Trading order"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal]  # None for market orders
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime]
    filled_price: Optional[Decimal]
    filled_quantity: Decimal
    
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

@dataclass
class Position:
    """Open position"""
    position_id: str
    symbol: str
    side: OrderSide
    entry_price: Decimal
    quantity: Decimal
    leverage: int
    opened_at: datetime
    stop_loss_price: Decimal
    stop_loss_order_id: Optional[str]
    
    def get_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Tính unrealized P&L"""
        if self.side == OrderSide.BUY:
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity
    
    def get_position_value(self) -> Decimal:
        return self.entry_price * self.quantity

@dataclass
class Trade:
    """Completed trade"""
    trade_id: str
    symbol: str
    side: OrderSide
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    opened_at: datetime
    closed_at: datetime
    pnl: Decimal
    pnl_percentage: Decimal
    commission: Decimal
    slippage: Decimal
    exit_reason: str  # "stop_loss", "take_profit", "signal", "kill_switch"
```

#### Risk Models

```python
@dataclass
class RiskMetrics:
    """Risk management metrics"""
    account_balance: Decimal
    peak_balance: Decimal
    current_drawdown: Decimal
    max_drawdown: Decimal
    daily_drawdown: Decimal
    consecutive_losses: int
    position_size_multiplier: Decimal  # Adjusted based on drawdown
    
    def is_drawdown_critical(self) -> bool:
        return self.daily_drawdown > Decimal("0.05")  # 5%

@dataclass
class KillSwitchState:
    """Kill switch state"""
    is_active: bool
    activation_time: Optional[datetime]
    activation_reason: Optional[str]
    system_state_snapshot: Optional[dict]
```

#### Performance Models

```python
@dataclass
class PerformanceMetrics:
    """Trading performance metrics"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_pnl: Decimal
    total_return: Decimal
    annualized_return: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    average_drawdown: Decimal
    profit_factor: Decimal  # gross_profit / gross_loss
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    
    @classmethod
    def calculate(cls, trades: List[Trade], initial_balance: Decimal) -> 'PerformanceMetrics':
        """Tính toán metrics từ trade history"""
        # Implementation details...
```

#### Configuration Models

```python
@dataclass
class AlphaConfig:
    """Alpha model configuration"""
    indicator_periods: Dict[str, List[int]]
    rsi_period: int
    macd_params: Tuple[int, int, int]
    bb_params: Tuple[int, int]
    volume_profile_window: int
    order_flow_window: int
    min_confidence_threshold: int

@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_risk_per_trade: Decimal
    max_position_size: Decimal
    initial_stop_loss_pct: Decimal
    breakeven_trigger_pct: Decimal
    trailing_stop_trigger_pct: Decimal
    trailing_stop_distance_pct: Decimal
    kill_switch_daily_dd: Decimal
    kill_switch_consecutive_losses: int

@dataclass
class ExecutionConfig:
    """Execution configuration"""
    limit_order_timeout: int
    max_slippage_pct: Decimal
    max_total_cost_pct: Decimal
    max_retries: int

@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal
    commission_rate: Decimal
    slippage_model: str  # "fixed", "orderbook"

@dataclass
class Configuration:
    """Complete system configuration"""
    mode: str  # "testnet", "live", "paper", "backtest"
    symbol: str
    timeframes: List[str]
    alpha: AlphaConfig
    risk: RiskConfig
    execution: ExecutionConfig
    backtest: Optional[BacktestConfig]
    bybit_api_key: str
    bybit_api_secret: str
    telegram_bot_token: str
    telegram_chat_ids: List[int]
    database_url: str
```

### Database Schema (TimescaleDB)

```sql
-- Klines hypertable
CREATE TABLE klines (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    PRIMARY KEY (timestamp, symbol, timeframe)
);

SELECT create_hypertable('klines', 'timestamp');
CREATE INDEX idx_klines_symbol_timeframe ON klines (symbol, timeframe, timestamp DESC);

-- Trades hypertable
CREATE TABLE trades (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    side TEXT NOT NULL,
    PRIMARY KEY (timestamp, symbol, trade_id)
);

SELECT create_hypertable('trades', 'timestamp');
CREATE INDEX idx_trades_symbol ON trades (symbol, timestamp DESC);

-- Orderbooks hypertable
CREATE TABLE orderbooks (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    PRIMARY KEY (timestamp, symbol)
);

SELECT create_hypertable('orderbooks', 'timestamp');

-- Signals table
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    reasons JSONB NOT NULL,
    indicators JSONB NOT NULL,
    order_flow JSONB NOT NULL,
    wyckoff_phase TEXT NOT NULL
);

CREATE INDEX idx_signals_timestamp ON signals (timestamp DESC);

-- Trades table (completed trades)
CREATE TABLE completed_trades (
    id SERIAL PRIMARY KEY,
    trade_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL,
    pnl NUMERIC NOT NULL,
    pnl_percentage NUMERIC NOT NULL,
    commission NUMERIC NOT NULL,
    slippage NUMERIC NOT NULL,
    exit_reason TEXT NOT NULL
);

CREATE INDEX idx_completed_trades_closed_at ON completed_trades (closed_at DESC);
```

### Event Models

```python
@dataclass
class Event:
    """Base event class"""
    timestamp: datetime
    event_type: str

@dataclass
class KlineReceived(Event):
    """Kline data received from WebSocket"""
    symbol: str
    timeframe: str
    kline: Kline

@dataclass
class TradeReceived(Event):
    """Trade data received from WebSocket"""
    symbol: str
    trade: Trade

@dataclass
class OrderbookReceived(Event):
    """Orderbook snapshot received"""
    symbol: str
    orderbook: Orderbook

@dataclass
class SignalGenerated(Event):
    """Trading signal generated"""
    signal: Signal

@dataclass
class OrderPlaced(Event):
    """Order placed on exchange"""
    order: Order

@dataclass
class OrderFilled(Event):
    """Order filled"""
    order: Order

@dataclass
class PositionOpened(Event):
    """Position opened"""
    position: Position

@dataclass
class PositionClosed(Event):
    """Position closed"""
    position: Position
    exit_price: Decimal
    pnl: Decimal
    exit_reason: str

@dataclass
class StopLossTriggered(Event):
    """Stop-loss triggered"""
    position: Position
    stop_price: Decimal

@dataclass
class KillSwitchActivated(Event):
    """Kill switch activated"""
    reason: str
    system_state: dict

@dataclass
class DataGapDetected(Event):
    """Gap detected in time-series data"""
    symbol: str
    timeframe: str
    gap_start: datetime
    gap_end: datetime

@dataclass
class DataGapFilled(Event):
    """Gap filled with historical data"""
    symbol: str
    timeframe: str
    records_filled: int
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: WebSocket Auto-Reconnection

*For any* WebSocket disconnection event, the Bybit_Connector should successfully reconnect within 5 seconds.

**Validates: Requirements 1.3**

### Property 2: API Request Retry with Exponential Backoff

*For any* failed API request, the system should retry up to the configured maximum (3 times for Bybit_Connector, 2 times for Order_Manager) with exponential backoff between attempts.

**Validates: Requirements 1.4, 10.5**

### Property 3: API Rate Limiting

*For any* sequence of API requests within a 5-second window, the total number of requests sent to Bybit should not exceed 600.

**Validates: Requirements 1.8, 1.9**

### Property 4: Time Drift Warning

*For any* system time measurement, if the drift from NTP server exceeds 1 second, a time synchronization warning should be emitted.

**Validates: Requirements 1.11**

### Property 5: Data Storage Latency

*For any* market data received via WebSocket, the time from reception to storage in TimescaleDB should be less than 100 milliseconds.

**Validates: Requirements 2.1**

### Property 6: Data Completeness

*For any* collected trade data, all required fields (price, quantity, side, timestamp) must be present and non-null.

**Validates: Requirements 2.3**

### Property 7: Orderbook Depth Requirement

*For any* collected orderbook snapshot, there should be at least 20 price levels on both the bid and ask sides.

**Validates: Requirements 2.4**

### Property 8: Data Deduplication

*For any* set of incoming market data records with identical (timestamp, symbol, timeframe) tuples, only one record should be stored in the database.

**Validates: Requirements 2.5**

### Property 9: Data Buffering on Connection Failure

*For any* TimescaleDB connection failure, the Data_Pipeline should buffer incoming data in memory up to a maximum of 10,000 records without data loss.

**Validates: Requirements 2.6**

### Property 10: Indicator Update Performance

*For any* new kline data arrival, all technical indicators should be updated within 50 milliseconds.

**Validates: Requirements 3.6**

### Property 11: Cumulative Delta Calculation

*For any* sequence of trades, the cumulative delta should equal the sum of quantities for buyer-initiated trades minus the sum of quantities for seller-initiated trades.

**Validates: Requirements 4.1**

### Property 12: Footprint Aggregation Consistency

*For any* set of trades aggregated by price level, the sum of deltas across all price levels should equal the cumulative delta for the entire set.

**Validates: Requirements 4.2**

### Property 13: Imbalance Zone Detection

*For any* price level in the footprint chart, if the absolute value of delta divided by total volume exceeds 0.7, that price level should be identified as an imbalance zone.

**Validates: Requirements 4.3**

### Property 14: Rolling Window Size Constraint

*For any* state of the Order_Flow_Analyzer, the number of trades in the rolling window should never exceed 1000.

**Validates: Requirements 4.5**

### Property 15: Trade Classification Completeness

*For any* trade received, it should be classified as either buyer-initiated or seller-initiated based on the aggressor side field.

**Validates: Requirements 4.6**

### Property 16: Phase Transition Event Emission

*For any* change in Wyckoff phase detected by the Wyckoff_Detector, a phase transition event should be emitted.

**Validates: Requirements 5.7**

### Property 17: Volume Confirmation for Breakouts

*For any* potential breakout signal, if the volume does not exceed 1.5x the average volume, the signal should be filtered out.

**Validates: Requirements 6.4**

### Property 18: Multi-Timeframe Alignment Requirement

*For any* generated trading signal, all configured timeframes (1m, 5m, 15m) must show alignment before the signal is considered valid.

**Validates: Requirements 6.5**

### Property 19: Confidence Score Range

*For any* generated signal, the confidence score should be within the range [0, 100].

**Validates: Requirements 6.6**

### Property 20: Low Confidence Signal Suppression

*For any* signal with confidence score below 60, the signal should be suppressed and not forwarded for execution.

**Validates: Requirements 6.7**

### Property 21: Maximum Risk Per Trade

*For any* calculated position size, the maximum potential loss (position_size × stop_loss_distance) should not exceed 2% of the current account balance.

**Validates: Requirements 7.1**

### Property 22: Position Size Inverse Proportionality

*For any* two position size calculations with the same risk amount but different stop-loss distances, the position size should be inversely proportional to the stop-loss distance.

**Validates: Requirements 7.2**

### Property 23: Maximum Position Size Limit

*For any* calculated position size, the position value should not exceed 10% of the current account balance.

**Validates: Requirements 7.3**

### Property 24: Confidence-Based Position Adjustment

*For any* signal with confidence score C, the adjusted position size should be base_position_size × (C / 100).

**Validates: Requirements 7.4**

### Property 25: Drawdown-Based Position Reduction

*For any* account state where current balance is less than 90% of peak balance, all calculated position sizes should be reduced by 50%.

**Validates: Requirements 7.5**

### Property 26: Leverage Adjustment in Position Sizing

*For any* position size calculation with leverage L > 1, the effective position size should account for leverage such that actual_capital_required = position_value / L.

**Validates: Requirements 7.6**

### Property 27: Minimum Order Quantity Compliance

*For any* calculated position size, after rounding to meet exchange requirements, the final quantity should be greater than or equal to Bybit's minimum order quantity for the symbol.

**Validates: Requirements 7.7**

### Property 28: Initial Stop-Loss Placement

*For any* opened position, an initial stop-loss order should be placed at a price that is 2% away from the entry price (2% below for long, 2% above for short).

**Validates: Requirements 8.1**

### Property 29: Breakeven Stop-Loss Adjustment

*For any* open position where the current price has moved favorably by at least 1%, the stop-loss should be moved to the entry price (breakeven).

**Validates: Requirements 8.2**

### Property 30: Trailing Stop Activation

*For any* open position where the current price has moved favorably by at least 2%, a trailing stop should be activated with a 1% distance from the current price.

**Validates: Requirements 8.3**

### Property 31: Emergency Position Closure on Stop-Loss Failure

*For any* stop-loss order that is cancelled or rejected by the exchange, the associated position should be immediately closed at market price.

**Validates: Requirements 8.5**

### Property 32: Stop-Loss Trigger Logging

*For any* triggered stop-loss, the system should log both the exit reason and the loss amount.

**Validates: Requirements 8.7**

### Property 33: Kill Switch Activation on Daily Drawdown

*For any* system state where daily drawdown exceeds 5%, the Kill_Switch should activate, close all open positions, and stop accepting new trading signals.

**Validates: Requirements 9.1**

### Property 34: Kill Switch Activation on Consecutive Losses

*For any* sequence of trades where 5 consecutive losses occur, the Kill_Switch should activate and close all open positions.

**Validates: Requirements 9.2**

### Property 35: Kill Switch Activation on API Error Rate

*For any* 1-minute window where Bybit API error rate exceeds 20%, the Kill_Switch should activate and stop trading.

**Validates: Requirements 9.3**

### Property 36: Kill Switch Activation on Abnormal Price Movement

*For any* 1-minute window where price movement exceeds 10%, the Kill_Switch should activate and close all positions.

**Validates: Requirements 9.4**

### Property 37: Kill Switch Alert Notification

*For any* Kill_Switch activation, a Telegram alert should be sent with the activation reason.

**Validates: Requirements 9.5**

### Property 38: Kill Switch Activation Logging

*For any* Kill_Switch activation, the system should log the activation reason and a snapshot of the system state at the time of activation.

**Validates: Requirements 9.7**

### Property 39: Signal-Based Order Placement

*For any* actionable BUY signal, a limit order should be placed at the best bid price; for any actionable SELL signal, a limit order should be placed at the best ask price.

**Validates: Requirements 10.1, 10.2**

### Property 40: Limit Order Timeout Fallback

*For any* limit order that is not filled within 5 seconds, the order should be cancelled and replaced with a market order.

**Validates: Requirements 10.3**

### Property 41: Order Execution Verification

*For any* placed order, the Order_Manager should verify execution status by querying the Bybit API.

**Validates: Requirements 10.4**

### Property 42: Order Status Validity

*For any* tracked order, the status should always be one of the valid states: pending, filled, cancelled, or rejected.

**Validates: Requirements 10.6**

### Property 43: Position Opened Event on Fill

*For any* order that transitions to filled status, a PositionOpened event should be emitted containing the entry price and quantity.

**Validates: Requirements 10.7**

### Property 44: Slippage Calculation Before Order

*For any* order to be placed, expected slippage should be calculated based on current orderbook depth before order placement.

**Validates: Requirements 11.1**

### Property 45: Slippage-Based Trade Rejection

*For any* order where expected slippage exceeds 0.1%, the trade should be rejected and no order should be placed.

**Validates: Requirements 11.2**

### Property 46: Total Trading Cost Calculation

*For any* trade, the total trading cost should include commission, slippage, and spread components.

**Validates: Requirements 11.3**

### Property 47: Cost-Based Trade Rejection

*For any* trade where total cost exceeds 0.2% of position value, the trade should be rejected.

**Validates: Requirements 11.4**

### Property 48: Actual Slippage Tracking

*For any* executed order, the actual slippage (difference between expected and actual fill price) should be calculated and recorded.

**Validates: Requirements 11.6**

### Property 49: Trade Cost Logging

*For any* executed trade, a complete cost breakdown (commission, slippage, spread) should be logged.

**Validates: Requirements 11.7**

### Property 50: Chronological Data Replay

*For any* historical dataset being replayed, the timestamps of emitted events should be monotonically increasing (non-decreasing).

**Validates: Requirements 12.1**

### Property 51: Look-Ahead Bias Prevention

*For any* timestamp T during backtesting, only data with timestamp ≤ T should be accessible to the Alpha_Model and other decision-making components.

**Validates: Requirements 12.2**

### Property 52: Realistic Slippage Simulation

*For any* simulated order execution in backtesting, slippage should be calculated based on the orderbook depth available at the execution timestamp.

**Validates: Requirements 12.3, 12.4**

### Property 53: Commission Application in Backtest

*For any* simulated trade in backtesting, commission fees matching Bybit's fee structure should be applied to the trade P&L.

**Validates: Requirements 12.5**

### Property 54: Backtesting Consistency with Live Trading

*For any* identical market data sequence and configuration, the Alpha_Model and Risk_Model should produce the same signals and risk decisions in both backtesting and live trading modes.

**Validates: Requirements 12.6, 12.7**

### Property 55: Backtesting Performance Requirement

*For any* backtesting run, the engine should process at least 1000 candles per second.

**Validates: Requirements 12.9**

### Property 56: Configuration Round-Trip Property

*For any* valid Configuration object, serializing it to YAML and then parsing it back should produce an equivalent Configuration object.

**Validates: Requirements 19.4**

### Property 57: Paper Trading Slippage and Commission

*For any* simulated trade in Paper Trading mode, realistic slippage and commission should be applied to match live trading conditions.

**Validates: Requirements 14.4**

### Property 58: Paper Trading Logging

*For any* trade executed in Paper Trading mode, the trade should be logged with complete details for later analysis.

**Validates: Requirements 14.7**

### Property 59: Telegram Command Response

*For any* valid Telegram command (/status, /positions, /pnl) from an authenticated user, the bot should respond with the requested information.

**Validates: Requirements 16.9, 16.10, 16.11**

### Property 60: Telegram Authentication

*For any* Telegram command received, if the chat_id is not in the allowed list, the command should be rejected and no response should be sent.

**Validates: Requirements 16.12**

### Property 61: Alert Rate Limiting

*For any* 1-hour window, the total number of Telegram alerts sent should not exceed 10.

**Validates: Requirements 16.14**

### Property 62: Alert Message Completeness

*For any* Telegram alert sent, the message should include both a timestamp and the relevant symbol.

**Validates: Requirements 16.15**

### Property 63: Configuration Validation

*For any* configuration value loaded from file, the value should be validated against its allowed range, and invalid values should cause the system to refuse to start.

**Validates: Requirements 17.5**

### Property 64: Data Validation for Completeness and Correctness

*For any* incoming market data, all required fields must be present (completeness) and values must satisfy constraints (price > 0, volume ≥ 0).

**Validates: Requirements 18.1, 18.2**

### Property 65: Invalid Data Handling

*For any* invalid data received, the data should be discarded and an error should be logged.

**Validates: Requirements 18.3**

### Property 66: Time-Series Gap Detection

*For any* two consecutive data points in a time-series, if the time difference exceeds the expected interval for the timeframe, a gap should be detected.

**Validates: Requirements 18.4**

### Property 67: Gap Filling with Historical Data

*For any* detected data gap, the Data_Pipeline should fetch missing historical data from Bybit REST API to fill the gap.

**Validates: Requirements 18.5**

### Property 68: Indicator Recalculation After Gap Fill

*For any* filled data gap, all indicators that depend on the affected time range should be recalculated using the complete data.

**Validates: Requirements 18.6**

### Property 69: Large Gap Alert

*For any* detected data gap exceeding 1 minute, a data quality alert should be emitted.

**Validates: Requirements 18.7**

### Property 70: Data Quality Metrics Maintenance

*For any* system operation, data quality metrics (completeness rate, error rate) should be continuously calculated and maintained.

**Validates: Requirements 18.8**

### Property 71: Raw Data Preservation

*For any* processed data stored in the database, the corresponding raw data should also be stored for audit purposes.

**Validates: Requirements 18.9**

### Property 72: Complete Trade Logging

*For any* executed trade, the log entry should contain all required fields: timestamp, symbol, side, price, quantity, and reason.

**Validates: Requirements 20.1**

### Property 73: Complete Signal Logging

*For any* generated signal, the log entry should contain timestamp, symbol, direction, confidence, and contributing factors.

**Validates: Requirements 20.2**

### Property 74: Risk Event Logging

*For any* risk event (stop-loss triggered, kill switch activated, position size reduced), the event should be logged with complete details.

**Validates: Requirements 20.3**

### Property 75: Error Logging with Context

*For any* system error, the log entry should include the stack trace and relevant context information.

**Validates: Requirements 20.4**


## Error Handling

### Error Classification

Hệ thống phân loại errors thành 4 categories:

1. **Recoverable Errors**: Có thể retry và recover
   - Network timeouts
   - Temporary API errors (rate limit, server busy)
   - Database connection failures

2. **Fatal Errors**: Yêu cầu system shutdown
   - Invalid configuration
   - Authentication failures
   - Critical data corruption

3. **Trading Errors**: Ảnh hưởng đến trading decisions
   - Order placement failures
   - Position query failures
   - Invalid signal generation

4. **Data Quality Errors**: Ảnh hưởng đến data integrity
   - Invalid market data
   - Data gaps
   - Validation failures

### Error Handling Strategies

#### 1. Network and API Errors

```python
async def handle_api_error(error: APIError, context: dict) -> None:
    """
    Strategy:
        - Log error with full context
        - Increment error counter
        - Check if error rate triggers Kill Switch
        - Retry with exponential backoff if recoverable
        - Emit alert if error persists
    """
```

**Retry Logic**:
- Max retries: 3 for Bybit Connector, 2 for Order Manager
- Backoff: exponential (1s, 2s, 4s)
- Jitter: ±20% to prevent thundering herd

**Rate Limit Handling**:
- Queue requests when approaching limit
- Implement token bucket algorithm
- Priority queue: critical operations (close position) > normal operations

#### 2. WebSocket Disconnection

```python
async def handle_websocket_disconnect(reason: str) -> None:
    """
    Strategy:
        - Log disconnection reason
        - Attempt reconnection within 5 seconds
        - Use exponential backoff for repeated failures
        - Switch to REST API polling as fallback
        - Emit alert if reconnection fails after 3 attempts
    """
```

**Fallback Mechanism**:
- Primary: WebSocket streaming
- Fallback: REST API polling (1-second interval)
- Restore to WebSocket when connection recovered

#### 3. Database Errors

```python
async def handle_database_error(error: DatabaseError) -> None:
    """
    Strategy:
        - Buffer incoming data in memory (max 10,000 records)
        - Attempt reconnection every 5 seconds
        - Flush buffer when connection restored
        - Emit critical alert if buffer reaches 80% capacity
        - Activate Kill Switch if buffer overflows
    """
```

**Data Loss Prevention**:
- In-memory circular buffer
- Persistent queue fallback (disk-based)
- Checkpoint mechanism for recovery

#### 4. Order Execution Errors

```python
async def handle_order_error(order: Order, error: OrderError) -> None:
    """
    Strategy:
        - Log error with order details
        - Classify error type (insufficient balance, invalid price, etc.)
        - Retry if recoverable (max 2 retries)
        - Cancel order if unrecoverable
        - Notify via Telegram
        - Update order status to REJECTED
    """
```

**Error Types**:
- **Insufficient Balance**: Reduce position size and retry
- **Invalid Price**: Recalculate price from current orderbook and retry
- **Order Not Found**: Query order status via API
- **Rate Limit**: Queue and retry after cooldown
- **Unrecoverable**: Mark as failed, log, and alert

#### 5. Data Quality Errors

```python
async def handle_data_quality_error(data: dict, validation_errors: List[str]) -> None:
    """
    Strategy:
        - Log validation errors with data sample
        - Discard invalid data
        - Increment data quality error counter
        - Emit alert if error rate > 5% over 1 minute
        - Trigger data gap detection and filling
    """
```

**Validation Checks**:
- Required fields present
- Price > 0, Volume >= 0
- Timestamp is valid Unix timestamp
- OHLC constraints: high >= low, high >= open, high >= close

#### 6. Kill Switch Activation

```python
async def handle_kill_switch_activation(reason: str, system_state: dict) -> None:
    """
    Strategy:
        - Immediately close all open positions at market price
        - Cancel all pending orders
        - Stop accepting new signals
        - Log activation reason and system state snapshot
        - Send critical Telegram alert
        - Persist state to database
        - Require manual reset to resume trading
    """
```

**Recovery Process**:
1. User investigates activation reason
2. User fixes underlying issue
3. User manually resets Kill Switch via command
4. System performs health check before resuming
5. System resumes trading if all checks pass

### Error Recovery Patterns

#### Circuit Breaker Pattern

```python
class CircuitBreaker:
    """Prevent cascading failures"""
    
    states = ["CLOSED", "OPEN", "HALF_OPEN"]
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None
    
    async def call(self, func: Callable) -> Any:
        """
        CLOSED: Normal operation, count failures
        OPEN: Reject calls immediately, wait for timeout
        HALF_OPEN: Allow one test call, transition based on result
        """
```

**Usage**: Wrap external API calls (Bybit, Database) với Circuit Breaker để prevent cascading failures.

#### Graceful Degradation

**Degradation Levels**:
1. **Full Operation**: All features enabled
2. **Limited Operation**: Disable non-critical features (dashboard updates, non-critical alerts)
3. **Safe Mode**: Only monitor positions, no new trades
4. **Emergency Mode**: Close all positions, shutdown

**Triggers**:
- API error rate > 10%: Limited Operation
- API error rate > 20%: Safe Mode
- Kill Switch activation: Emergency Mode


## Performance Optimization

### Latency Targets

- **End-to-End Pipeline**: < 100ms (data reception → decision)
- **Indicator Calculation**: < 50ms
- **Database Write**: < 10ms
- **Order Placement**: < 50ms
- **Total Trading Decision**: < 100ms

### Optimization Strategies

#### 1. Data Processing

**Vectorized Operations**:
```python
# BAD: Loop-based calculation
for i in range(len(prices)):
    sma[i] = sum(prices[i-period:i]) / period

# GOOD: Vectorized with pandas/numpy
sma = prices.rolling(window=period).mean()
```

**Benefits**:
- 10-100x faster than loops
- Leverages CPU SIMD instructions
- Reduces Python interpreter overhead

**Incremental Updates**:
```python
class IncrementalEMA:
    """Update EMA incrementally instead of recalculating entire series"""
    
    def __init__(self, period: int):
        self.period = period
        self.alpha = 2 / (period + 1)
        self.current_ema = None
    
    def update(self, new_price: Decimal) -> Decimal:
        if self.current_ema is None:
            self.current_ema = new_price
        else:
            self.current_ema = self.alpha * new_price + (1 - self.alpha) * self.current_ema
        return self.current_ema
```

**Benefits**:
- O(1) instead of O(n) per update
- Reduces latency from 50ms to < 5ms

#### 2. Database Optimization

**Batch Writes**:
```python
async def batch_write_klines(klines: List[Kline]) -> None:
    """Write multiple klines in single transaction"""
    async with db.transaction():
        await db.executemany(
            "INSERT INTO klines VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            [(k.timestamp, k.symbol, k.timeframe, k.open, k.high, k.low, k.close, k.volume) 
             for k in klines]
        )
```

**Benefits**:
- Reduce network round-trips
- Amortize transaction overhead
- 10x throughput improvement

**Connection Pooling**:
```python
db_pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=5,
    max_size=20,
    command_timeout=60
)
```

**Benefits**:
- Reuse connections
- Reduce connection establishment overhead
- Handle concurrent queries efficiently

**Hypertable Optimization**:
```sql
-- Compression for older data
ALTER TABLE klines SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,timeframe',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy('klines', INTERVAL '7 days');

-- Retention policy
SELECT add_retention_policy('klines', INTERVAL '90 days');
```

**Benefits**:
- 90% storage reduction
- Faster queries on recent data
- Automatic data lifecycle management

#### 3. Caching

**Indicator Cache**:
```python
class IndicatorCache:
    """Cache calculated indicators to avoid recalculation"""
    
    def __init__(self, ttl: int = 60):
        self.cache = {}  # (symbol, timeframe, indicator) -> (value, timestamp)
        self.ttl = ttl
    
    def get(self, symbol: str, timeframe: str, indicator: str) -> Optional[Decimal]:
        key = (symbol, timeframe, indicator)
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
        return None
    
    def set(self, symbol: str, timeframe: str, indicator: str, value: Decimal) -> None:
        key = (symbol, timeframe, indicator)
        self.cache[key] = (value, time.time())
```

**Benefits**:
- Avoid redundant calculations
- Reduce CPU usage
- Improve response time for dashboard queries

**Orderbook Cache**:
- Cache latest orderbook snapshot
- Update on every OrderbookReceived event
- TTL: 1 second (orderbook changes frequently)

#### 4. Async I/O

**Concurrent API Calls**:
```python
async def fetch_multiple_symbols(symbols: List[str]) -> Dict[str, Position]:
    """Fetch positions for multiple symbols concurrently"""
    tasks = [rest_client.get_position(symbol) for symbol in symbols]
    positions = await asyncio.gather(*tasks)
    return dict(zip(symbols, positions))
```

**Benefits**:
- Reduce total latency from sum(latencies) to max(latencies)
- Better resource utilization
- Faster dashboard updates

**Non-Blocking Database Queries**:
```python
# Use asyncpg instead of psycopg2
async def query_klines(symbol: str, timeframe: str, limit: int) -> List[Kline]:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM klines WHERE symbol = $1 AND timeframe = $2 ORDER BY timestamp DESC LIMIT $3",
            symbol, timeframe, limit
        )
    return [Kline(**row) for row in rows]
```

**Benefits**:
- Don't block event loop during I/O
- Handle multiple concurrent requests
- Maintain low latency

#### 5. JSON Parsing

**Use ujson instead of standard json**:
```python
import ujson

# 2-3x faster than standard json
data = ujson.loads(message)
```

**Benefits**:
- Faster WebSocket message parsing
- Reduced CPU usage
- Lower latency

#### 6. Memory Management

**Circular Buffers for Rolling Windows**:
```python
from collections import deque

class OrderFlowAnalyzer:
    def __init__(self, window_size: int = 1000):
        self.trades_window = deque(maxlen=window_size)  # Auto-evict old items
```

**Benefits**:
- O(1) append and eviction
- Fixed memory footprint
- No manual cleanup needed

**Object Pooling for High-Frequency Objects**:
```python
class EventPool:
    """Reuse event objects to reduce GC pressure"""
    
    def __init__(self, size: int = 1000):
        self.pool = [Event() for _ in range(size)]
        self.available = list(range(size))
    
    def acquire(self) -> Event:
        if self.available:
            idx = self.available.pop()
            return self.pool[idx]
        return Event()  # Fallback to new object
    
    def release(self, event: Event) -> None:
        # Reset event and return to pool
        event.reset()
        self.available.append(self.pool.index(event))
```

**Benefits**:
- Reduce garbage collection overhead
- More predictable latency
- Better performance under high load

#### 7. Profiling and Monitoring

**Performance Metrics**:
```python
class PerformanceMonitor:
    """Track latency metrics"""
    
    def __init__(self):
        self.metrics = {
            "data_to_storage": [],
            "indicator_calculation": [],
            "signal_generation": [],
            "order_placement": []
        }
    
    @contextmanager
    def measure(self, operation: str):
        start = time.perf_counter()
        yield
        elapsed = (time.perf_counter() - start) * 1000  # ms
        self.metrics[operation].append(elapsed)
    
    def get_percentiles(self, operation: str) -> Dict[str, float]:
        values = self.metrics[operation]
        return {
            "p50": np.percentile(values, 50),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99)
        }
```

**Usage**:
```python
async def process_kline(kline: Kline):
    with perf_monitor.measure("indicator_calculation"):
        indicators = indicator_engine.calculate_indicators(kline)
```

**Continuous Optimization**:
- Monitor p95 and p99 latencies
- Identify bottlenecks
- Profile hot paths with cProfile
- Optimize critical sections


## Testing Strategy

### Testing Approach

Hệ thống sử dụng **dual testing approach** kết hợp:
1. **Property-Based Testing (PBT)**: Verify universal properties across all inputs
2. **Example-Based Unit Testing**: Verify specific examples and edge cases

### Property-Based Testing with Hypothesis

**Library**: Hypothesis (Python PBT framework)

**Configuration**:
```python
from hypothesis import given, settings, strategies as st

# Global settings
settings.register_profile("default", max_examples=100, deadline=1000)
settings.load_profile("default")
```

**Test Structure**:
```python
@given(
    symbol=st.text(min_size=1, max_size=10),
    price=st.decimals(min_value=0.01, max_value=100000, places=2),
    quantity=st.decimals(min_value=0.001, max_value=1000, places=3)
)
@settings(max_examples=100)
def test_position_size_max_risk_constraint(symbol, price, quantity):
    """
    Feature: quantitative-trading-bot, Property 21: Maximum Risk Per Trade
    
    For any calculated position size, the maximum potential loss 
    (position_size × stop_loss_distance) should not exceed 2% of the 
    current account balance.
    """
    account_balance = Decimal("10000")
    max_risk = Decimal("0.02")
    stop_loss_distance = price * Decimal("0.02")
    
    sizer = PositionSizer(account_balance, max_risk)
    position_size = sizer.calculate_position_size(
        signal=Signal(...),
        entry_price=price,
        stop_loss_price=price - stop_loss_distance
    )
    
    max_loss = position_size * stop_loss_distance
    assert max_loss <= account_balance * max_risk
```

### Property Test Coverage

**Mỗi Correctness Property trong Design Document phải có một property-based test tương ứng.**

**Tag Format**: 
```python
"""
Feature: quantitative-trading-bot, Property {number}: {property_title}
"""
```

**Example Properties to Test**:

1. **Data Integrity Properties** (Properties 6-9, 64-71):
   - Data completeness
   - Data deduplication
   - Gap detection and filling
   - Validation constraints

2. **Calculation Properties** (Properties 10-15):
   - Cumulative delta calculation
   - Footprint aggregation
   - Indicator calculations
   - Rolling window constraints

3. **Risk Management Properties** (Properties 21-32):
   - Position sizing constraints
   - Stop-loss placement
   - Drawdown-based adjustments
   - Leverage calculations

4. **Execution Properties** (Properties 39-49):
   - Order placement logic
   - Slippage calculations
   - Cost filtering
   - Order status transitions

5. **Backtesting Properties** (Properties 50-55):
   - Chronological replay
   - Look-ahead bias prevention
   - Slippage simulation
   - Consistency with live trading

6. **Configuration Properties** (Property 56):
   - Round-trip serialization

### Example-Based Unit Tests

**Purpose**: Test specific scenarios, edge cases, and integration points.

**Example Tests**:

```python
def test_kill_switch_activates_on_5_percent_drawdown():
    """Test specific threshold for kill switch activation"""
    kill_switch = KillSwitch(telegram_bot=mock_telegram)
    
    await kill_switch.check_conditions(
        daily_drawdown=Decimal("0.051"),  # 5.1% > 5% threshold
        consecutive_losses=0,
        api_error_rate=0.0,
        price_movement=Decimal("0.0")
    )
    
    assert kill_switch.is_active
    assert kill_switch.activation_reason == "Daily drawdown exceeded 5%"

def test_signal_suppression_below_60_confidence():
    """Test that signals with confidence < 60 are suppressed"""
    signal = Signal(
        timestamp=datetime.now(),
        symbol="BTCUSDT",
        direction=SignalDirection.BUY,
        confidence=59,  # Below threshold
        reasons=["test"],
        indicators=mock_indicators,
        order_flow=mock_order_flow,
        wyckoff_phase=WyckoffPhase.MARKUP
    )
    
    assert not signal.is_actionable()

def test_websocket_reconnect_within_5_seconds():
    """Test WebSocket reconnection timing"""
    ws_manager = WebSocketManager()
    
    start_time = time.time()
    await ws_manager.simulate_disconnect()
    await ws_manager.wait_for_reconnect()
    elapsed = time.time() - start_time
    
    assert elapsed < 5.0
    assert ws_manager.is_connected()
```

### Integration Tests

**Purpose**: Test component interactions and end-to-end flows.

**Test Scenarios**:

1. **Full Trading Flow**:
   - WebSocket receives kline data
   - Data Pipeline stores to database
   - Alpha Model generates signal
   - Risk Model calculates position size
   - Execution Model places order
   - Verify order execution

2. **Kill Switch Flow**:
   - Simulate 5 consecutive losses
   - Verify Kill Switch activates
   - Verify all positions closed
   - Verify Telegram alert sent

3. **Data Gap Recovery**:
   - Simulate WebSocket disconnection
   - Create data gap
   - Verify gap detection
   - Verify gap filling from REST API
   - Verify indicator recalculation

### Backtesting Tests

**Purpose**: Validate backtesting engine correctness.

**Test Scenarios**:

1. **Look-Ahead Bias Prevention**:
   ```python
   def test_no_look_ahead_bias():
       """Verify that future data is not accessible during backtest"""
       backtest = BacktestRunner()
       
       # Inject future data access detector
       with pytest.raises(LookAheadBiasError):
           await backtest.run_with_future_data_access()
   ```

2. **Slippage Simulation Accuracy**:
   ```python
   def test_realistic_slippage_simulation():
       """Verify slippage calculation matches orderbook depth"""
       orderbook = create_test_orderbook()
       order = Order(side=OrderSide.BUY, quantity=Decimal("1.0"))
       
       simulated_slippage = simulated_exchange.calculate_realistic_slippage(orderbook, order)
       expected_slippage = calculate_expected_slippage_from_orderbook(orderbook, order)
       
       assert abs(simulated_slippage - expected_slippage) < Decimal("0.0001")
   ```

3. **Consistency with Live Trading**:
   ```python
   @given(market_data=st.lists(st.builds(Kline), min_size=100, max_size=1000))
   def test_backtest_live_consistency(market_data):
       """
       Feature: quantitative-trading-bot, Property 54: Backtesting Consistency
       
       For any identical market data sequence, Alpha Model should produce 
       same signals in both backtest and live mode.
       """
       # Run in backtest mode
       backtest_signals = run_backtest(market_data)
       
       # Run in live simulation mode
       live_signals = run_live_simulation(market_data)
       
       assert backtest_signals == live_signals
   ```

### Test Organization

```
tests/
├── unit/
│   ├── test_bybit_connector.py
│   ├── test_data_pipeline.py
│   ├── test_alpha_model.py
│   ├── test_risk_model.py
│   ├── test_execution_model.py
│   └── test_monitoring.py
├── property/
│   ├── test_data_properties.py
│   ├── test_calculation_properties.py
│   ├── test_risk_properties.py
│   ├── test_execution_properties.py
│   └── test_backtest_properties.py
├── integration/
│   ├── test_trading_flow.py
│   ├── test_kill_switch_flow.py
│   └── test_data_recovery.py
└── backtest/
    ├── test_look_ahead_bias.py
    ├── test_slippage_simulation.py
    └── test_consistency.py
```

### Test Execution

**Commands**:
```bash
# Run all tests
pytest tests/

# Run only property tests (100 iterations each)
pytest tests/property/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific property test
pytest tests/property/test_risk_properties.py::test_position_size_max_risk_constraint -v
```

### Continuous Testing

**Pre-commit Hooks**:
- Run unit tests
- Run linting (flake8, mypy)
- Check code formatting (black)

**CI/CD Pipeline**:
1. Run all unit tests
2. Run property tests (100 iterations)
3. Run integration tests
4. Generate coverage report (target: > 80%)
5. Run backtesting validation suite

### Mock Objects

**Purpose**: Isolate components during testing.

**Key Mocks**:

```python
class MockBybitConnector:
    """Mock Bybit API for testing without real connection"""
    
    async def place_order(self, *args, **kwargs) -> Order:
        return Order(
            order_id="mock_order_123",
            status=OrderStatus.FILLED,
            filled_price=Decimal("50000"),
            filled_quantity=Decimal("0.1")
        )

class MockTimescaleDB:
    """In-memory database for testing"""
    
    def __init__(self):
        self.klines = []
        self.trades = []
    
    async def write_kline(self, kline: Kline) -> None:
        self.klines.append(kline)

class MockTelegramBot:
    """Mock Telegram bot for testing alerts"""
    
    def __init__(self):
        self.sent_messages = []
    
    async def send_alert(self, message: str) -> None:
        self.sent_messages.append(message)
```

### Performance Testing

**Load Testing**:
```python
async def test_high_frequency_data_processing():
    """Test system under high data volume"""
    data_pipeline = DataPipeline()
    
    # Generate 1000 klines/second for 60 seconds
    klines = generate_high_frequency_klines(rate=1000, duration=60)
    
    start_time = time.time()
    for kline in klines:
        await data_pipeline.process_kline(kline)
    elapsed = time.time() - start_time
    
    # Verify latency target
    avg_latency = elapsed / len(klines) * 1000  # ms
    assert avg_latency < 100  # < 100ms per kline
```

**Stress Testing**:
- Test with 10x normal data volume
- Test with simulated network delays
- Test with database connection failures
- Verify graceful degradation

### Test Data Generation

**Hypothesis Strategies**:
```python
# Custom strategies for domain objects
@st.composite
def kline_strategy(draw):
    """Generate valid Kline objects"""
    low = draw(st.decimals(min_value=1, max_value=100000, places=2))
    high = draw(st.decimals(min_value=low, max_value=low * Decimal("1.1"), places=2))
    open_price = draw(st.decimals(min_value=low, max_value=high, places=2))
    close_price = draw(st.decimals(min_value=low, max_value=high, places=2))
    
    return Kline(
        symbol=draw(st.sampled_from(["BTCUSDT", "ETHUSDT"])),
        timeframe=draw(st.sampled_from(["1m", "5m", "15m", "1h"])),
        timestamp=draw(st.datetimes()),
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        volume=draw(st.decimals(min_value=0, max_value=1000000, places=3))
    )

@st.composite
def signal_strategy(draw):
    """Generate valid Signal objects"""
    return Signal(
        timestamp=draw(st.datetimes()),
        symbol=draw(st.sampled_from(["BTCUSDT", "ETHUSDT"])),
        direction=draw(st.sampled_from(list(SignalDirection))),
        confidence=draw(st.integers(min_value=0, max_value=100)),
        reasons=draw(st.lists(st.text(), min_size=1, max_size=5)),
        indicators=draw(indicator_set_strategy()),
        order_flow=draw(order_flow_strategy()),
        wyckoff_phase=draw(st.sampled_from(list(WyckoffPhase)))
    )
```

### Test Documentation

**Each test MUST include**:
- Docstring explaining what is being tested
- Reference to requirement or property (if applicable)
- Expected behavior
- Edge cases covered

**Example**:
```python
def test_position_size_with_high_leverage():
    """
    Test position sizing with leverage > 1.
    
    Validates: Requirement 7.6 - Leverage Adjustment in Position Sizing
    Property 26: For any position size calculation with leverage L > 1, 
    the effective position size should account for leverage.
    
    Edge cases:
    - Leverage = 10x
    - Leverage = 100x (max on Bybit)
    
    Expected: Actual capital required = position_value / leverage
    """
    # Test implementation...
```

---

## Deployment and Operations

### Deployment Modes

1. **Testnet Mode**: Connect to Bybit testnet for testing
2. **Paper Trading Mode**: Use live data but simulate trades
3. **Live Mode**: Real trading with real capital

### Configuration Management

**Environment Variables**:
```bash
# Mode selection
TRADING_MODE=testnet  # testnet | paper | live

# Bybit API
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/trading_bot

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_IDS=123456789,987654321

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/trading_bot/app.log
```

**Configuration File** (config.yaml):
```yaml
mode: testnet
symbol: BTCUSDT
timeframes: [1m, 5m, 15m, 1h]

alpha:
  indicator_periods:
    sma: [9, 21, 50, 200]
    ema: [9, 21, 50, 200]
  rsi_period: 14
  macd_params: [12, 26, 9]
  bb_params: [20, 2]
  volume_profile_window: 1440  # 24 hours in minutes
  order_flow_window: 1000
  min_confidence_threshold: 60

risk:
  max_risk_per_trade: 0.02  # 2%
  max_position_size: 0.10  # 10%
  initial_stop_loss_pct: 0.02  # 2%
  breakeven_trigger_pct: 0.01  # 1%
  trailing_stop_trigger_pct: 0.02  # 2%
  trailing_stop_distance_pct: 0.01  # 1%
  kill_switch_daily_dd: 0.05  # 5%
  kill_switch_consecutive_losses: 5

execution:
  limit_order_timeout: 5  # seconds
  max_slippage_pct: 0.001  # 0.1%
  max_total_cost_pct: 0.002  # 0.2%
  max_retries: 2
```

### Monitoring and Alerting

**Health Checks**:
- API connection status
- Database connection status
- WebSocket connection status
- Error rate
- Latency metrics

**Alerts**:
- Kill Switch activation
- High error rate (> 10%)
- High latency (p95 > 200ms)
- Data quality issues
- Position opened/closed
- Daily P&L threshold exceeded

### Logging

**Log Levels**:
- DEBUG: Detailed diagnostic information
- INFO: General informational messages
- WARNING: Warning messages (non-critical issues)
- ERROR: Error messages (recoverable errors)
- CRITICAL: Critical messages (fatal errors)

**Log Rotation**:
- Daily rotation
- Retain 90 days
- Compress old logs

### Backup and Recovery

**Database Backup**:
- Daily full backup
- Continuous WAL archiving
- Retain 30 days

**Configuration Backup**:
- Version control (Git)
- Backup before changes

**State Recovery**:
- Restore from last known good state
- Replay events from database
- Verify consistency before resuming

---

## Conclusion

Design Document này cung cấp blueprint đầy đủ cho việc implement Quantitative Trading Bot với:

- **Architecture rõ ràng**: Event-driven, phân tầng, separation of concerns
- **Components chi tiết**: Interfaces, algorithms, data models
- **Performance optimization**: Latency < 100ms, throughput cao
- **Error handling toàn diện**: Recovery strategies, graceful degradation
- **Testing strategy mạnh mẽ**: Property-based testing + unit tests
- **Correctness properties**: 75 properties verify system behavior

Hệ thống được thiết kế để:
- **Reliable**: Error handling, kill switch, data integrity
- **Fast**: < 100ms latency, vectorized operations, caching
- **Testable**: Property-based testing, mocks, integration tests
- **Observable**: Logging, monitoring, alerts
- **Maintainable**: Clear architecture, type hints, documentation

Next steps: Implement theo design này, viết tests song song với code, và continuous optimization dựa trên performance metrics.