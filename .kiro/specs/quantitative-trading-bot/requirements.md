# Requirements Document - Quantitative Trading Bot

## Introduction

Hệ thống Quantitative Trading Bot là một nền tảng giao dịch tự động định lượng trên sàn Bybit, được xây dựng bằng Python 3.11+. Hệ thống tự động phân tích thị trường, tạo tín hiệu giao dịch dựa trên lý thuyết Dow, Wyckoff và Order Flow, quản trị rủi ro theo khung Six Sigma, và thực thi lệnh với chi phí tối ưu. Hệ thống hỗ trợ backtesting và vận hành theo chu trình cải tiến liên tục PDCA + Kaizen.

## Glossary

- **Trading_Bot**: Hệ thống giao dịch tự động chính
- **Bybit_Connector**: Module kết nối với Bybit API (WebSocket và REST)
- **Data_Pipeline**: Module thu thập và lưu trữ dữ liệu thị trường
- **Alpha_Model**: Module tạo tín hiệu giao dịch
- **Risk_Model**: Module quản trị rủi ro
- **Execution_Model**: Module thực thi lệnh giao dịch
- **Backtesting_Engine**: Module kiểm thử chiến lược trên dữ liệu lịch sử
- **Order_Flow_Analyzer**: Module phân tích dòng lệnh (delta, footprint)
- **Wyckoff_Detector**: Module nhận diện các pha Wyckoff
- **Position_Sizer**: Module tính toán kích thước vị thế
- **Stop_Loss_Engine**: Module quản lý stop-loss
- **Kill_Switch**: Cơ chế dừng giao dịch khẩn cấp
- **Order_Manager**: Module quản lý và thực thi lệnh
- **Performance_Analytics**: Module phân tích hiệu suất giao dịch
- **Dashboard**: Giao diện giám sát hệ thống
- **TimescaleDB**: Cơ sở dữ liệu time-series
- **Signal**: Tín hiệu giao dịch (BUY/SELL/NEUTRAL)
- **Drawdown**: Mức sụt giảm từ đỉnh cao nhất
- **Look_Ahead_Bias**: Lỗi sử dụng dữ liệu tương lai trong backtesting
- **Slippage**: Chênh lệch giá giữa kỳ vọng và thực tế
- **Paper_Trading**: Chế độ giao dịch mô phỏng với dữ liệu thực
- **Testnet**: Môi trường thử nghiệm của Bybit

## Requirements

### Requirement 1: Kết nối Bybit API

**User Story:** Là một trading bot, tôi cần kết nối với Bybit API, để có thể nhận dữ liệu thị trường và thực thi lệnh giao dịch.

#### Acceptance Criteria

1. THE Bybit_Connector SHALL establish WebSocket connections to Bybit public endpoints for klines, trades, and orderbook data
2. THE Bybit_Connector SHALL establish REST API connections to Bybit for order placement and account queries
3. WHEN a WebSocket connection is disconnected, THE Bybit_Connector SHALL automatically reconnect within 5 seconds
4. WHEN an API request fails, THE Bybit_Connector SHALL retry up to 3 times with exponential backoff
5. THE Bybit_Connector SHALL authenticate using API key and secret for private endpoints
6. WHERE Testnet mode is enabled, THE Bybit_Connector SHALL connect to Bybit testnet endpoints
7. WHERE Live mode is enabled, THE Bybit_Connector SHALL connect to Bybit production endpoints
8. THE Bybit_Connector SHALL throttle API requests to maximum 600 requests per 5 seconds per IP address
9. WHEN API request rate approaches 600 requests per 5 seconds, THE Bybit_Connector SHALL queue additional requests
10. THE Bybit_Connector SHALL synchronize system time with NTP server every 1 hour
11. IF system time drift exceeds 1 second from NTP server, THEN THE Bybit_Connector SHALL emit time synchronization warning

### Requirement 2: Thu thập và lưu trữ dữ liệu thị trường

**User Story:** Là một trading bot, tôi cần thu thập và lưu trữ dữ liệu thị trường, để có thể phân tích và tạo tín hiệu giao dịch.

#### Acceptance Criteria

1. WHEN market data is received via WebSocket, THE Data_Pipeline SHALL store it in TimescaleDB within 100 milliseconds
2. THE Data_Pipeline SHALL collect klines data for timeframes 1m, 5m, 15m, and 1h
3. THE Data_Pipeline SHALL collect trade data including price, quantity, side, and timestamp
4. THE Data_Pipeline SHALL collect orderbook snapshots with at least 20 levels on each side
5. THE Data_Pipeline SHALL deduplicate incoming data based on timestamp and symbol
6. WHEN TimescaleDB connection fails, THE Data_Pipeline SHALL buffer data in memory up to 10000 records
7. THE Data_Pipeline SHALL create hypertables for time-series data with automatic partitioning

### Requirement 3: Tính toán chỉ báo kỹ thuật

**User Story:** Là một alpha model, tôi cần tính toán các chỉ báo kỹ thuật, để có thể phân tích xu hướng và động lượng thị trường.

#### Acceptance Criteria

1. THE Alpha_Model SHALL calculate moving averages (SMA, EMA) for periods 9, 21, 50, 200
2. THE Alpha_Model SHALL calculate RSI with period 14
3. THE Alpha_Model SHALL calculate MACD with parameters (12, 26, 9)
4. THE Alpha_Model SHALL calculate Bollinger Bands with period 20 and standard deviation 2
5. THE Alpha_Model SHALL calculate Volume Profile for the last 24 hours
6. WHEN new kline data arrives, THE Alpha_Model SHALL update all indicators within 50 milliseconds
7. THE Alpha_Model SHALL maintain indicator values for all configured timeframes (1m, 5m, 15m, 1h)

### Requirement 4: Phân tích Order Flow

**User Story:** Là một alpha model, tôi cần phân tích order flow, để có thể nhận diện áp lực mua bán thực tế từ thị trường.

#### Acceptance Criteria

1. WHEN trade data is received, THE Order_Flow_Analyzer SHALL calculate cumulative delta (buy volume minus sell volume)
2. THE Order_Flow_Analyzer SHALL aggregate delta by price levels to create footprint chart data
3. THE Order_Flow_Analyzer SHALL identify imbalance zones where delta exceeds 70% in one direction
4. THE Order_Flow_Analyzer SHALL calculate delta divergence between price and cumulative delta
5. THE Order_Flow_Analyzer SHALL maintain rolling window of 1000 trades for real-time analysis
6. THE Order_Flow_Analyzer SHALL classify trades as buyer-initiated or seller-initiated based on aggressor side

### Requirement 5: Nhận diện pha Wyckoff

**User Story:** Là một alpha model, tôi cần nhận diện các pha Wyckoff, để có thể xác định vị trí trong chu kỳ thị trường.

#### Acceptance Criteria

1. THE Wyckoff_Detector SHALL identify Accumulation phases based on price range contraction and volume patterns
2. THE Wyckoff_Detector SHALL identify Distribution phases based on price range expansion and volume patterns
3. THE Wyckoff_Detector SHALL identify Markup phases based on higher highs and higher lows with increasing volume
4. THE Wyckoff_Detector SHALL identify Markdown phases based on lower highs and lower lows with increasing volume
5. THE Wyckoff_Detector SHALL detect Spring events (false breakdowns) in Accumulation phases
6. THE Wyckoff_Detector SHALL detect Upthrust events (false breakouts) in Distribution phases
7. WHEN a Wyckoff phase changes, THE Wyckoff_Detector SHALL emit a phase transition event

### Requirement 6: Tạo tín hiệu giao dịch

**User Story:** Là một alpha model, tôi cần tổng hợp các phân tích thành tín hiệu giao dịch, để có thể đưa ra quyết định mua hoặc bán.

#### Acceptance Criteria

1. THE Alpha_Model SHALL generate BUY signal when Wyckoff phase is Markup AND cumulative delta is positive AND price breaks above resistance
2. THE Alpha_Model SHALL generate SELL signal when Wyckoff phase is Markdown AND cumulative delta is negative AND price breaks below support
3. THE Alpha_Model SHALL generate NEUTRAL signal when conditions for BUY or SELL are not met
4. THE Alpha_Model SHALL filter false breakouts by requiring volume confirmation (volume exceeds 1.5x average)
5. THE Alpha_Model SHALL require alignment across multiple timeframes (1m, 5m, 15m) before generating signal
6. THE Alpha_Model SHALL assign confidence score (0-100) to each signal based on indicator alignment
7. THE Alpha_Model SHALL suppress signals when confidence score is below 60

### Requirement 7: Tính toán kích thước vị thế

**User Story:** Là một risk model, tôi cần tính toán kích thước vị thế, để có thể giới hạn rủi ro mỗi giao dịch.

#### Acceptance Criteria

1. THE Position_Sizer SHALL calculate position size such that maximum loss per trade does not exceed 2% of account balance
2. THE Position_Sizer SHALL use stop-loss distance to determine position size
3. THE Position_Sizer SHALL limit position size to maximum 10% of account balance
4. THE Position_Sizer SHALL adjust position size based on signal confidence score
5. WHEN account balance decreases by 10% from peak, THE Position_Sizer SHALL reduce position sizes by 50%
6. THE Position_Sizer SHALL account for leverage when calculating position size
7. THE Position_Sizer SHALL ensure position size meets Bybit minimum order quantity requirements

### Requirement 8: Quản lý Stop-Loss

**User Story:** Là một risk model, tôi cần quản lý stop-loss, để có thể bảo vệ vốn khi thị trường đi ngược dự đoán.

#### Acceptance Criteria

1. WHEN a position is opened, THE Stop_Loss_Engine SHALL place initial stop-loss at 2% from entry price
2. WHEN price moves favorably by 1%, THE Stop_Loss_Engine SHALL move stop-loss to breakeven
3. WHEN price moves favorably by 2%, THE Stop_Loss_Engine SHALL implement trailing stop with 1% distance
4. THE Stop_Loss_Engine SHALL place stop-loss orders on Bybit exchange
5. IF stop-loss order is cancelled or rejected, THEN THE Stop_Loss_Engine SHALL immediately close position at market price
6. THE Stop_Loss_Engine SHALL monitor position every 1 second to ensure stop-loss is active
7. WHEN stop-loss is triggered, THE Stop_Loss_Engine SHALL log the exit reason and loss amount

### Requirement 9: Kill Switch

**User Story:** Là một risk model, tôi cần kill switch, để có thể dừng giao dịch khẩn cấp khi hệ thống gặp sự cố hoặc thua lỗ quá mức.

#### Acceptance Criteria

1. WHEN daily drawdown exceeds 5%, THE Kill_Switch SHALL close all open positions and stop trading
2. WHEN consecutive losses reach 5 trades, THE Kill_Switch SHALL close all open positions and stop trading
3. WHEN Bybit API returns error rate exceeds 20% over 1 minute, THE Kill_Switch SHALL stop trading
4. WHEN system detects abnormal price movement (>10% in 1 minute), THE Kill_Switch SHALL close all positions
5. THE Kill_Switch SHALL send Telegram alert when activated
6. THE Kill_Switch SHALL require manual reset before trading can resume
7. THE Kill_Switch SHALL log activation reason and system state at time of activation

### Requirement 10: Thực thi lệnh giao dịch

**User Story:** Là một execution model, tôi cần thực thi lệnh giao dịch, để có thể mở và đóng vị thế trên Bybit.

#### Acceptance Criteria

1. WHEN a BUY signal is generated, THE Order_Manager SHALL place limit order at best bid price
2. WHEN a SELL signal is generated, THE Order_Manager SHALL place limit order at best ask price
3. IF limit order is not filled within 5 seconds, THEN THE Order_Manager SHALL cancel and place market order
4. THE Order_Manager SHALL verify order execution by querying Bybit API
5. THE Order_Manager SHALL retry failed orders up to 2 times
6. THE Order_Manager SHALL track order status (pending, filled, cancelled, rejected)
7. WHEN order is filled, THE Order_Manager SHALL emit position opened event with entry price and quantity

### Requirement 11: Kiểm soát chi phí giao dịch

**User Story:** Là một execution model, tôi cần kiểm soát chi phí giao dịch, để có thể tối ưu hóa lợi nhuận ròng.

#### Acceptance Criteria

1. THE Order_Manager SHALL calculate expected slippage before placing order
2. IF expected slippage exceeds 0.1%, THEN THE Order_Manager SHALL reject the trade
3. THE Order_Manager SHALL calculate total trading cost including commission, slippage, and spread
4. THE Order_Manager SHALL reject trades where total cost exceeds 0.2% of position value
5. THE Order_Manager SHALL prefer limit orders over market orders to minimize costs
6. THE Order_Manager SHALL track actual slippage for each executed order
7. THE Order_Manager SHALL log cost breakdown for each trade

### Requirement 12: Backtesting Engine

**User Story:** Là một developer, tôi cần backtesting engine, để có thể kiểm thử chiến lược trên dữ liệu lịch sử.

#### Acceptance Criteria

1. THE Backtesting_Engine SHALL replay historical data in chronological order
2. THE Backtesting_Engine SHALL prevent look-ahead bias by only using data available at each timestamp
3. THE Backtesting_Engine SHALL simulate order execution with realistic slippage based on orderbook depth at execution time
4. WHEN simulating order execution, THE Backtesting_Engine SHALL calculate slippage by analyzing orderbook liquidity within 0.5% of execution price
5. THE Backtesting_Engine SHALL apply commission fees matching Bybit fee structure
6. THE Backtesting_Engine SHALL apply the same risk management rules as live trading
7. THE Backtesting_Engine SHALL generate trades using the same Alpha_Model logic as live trading
8. THE Backtesting_Engine SHALL support date range selection for backtest period
9. THE Backtesting_Engine SHALL process at least 1000 candles per second

### Requirement 13: Phân tích hiệu suất

**User Story:** Là một trader, tôi cần phân tích hiệu suất, để có thể đánh giá và cải thiện chiến lược giao dịch.

#### Acceptance Criteria

1. THE Performance_Analytics SHALL calculate total return, annualized return, and Sharpe ratio
2. THE Performance_Analytics SHALL calculate maximum drawdown and average drawdown
3. THE Performance_Analytics SHALL calculate win rate and profit factor
4. THE Performance_Analytics SHALL calculate average win and average loss
5. THE Performance_Analytics SHALL generate equity curve showing account balance over time
6. THE Performance_Analytics SHALL identify best and worst performing periods
7. THE Performance_Analytics SHALL export performance metrics to JSON format

### Requirement 14: Paper Trading Mode

**User Story:** Là một trader, tôi cần paper trading mode, để có thể kiểm thử chiến lược với dữ liệu thực mà không rủi ro vốn.

#### Acceptance Criteria

1. WHERE Paper_Trading mode is enabled, THE Trading_Bot SHALL simulate order execution without placing real orders
2. WHERE Paper_Trading mode is enabled, THE Trading_Bot SHALL use real-time market data from Bybit
3. WHERE Paper_Trading mode is enabled, THE Trading_Bot SHALL maintain simulated account balance and positions
4. WHERE Paper_Trading mode is enabled, THE Trading_Bot SHALL apply realistic slippage and commission to simulated trades
5. THE Trading_Bot SHALL allow switching from Paper_Trading to Live mode via configuration
6. WHEN switching to Live mode, THE Trading_Bot SHALL require explicit confirmation
7. THE Trading_Bot SHALL log all trades in Paper_Trading mode for later analysis

### Requirement 15: Monitoring Dashboard

**User Story:** Là một trader, tôi cần monitoring dashboard, để có thể giám sát trạng thái hệ thống và hiệu suất giao dịch.

#### Acceptance Criteria

1. THE Dashboard SHALL display current account balance and open positions
2. THE Dashboard SHALL display recent signals and their confidence scores
3. THE Dashboard SHALL display current Wyckoff phase and order flow delta
4. THE Dashboard SHALL display equity curve for the last 30 days
5. THE Dashboard SHALL display key performance metrics (win rate, profit factor, Sharpe ratio)
6. THE Dashboard SHALL display system health status (API connection, database connection, error rate)
7. THE Dashboard SHALL refresh data every 5 seconds

### Requirement 16: Alert System

**User Story:** Là một trader, tôi cần alert system, để có thể nhận thông báo về các sự kiện quan trọng và tương tác với hệ thống qua Telegram.

#### Acceptance Criteria

1. WHEN a trade is executed, THE Trading_Bot SHALL send Telegram notification with entry price and position size
2. WHEN an order is pending, THE Trading_Bot SHALL send Telegram notification with order details
3. WHEN an order is filled, THE Trading_Bot SHALL send Telegram notification with fill price and quantity
4. WHEN an order is cancelled, THE Trading_Bot SHALL send Telegram notification with cancellation reason
5. WHEN an order is rejected, THE Trading_Bot SHALL send Telegram notification with rejection reason
6. WHEN Kill_Switch is activated, THE Trading_Bot SHALL send Telegram alert with activation reason
7. WHEN daily profit or loss exceeds 3%, THE Trading_Bot SHALL send Telegram notification
8. WHEN system error occurs, THE Trading_Bot SHALL send Telegram alert with error details
9. WHEN user sends /status command via Telegram, THE Trading_Bot SHALL respond with current system status and connection health
10. WHEN user sends /positions command via Telegram, THE Trading_Bot SHALL respond with all open positions and their unrealized P&L
11. WHEN user sends /pnl command via Telegram, THE Trading_Bot SHALL respond with daily, weekly, and total P&L
12. THE Trading_Bot SHALL authenticate Telegram users by chat ID before responding to commands
13. THE Trading_Bot SHALL allow configuring alert preferences via configuration file
14. THE Trading_Bot SHALL rate-limit alerts to maximum 10 per hour
15. THE Trading_Bot SHALL include timestamp and symbol in all alert messages

### Requirement 17: Configuration Management

**User Story:** Là một developer, tôi cần configuration management, để có thể điều chỉnh tham số chiến lược mà không thay đổi code.

#### Acceptance Criteria

1. THE Trading_Bot SHALL load configuration from YAML file at startup
2. THE Trading_Bot SHALL support configuration for all indicator parameters (periods, thresholds)
3. THE Trading_Bot SHALL support configuration for risk parameters (max risk per trade, max drawdown)
4. THE Trading_Bot SHALL support configuration for execution parameters (order timeout, slippage limit)
5. THE Trading_Bot SHALL validate configuration values against allowed ranges
6. IF configuration is invalid, THEN THE Trading_Bot SHALL log error and refuse to start
7. THE Trading_Bot SHALL support hot-reload of configuration without restart for non-critical parameters

### Requirement 18: Data Integrity

**User Story:** Là một trading bot, tôi cần đảm bảo tính toàn vẹn dữ liệu, để có thể đưa ra quyết định chính xác.

#### Acceptance Criteria

1. THE Data_Pipeline SHALL validate incoming data for completeness (no missing required fields)
2. THE Data_Pipeline SHALL validate incoming data for correctness (price > 0, volume >= 0)
3. IF invalid data is received, THEN THE Data_Pipeline SHALL log error and discard the data
4. THE Data_Pipeline SHALL detect gaps in time-series data by comparing timestamps
5. WHEN data gap is detected, THE Data_Pipeline SHALL call Bybit REST API to fetch missing historical data
6. WHEN data gap is filled, THE Data_Pipeline SHALL recalculate all affected indicators (EMA, RSI) using complete data
7. IF data gap exceeds 1 minute, THEN THE Data_Pipeline SHALL emit data quality alert
8. THE Data_Pipeline SHALL maintain data quality metrics (completeness rate, error rate)
9. THE Data_Pipeline SHALL store raw data alongside processed data for audit purposes

### Requirement 19: Parser và Serializer cho Configuration

**User Story:** Là một developer, tôi cần parse và serialize configuration, để có thể load và save cài đặt hệ thống.

#### Acceptance Criteria

1. WHEN a valid YAML configuration file is provided, THE Trading_Bot SHALL parse it into a Configuration object
2. WHEN an invalid YAML configuration file is provided, THE Trading_Bot SHALL return a descriptive error message
3. THE Trading_Bot SHALL serialize Configuration objects back into valid YAML format
4. FOR ALL valid Configuration objects, parsing then serializing then parsing SHALL produce an equivalent Configuration object (round-trip property)
5. THE Trading_Bot SHALL preserve comments in YAML files during serialization
6. THE Trading_Bot SHALL validate configuration schema against predefined structure
7. THE Trading_Bot SHALL support nested configuration sections (alpha, risk, execution, backtesting)

### Requirement 20: Logging và Audit Trail

**User Story:** Là một developer, tôi cần logging và audit trail, để có thể debug và audit hệ thống.

#### Acceptance Criteria

1. THE Trading_Bot SHALL log all trades with timestamp, symbol, side, price, quantity, and reason
2. THE Trading_Bot SHALL log all signals with timestamp, symbol, direction, confidence, and contributing factors
3. THE Trading_Bot SHALL log all risk events (stop-loss triggered, kill switch activated, position size reduced)
4. THE Trading_Bot SHALL log all system errors with stack trace and context
5. THE Trading_Bot SHALL rotate log files daily and retain logs for 90 days
6. THE Trading_Bot SHALL support configurable log levels (DEBUG, INFO, WARNING, ERROR)
7. THE Trading_Bot SHALL write logs to both file and console output
