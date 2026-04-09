# Tasks - Quantitative Trading Bot

## Overview

Tài liệu này mô tả chi tiết các tasks cần thực hiện để implement Quantitative Trading Bot theo thiết kế đã được phê duyệt. Tổng thời gian ước tính: **142 giờ** (bao gồm buffer 30%).

## Phase 1: Nền tảng & Kết nối (20h)

### Task 1: Thiết lập kiến trúc dự án

**Mô tả**: Khởi tạo project structure, Docker Compose, và các file cấu hình cơ bản.

**Estimated Hours**: 4h

**Dependencies**: None

**Acceptance Criteria**:
- [ ] Project structure được tạo theo design (src/connectors, src/data, src/alpha, src/risk, src/execution, src/backtest, src/monitoring)
- [ ] Docker Compose file với services: trading-bot, timescaledb, dashboard
- [ ] requirements.txt với tất cả dependencies (pybit, pandas-ta, hypothesis, ujson, asyncpg, streamlit, python-telegram-bot)
- [ ] .env.example template với tất cả biến môi trường cần thiết
- [ ] .gitignore configured (không commit .env, __pycache__, *.pyc)
- [ ] Logging system với configurable levels (DEBUG, INFO, WARNING, ERROR)
- [ ] `docker-compose up` chạy thành công không lỗi

**Files to Create**:
- `docker-compose.yml`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `src/__init__.py`
- `src/connectors/__init__.py`
- `src/data/__init__.py`
- `src/alpha/__init__.py`
- `src/risk/__init__.py`
- `src/execution/__init__.py`
- `src/backtest/__init__.py`
- `src/monitoring/__init__.py`
- `config/config.yaml`
- `tests/__init__.py`

**Property Tests**: None (infrastructure setup)

---

### Task 2: Bybit Connector (WebSocket + REST)

**Mô tả**: Implement Bybit API connector với WebSocket streams và REST client, bao gồm rate limiting và auto-reconnect.

**Estimated Hours**: 8h

**Dependencies**: Task 1

**Acceptance Criteria**:
- [ ] WebSocketManager kết nối thành công với Bybit Testnet
- [ ] Subscribe được kline streams (1m, 5m, 15m, 1h)
- [ ] Subscribe được trade stream
- [ ] Subscribe được orderbook stream (20 levels)
- [ ] Auto-reconnect trong vòng 5 giây khi disconnect
- [ ] RESTClient đặt được lệnh market và limit trên Testnet
- [ ] RateLimiter giới hạn 600 requests/5s
- [ ] Exponential backoff retry (1s, 2s, 4s) cho failed requests
- [ ] NTP sync mỗi 1 giờ, warning nếu drift > 1s
- [ ] Nhận được tick real-time liên tục >= 60 phút không lỗi

**Files to Create**:
- `src/connectors/bybit_ws.py` (WebSocketManager)
- `src/connectors/bybit_rest.py` (RESTClient)
- `src/connectors/rate_limiter.py` (RateLimiter)
- `src/connectors/ntp_sync.py` (NTP synchronization)
- `tests/unit/test_bybit_connector.py`
- `tests/property/test_connector_properties.py`

**Property Tests**:
- Property 1: WebSocket Auto-Reconnection
- Property 2: API Request Retry with Exponential Backoff
- Property 3: API Rate Limiting
- Property 4: Time Drift Warning

---

### Task 3: Data Pipeline & TimescaleDB

**Mô tả**: Implement data pipeline để thu thập, validate, deduplicate và lưu trữ market data vào TimescaleDB.

**Estimated Hours**: 8h

**Dependencies**: Task 2

**Acceptance Criteria**:
- [x] StreamProcessor xử lý kline/trade/orderbook data trong < 100ms
- [x] DataValidator kiểm tra completeness và correctness
- [x] Deduplication dựa trên (symbol, timestamp, timeframe)
- [x] TimescaleDB hypertables được tạo (klines, trades, orderbooks)
- [x] GapDetector phát hiện gaps trong time-series
- [x] GapFiller tự động fetch historical data từ REST API
- [x] In-memory buffer 10,000 records khi DB connection fails
- [x] Query 1 triệu rows OHLCV < 2 giây
- [x] Không mất data khi reconnect WebSocket
- [x] Script tải historical data 6 tháng thành công

**Files to Create**:
- `src/data/stream_processor.py`
- `src/data/validator.py`
- `src/data/gap_detector.py`
- `src/data/timescaledb_writer.py`
- `migrations/001_init.sql` (TimescaleDB schema)
- `scripts/download_historical_data.py`
- `tests/unit/test_data_pipeline.py`
- `tests/property/test_data_properties.py`

**Property Tests**:
- Property 5: Data Storage Latency
- Property 6: Data Completeness
- Property 7: Orderbook Depth Requirement
- Property 8: Data Deduplication
- Property 9: Data Buffering on Connection Failure
- Property 64-71: Data Validation and Integrity

---

## Phase 2: Alpha Model (36h)

### Task 4: Indicator Engine

**Mô tả**: Implement technical indicators engine sử dụng numpy với vectorized operations.

**Estimated Hours**: 6h

**Dependencies**: Task 3

**Acceptance Criteria**:
- [x] Calculate SMA/EMA cho periods [9, 21, 50, 200]
- [x] Calculate RSI period 14
- [x] Calculate MACD (12, 26, 9)
- [x] Calculate Bollinger Bands (20, 2)
- [x] Calculate Volume Profile 24h
- [x] Update tất cả indicators trong < 50ms khi có kline mới
- [x] Maintain indicator values cho tất cả timeframes (1m, 5m, 15m, 1h)
- [x] Kết quả match TradingView với sai số < 0.01%
- [x] Unit test coverage >= 90%
- [x] Incremental update thay vì recalculate toàn bộ

**Files to Create**:
- `src/alpha/indicators.py` (IndicatorEngine, TechnicalIndicators)
- `src/alpha/incremental_ema.py` (Incremental EMA calculator)
- `tests/unit/test_indicators.py`
- `tests/property/test_calculation_properties.py`

**Property Tests**:
- Property 10: Indicator Update Performance

---

### Task 5: Order Flow Delta Calculator

**Mô tả**: Implement order flow analyzer để tính cumulative delta, footprint chart và phát hiện imbalance zones.

**Estimated Hours**: 10h

**Dependencies**: Task 3

**Acceptance Criteria**:
- [x] Calculate cumulative delta (buy volume - sell volume)
- [x] Aggregate delta by price levels (footprint chart)
- [x] Identify imbalance zones (delta > 70% one direction)
- [x] Calculate delta divergence với price
- [x] Maintain rolling window 1000 trades
- [x] Classify trades as buyer/seller initiated
- [x] Visualize footprint để verify correctness
- [x] Volume imbalance detection khi |ratio| > threshold

**Files to Create**:
- `src/alpha/order_flow.py` (OrderFlowAnalyzer)
- `src/alpha/footprint.py` (Footprint chart generator)
- `tests/unit/test_order_flow.py`
- `tests/property/test_order_flow_properties.py`

**Property Tests**:
- Property 11: Cumulative Delta Calculation
- Property 12: Footprint Aggregation Consistency
- Property 13: Imbalance Zone Detection
- Property 14: Rolling Window Size Constraint
- Property 15: Trade Classification Completeness

---

### Task 6: Wyckoff Phase Detector

**Mô tả**: Implement Wyckoff phase detection dựa trên price action và volume patterns.

**Estimated Hours**: 12h

**Dependencies**: Task 4, Task 5

**Acceptance Criteria**:
- [x] Detect ACCUMULATION phase (range contraction + volume decrease)
- [x] Detect MARKUP phase (higher highs/lows + volume increase)
- [x] Detect DISTRIBUTION phase (range expansion + volume increase)
- [x] Detect MARKDOWN phase (lower highs/lows + volume increase)
- [x] Detect Spring events (false breakdown in Accumulation)
- [x] Detect Upthrust events (false breakout in Distribution)
- [x] Emit phase transition events
- [x] Backtest 6 tháng BTC, label đúng >= 70% pha rõ ràng
- [x] Không emit signal khi phase = UNKNOWN

**Files to Create**:
- `src/alpha/wyckoff.py` (WyckoffDetector)
- `src/alpha/swing_detector.py` (Swing high/low detection)
- `tests/unit/test_wyckoff.py`
- `tests/property/test_wyckoff_properties.py`

**Property Tests**:
- Property 16: Phase Transition Event Emission

---

### Task 7: Signal Aggregator & False Breakout Filter

**Mô tả**: Tổng hợp indicators, order flow và Wyckoff analysis để tạo trading signals với confidence scoring.

**Estimated Hours**: 8h

**Dependencies**: Task 4, Task 5, Task 6

**Acceptance Criteria**:
- [x] Generate BUY signal khi: Wyckoff=Markup + delta>0 + breakout + volume confirm
- [x] Generate SELL signal khi: Wyckoff=Markdown + delta<0 + breakdown + volume confirm
- [x] Generate NEUTRAL khi không đủ điều kiện
- [x] Filter false breakouts (volume < 1.5x average)
- [x] Require multi-timeframe alignment (1m, 5m, 15m)
- [x] Assign confidence score 0-100
- [x] Suppress signals khi confidence < 60
- [x] False breakout filter giảm > 30% lệnh giả (đo trên backtest)
- [x] Tất cả parameters trong config YAML

**Files to Create**:
- `src/alpha/signal_engine.py` (SignalGenerator)
- `src/alpha/breakout_filter.py` (False breakout filter)
- `config/alpha_params.yaml`
- `tests/unit/test_signal_engine.py`
- `tests/property/test_signal_properties.py`

**Property Tests**:
- Property 17: Volume Confirmation for Breakouts
- Property 18: Multi-Timeframe Alignment Requirement
- Property 19: Confidence Score Range
- Property 20: Low Confidence Signal Suppression

---

## Phase 3: Risk Model (14h)

### Task 8: Position Sizing Calculator

**Mô tả**: Implement position sizing với risk management rules (2% max risk per trade).

**Estimated Hours**: 4h

**Dependencies**: Task 2

**Acceptance Criteria**:
- [x] Calculate position size: (balance × risk_pct) / stop_loss_distance
- [x] Support Fixed % và Kelly Criterion
- [x] Tự động làm tròn theo Bybit lot size
- [x] Return 0 nếu size < min_lot
- [x] Risk/lệnh không bao giờ vượt 2% balance
- [x] Position size <= 10% balance
- [x] Adjust based on signal confidence
- [x] Reduce 50% khi drawdown > 10%
- [x] Account for leverage
- [x] 20 unit tests bao gồm edge cases

**Files to Create**:
- `src/risk/position_sizing.py` (PositionSizer)
- `tests/unit/test_position_sizing.py`
- `tests/property/test_risk_properties.py`

**Property Tests**:
- Property 21: Maximum Risk Per Trade
- Property 22: Position Size Inverse Proportionality
- Property 23: Maximum Position Size Limit
- Property 24: Confidence-Based Position Adjustment
- Property 25: Drawdown-Based Position Reduction
- Property 26: Leverage Adjustment in Position Sizing
- Property 27: Minimum Order Quantity Compliance

---

### Task 9: Stop-Loss Engine

**Mô tả**: Implement stop-loss management với 3 modes: Hard SL, Trailing SL, ATR-based SL.

**Estimated Hours**: 6h

**Dependencies**: Task 2, Task 8

**Acceptance Criteria**:
- [x] Place initial stop-loss 2% from entry
- [x] Move to breakeven khi profit >= 1%
- [x] Activate trailing stop khi profit >= 2% (1% distance)
- [x] Support 3 modes: Fixed %, Trailing, ATR-based
- [x] Place stop-loss orders on Bybit exchange
- [x] Emergency close at market nếu SL cancelled/rejected
- [x] Monitor positions every 1 second
- [x] Trailing SL không lùi về bất lợi
- [x] ATR SL tự điều chỉnh khi ATR thay đổi > 20%
- [x] Log exit reason và loss amount

**Files to Create**:
- `src/risk/stop_loss.py` (StopLossEngine)
- `src/risk/trailing_stop.py` (Trailing stop logic)
- `tests/unit/test_stop_loss.py`
- `tests/property/test_stop_loss_properties.py`

**Property Tests**:
- Property 28: Initial Stop-Loss Placement
- Property 29: Breakeven Stop-Loss Adjustment
- Property 30: Trailing Stop Activation
- Property 31: Emergency Position Closure on Stop-Loss Failure
- Property 32: Stop-Loss Trigger Logging
- Property 32: Stop-Loss Trigger Logging

---

### Task 10: Kill Switch & Alert System

**Mô tả**: Implement kill switch mechanism và Telegram alert system.

**Estimated Hours**: 4h

**Dependencies**: Task 8, Task 9

**Acceptance Criteria**:
- [x] Activate khi daily drawdown > 5%
- [x] Activate khi consecutive losses >= 5
- [x] Activate khi API error rate > 20% over 1 minute
- [x] Activate khi price movement > 10% in 1 minute
- [x] Close all positions và stop trading khi activated
- [x] Send Telegram alert với activation reason
- [x] Require manual reset
- [x] Log activation reason và system state snapshot
- [x] Kích hoạt < 1 giây
- [x] Hủy pending orders, giữ nguyên open positions

**Files to Create**:
- `src/risk/kill_switch.py` (KillSwitch)
- `src/risk/drawdown_monitor.py` (DrawdownMonitor)
- `src/notifications/telegram.py` (TelegramBot)
- `tests/unit/test_kill_switch.py`
- `tests/property/test_kill_switch_properties.py`

**Property Tests**:
- Property 33: Kill Switch Activation on Daily Drawdown
- Property 34: Kill Switch Activation on Consecutive Losses
- Property 35: Kill Switch Activation on API Error Rate
- Property 36: Kill Switch Activation on Abnormal Price Movement
- Property 37: Kill Switch Alert Notification
- Property 38: Kill Switch Activation Logging

---

## Phase 4: Execution Model (11h)

### Task 11: Order Manager

**Mô tả**: Implement order manager với state machine để quản lý vòng đời lệnh.

**Estimated Hours**: 8h

**Dependencies**: Task 2, Task 8, Task 9

**Acceptance Criteria**:
- [x] State machine: PENDING → OPEN → PARTIAL → FILLED → CLOSED
- [x] Place limit order at best bid/ask
- [x] Cancel và place market order nếu không fill trong 5s
- [x] Verify execution qua Bybit API
- [x] Retry failed orders up to 2 times
- [x] Track order status (pending, filled, cancelled, rejected)
- [x] Emit PositionOpened event với entry price và quantity
- [x] Handle partial fills
- [x] P&L calculation khớp với Bybit sai số < 0.1%
- [x] Detect order reject < 500ms

**Files to Create**:
- `src/execution/order_manager.py` (OrderManager)
- `src/execution/state_machine.py` (Order state machine)
- `src/execution/order_tracker.py` (Order tracking)
- `tests/unit/test_order_manager.py`
- `tests/property/test_execution_properties.py`

**Property Tests**:
- Property 39: Signal-Based Order Placement
- Property 40: Limit Order Timeout Fallback
- Property 41: Order Execution Verification
- Property 42: Order Status Validity
- Property 43: Position Opened Event on Fill

---

### Task 12: Slippage & Cost Filter

**Mô tả**: Implement cost analysis và filtering dựa trên slippage và total trading cost.

**Estimated Hours**: 3h

**Dependencies**: Task 11

**Acceptance Criteria**:
- [x] Calculate expected slippage từ orderbook depth
- [x] Reject trade nếu slippage > 0.1%
- [x] Calculate total cost (commission + slippage + spread)
- [x] Reject trade nếu total cost > 0.2% position value
- [x] Prefer limit orders over market orders
- [x] Track actual slippage cho mỗi order
- [x] Log cost breakdown
- [x] Bot tự bỏ qua khi spread > max_spread_config
- [x] Estimate slippage sai số < 20%

**Files to Create**:
- `src/execution/cost_filter.py` (CostFilter)
- `src/execution/slippage_calculator.py` (Slippage calculation)
- `tests/unit/test_cost_filter.py`
- `tests/property/test_cost_properties.py`

**Property Tests**:
- Property 44: Slippage Calculation Before Order
- Property 45: Slippage-Based Trade Rejection
- Property 46: Total Trading Cost Calculation
- Property 47: Cost-Based Trade Rejection
- Property 48: Actual Slippage Tracking
- Property 49: Trade Cost Logging

---

## Phase 5: Backtesting & PDCA (20h)

### Task 13: Backtesting Engine

**Mô tả**: Implement event-driven backtesting engine với realistic slippage simulation.

**Estimated Hours**: 10h

**Dependencies**: Task 7, Task 11

**Acceptance Criteria**:
- [x] Event-driven architecture (EventEngine)
- [x] Replay historical data chronologically
- [x] Prevent look-ahead bias (chỉ dùng data <= current timestamp)
- [x] Simulate slippage dựa trên orderbook depth
- [x] Apply commission matching Bybit fee structure
- [x] Apply same risk management rules như live trading
- [x] Generate trades using same Alpha Model logic
- [x] Support date range selection
- [x] Process >= 1000 candles/second
- [ ] Backtest 1 năm BTC 1m chạy < 5 phút
- [x] Output CSV mỗi lệnh với entry/exit/P&L/reason

**Files to Create**:
- `src/backtest/engine.py` (EventEngine, BacktestRunner)
- `src/backtest/replayer.py` (HistoricalDataReplayer)
- `src/backtest/simulator.py` (SimulatedExchange)
- `src/backtest/slippage_model.py` (Orderbook-based slippage)
- `tests/unit/test_backtest_engine.py`
- `tests/backtest/test_look_ahead_bias.py`
- `tests/backtest/test_slippage_simulation.py`
- `tests/backtest/test_consistency.py`

**Property Tests**:
- Property 50: Chronological Data Replay
- Property 51: Look-Ahead Bias Prevention
- Property 52: Realistic Slippage Simulation
- Property 53: Commission Application in Backtest
- Property 54: Backtesting Consistency with Live Trading
- Property 55: Backtesting Performance Requirement

---

### Task 14: Performance Analytics

**Mô tả**: Implement performance metrics calculation và reporting.

**Estimated Hours**: 6h

**Dependencies**: Task 13

**Acceptance Criteria**:
- [ ] Calculate total return, annualized return, Sharpe ratio
- [ ] Calculate max drawdown và average drawdown
- [ ] Calculate win rate và profit factor
- [ ] Calculate average win và average loss
- [ ] Generate equity curve (Plotly interactive)
- [ ] Identify best và worst performing periods
- [ ] Export metrics to JSON
- [ ] Sharpe Ratio tính đúng công thức chuẩn
- [ ] PDF report tự động generate sau mỗi backtest

**Files to Create**:
- `src/backtest/analytics.py` (PerformanceAnalytics)
- `src/backtest/equity_curve.py` (Equity curve generator)
- `reports/template.html` (PDF report template)
- `tests/unit/test_analytics.py`

**Property Tests**: None (metrics calculation)

---

### Task 15: Paper Trading Mode & Live Switch

**Mô tả**: Implement paper trading mode và mechanism để switch sang live mode.

**Estimated Hours**: 4h

**Dependencies**: Task 11, Task 13

**Acceptance Criteria**:
- [x] Paper mode simulate order execution không place real orders
- [x] Paper mode use real-time market data từ Bybit
- [x] Paper mode maintain simulated balance và positions
- [x] Paper mode apply realistic slippage và commission
- [x] Allow switching từ Paper → Live via config
- [x] Require explicit confirmation khi switch to Live
- [x] Log all trades trong Paper mode
- [x] Paper và live dùng chung 100% code
- [x] Không thể vô tình bật live mode

**Files to Create**:
- `src/execution/paper_trader.py` (Paper trading simulator)
- `src/execution/mode_switcher.py` (Mode switching logic)
- `tests/unit/test_paper_trading.py`
- `tests/property/test_paper_trading_properties.py`

**Property Tests**:
- Property 57: Paper Trading Slippage and Commission
- Property 58: Paper Trading Logging

---

## Phase 6: Vận hành & Kaizen (8h)

### Task 16: Monitoring Dashboard

**Mô tả**: Implement Streamlit dashboard và Telegram bot với commands.

**Estimated Hours**: 5h

**Dependencies**: Task 10, Task 11

**Acceptance Criteria**:
- [x] Display current balance và open positions
- [x] Display recent signals với confidence scores
- [x] Display current Wyckoff phase và order flow delta
- [x] Display equity curve last 30 days
- [x] Display key metrics (win rate, profit factor, Sharpe ratio)
- [x] Display system health (API, DB, error rate)
- [x] Refresh data every 5 seconds
- [x] Telegram bot respond to /status command
- [x] Telegram bot respond to /positions command
- [x] Telegram bot respond to /pnl command
- [x] Authenticate users by chat_id
- [x] Send alerts for all order states (pending, filled, cancelled, rejected)
- [x] Rate limit alerts to 10/hour

**Files to Create**:
- `src/monitoring/dashboard.py` (Streamlit dashboard)
- `src/monitoring/telegram_bot.py` (Telegram bot với commands)
- `src/monitoring/metrics_collector.py` (Metrics collection)
- `tests/unit/test_monitoring.py`
- `tests/property/test_telegram_properties.py`

**Property Tests**:
- Property 59: Telegram Command Response
- Property 60: Telegram Authentication
- Property 61: Alert Rate Limiting
- Property 62: Alert Message Completeness

---

### Task 17: Config-driven Tuning & Grid Search

**Mô tả**: Implement configuration management và grid search optimization.

**Estimated Hours**: 3h

**Dependencies**: Task 13, Task 14

**Acceptance Criteria**:
- [ ] Load configuration từ YAML at startup
- [ ] Support config cho all indicator parameters
- [ ] Support config cho risk parameters
- [ ] Support config cho execution parameters
- [ ] Validate config values against allowed ranges
- [ ] Refuse to start nếu config invalid
- [ ] Support hot-reload cho non-critical parameters
- [ ] Grid search script chạy song song >= 4 cores
- [ ] Thay tham số không cần sửa code
- [ ] Preserve comments trong YAML khi serialize

**Files to Create**:
- `src/config/config_manager.py` (Configuration management)
- `src/config/validator.py` (Config validation)
- `scripts/optimize.py` (Grid search optimization)
- `config/strategy_params.yaml` (Strategy parameters)
- `tests/unit/test_config.py`
- `tests/property/test_config_properties.py`

**Property Tests**:
- Property 56: Configuration Round-Trip Property
- Property 63: Configuration Validation

---

## Summary

**Total Tasks**: 17 main tasks
**Total Estimated Hours**: 109h (raw) + 33h (buffer) = **142h**
**Total Phases**: 6 phases

**Critical Path**: Task 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

**Parallel Opportunities**:
- Task 8-10 (Risk Model) có thể phát triển song song với Task 6-7 (Alpha Model)
- Task 16-17 (Monitoring) có thể phát triển song song với Task 13-15 (Backtesting)

**Testing Requirements**:
- **75 Property-Based Tests** (Hypothesis) covering all Correctness Properties
- **Unit Tests** cho tất cả modules với coverage >= 80%
- **Integration Tests** cho end-to-end flows
- **Backtesting Validation** suite

**Next Steps**:
1. Chuẩn bị môi trường development (xem SETUP.md)
2. Tạo Bybit Testnet account và API keys
3. Bắt đầu với Task 1 (Project Setup)
4. Implement tasks theo thứ tự, test song song với code
5. Chạy backtest sau khi hoàn thành Phase 5
6. Paper trading >= 2 tuần trước khi live
