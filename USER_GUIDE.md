# 📖 User Guide - Quantitative Trading Bot

Hướng dẫn sử dụng đầy đủ cho Quantitative Trading Bot, từ setup đến vận hành hàng ngày.

---

## 📑 Mục lục

1. [Getting Started](#getting-started)
2. [Configuration Parameters](#configuration-parameters)
3. [Trading Workflow](#trading-workflow)
4. [Using the Dashboard](#using-the-dashboard)
5. [Telegram Bot Commands](#telegram-bot-commands)
6. [Daily Operations](#daily-operations)

---

## 🚀 Getting Started

### Bybit Account Setup

#### 1. Tạo Bybit Testnet Account
1. Truy cập [testnet.bybit.com](https://testnet.bybit.com)
2. Đăng ký với email (không cần KYC)
3. Verify email và đăng nhập

#### 2. Nhận Test Coins
1. Click **Assets** → **Assets Overview**
2. Click **Request Test Coins**
3. Nhận ngay 10,000 USDT + 1 BTC (testnet)
4. Có thể request 1 lần mỗi 24 giờ

#### 3. Transfer sang Unified Trading Account
```
Spot Account → Transfer → Unified Trading Account
Amount: 10,000 USDT
```

#### 4. Tạo API Keys
1. **Account & Security** → **API Management**
2. **Create New Key** → **System-generated**
3. Chọn quyền:
   - ✅ Read-Write cho Contract (Derivatives/Futures)
   - ✅ Read-Write cho Spot
   - ❌ Withdraw (KHÔNG cần)
4. Lưu lại API Key và API Secret

### Environment Configuration

Tạo file `.env`:
```bash
# Bybit API
BYBIT_API_KEY=your_testnet_api_key
BYBIT_API_SECRET=your_testnet_secret
BYBIT_TESTNET=true

# Database
DATABASE_URL=postgresql://trading_user:trading_pass@timescaledb:5432/trading_db

# Trading Mode
TRADING_MODE=testnet  # testnet | paper | live
INITIAL_BALANCE=10000

# Telegram Bot (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### First Run

#### 🚀 Cách Nhanh Nhất: Dùng Setup Script (Khuyến nghị)

**Windows PowerShell**:
```powershell
# Chạy script setup tự động
.\setup.ps1
```

**Linux/macOS**:
```bash
# Cho phép execute
chmod +x setup.sh

# Chạy script setup tự động
./setup.sh
```

**Script sẽ tự động**:
1. ✅ Kiểm tra Docker, Docker Compose
2. ✅ Kiểm tra .env file
3. ✅ Build và start containers
4. ✅ Tạo database và tables
5. ✅ Test kết nối Bybit
6. ✅ Hiển thị hướng dẫn tiếp theo

**Nếu script báo lỗi về time sync**:
- Windows: Settings → Time & Language → Sync now
- Linux/macOS: `sudo ntpdate -s time.nist.gov`

---

#### 📝 Cách Thủ Công (Nếu script không chạy được)

<details>
<summary>Click để xem hướng dẫn chi tiết</summary>

**⚠️ BẮT BUỘC**: Bybit API yêu cầu giờ chính xác (sai lệch < 5 giây sẽ bị reject)

**Windows**:
1. Mở **Settings** (Win + I)
2. **Time & Language** → **Date & Time**
3. Bật **Set time automatically**
4. Click **Sync now**

**Hoặc dùng PowerShell (Run as Administrator)**:
```powershell
Start-Service w32time
w32tm /resync
```

**Linux/macOS**:
```bash
sudo ntpdate -s time.nist.gov
```

#### Bước 2: Start Docker containers

```bash
# Start services
docker compose up -d

# Đợi 10-15 giây để database khởi động
```

#### Bước 3: Tạo database

```bash
# Tạo database trading_db
docker compose exec timescaledb psql -U trading_user -d postgres -c "CREATE DATABASE trading_db;"

# Enable TimescaleDB extension
docker compose exec timescaledb psql -U trading_user -d trading_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

#### Bước 4: Tạo database tables

**Tạo file init_db.sql tạm thời**:
```sql
-- Copy nội dung này vào file init_db.sql
CREATE TABLE IF NOT EXISTS klines (
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

SELECT create_hypertable('klines', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_klines_symbol_timeframe ON klines (symbol, timeframe, timestamp DESC);

CREATE TABLE IF NOT EXISTS trades (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    side TEXT NOT NULL,
    PRIMARY KEY (timestamp, symbol, trade_id)
);

SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS signals (
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

CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals (timestamp DESC);

CREATE TABLE IF NOT EXISTS completed_trades (
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

CREATE INDEX IF NOT EXISTS idx_completed_trades_closed_at ON completed_trades (closed_at DESC);
```

**Chạy script tạo tables**:

**Windows PowerShell**:
```powershell
Get-Content init_db.sql | docker compose exec -T timescaledb psql -U trading_user -d trading_db
```

**Linux/macOS**:
```bash
cat init_db.sql | docker compose exec -T timescaledb psql -U trading_user -d trading_db
```

**Xóa file tạm**:
```bash
rm init_db.sql
```

#### Bước 5: Verify setup

```bash
# Test Bybit connection
docker compose exec trading_bot python scripts/test_connection_docker.py

# Kết quả mong đợi:
# ✅ Bybit client initialized
# ✅ Connected to Bybit Testnet
# ✅ Account Balance Retrieved
# ✅ Market Data Retrieved
# 🎉 All tests passed!

# Verify database tables
docker compose exec timescaledb psql -U trading_user -d trading_db -c "\dt"

# Kết quả mong đợi: 4 tables (klines, trades, signals, completed_trades)
```

</details>

---

### ✅ Sau khi setup xong

---

## ⚙️ Configuration Parameters

### File Location
```
config/strategy_params.yaml
```

### 📊 Indicator Parameters

#### SMA (Simple Moving Average)
```yaml
indicators:
  sma:
    periods: [9, 21, 50, 200]
```
- **9**: Xu hướng rất ngắn hạn (vài giờ)
- **21**: Xu hướng ngắn hạn (1-2 ngày)
- **50**: Xu hướng trung hạn (1 tuần)
- **200**: Xu hướng dài hạn (1 tháng)

**Điều chỉnh**: Giữ nguyên [9, 21, 50, 200] (an toàn)

#### EMA (Exponential Moving Average)
```yaml
indicators:
  ema:
    periods: [9, 21, 50, 200]
```
- Nhạy hơn SMA, ưu tiên giá gần đây
- **Aggressive**: [5, 13, 34, 89] (Fibonacci)

#### RSI (Relative Strength Index)
```yaml
indicators:
  rsi:
    period: 14
    overbought: 70
    oversold: 30
```
- **period**: Số nến tính RSI
- **overbought**: Vùng quá mua (>70 → có thể giảm)
- **oversold**: Vùng quá bán (<30 → có thể tăng)

**Điều chỉnh**:
- Nhạy hơn: period=9, overbought=80, oversold=20
- Chậm hơn: period=21, overbought=65, oversold=35

#### MACD
```yaml
indicators:
  macd:
    fast: 12
    slow: 26
    signal: 9
```
- MACD = EMA(12) - EMA(26)
- Signal = EMA(MACD, 9)
- MACD cắt lên Signal → Mua
- MACD cắt xuống Signal → Bán

#### Bollinger Bands
```yaml
indicators:
  bollinger:
    period: 20
    std: 2.0
```
- Upper/Lower Band = SMA ± (2 × StdDev)
- Giá chạm Upper → Quá mua
- Giá chạm Lower → Quá bán

---

### 🛡️ Risk Management Parameters

#### Max Risk Per Trade
```yaml
risk:
  max_risk_per_trade: 0.02  # 2%
```
**Công thức**:
```
Position Size = (Balance × 0.02) / Stop Loss Distance
```

**Khuyến nghị**:
- Người mới: 0.01 (1%)
- Chuẩn: 0.02 (2%)
- Nguy hiểm: >0.05 (5%)

#### Max Position Size
```yaml
risk:
  max_position_size: 0.10  # 10%
```
- Giá trị vị thế tối đa
- An toàn: 5-10%
- Nguy hiểm: >25%

#### Stop Loss
```yaml
risk:
  stop_loss_pct: 0.02              # 2% từ entry
  breakeven_threshold: 0.01        # Lời 1% → SL về breakeven
  trailing_activation: 0.02        # Lời 2% → Kích hoạt trailing
  trailing_stop_distance: 0.01     # Trailing cách 1%
```

**Quy trình**:
1. Entry → SL cách 2%
2. Lời 1% → SL về breakeven
3. Lời 2% → Trailing stop (cách 1%)
4. Giá tăng → SL theo sau

#### Kill Switch
```yaml
risk:
  kill_switch:
    max_daily_drawdown: 0.05       # 5%
    max_consecutive_losses: 5
    max_api_error_rate: 0.20       # 20%
    max_price_movement: 0.10       # 10%
```

**Kích hoạt khi**:
- Mất >5% vốn trong ngày
- Thua 5 lệnh liên tiếp
- >20% API requests lỗi
- Giá biến động >10% trong 1 phút

---

### 🔄 Execution Parameters

```yaml
execution:
  max_slippage: 0.001        # 0.1%
  max_total_cost: 0.002      # 0.2%
  order_timeout: 5           # seconds
  max_retries: 2
```

- **max_slippage**: Slippage tối đa chấp nhận
- **max_total_cost**: Tổng chi phí (slippage + commission + spread)
- **order_timeout**: Thời gian chờ limit order
- **max_retries**: Số lần retry khi fail

---

### 🎯 Signal Parameters

```yaml
signal:
  min_confidence: 60
  volume_multiplier: 1.5
  require_alignment: true
```

**Confidence Score** (0-100):
- Base: 40
- Wyckoff alignment: +20
- Order flow alignment: +20
- Volume confirmation: +10
- Multi-timeframe: +10

**Điều chỉnh**:
- Chặt chẽ: min_confidence=70 (ít tín hiệu, chất lượng cao)
- Cân bằng: min_confidence=60 (khuyến nghị)
- Nới lỏng: min_confidence=50 (nhiều tín hiệu)

---

### 📈 Order Flow & Wyckoff Parameters

```yaml
order_flow:
  window_size: 1000
  imbalance_threshold: 0.70

wyckoff:
  swing_lookback: 20
  range_contraction_threshold: 0.5
  volume_decrease_threshold: 0.7
```

**Order Flow**:
- Phân tích 1000 trades gần nhất
- Imbalance khi buy/sell >70%

**Wyckoff**:
- Phát hiện swing high/low trong 20 nến
- Detect Accumulation, Markup, Distribution, Markdown

---

### 🧪 Backtest Parameters

```yaml
backtest:
  initial_balance: 10000
  commission_rate: 0.0006    # Bybit taker 0.06%
  risk_free_rate: 0.02       # 2% cho Sharpe ratio
```

---

### 🎨 Recommended Presets

#### Người mới bắt đầu (Conservative)
```yaml
risk:
  max_risk_per_trade: 0.01
  max_position_size: 0.05
  stop_loss_pct: 0.02

signal:
  min_confidence: 70

execution:
  max_slippage: 0.001
```

#### Trader có kinh nghiệm (Balanced)
```yaml
risk:
  max_risk_per_trade: 0.02
  max_position_size: 0.10
  stop_loss_pct: 0.02

signal:
  min_confidence: 60

execution:
  max_slippage: 0.0015
```

#### Aggressive Trader
```yaml
risk:
  max_risk_per_trade: 0.03
  max_position_size: 0.15
  stop_loss_pct: 0.025

signal:
  min_confidence: 50

execution:
  max_slippage: 0.002
```

---

## 🔄 Trading Workflow

### Quy trình 3 bước (BẮT BUỘC)

```
Backtest (1-2 tuần) → Paper Trading (2-4 tuần) → Live Trading
```

### Bước 1: Backtesting

**Mục đích**: Test chiến lược trên dữ liệu lịch sử

**Quy trình**:
```bash
# 1. Download historical data
docker compose exec trading_bot python scripts/download_historical_data.py \
  --symbol BTCUSDT \
  --start-date 2024-01-01 \
  --end-date 2024-06-30

# 2. Run backtest
docker compose exec trading_bot python -c "
from src.backtest.engine import BacktestRunner
from datetime import datetime
import asyncio

async def run():
    runner = BacktestRunner(
        symbol='BTCUSDT',
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 6, 30),
        initial_balance=10000
    )
    results = await runner.run()
    print(results)

asyncio.run(run())
"

# 3. View report
# Open reports/backtest_YYYYMMDD_HHMMSS.html
```

**Tiêu chí PASS**:
- ✅ Sharpe Ratio > 1.5
- ✅ Max Drawdown < 20%
- ✅ Win Rate > 50%
- ✅ Profit Factor > 1.5
- ✅ Total Return > 0%

**Nếu FAIL**: Điều chỉnh parameters → Backtest lại

---

### Bước 2: Paper Trading

**Mục đích**: Test với real-time data, không đặt lệnh thật

**Setup**:
```bash
# Edit .env
TRADING_MODE=paper
BYBIT_TESTNET=true

# Restart
docker compose restart trading_bot
```

**Monitor**:
- Dashboard: http://localhost:8501
- Telegram alerts
- Daily review

**Duration**: Tối thiểu 2 tuần, khuyến nghị 4 tuần

**Tiêu chí PASS**:
- ✅ Sharpe Ratio > 1.0
- ✅ Max Drawdown < 25%
- ✅ Win Rate > 45%
- ✅ Không có lỗi kỹ thuật
- ✅ Kill switch không kích hoạt sai

---

### Bước 3: Live Trading

**⚠️ CẢNH BÁO**: Chỉ chuyển sang live khi PASS cả Backtest và Paper Trading

**Setup**:
```bash
# 1. Tạo Bybit Mainnet account
# 2. Nạp tiền (bắt đầu với $1000-$5000)
# 3. Tạo Mainnet API keys

# 4. Edit .env
TRADING_MODE=live
BYBIT_TESTNET=false
BYBIT_API_KEY=your_mainnet_key
BYBIT_API_SECRET=your_mainnet_secret

# 5. Restart
docker compose down
docker compose up -d
```

**Checklist trước khi start**:
- [ ] Backtest PASS
- [ ] Paper trading ≥2 tuần PASS
- [ ] API keys là Mainnet
- [ ] BYBIT_TESTNET=false
- [ ] TRADING_MODE=live
- [ ] Telegram alerts hoạt động
- [ ] Dashboard accessible

**First hour**: Ngồi trước màn hình, monitor mọi order

**First week**: Check dashboard 3 lần/ngày

---

## 📊 Using the Dashboard

### Access
```bash
# Start dashboard
docker compose --profile monitoring up -d dashboard

# Open browser
http://localhost:8501
```

### Dashboard Sections

#### 1. Trading Performance (Top Left)
- **Current Balance**: Số tiền hiện tại
- **Total Return**: % lời/lỗ
- **Win Rate**: % lệnh thắng
- **Open Positions**: Số lệnh đang mở

**Đọc**:
- Balance tăng đều → Tốt
- Win rate >50% → Tốt
- Open positions >3 → Có thể quá nhiều risk

#### 2. Equity Curve (Middle Left)
- **Equity (xanh dương)**: Balance + Unrealized P&L
- **Balance (xanh lá)**: Số tiền đã chốt
- **P&L bars**: Cột xanh (lời), cột đỏ (lỗ)

**Đọc**:
- Equity đi lên → Tốt
- Drawdown <20% → An toàn

#### 3. Recent Signals (Bottom Left)
```
🟢 BUY BTCUSDT | Confidence: 75% | Phase: MARKUP | Delta: 150.5
```
- Confidence >70 → Tín hiệu mạnh
- Confidence 60-70 → Trung bình
- Confidence <60 → Bot không trade

#### 4. System Health (Top Right)
- **API Status**: 🟢 Connected / 🔴 Down
- **Database**: 🟢 Connected / 🔴 Down
- **Error Rate**: <5% là tốt
- **Last Tick**: <60s là OK

**Cảnh báo**:
- Error rate >10% → Có vấn đề
- Last tick >60s → Không nhận data (NGUY HIỂM)

#### 5. Current Market Phase (Middle Right)
- **📦 ACCUMULATION**: Smart money đang mua
- **🚀 MARKUP**: Uptrend
- **📤 DISTRIBUTION**: Smart money đang bán
- **📉 MARKDOWN**: Downtrend
- **❓ UNKNOWN**: Không rõ pha

**Order Flow Delta**:
- Dương → Buying pressure
- Âm → Selling pressure

#### 6. Recent Errors (Bottom Right)
- 1-2 lỗi/giờ → Bình thường
- >10 lỗi/giờ → Có vấn đề

---

## 🤖 Telegram Bot Commands

### Setup

1. Tìm bot trên Telegram (username từ BotFather)
2. Gửi `/start`
3. Nếu "Unauthorized" → Chat ID chưa được thêm vào `.env`

### Commands

#### `/start`
Khởi động bot và xem danh sách commands

#### `/status`
Kiểm tra system health

**Output**:
```
✅ System Status

🟢 API: healthy
🟢 Database: healthy
📊 Error Rate: 0.50%
⏱ Uptime: 12.5 hours
```

**Khi nào dùng**:
- Mỗi sáng check 1 lần
- Khi nhận alert lỗi
- Trước khi đi ngủ

#### `/positions`
Xem open positions và unrealized P&L

**Output**:
```
📊 Open Positions

Count: 2
Unrealized P&L: $150.50

💰 Account
Balance: $10,500.00
Equity: $10,650.50
```

#### `/pnl`
Xem P&L summary và performance

**Output**:
```
💰 P&L Summary

🟢 Total P&L: $650.50
🟢 Realized: $500.00
🟢 Unrealized: $150.50

📈 Performance
Total Return: 6.51%
Win Rate: 65.0%
Total Trades: 20
```

#### `/help`
Xem danh sách commands

### Alerts

Bot tự động gửi alerts cho:

**Order Alerts**:
```
⏳ Order PENDING
✅ Order FILLED
❌ Order CANCELLED
🚫 Order REJECTED
```

**Kill Switch Alert**:
```
🚨 KILL SWITCH ACTIVATED 🚨

Reason: Daily drawdown > 5%
All trading stopped.
Manual reset required.
```

**Rate Limiting**: Maximum 10 alerts/hour (critical alerts không bị limit)

---

## 📅 Daily Operations

### Morning Routine (5 phút)
```
[ ] Check Telegram alerts từ đêm qua
[ ] /status - Check system health
[ ] /pnl - Xem P&L overnight
[ ] Mở Dashboard, check equity curve
[ ] Review recent errors (nếu có)
[ ] Verify balance khớp với Bybit
```

### Midday Check (2 phút)
```
[ ] /status
[ ] Check Dashboard system health
[ ] Verify Last Tick <60s
```

### Evening Review (10 phút)
```
[ ] /pnl - Review daily performance
[ ] Analyze equity curve
[ ] Review all trades trong ngày
[ ] Check logs: docker compose logs trading_bot | grep ERROR
[ ] Note bất thường vào journal
```

### Weekly Review (30 phút)
```
[ ] Calculate weekly P&L
[ ] Compare với backtest results
[ ] Review win rate, profit factor
[ ] Analyze worst trades
[ ] Check max drawdown
[ ] Plan adjustments (nếu cần)
```

### Monthly Review (2 giờ)
```
[ ] Calculate monthly metrics
[ ] Generate performance report
[ ] Compare với previous months
[ ] Backtest với data mới
[ ] Optimize parameters (nếu cần)
[ ] Backup database
```

---

## 🎯 Best Practices

### DO ✅
- Monitor daily
- Keep trading journal
- Backtest regularly với data mới
- Start small (10-20% vốn dự định)
- Follow process: Backtest → Paper → Live
- Enable Telegram notifications
- Backup data định kỳ
- Trust kill switch

### DON'T ❌
- Don't skip paper trading
- Don't over-optimize parameters
- Don't ignore alerts
- Don't trade manually khi bot đang chạy
- Don't disable kill switch
- Don't increase risk >2% per trade
- Don't revenge trade
- Don't trust blindly - verify mọi thứ

---

## 📊 Performance Metrics

### Target Metrics
- **Sharpe Ratio**: >1.5 là tốt
- **Max Drawdown**: <20% là an toàn
- **Win Rate**: >50% là tốt
- **Profit Factor**: >1.5 là tốt

### When to Adjust Parameters
1. Thay đổi parameter trong `config/strategy_params.yaml`
2. Backtest với 6 tháng data
3. So sánh metrics
4. Chỉ áp dụng nếu cải thiện rõ rệt

---

## 🆘 Emergency Procedures

### Kill Switch Activated

**Hành động**:
1. Đừng panic - đây là cơ chế bảo vệ
2. Check logs: `docker compose logs trading_bot | grep "Kill switch"`
3. Phân tích nguyên nhân
4. Fix issues
5. Reset: `docker compose restart trading_bot`
6. Monitor closely 1 giờ đầu

### API Connection Lost

**Hành động**:
1. Check network: `ping api.bybit.com`
2. Check Bybit status: https://status.bybit.com
3. Restart bot: `docker compose restart trading_bot`
4. Verify API keys nếu vẫn fail

### Unexpected Losses

**Hành động**:
1. **STOP TRADING**: `docker compose down`
2. Export trades: Analyze pattern
3. Review market conditions
4. Backtest lại với data gần đây
5. Adjust hoặc STOP - đừng trade khi không rõ vấn đề

---

## 📞 Support

- **Installation**: [docs/INSTALLATION_GUIDE.md](docs/INSTALLATION_GUIDE.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Development**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Docker**: [DOCKER.md](DOCKER.md)

---

## ⚠️ Final Warning

**Giao dịch cryptocurrency có rủi ro cao**

- ❌ Không phải lời khuyên tài chính
- ❌ Không đảm bảo lợi nhuận
- ✅ Chỉ dùng số vốn bạn có thể mất hoàn toàn
- ✅ Luôn test trên Testnet và Paper Trading trước
- ✅ Bắt đầu với vốn nhỏ khi Live

**Sử dụng bot là trách nhiệm của bạn!**
