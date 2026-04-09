# Hướng Dẫn Chuẩn Bị Tài Nguyên - Quantitative Trading Bot

## Tổng Quan

Tài liệu này hướng dẫn chi tiết các bước chuẩn bị môi trường và tài nguyên cần thiết để bắt đầu phát triển Quantitative Trading Bot.

---

## 1. Yêu Cầu Hệ Thống

### Phần Cứng Tối Thiểu
- **CPU**: 4 cores (khuyến nghị 8 cores cho grid search)
- **RAM**: 8GB (khuyến nghị 16GB)
- **Storage**: 50GB SSD (cho TimescaleDB và historical data)
- **Network**: Kết nối internet ổn định (latency < 100ms đến Bybit)

### Hệ Điều Hành
- **Windows**: Windows 10/11 (với WSL2 cho Docker)
- **macOS**: macOS 10.15+
- **Linux**: Ubuntu 20.04+ / Debian 11+ (khuyến nghị)

---

## 2. Cài Đặt Phần Mềm Cơ Bản

### 2.1 Python 3.11+

**Windows**:
```powershell
# Download từ python.org
# Hoặc dùng Chocolatey
choco install python --version=3.11.0
```

**macOS**:
```bash
# Dùng Homebrew
brew install python@3.11
```

**Linux**:
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

**Verify**:
```bash
python3.11 --version
# Output: Python 3.11.x
```

### 2.2 Docker & Docker Compose

**Windows**:
1. Download Docker Desktop từ [docker.com](https://www.docker.com/products/docker-desktop)
2. Install và enable WSL2 backend
3. Restart máy

**macOS**:
```bash
brew install --cask docker
```

**Linux**:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Verify**:
```bash
docker --version
docker compose version
```

### 2.3 Git

**Windows**:
```powershell
choco install git
```

**macOS**:
```bash
brew install git
```

**Linux**:
```bash
sudo apt install git
```

**Verify**:
```bash
git --version
```

### 2.4 Code Editor

**Khuyến nghị**: Visual Studio Code
```bash
# Windows
choco install vscode

# macOS
brew install --cask visual-studio-code

# Linux
sudo snap install code --classic
```

**Extensions cần thiết**:
- Python (Microsoft)
- Docker (Microsoft)
- YAML (Red Hat)
- GitLens
- Pylance

---

## 3. Tạo Tài Khoản Bybit Testnet

### 3.1 Đăng Ký Testnet

1. Truy cập [testnet.bybit.com](https://testnet.bybit.com)
2. Click "Sign Up" ở góc trên phải
3. Đăng ký với email (không cần KYC)
4. Verify email
5. Đăng nhập vào Testnet

### 3.2 Nhận Test Coins Miễn Phí

1. Sau khi đăng nhập Testnet, click vào **Assets** (góc trên phải)
2. Chọn **Assets Overview**
3. Click **Request Test Coins**
4. Một popup sẽ xuất hiện, click **Request** để confirm
5. Bạn sẽ nhận ngay:
   - **10,000 USDT** (Testnet)
   - **1 BTC** (Testnet)
6. Test coins được deposit vào **Spot Account**

**Lưu ý quan trọng**:
- Chỉ có thể request **1 lần mỗi 24 giờ**
- 24 giờ được tính từ lần request cuối cùng
- Nếu cần trade coins khác, dùng Testnet Spot Trading hoặc Convert
- **KHÔNG BAO GIỜ** deposit tiền thật vào Testnet account (sẽ mất vĩnh viễn)

### 3.3 Transfer USDT sang Unified Trading Account (Để Trade Futures)

**Quan trọng**: Test coins được deposit vào Spot Account, nhưng để trade **USDT Perpetual Futures**, bạn cần transfer sang **Unified Trading Account**.

**Các bước transfer**:

1. Vào **Assets** (góc trên phải) → Chọn **Spot Account**
2. Tìm dòng **USDT** trong danh sách
3. Click **Transfer** ở cột bên phải
4. Trong popup Transfer:
   - **From**: Spot Account
   - **To**: Unified Trading Account
   - **Coin**: USDT
   - **Amount**: 10000 (hoặc số tiền bạn muốn transfer)
5. Click **Confirm**
6. Transfer hoàn tất ngay lập tức (< 10 giây)

**Verify Transfer**:
1. Vào **Assets** → **Unified Trading Account**
2. Bạn sẽ thấy 10,000 USDT available
3. Bây giờ bạn có thể trade **Derivatives** → **USDT Perpetual** (BTCUSDT, ETHUSDT, etc.)

**Lưu ý**:
- Unified Trading Account cho phép trade cả Spot, Futures, và Options
- Bạn có thể transfer ngược lại từ Unified → Spot bất cứ lúc nào
- Không mất phí transfer giữa các accounts

### 3.4 Tạo API Key

1. Vào **Account & Security** → **API Management**
2. Click **Create New Key**
3. Chọn **System-generated API Keys**
4. Cấu hình quyền:
   - ✅ **Read-Write** cho **Contract** (Derivatives/Futures)
   - ✅ **Read-Write** cho **Spot** (nếu cần)
   - ❌ **Withdraw** (KHÔNG cần)
5. Click **Submit**
6. **LƯU LẠI**:
   - API Key
   - API Secret
   - **QUAN TRỌNG**: Không chia sẻ API Secret với ai!

**Lưu ý**: API Key cho phép bot đặt lệnh trên Unified Trading Account (bao gồm cả Spot và Derivatives/Futures).

### 3.5 Lưu API Credentials

Tạo file `.env` (KHÔNG commit lên Git):
```bash
# Bybit Testnet API
BYBIT_API_KEY=your_testnet_api_key_here
BYBIT_API_SECRET=your_testnet_api_secret_here
BYBIT_TESTNET=true

# Database
DATABASE_URL=postgresql://trading_user:trading_pass@localhost:5432/trading_bot

# Telegram Bot (tạo sau)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_IDS=

# Trading Mode
TRADING_MODE=testnet  # testnet | paper | live
LOG_LEVEL=INFO
```

---

## 4. Tạo Telegram Bot (Optional nhưng khuyến nghị)

### 4.1 Tạo Bot với BotFather

1. Mở Telegram, tìm **@BotFather**
2. Gửi `/newbot`
3. Đặt tên bot (ví dụ: "My Trading Bot")
4. Đặt username (phải kết thúc bằng "bot", ví dụ: "my_trading_bot")
5. **LƯU LẠI** Bot Token (dạng: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 4.2 Lấy Chat ID

1. Gửi message bất kỳ cho bot của bạn
2. Truy cập: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Tìm `"chat":{"id":123456789}` trong response
4. **LƯU LẠI** Chat ID

### 4.3 Cập Nhật .env

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_IDS=123456789,987654321  # Có thể nhiều chat IDs, phân cách bằng dấu phẩy
```

---

## 5. Cài Đặt Dependencies Python

### 5.1 Tạo Virtual Environment

```bash
# Tạo project directory
mkdir quantitative-trading-bot
cd quantitative-trading-bot

# Tạo virtual environment
python3.11 -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 5.2 Tạo requirements.txt

```txt
# Core
python-dotenv==1.0.0

# Bybit API
pybit==5.7.0

# Data Processing
pandas==2.1.4
numpy==1.26.2
pandas-ta==0.3.14b

# Database
asyncpg==0.29.0
psycopg2-binary==2.9.9

# JSON Parsing
ujson==5.9.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
hypothesis==6.92.1
pytest-cov==4.1.0

# Configuration
pyyaml==6.0.1

# Monitoring
streamlit==1.29.0
plotly==5.18.0
python-telegram-bot==21.0

# Utilities
ntplib==0.4.0
aiohttp==3.9.1

# Type Checking
mypy==1.7.1

# Code Quality
black==23.12.1
flake8==6.1.0
isort==5.13.2
```

### 5.3 Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Verify**:
```bash
pip list | grep pybit
# Output: pybit 5.7.0
```

---

## 6. Cài Đặt TimescaleDB

### 6.1 Sử Dụng Docker (Khuyến nghị)

Tạo `docker-compose.yml`:
```yaml
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    container_name: trading_bot_db
    environment:
      POSTGRES_USER: trading_user
      POSTGRES_PASSWORD: trading_pass
      POSTGRES_DB: trading_bot
    ports:
      - "5432:5432"
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  timescaledb_data:
```

**Start Database**:
```bash
docker compose up -d timescaledb
```

**Verify**:
```bash
docker compose ps
# timescaledb should be "Up"

# Test connection
docker exec -it trading_bot_db psql -U trading_user -d trading_bot -c "SELECT version();"
```

### 6.2 Cài Đặt Trực Tiếp (Alternative)

**Ubuntu/Debian**:
```bash
# Add TimescaleDB repository
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -

# Install
sudo apt update
sudo apt install timescaledb-2-postgresql-15

# Configure
sudo timescaledb-tune

# Restart PostgreSQL
sudo systemctl restart postgresql
```

---

## 7. Cấu Trúc Project

### 7.1 Tạo Cấu Trúc Thư Mục

```bash
mkdir -p src/{connectors,data,alpha,risk,execution,backtest,monitoring,config}
mkdir -p tests/{unit,property,integration,backtest}
mkdir -p config
mkdir -p scripts
mkdir -p reports
mkdir -p logs
```

### 7.2 Tạo __init__.py Files

```bash
# Create __init__.py in all Python packages
touch src/__init__.py
touch src/connectors/__init__.py
touch src/data/__init__.py
touch src/alpha/__init__.py
touch src/risk/__init__.py
touch src/execution/__init__.py
touch src/backtest/__init__.py
touch src/monitoring/__init__.py
touch src/config/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/property/__init__.py
touch tests/integration/__init__.py
touch tests/backtest/__init__.py
```

### 7.3 Tạo .gitignore

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/
.hypothesis/

# Logs
logs/
*.log

# Database
*.db
*.sqlite

# OS
.DS_Store
Thumbs.db

# Reports
reports/*.pdf
reports/*.html

# Temporary
tmp/
temp/
EOF
```

---

## 8. Kiểm Tra Kết Nối Bybit

### 8.1 Test Script

Tạo `test_bybit_connection.py`:
```python
import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Load environment variables
load_dotenv()

# Initialize client
session = HTTP(
    testnet=True,
    api_key=os.getenv('BYBIT_API_KEY'),
    api_secret=os.getenv('BYBIT_API_SECRET')
)

# Test connection
try:
    # Get server time
    server_time = session.get_server_time()
    print(f"✅ Connected to Bybit Testnet")
    print(f"Server Time: {server_time}")
    
    # Get account balance
    balance = session.get_wallet_balance(accountType="UNIFIED")
    print(f"✅ Account Balance Retrieved")
    print(f"Balance: {balance}")
    
    # Get ticker
    ticker = session.get_tickers(category="linear", symbol="BTCUSDT")
    print(f"✅ Market Data Retrieved")
    print(f"BTC Price: {ticker['result']['list'][0]['lastPrice']}")
    
    print("\n🎉 All tests passed! Ready to start development.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("Please check your API credentials in .env file")
```

**Run Test**:
```bash
python test_bybit_connection.py
```

**Expected Output**:
```
✅ Connected to Bybit Testnet
Server Time: {'retCode': 0, 'retMsg': 'OK', 'result': {...}}
✅ Account Balance Retrieved
Balance: {...}
✅ Market Data Retrieved
BTC Price: 50000.00
🎉 All tests passed! Ready to start development.
```

---

## 9. Cấu Hình Development Tools

### 9.1 Setup Black (Code Formatter)

Tạo `pyproject.toml`:
```toml
[tool.black]
line-length = 100
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''
```

### 9.2 Setup Pytest

Tạo `pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --cov=src
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests
    property: Property-based tests
    integration: Integration tests
    slow: Slow running tests
```

### 9.3 Setup Hypothesis

Tạo `.hypothesis/profiles.yml`:
```yaml
default:
  max_examples: 100
  deadline: 1000
  verbosity: normal

ci:
  max_examples: 1000
  deadline: 5000

dev:
  max_examples: 10
  deadline: null
```

### 9.4 Setup MyPy (Type Checking)

Tạo `mypy.ini`:
```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
strict_equality = True

[mypy-pytest.*]
ignore_missing_imports = True

[mypy-hypothesis.*]
ignore_missing_imports = True
```

---

## 10. Tạo Configuration Files

### 10.1 config/config.yaml

```yaml
# Trading Configuration
mode: testnet  # testnet | paper | live
symbol: BTCUSDT
timeframes: [1m, 5m, 15m, 1h]

# Alpha Model Configuration
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

# Risk Management Configuration
risk:
  max_risk_per_trade: 0.02  # 2%
  max_position_size: 0.10  # 10%
  initial_stop_loss_pct: 0.02  # 2%
  breakeven_trigger_pct: 0.01  # 1%
  trailing_stop_trigger_pct: 0.02  # 2%
  trailing_stop_distance_pct: 0.01  # 1%
  kill_switch_daily_dd: 0.05  # 5%
  kill_switch_consecutive_losses: 5

# Execution Configuration
execution:
  limit_order_timeout: 5  # seconds
  max_slippage_pct: 0.001  # 0.1%
  max_total_cost_pct: 0.002  # 0.2%
  max_retries: 2

# Backtesting Configuration
backtest:
  initial_balance: 10000
  commission_rate: 0.0006  # Bybit taker fee
  slippage_model: orderbook  # fixed | orderbook
```

---

## 11. Download Historical Data

### 11.1 Tạo Script Download

Tạo `scripts/download_historical_data.py`:
```python
"""
Script to download historical data from Bybit for backtesting.
Downloads 6 months of OHLCV data for specified symbols and timeframes.
"""
import asyncio
import asyncpg
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

load_dotenv()

async def download_historical_data():
    # Initialize Bybit client
    session = HTTP(testnet=True)
    
    # Connect to database
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Configuration
    symbol = "BTCUSDT"
    timeframes = ["1", "5", "15", "60"]  # minutes
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)  # 6 months
    
    print(f"Downloading data from {start_date} to {end_date}")
    
    for interval in timeframes:
        print(f"\nDownloading {interval}m data...")
        
        current_date = start_date
        total_candles = 0
        
        while current_date < end_date:
            # Bybit allows max 200 candles per request
            response = session.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                start=int(current_date.timestamp() * 1000),
                limit=200
            )
            
            if response['retCode'] == 0:
                candles = response['result']['list']
                
                # Insert into database
                for candle in candles:
                    await conn.execute("""
                        INSERT INTO klines (timestamp, symbol, timeframe, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (timestamp, symbol, timeframe) DO NOTHING
                    """, 
                        datetime.fromtimestamp(int(candle[0]) / 1000),
                        symbol,
                        f"{interval}m",
                        float(candle[1]),  # open
                        float(candle[2]),  # high
                        float(candle[3]),  # low
                        float(candle[4]),  # close
                        float(candle[5])   # volume
                    )
                
                total_candles += len(candles)
                current_date += timedelta(minutes=int(interval) * 200)
                print(f"  Downloaded {total_candles} candles...", end='\r')
                
                # Rate limiting
                await asyncio.sleep(0.1)
            else:
                print(f"Error: {response['retMsg']}")
                break
        
        print(f"  ✅ Downloaded {total_candles} candles for {interval}m")
    
    await conn.close()
    print("\n🎉 Historical data download complete!")

if __name__ == "__main__":
    asyncio.run(download_historical_data())
```

**Run Script** (sau khi setup database schema):
```bash
python scripts/download_historical_data.py
```

---

## 12. Checklist Chuẩn Bị

### ✅ Phần Mềm
- [ ] Python 3.11+ installed
- [ ] Docker & Docker Compose installed
- [ ] Git installed
- [ ] VS Code installed với extensions

### ✅ Tài Khoản & API
- [ ] Bybit Testnet account created
- [ ] Testnet USDT received (10,000 USDT)
- [ ] API Key created với Read-Write permissions
- [ ] API credentials saved trong .env
- [ ] Telegram Bot created (optional)
- [ ] Telegram Chat ID obtained (optional)

### ✅ Database
- [ ] TimescaleDB running (Docker hoặc local)
- [ ] Database connection tested
- [ ] Database schema created (sẽ làm trong Task 3)

### ✅ Project Setup
- [ ] Virtual environment created và activated
- [ ] Dependencies installed từ requirements.txt
- [ ] Project structure created
- [ ] .gitignore configured
- [ ] Configuration files created

### ✅ Testing
- [ ] Bybit connection test passed
- [ ] pytest configured
- [ ] hypothesis configured
- [ ] mypy configured

---

## 13. Next Steps

Sau khi hoàn thành tất cả các bước trên:

1. **Verify Setup**:
   ```bash
   # Test Python
   python --version
   
   # Test Docker
   docker compose ps
   
   # Test Bybit connection
   python test_bybit_connection.py
   
   # Test pytest
   pytest --version
   ```

2. **Start Development**:
   - Mở `.kiro/specs/quantitative-trading-bot/tasks.md`
   - Bắt đầu với **Task 1: Thiết lập kiến trúc dự án**
   - Follow tasks theo thứ tự

3. **Development Workflow**:
   ```bash
   # Activate virtual environment
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate     # Windows
   
   # Start database
   docker compose up -d timescaledb
   
   # Run tests
   pytest tests/
   
   # Format code
   black src/ tests/
   
   # Type check
   mypy src/
   ```

4. **Git Workflow**:
   ```bash
   # Initialize git
   git init
   git add .
   git commit -m "Initial project setup"
   
   # Create feature branch
   git checkout -b feature/task-1-project-setup
   
   # After completing task
   git add .
   git commit -m "Complete Task 1: Project setup"
   git checkout main
   git merge feature/task-1-project-setup
   ```

---

## 14. Troubleshooting

### Issue: Docker không start được

**Solution**:
```bash
# Check Docker service
sudo systemctl status docker

# Restart Docker
sudo systemctl restart docker

# Check logs
docker compose logs timescaledb
```

### Issue: Python dependencies conflict

**Solution**:
```bash
# Remove virtual environment
rm -rf venv

# Recreate
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: Bybit API connection failed

**Solution**:
1. Verify API key và secret trong .env
2. Check testnet=True trong code
3. Verify internet connection
4. Check Bybit Testnet status: [status.bybit.com](https://status.bybit.com)

### Issue: TimescaleDB connection refused

**Solution**:
```bash
# Check if container is running
docker compose ps

# Check logs
docker compose logs timescaledb

# Restart container
docker compose restart timescaledb

# Test connection
docker exec -it trading_bot_db psql -U trading_user -d trading_bot
```

---

## 15. Resources & Documentation

### Official Documentation
- **Bybit API**: https://bybit-exchange.github.io/docs/
- **pybit**: https://github.com/bybit-exchange/pybit
- **TimescaleDB**: https://docs.timescale.com/
- **Hypothesis**: https://hypothesis.readthedocs.io/
- **pandas-ta**: https://github.com/twopirllc/pandas-ta

### Learning Resources
- **Wyckoff Method**: https://school.stockcharts.com/doku.php?id=market_analysis:the_wyckoff_method
- **Order Flow Trading**: https://www.investopedia.com/terms/o/order-flow.asp
- **Property-Based Testing**: https://hypothesis.works/articles/what-is-property-based-testing/

### Community
- **Bybit Discord**: https://discord.gg/bybit
- **Python Trading**: https://www.reddit.com/r/algotrading/

---

## 🎉 Bạn đã sẵn sàng!

Sau khi hoàn thành tất cả các bước trong tài liệu này, bạn đã có đầy đủ môi trường và tài nguyên để bắt đầu phát triển Quantitative Trading Bot.

**Bước tiếp theo**: Mở `.kiro/specs/quantitative-trading-bot/tasks.md` và bắt đầu với Task 1!

Good luck và happy coding! 🚀
