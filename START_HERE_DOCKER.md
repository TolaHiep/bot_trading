# 🐳 Start Here - Docker Guide

## 📋 Bước 1: Cấu Hình .env

```bash
copy .env.example .env
notepad .env
```

Điền credentials:
```env
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_IDS=your_chat_id
```

## 🐳 Bước 2: Chạy Docker

```bash
docker-compose up -d
```

Tất cả services sẽ tự động chạy:
- ✅ TimescaleDB (Database)
- ✅ Trading Bot (Main)
- ✅ Telegram Bot (Alerts)
- ✅ Dashboard (Monitoring)

## 📊 Bước 3: Kiểm Tra

### Check logs
```bash
docker-compose logs -f trading_bot
docker-compose logs -f telegram_bot
```

### Check status
```bash
docker-compose ps
```

### Test Telegram
Mở Telegram, gửi:
```
/start
/status
```

## 🌐 Bước 4: Truy Cập Dashboard

Mở browser: http://localhost:8501

## 🔧 Quản Lý

### Dừng tất cả
```bash
docker-compose down
```

### Restart
```bash
docker-compose restart
```

### Xem logs
```bash
docker-compose logs -f
```

### Rebuild (sau khi sửa code)
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

## ⚙️ Chọn Mode Trading

Edit `docker-compose.yml`, tìm dòng `command:` trong service `trading_bot`:

```yaml
# 1. Paper Trading với Live data (KHUYẾN NGHỊ)
command: python scripts/run_live_paper_trading.py

# 2. Paper Trading với Mainnet data
# command: python scripts/run_paper_trading_mainnet.py

# 3. Testnet Trading
# command: python scripts/run_testnet_trading.py
```

Sau đó:
```bash
docker-compose restart trading_bot
```

## 📁 Cấu Trúc

```
Trading_bot/
├── docker-compose.yml    ← Cấu hình services
├── Dockerfile            ← Build image
├── .env                  ← Credentials
└── config/
    └── config.yaml       ← Trading config
```

## ⚠️ Lưu Ý

- **Không cần cài Python local** - Docker lo hết
- **Không cần setup.bat** - Docker tự cài dependencies
- **Không cần run.bat** - Docker tự chạy
- Chỉ cần Docker Desktop đang chạy

## 🆘 Troubleshooting

### Docker không chạy
```bash
# Check Docker Desktop đang chạy
docker --version
docker ps
```

### Service lỗi
```bash
# Check logs
docker-compose logs trading_bot
docker-compose logs telegram_bot

# Restart
docker-compose restart
```

### Rebuild sau khi sửa code
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Happy Trading! 🚀**
