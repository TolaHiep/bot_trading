# 🤖 Quantitative Trading Bot

Bot trading tự động sử dụng chiến lược Wyckoff và Scalping, tích hợp với Bybit API.

## ✨ Tính Năng

- **Dual Strategy System**
  - 🎯 **Wyckoff (Main)**: Chiến lược xu hướng chính (5m-1h timeframes)
  - ⚡ **Scalping**: Trade siêu tốc 1m với RSI, VWAP, Bollinger Bands

- **Multi-Symbol Trading**
  - Tự động scan 50-100 symbols từ Bybit
  - Capital allocation thông minh (5% per position, 80% max exposure)
  - Quản lý tối đa 16 positions đồng thời

- **Execution-Based Notifications**
  - Chỉ thông báo khi VÀO/ĐÓNG lệnh thực tế
  - Không spam tín hiệu phát hiện
  - Format đẹp với Telegram bot

- **Paper Trading**
  - Mô phỏng giao dịch với dữ liệu real-time
  - Không rủi ro tài chính
  - Slippage và commission realistic

## 🐳 Quick Start

### Bước 1: Cấu Hình

```bash
# Copy .env template
copy .env.example .env

# Edit credentials
notepad .env
```

Điền:
```env
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_IDS=your_chat_id
```

### Bước 2: Chạy Docker

```bash
docker-compose up -d
```

### Bước 3: Kiểm Tra

```bash
# Check logs
docker-compose logs -f trading_bot

# Check status
docker-compose ps
```

### Bước 4: Test Telegram

Mở Telegram, gửi:
```
/start
/status
/positions
```

## 📊 Services

Khi chạy `docker-compose up -d`, các services sau sẽ tự động khởi động:

| Service | Port | Mô Tả |
|---------|------|-------|
| **trading_bot** | - | Main trading bot |
| **telegram_bot** | - | Telegram alerts & commands |
| **dashboard** | 8501 | Streamlit monitoring UI |
| **timescaledb** | 5432 | TimescaleDB database |

## 📱 Telegram Bot Commands

```
/status    - Dashboard sức khỏe bot
/positions - Lệnh đang Hold hiện tại
/pnl       - Quản lý tài chính tổng quát
/scalp     - Thống kê bot Scalping
/wyckoff   - Thống kê bot Wyckoff (Main)
/help      - Hướng dẫn sử dụng
```

## 🌐 Dashboard

Truy cập: http://localhost:8501

## ⚙️ Cấu Hình

### Trading Config

File: `config/config.yaml`

```yaml
symbol: BTCUSDT
initial_balance: 100

multi_symbol:
  enabled: true
  volume_threshold: 10000000

scalping:
  enabled: true
  risk_per_trade: 0.01
```

### Chọn Strategy

Edit `config/config.yaml`:

```yaml
# Bật/tắt Multi-Symbol
multi_symbol:
  enabled: true  # true/false

# Bật/tắt Scalping
scalping:
  enabled: true  # true/false
```

Sau đó restart:
```bash
docker-compose restart trading_bot
```

## 🔧 Quản Lý

### Xem Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f trading_bot
docker-compose logs -f telegram_bot
```

### Restart

```bash
# All services
docker-compose restart

# Specific service
docker-compose restart trading_bot
```

### Stop

```bash
docker-compose down
```

### Rebuild (sau khi sửa code)

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 📊 Notification System

**Execution-Based Alerts:**

✅ **Vào Lệnh**
```
🟢 OPENED BUY • SCALP
BTCUSDT × 0.010000
Entry: $50,010.00
Size: $500.10
```

🏁 **Đóng Lệnh**
```
🟢 CLOSED BUY • MAIN
ETHUSDT × 0.500000
Exit: $3,850.25 • Take Profit
P&L: +15.50 USDT (+3.10%)
```

## 🏗️ Kiến Trúc

```
src/
├── alpha/           # Signal generators (Wyckoff, Scalping)
├── connectors/      # Bybit WebSocket & REST API
├── core/            # Trading loops & multi-symbol manager
├── execution/       # Paper trader & order management
├── risk/            # Position sizing & risk management
└── monitoring/      # Telegram bot & metrics
```

## 📈 Performance Tracking

Metrics được export vào `logs/metrics.json`:

```json
{
  "strategies": {
    "scalp": {
      "total_trades": 5,
      "win_rate": 60.0,
      "realized_pnl": 12.50
    },
    "main": {
      "total_trades": 10,
      "win_rate": 70.0,
      "realized_pnl": 45.80
    }
  }
}
```

## 🛠️ Tech Stack

- **Python 3.11+**
- **Docker & Docker Compose**
- **Bybit API v5** (WebSocket & REST)
- **TimescaleDB** (Time-series database)
- **python-telegram-bot** (Notifications)
- **Streamlit** (Dashboard)
- **pandas & numpy** (Data processing)

## ⚠️ Important Notes

- Bot runs in **Paper Trading** mode (simulated with real market data)
- Uses **real Bybit API** for market data
- **No real money at risk** - all trades are simulated
- Data is real-time from Bybit Mainnet

## 🆘 Troubleshooting

### Docker không chạy

```bash
# Check Docker Desktop
docker --version
docker ps
```

### Service lỗi

```bash
# Check logs
docker-compose logs trading_bot

# Restart
docker-compose restart trading_bot
```

### Telegram bot không phản hồi

1. Check TELEGRAM_BOT_TOKEN trong .env
2. Check TELEGRAM_CHAT_IDS trong .env
3. Gửi /start cho bot
4. Restart: `docker-compose restart telegram_bot`

### Database connection error

```bash
# Check database
docker-compose logs timescaledb

# Restart database
docker-compose restart timescaledb
```

## 📚 Documentation

- [START_HERE_DOCKER.md](START_HERE_DOCKER.md) - Quick start guide
- [docker-compose.yml](docker-compose.yml) - Services configuration
- [Dockerfile](Dockerfile) - Image build configuration

## 📄 License

MIT License - Xem [LICENSE](LICENSE) để biết thêm chi tiết.

---

**Happy Trading! 🚀**
