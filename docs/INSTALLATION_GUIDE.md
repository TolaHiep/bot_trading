# Installation Guide - Quantitative Trading Bot

## Mục lục
1. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
2. [Cài đặt Dependencies](#cài-đặt-dependencies)
3. [Clone và Setup Project](#clone-và-setup-project)
4. [Cấu hình môi trường](#cấu-hình-môi-trường)
5. [Khởi động hệ thống](#khởi-động-hệ-thống)
6. [Kiểm tra hoạt động](#kiểm-tra-hoạt-động)
7. [Xử lý sự cố](#xử-lý-sự-cố)

---

## Yêu cầu hệ thống

### Phần cứng tối thiểu
- **CPU**: 4 cores (khuyến nghị 8 cores cho grid search)
- **RAM**: 8GB (khuyến nghị 16GB)
- **Disk**: 50GB SSD (cho TimescaleDB và logs)
- **Network**: Kết nối internet ổn định (< 100ms latency đến Bybit)

### Phần mềm cần thiết
- **Docker Desktop**: Version 20.10+ ([Download](https://www.docker.com/products/docker-desktop))
- **Docker Compose**: Version 2.0+ (đi kèm Docker Desktop)
- **Git**: Version 2.30+ ([Download](https://git-scm.com/downloads))
- **Python**: 3.11+ (optional, cho local development)

### Hệ điều hành hỗ trợ
- ✅ Windows 10/11 (WSL2 enabled)
- ✅ macOS 11+ (Intel hoặc Apple Silicon)
- ✅ Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)

---

## Cài đặt Dependencies

### 1. Cài đặt Docker Desktop

#### Windows
```powershell
# Download Docker Desktop từ https://www.docker.com/products/docker-desktop
# Chạy installer và làm theo hướng dẫn
# Khởi động lại máy sau khi cài đặt

# Kiểm tra cài đặt
docker --version
docker compose version
```

#### macOS
```bash
# Download Docker Desktop từ https://www.docker.com/products/docker-desktop
# Kéo Docker.app vào Applications
# Mở Docker từ Applications

# Kiểm tra cài đặt
docker --version
docker compose version
```

#### Linux (Ubuntu/Debian)
```bash
# Cài đặt Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Thêm user vào docker group
sudo usermod -aG docker $USER
newgrp docker

# Cài đặt Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Kiểm tra cài đặt
docker --version
docker compose version
```

### 2. Cài đặt Git

#### Windows
```powershell
# Download Git từ https://git-scm.com/download/win
# Chạy installer với cấu hình mặc định
git --version
```

#### macOS
```bash
# Sử dụng Homebrew
brew install git

# Hoặc download từ https://git-scm.com/download/mac
git --version
```

#### Linux
```bash
sudo apt-get update
sudo apt-get install git
git --version
```

---

## Clone và Setup Project

### 1. Clone Repository

```bash
# Clone project từ GitHub
git clone https://github.com/TolaHiep/bot_trading.git
cd bot_trading

# Kiểm tra branch
git branch
# Nên thấy: * master
```

### 2. Kiểm tra cấu trúc thư mục

```bash
# Liệt kê các thư mục chính
ls -la

# Nên thấy:
# - config/          (Configuration files)
# - src/             (Source code)
# - tests/           (Test files)
# - docker-compose.yml
# - requirements.txt
# - .env.example
```

---

## Cấu hình môi trường

### 1. Tạo file .env

```bash
# Copy từ template
cp .env.example .env

# Chỉnh sửa file .env
nano .env  # hoặc notepad .env trên Windows
```

### 2. Cấu hình Bybit API

**Bước 1: Tạo Bybit Testnet Account**
1. Truy cập: https://testnet.bybit.com
2. Đăng ký tài khoản mới
3. Xác thực email

**Bước 2: Tạo API Keys**
1. Đăng nhập Testnet
2. Vào **API Management** → **Create New Key**
3. Chọn quyền:
   - ✅ Read-Write
   - ✅ Contract Trading
   - ✅ Wallet
4. Copy **API Key** và **Secret Key**

**Bước 3: Cập nhật .env**
```bash
# Bybit API Configuration
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_secret_key_here
BYBIT_TESTNET=true

# Database Configuration
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=trading_db
POSTGRES_HOST=timescaledb
POSTGRES_PORT=5432

# Trading Configuration
TRADING_MODE=paper
INITIAL_BALANCE=10000

# Telegram Bot (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Cấu hình Telegram Bot (Optional)

**Bước 1: Tạo Bot**
1. Mở Telegram, tìm **@BotFather**
2. Gửi `/newbot`
3. Đặt tên bot (ví dụ: "My Trading Bot")
4. Đặt username (ví dụ: "my_trading_bot")
5. Copy **Bot Token**

**Bước 2: Lấy Chat ID**
1. Mở bot vừa tạo, gửi `/start`
2. Truy cập: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Tìm `"chat":{"id":123456789}` → Copy số này

**Bước 3: Cập nhật .env**
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## Khởi động hệ thống

### 1. Build Docker Images

```bash
# Build tất cả services
docker compose build

# Quá trình này mất 5-10 phút lần đầu
# Sẽ thấy:
# - Building trading_bot...
# - Building timescaledb...
```

### 2. Khởi động Services

```bash
# Khởi động tất cả containers
docker compose up -d

# Kiểm tra status
docker compose ps

# Nên thấy:
# NAME                STATUS              PORTS
# trading_bot_app     Up 10 seconds       
# trading_bot_db      Up 10 seconds (healthy)  0.0.0.0:5432->5432/tcp
```

### 3. Kiểm tra Logs

```bash
# Xem logs của trading bot
docker compose logs -f trading_bot

# Xem logs của database
docker compose logs -f timescaledb

# Dừng xem logs: Ctrl+C
```

### 4. Chạy Database Migrations

```bash
# Tạo database schema
docker compose exec trading_bot python -c "
from src.data.timescaledb_writer import TimescaleDBWriter
import asyncio

async def init_db():
    writer = TimescaleDBWriter()
    await writer.connect()
    await writer.create_tables()
    print('Database initialized successfully')

asyncio.run(init_db())
"
```

---

## Kiểm tra hoạt động

### 1. Kiểm tra kết nối Database

```bash
# Kết nối vào database
docker compose exec timescaledb psql -U trading_user -d trading_db

# Chạy query test
SELECT version();
\dt  # Liệt kê tables
\q   # Thoát
```

### 2. Chạy Unit Tests

```bash
# Chạy tất cả tests
docker compose exec trading_bot pytest tests/unit/ -v

# Nên thấy: XXX passed in X.XXs
```

### 3. Kiểm tra Bybit Connection

```bash
# Test kết nối Bybit API
docker compose exec trading_bot python scripts/test_connection_docker.py

# Nên thấy:
# ✓ Bybit REST API connected
# ✓ Account balance: $10000
```

### 4. Truy cập Dashboard

```bash
# Khởi động Streamlit dashboard
docker compose exec trading_bot streamlit run src/monitoring/dashboard.py --server.port 8501

# Mở browser: http://localhost:8501
```

---

## Xử lý sự cố

### Lỗi: Docker daemon not running

**Triệu chứng:**
```
Cannot connect to the Docker daemon
```

**Giải pháp:**
1. Mở Docker Desktop
2. Đợi Docker khởi động hoàn toàn (icon Docker màu xanh)
3. Chạy lại lệnh

### Lỗi: Port already in use

**Triệu chứng:**
```
Error: bind: address already in use
```

**Giải pháp:**
```bash
# Tìm process đang dùng port
# Windows
netstat -ano | findstr :5432

# Linux/Mac
lsof -i :5432

# Kill process hoặc đổi port trong docker-compose.yml
```

### Lỗi: Database connection failed

**Triệu chứng:**
```
psycopg2.OperationalError: could not connect to server
```

**Giải pháp:**
```bash
# Kiểm tra database container
docker compose ps timescaledb

# Nếu không healthy, restart
docker compose restart timescaledb

# Đợi 30 giây cho database khởi động
sleep 30
```

### Lỗi: Bybit API authentication failed

**Triệu chứng:**
```
APIError: Invalid API key
```

**Giải pháp:**
1. Kiểm tra API key trong `.env`
2. Đảm bảo `BYBIT_TESTNET=true`
3. Tạo lại API key trên Bybit Testnet
4. Restart container: `docker compose restart trading_bot`

### Lỗi: Out of memory

**Triệu chứng:**
```
MemoryError: Unable to allocate array
```

**Giải pháp:**
1. Tăng memory cho Docker Desktop (Settings → Resources → Memory)
2. Khuyến nghị: 8GB minimum
3. Restart Docker Desktop

---

## Các lệnh hữu ích

### Quản lý Containers

```bash
# Khởi động
docker compose up -d

# Dừng
docker compose down

# Restart
docker compose restart

# Xem logs
docker compose logs -f [service_name]

# Vào container shell
docker compose exec trading_bot bash
```

### Quản lý Database

```bash
# Backup database
docker compose exec timescaledb pg_dump -U trading_user trading_db > backup.sql

# Restore database
docker compose exec -T timescaledb psql -U trading_user trading_db < backup.sql

# Xóa tất cả data
docker compose down -v
```

### Development

```bash
# Chạy tests
docker compose exec trading_bot pytest tests/ -v

# Chạy specific test
docker compose exec trading_bot pytest tests/unit/test_indicators.py -v

# Code coverage
docker compose exec trading_bot pytest tests/ --cov=src --cov-report=html

# Linting
docker compose exec trading_bot flake8 src/
```

---

## Next Steps

Sau khi cài đặt thành công:

1. ✅ Đọc [Parameter Dictionary](PARAMETER_DICTIONARY.md) để hiểu các thông số
2. ✅ Đọc [Operational Manual](OPERATIONAL_MANUAL.md) để học cách vận hành
3. ✅ Chạy backtest đầu tiên
4. ✅ Thử paper trading
5. ✅ Chỉ chuyển sang live khi đã test kỹ

---

## Hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra [Troubleshooting Guide](TROUBLESHOOTING.md)
2. Xem logs: `docker compose logs -f`
3. Tạo issue trên GitHub với logs đầy đủ
