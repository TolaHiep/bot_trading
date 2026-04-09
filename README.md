# Quantitative Trading Bot

Hệ thống giao dịch tự động định lượng trên sàn Bybit sử dụng Python 3.11+.

## 🚀 Quick Start

### 1. Setup môi trường
```bash
# Copy environment template
cp .env.example .env

# Edit .env và thêm Bybit API credentials
# (Xem SETUP.md để biết cách tạo API keys)
```

### 2. Install dependencies
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Start database
```bash
docker compose up -d timescaledb
```

### 4. Test connection
```bash
python test_bybit_connection.py
```

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Hướng dẫn chuẩn bị môi trường chi tiết
- **[.kiro/specs/quantitative-trading-bot/requirements.md](.kiro/specs/quantitative-trading-bot/requirements.md)** - Requirements document
- **[.kiro/specs/quantitative-trading-bot/design.md](.kiro/specs/quantitative-trading-bot/design.md)** - Design document
- **[.kiro/specs/quantitative-trading-bot/tasks.md](.kiro/specs/quantitative-trading-bot/tasks.md)** - Implementation tasks

## 🏗️ Project Structure

```
.
├── src/                    # Source code
│   ├── connectors/        # Bybit API connectors
│   ├── data/              # Data pipeline
│   ├── alpha/             # Alpha model (signals)
│   ├── risk/              # Risk management
│   ├── execution/         # Order execution
│   ├── backtest/          # Backtesting engine
│   ├── monitoring/        # Dashboard & alerts
│   └── config/            # Configuration management
├── tests/                 # Test suites
│   ├── unit/             # Unit tests
│   ├── property/         # Property-based tests
│   ├── integration/      # Integration tests
│   └── backtest/         # Backtesting tests
├── config/               # Configuration files
├── scripts/              # Utility scripts
├── migrations/           # Database migrations
└── logs/                 # Log files

## 🧪 Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run property tests
pytest tests/property/

# Run with coverage
pytest --cov=src --cov-report=html
```

## 📊 Development Workflow

1. Đọc task trong `tasks.md`
2. Tạo feature branch: `git checkout -b feature/task-X`
3. Implement task
4. Write tests (unit + property tests)
5. Run tests: `pytest`
6. Format code: `black src/ tests/`
7. Type check: `mypy src/`
8. Commit và merge

## ⚠️ Important Notes

- **KHÔNG BAO GIỜ** commit file `.env` (chứa API secrets)
- Luôn test trên **Testnet** trước khi chuyển sang Live
- Chạy **Paper Trading** >= 2 tuần trước khi Live
- Đọc kỹ **Risk Management** trong design document

## 📈 Trading Modes

1. **Testnet**: Test với Bybit Testnet (fake money)
2. **Paper Trading**: Dữ liệu thật, giao dịch giả lập
3. **Live**: Giao dịch thật với tiền thật (⚠️ RỦI RO CAO)

## 🛠️ Tech Stack

- **Python 3.11+**
- **Bybit API** (pybit v5)
- **TimescaleDB** (PostgreSQL)
- **pandas-ta** + **numpy** (indicators)
- **Hypothesis** (property-based testing)
- **Docker** + **Docker Compose**
- **Streamlit** (dashboard)
- **Telegram Bot** (alerts)

## 📞 Support

- Bybit API Docs: https://bybit-exchange.github.io/docs/
- pybit GitHub: https://github.com/bybit-exchange/pybit
- Hypothesis Docs: https://hypothesis.readthedocs.io/

## ⚖️ License

Private project - All rights reserved

## ⚠️ Disclaimer

Giao dịch cryptocurrency có rủi ro cao. Bot này chỉ dùng cho mục đích học tập và nghiên cứu. Không đảm bảo lợi nhuận. Chỉ sử dụng số vốn bạn có thể chấp nhận mất hoàn toàn.
