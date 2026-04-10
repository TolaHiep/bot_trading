# 🚀 Quick Start Guide - Trading Bot

## Yêu cầu hệ thống

- **Windows 10/11** (64-bit)
- **Docker Desktop** (phải cài đặt trước)
- **8GB RAM** tối thiểu
- **Kết nối Internet** ổn định

---

## 📦 Cài đặt trên máy mới (5 phút)

### Bước 1: Cài đặt Docker Desktop

1. Tải Docker Desktop: https://www.docker.com/products/docker-desktop
2. Cài đặt và khởi động Docker Desktop
3. Đợi Docker khởi động hoàn tất (icon Docker màu xanh)

### Bước 2: Tải code về máy

```bash
# Clone repository hoặc copy folder vào máy
cd D:\My_Project\Trading_bot
```

### Bước 3: Chạy setup

```bash
# Double-click file setup.bat
# Hoặc chạy trong Command Prompt:
setup.bat
```

Script sẽ tự động:
- ✅ Kiểm tra Docker
- ✅ Tạo file `.env`
- ✅ Tạo thư mục logs, reports
- ✅ Tạo các script tiện ích (start.bat, stop.bat, etc.)

### Bước 4: Cấu hình API Keys

Mở file `.env` và điền thông tin:

```env
# 1. Bybit API Keys (bắt buộc)
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# 2. Telegram Bot (bắt buộc)
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHAT_IDS=123456789

# 3. Database (có thể giữ nguyên)
POSTGRES_PASSWORD=secure_password_123
```

#### 🔑 Lấy Bybit API Keys:

1. Vào: https://www.bybit.com/app/user/api-management
2. Click "Create New Key" → "System-generated API Keys"
3. Đặt tên: `Trading Bot`
4. Permissions: **Read-Write** (cho paper trading)
5. Copy API Key và Secret → paste vào `.env`

#### 🤖 Lấy Telegram Bot Token:

1. Mở Telegram → tìm `@BotFather`
2. Gửi: `/newbot`
3. Đặt tên bot (ví dụ: `My Trading Bot`)
4. Đặt username (ví dụ: `my_trading_bot`)
5. Copy token → paste vào `.env`

#### 💬 Lấy Telegram Chat ID:

1. Mở Telegram → tìm `@userinfobot`
2. Gửi: `/start`
3. Copy ID (số) → paste vào `.env`

### Bước 5: Khởi động bot

```bash
# Double-click file start.bat
# Hoặc:
start.bat
```

Bot sẽ:
- 🔨 Build Docker containers (lần đầu ~5 phút)
- 🚀 Khởi động 3 bots (Wyckoff, Scalp V1, Scalp V2)
- 📱 Kết nối Telegram
- 📊 Mở Dashboard tại http://localhost:8501

### Bước 6: Test Telegram

1. Mở Telegram
2. Tìm bot của bạn (username đã tạo)
3. Gửi: `/start`
4. Gửi: `/all` để xem tổng hợp 3 bots

---

## 🎮 Các lệnh thường dùng

### Windows Scripts (double-click)

- **start.bat** - Khởi động bot
- **stop.bat** - Dừng bot
- **restart.bat** - Khởi động lại
- **logs.bat** - Xem logs
- **status.bat** - Kiểm tra trạng thái

### Telegram Commands

```
/all          - Báo cáo tổng hợp cả 3 bot
/wyckoff      - Báo cáo bot Wyckoff
/wyckoff_pos  - Lệnh đang chạy Wyckoff
/scalp        - Báo cáo bot Scalping V1
/scalp_pos    - Lệnh đang chạy Scalp V1
/scalp_v2     - Báo cáo bot Scalping V2
/scalp_v2_pos - Lệnh đang chạy Scalp V2
/status       - Trạng thái hệ thống
/help         - Hướng dẫn
```

### Docker Commands (nâng cao)

```bash
# Xem logs realtime
docker logs -f trading_bot_app

# Xem logs Telegram
docker logs -f trading_bot_telegram

# Xem tất cả containers
docker-compose ps

# Rebuild sau khi sửa code
docker-compose down
docker-compose build
docker-compose up -d

# Xóa tất cả và reset
docker-compose down -v
```

---

## 📊 Dashboard

Mở trình duyệt: http://localhost:8501

Dashboard hiển thị:
- 📈 Biểu đồ giá realtime
- 💰 Portfolio performance
- 📊 Open positions
- 📉 P&L charts
- 📋 Trade history

---

## 🔧 Cấu hình nâng cao

### Thay đổi symbols

Sửa file `config/config.yaml`:

```yaml
# Single symbol
symbol: BTCUSDT

# Multi-symbol
multi_symbol:
  enabled: true
  symbols:
    - BTCUSDT
    - ETHUSDT
    - SOLUSDT
```

### Thay đổi risk settings

```yaml
risk:
  risk_per_trade: 0.02  # 2% per trade
  max_positions: 3
  max_drawdown_pct: 0.15  # 15% max drawdown
```

### Thay đổi leverage

```yaml
scalping:
  risk:
    leverage: 20.0  # 20x leverage
    risk_per_trade: 0.05  # 5% per trade
```

---

## ⚠️ Lưu ý quan trọng

### Paper Trading (Mặc định)

- ✅ **An toàn**: Không mất tiền thật
- ✅ **Dữ liệu thật**: Giá từ Bybit mainnet
- ✅ **Test chiến lược**: Thử nghiệm không rủi ro
- ⚠️ **Không có lợi nhuận thật**: Chỉ là mô phỏng

### Live Trading (KHÔNG khuyến khích)

- ⚠️ **Rủi ro cao**: Có thể mất tiền
- ⚠️ **Chưa test đầy đủ**: Bot vẫn đang phát triển
- ⚠️ **Cần kinh nghiệm**: Hiểu rõ trading và risk management
- 🚫 **KHÔNG bật** nếu chưa hiểu rõ

### Bảo mật

- 🔒 **Không share API keys**: Giữ bí mật
- 🔒 **Bật IP whitelist**: Trên Bybit API settings
- 🔒 **Không commit .env**: File này chứa secrets
- 🔒 **Backup thường xuyên**: Logs và reports

---

## 🐛 Xử lý lỗi thường gặp

### Bot không khởi động

```bash
# Kiểm tra Docker đang chạy
docker --version

# Kiểm tra containers
docker-compose ps

# Xem logs lỗi
docker logs trading_bot_app
```

### Telegram không nhận lệnh

1. Kiểm tra `TELEGRAM_BOT_TOKEN` đúng chưa
2. Kiểm tra `TELEGRAM_CHAT_IDS` đúng chưa
3. Đảm bảo đã gửi `/start` cho bot
4. Xem logs: `docker logs trading_bot_telegram`

### API connection failed

1. Kiểm tra `BYBIT_API_KEY` và `BYBIT_API_SECRET`
2. Kiểm tra API permissions (Read-Write)
3. Kiểm tra IP whitelist (nếu có)
4. Kiểm tra kết nối Internet

### Database error

```bash
# Reset database
docker-compose down -v
docker-compose up -d
```

---

## 📁 Cấu trúc thư mục

```
Trading_bot/
├── .env                    # API keys (TỰ TẠO)
├── .env.example           # Template
├── setup.bat              # Setup script
├── start.bat              # Start bot
├── stop.bat               # Stop bot
├── logs.bat               # View logs
├── restart.bat            # Restart bot
├── status.bat             # Check status
├── docker-compose.yml     # Docker config
├── config/
│   └── config.yaml        # Bot settings
├── logs/                  # Log files
│   ├── metrics.json
│   ├── metrics_wyckoff.json
│   ├── metrics_scalp.json
│   └── metrics_scalp_v2.json
├── reports/               # Liquidation reports
│   └── liquidations/
└── src/                   # Source code
```

---

## 📞 Hỗ trợ

### Logs quan trọng

```bash
# Trading bot logs
docker logs -f trading_bot_app

# Telegram bot logs
docker logs -f trading_bot_telegram

# All logs
docker-compose logs -f
```

### Metrics files

- `logs/metrics_wyckoff.json` - Wyckoff bot metrics
- `logs/metrics_scalp.json` - Scalp V1 metrics
- `logs/metrics_scalp_v2.json` - Scalp V2 metrics
- `logs/metrics_*_positions.json` - Position details

### Liquidation reports

- `reports/liquidations/wyckoff/` - Wyckoff liquidations
- `reports/liquidations/scalp/` - Scalp V1 liquidations
- `reports/liquidations/scalp_v2/` - Scalp V2 liquidations

---

## ✅ Checklist cài đặt

- [ ] Docker Desktop đã cài và chạy
- [ ] Đã chạy `setup.bat`
- [ ] Đã điền Bybit API keys vào `.env`
- [ ] Đã điền Telegram bot token vào `.env`
- [ ] Đã điền Telegram chat ID vào `.env`
- [ ] Đã chạy `start.bat`
- [ ] Đã gửi `/start` cho bot trên Telegram
- [ ] Đã test lệnh `/all` trên Telegram
- [ ] Dashboard mở được tại http://localhost:8501

---

## 🎯 Bước tiếp theo

1. **Theo dõi bot 24h đầu**: Xem bot hoạt động như thế nào
2. **Đọc docs**: `docs/LIQUIDATION_HANDLING.md`, `docs/SCALPING_STRATEGY.md`
3. **Tùy chỉnh config**: Thay đổi symbols, risk settings
4. **Backup thường xuyên**: Logs và reports
5. **Monitor performance**: Qua Telegram và Dashboard

---

**Chúc bạn trading thành công! 🚀📈**
