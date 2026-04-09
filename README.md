# 📈 Quantitative Trading Bot

Hệ thống giao dịch tự động định lượng trên sàn Bybit sử dụng Python 3.11+, kết hợp phân tích kỹ thuật, Order Flow và Wyckoff Method.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-Private-red.svg)]()

---

## 🎯 Overview

Bot giao dịch định lượng với các tính năng:

- **Alpha Model**: Technical Indicators + Order Flow + Wyckoff Analysis
- **Risk Management**: Position sizing, Stop loss, Kill switch
- **Backtesting**: Event-driven engine với realistic slippage
- **Paper Trading**: Simulation với real-time data
- **Live Trading**: Tích hợp Bybit API
- **Monitoring**: Streamlit Dashboard + Telegram Bot

---

## ✨ Features

### 🧠 Alpha Model
- **Technical Indicators**: SMA, EMA, RSI, MACD, Bollinger Bands
- **Order Flow Analysis**: Cumulative delta, Footprint chart, Imbalance detection
- **Wyckoff Method**: Phase detection (Accumulation, Markup, Distribution, Markdown)
- **Signal Generation**: Multi-timeframe alignment với confidence scoring
- **False Breakout Filter**: Volume confirmation

### 🛡️ Risk Management
- **Position Sizing**: 2% max risk per trade
- **Stop Loss**: Hard SL, Trailing SL, ATR-based SL
- **Kill Switch**: Auto-stop khi daily drawdown > 5% hoặc 5 consecutive losses
- **Drawdown Monitor**: Real-time tracking

### 🔄 Execution
- **Order Types**: Market, Limit với timeout fallback
- **Slippage Control**: Max 0.1% slippage tolerance
- **Cost Filter**: Total cost < 0.2% position value
- **Retry Logic**: Exponential backoff

### 📊 Backtesting
- **Event-Driven**: Chronological data replay
- **Look-Ahead Bias Prevention**: Strict timestamp ordering
- **Realistic Slippage**: Orderbook-based simulation
- **Performance Analytics**: Sharpe ratio, Max drawdown, Win rate, Profit factor

### 📡 Monitoring
- **Streamlit Dashboard**: Real-time metrics, Equity curve, System health
- **Telegram Bot**: Commands (/status, /positions, /pnl) + Alerts
- **Logging**: Structured logs với multiple levels

---

## 🚀 Quick Start (Docker)

### Prerequisites
- Docker Desktop 20.10+
- Git 2.30+
- Bybit Testnet account với API keys

### 1. Clone Repository
```bash
git clone https://github.com/TolaHiep/bot_trading.git
cd bot_trading
```

### 2. Configure Environment
```bash
# Copy template
cp .env.example .env

# Edit .env và thêm Bybit API credentials
# BYBIT_API_KEY=your_testnet_api_key
# BYBIT_API_SECRET=your_testnet_api_secret
# BYBIT_TESTNET=true
```

### 3. Start Services
```bash
# Build và start containers
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f trading_bot
```

### 4. Verify Setup
```bash
# Test Bybit connection
docker compose exec trading_bot python scripts/test_connection_docker.py

# Test database
docker compose exec timescaledb psql -U trading_user -d trading_db -c "SELECT 1"

# Run tests
docker compose exec trading_bot pytest tests/ -v
```

### 5. Access Dashboard
```bash
# Start dashboard
docker compose --profile monitoring up -d dashboard

# Open browser: http://localhost:8501
```

---

## 📊 Project Status

**Current Status**: ✅ **Production Ready**

### Completed Tasks (18/18)
- ✅ Task 1: Project Architecture Setup
- ✅ Task 2: Bybit Connector (WebSocket + REST)
- ✅ Task 3: Data Pipeline & TimescaleDB
- ✅ Task 4: Indicator Engine
- ✅ Task 5: Order Flow Delta Calculator
- ✅ Task 6: Wyckoff Phase Detector
- ✅ Task 7: Signal Aggregator & False Breakout Filter
- ✅ Task 8: Position Sizing Calculator
- ✅ Task 9: Stop-Loss Engine
- ✅ Task 10: Kill Switch & Alert System
- ✅ Task 11: Order Manager
- ✅ Task 12: Slippage & Cost Filter
- ✅ Task 13: Backtesting Engine
- ✅ Task 14: Performance Analytics
- ✅ Task 15: Paper Trading Mode & Live Switch
- ✅ Task 16: Monitoring Dashboard
- ✅ Task 17: Config-driven Tuning & Grid Search
- ✅ Task 18: System Handbook & Operations Guide

### Test Coverage
- **Unit Tests**: 16 files (345 tests passing)
- **Property Tests**: 13 files (75 properties)
- **Integration Tests**: 1 file
- **Backtest Tests**: 3 files (25 tests passing)
- **Total**: 33 test files, 445+ tests

### Performance Metrics
- ✅ Pipeline latency: < 100ms
- ✅ Indicator update: < 50ms
- ✅ API rate limit: 600 requests/5s
- ✅ Backtest speed: 1000+ candles/second

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Trading Bot                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │   Bybit API  │◄────►│  Connectors  │               │
│  │  (WebSocket  │      │  - REST      │               │
│  │   + REST)    │      │  - WebSocket │               │
│  └──────────────┘      └──────┬───────┘               │
│                               │                         │
│                               ▼                         │
│                        ┌──────────────┐                │
│                        │     Data     │                │
│                        │   Pipeline   │                │
│                        └──────┬───────┘                │
│                               │                         │
│                               ▼                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │ TimescaleDB  │◄────►│ Alpha Model  │               │
│  │  (OHLCV,     │      │ - Indicators │               │
│  │   Trades,    │      │ - Order Flow │               │
│  │   Signals)   │      │ - Wyckoff    │               │
│  └──────────────┘      └──────┬───────┘               │
│                               │                         │
│                               ▼                         │
│                        ┌──────────────┐                │
│                        │     Risk     │                │
│                        │  Management  │                │
│                        └──────┬───────┘                │
│                               │                         │
│                               ▼                         │
│                        ┌──────────────┐                │
│                        │  Execution   │                │
│                        │    Engine    │                │
│                        └──────┬───────┘                │
│                               │                         │
│                               ▼                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │  Dashboard   │◄────►│  Monitoring  │               │
│  │ (Streamlit)  │      │  - Metrics   │               │
│  └──────────────┘      │  - Telegram  │               │
│                        └──────────────┘               │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Core
- **Python 3.11+**: Main language
- **Docker & Docker Compose**: Containerization
- **TimescaleDB**: Time-series database (PostgreSQL extension)

### Trading
- **pybit 5.14.0**: Bybit API client
- **pandas 3.0.2**: Data processing
- **numpy 2.4.4**: Numerical computing
- **pandas-ta**: Technical indicators (reference)

### Async & Networking
- **asyncio**: Async programming
- **aiohttp 3.13.5**: Async HTTP client
- **asyncpg 0.31.0**: Async PostgreSQL driver
- **websockets**: WebSocket client

### Testing
- **pytest 9.0.3**: Test framework
- **hypothesis 6.151.12**: Property-based testing
- **pytest-cov**: Coverage reporting
- **pytest-asyncio**: Async test support

### Code Quality
- **black 26.3.1**: Code formatter
- **mypy 1.20.0**: Type checker
- **flake8**: Linter
- **isort**: Import sorter

### Monitoring
- **streamlit**: Dashboard framework
- **plotly**: Interactive charts
- **python-telegram-bot 22.7**: Telegram integration

### Utilities
- **python-dotenv**: Environment variables
- **pyyaml**: YAML configuration
- **ujson**: Fast JSON parsing
- **ntplib**: Time synchronization

---

## 📚 Documentation

### Getting Started
- **[Installation Guide](docs/INSTALLATION_GUIDE.md)** - Hướng dẫn cài đặt chi tiết từ đầu
- **[User Guide](USER_GUIDE.md)** - Hướng dẫn sử dụng, cấu hình parameters, Dashboard, Telegram Bot

### Development
- **[Contributing Guide](CONTRIBUTING.md)** - Development workflow, coding standards
- **[Docker Guide](DOCKER.md)** - Docker usage, commands, troubleshooting

### Operations
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues và solutions

### Specifications
- **[Requirements](.kiro/specs/quantitative-trading-bot/requirements.md)** - 20 functional requirements
- **[Design](.kiro/specs/quantitative-trading-bot/design.md)** - Architecture và design decisions
- **[Tasks](.kiro/specs/quantitative-trading-bot/tasks.md)** - 18 implementation tasks

---

## 🧪 Testing

### Run All Tests
```bash
# Inside container
docker compose exec trading_bot pytest tests/ -v

# With coverage
docker compose exec trading_bot pytest tests/ --cov=src --cov-report=html
```

### Run Specific Test Suites
```bash
# Unit tests only
docker compose exec trading_bot pytest tests/unit/ -v

# Property tests only
docker compose exec trading_bot pytest tests/property/ -v

# Integration tests
docker compose exec trading_bot pytest tests/integration/ -v

# Backtest tests
docker compose exec trading_bot pytest tests/backtest/ -v
```

### Test Structure
```
tests/
├── unit/           # Unit tests (16 files, 345 tests)
├── property/       # Property-based tests (13 files, 75 properties)
├── integration/    # Integration tests (1 file)
└── backtest/       # Backtest validation (3 files, 25 tests)
```

---

## 📈 Trading Modes

### 1. Testnet (Current)
- **Purpose**: Development và testing
- **Data**: Real market data
- **Orders**: Placed on Bybit Testnet
- **Money**: Fake (10,000 USDT testnet)
- **Risk**: Zero

### 2. Paper Trading
- **Purpose**: Strategy validation
- **Data**: Real-time market data
- **Orders**: Simulated (không place thật)
- **Money**: Simulated
- **Risk**: Zero
- **Duration**: Minimum 2 weeks

### 3. Live Trading
- **Purpose**: Real trading
- **Data**: Real-time market data
- **Orders**: Real orders on Bybit Mainnet
- **Money**: Real money
- **Risk**: HIGH
- **Requirement**: Pass Backtest + Paper Trading

---

## 🔄 Development Workflow

### 1. Setup Development Environment
```bash
# Clone repository
git clone https://github.com/TolaHiep/bot_trading.git
cd bot_trading

# Configure environment
cp .env.example .env
# Edit .env với Bybit API credentials

# Start services
docker compose up -d
```

### 2. Make Changes
```bash
# Create feature branch
git checkout -b feature/your-feature

# Edit code in src/
# Code changes auto-sync vào container (volume mount)
```

### 3. Test Changes
```bash
# Run tests
docker compose exec trading_bot pytest tests/ -v

# Format code
docker compose exec trading_bot black src/ tests/

# Type check
docker compose exec trading_bot mypy src/

# Lint
docker compose exec trading_bot flake8 src/ tests/
```

### 4. Commit và Push
```bash
git add .
git commit -m "feat: your feature description"
git push origin feature/your-feature
```

---

## 🎯 Quick Commands

### Using Makefile
```bash
make help           # Show all commands
make start          # Start services
make stop           # Stop services
make status         # Check status
make logs           # View logs
make shell          # Open container shell
make test           # Run tests
make format         # Format code
make lint           # Run linter
make type-check     # Type checking
make check          # Run all checks
```

### Using Docker Compose
```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f trading_bot

# Open shell
docker compose exec trading_bot bash

# Run tests
docker compose exec trading_bot pytest tests/ -v
```

---

## ⚠️ Important Notes

### Risk Management
- **Max Risk per Trade**: 2% of account balance
- **Max Position Size**: 10% of account balance
- **Daily Drawdown Limit**: 5% (triggers kill switch)
- **Consecutive Loss Limit**: 5 trades (triggers kill switch)

### Trading Progression
1. ✅ **Backtest** (1-2 weeks): Test strategy on historical data
2. ✅ **Paper Trading** (2-4 weeks): Simulate with real-time data
3. ⚠️ **Live Trading**: Start small (10-20% of intended capital)

### Security
- ❌ **NEVER** commit `.env` file (contains API secrets)
- ✅ Use **Read-Write** permissions only (NO Withdraw)
- ✅ Enable **2FA** on Bybit account
- ✅ Use **Testnet** for development
- ✅ Regular **API key rotation**

### Data Integrity
- ✅ NTP time synchronization (drift < 1s)
- ✅ Data validation before trading decisions
- ✅ Gap detection và auto-fill
- ✅ Deduplication on (symbol, timestamp, timeframe)

---

## 📞 Support & Resources

### Documentation
- **Bybit API**: https://bybit-exchange.github.io/docs/
- **pybit GitHub**: https://github.com/bybit-exchange/pybit
- **TimescaleDB**: https://docs.timescale.com/
- **Hypothesis**: https://hypothesis.readthedocs.io/

### Community
- **GitHub Issues**: Report bugs và feature requests
- **Bybit Discord**: https://discord.gg/bybit

### Learning Resources
- **Wyckoff Method**: https://school.stockcharts.com/doku.php?id=market_analysis:the_wyckoff_method
- **Order Flow Trading**: https://www.investopedia.com/terms/o/order-flow.asp
- **Algorithmic Trading**: https://www.reddit.com/r/algotrading/

---

## ⚖️ License

Private project - All rights reserved

---

## ⚠️ Disclaimer

**CẢNH BÁO RỦI RO**

Giao dịch cryptocurrency có rủi ro cao và có thể không phù hợp với tất cả nhà đầu tư. Bot này được cung cấp "AS IS" không có bảo đảm nào. Không đảm bảo lợi nhuận.

- ❌ Không phải lời khuyên tài chính
- ❌ Không đảm bảo lợi nhuận
- ❌ Có thể mất toàn bộ vốn đầu tư
- ✅ Chỉ sử dụng số vốn bạn có thể chấp nhận mất hoàn toàn
- ✅ Luôn test kỹ trên Testnet và Paper Trading trước khi Live
- ✅ Bắt đầu với số vốn nhỏ khi chuyển sang Live

**Sử dụng bot này hoàn toàn là trách nhiệm của bạn.**

---

## 🚀 Ready to Start?

1. ✅ Đọc [Installation Guide](docs/INSTALLATION_GUIDE.md)
2. ✅ Đọc [User Guide](USER_GUIDE.md)
3. ✅ Setup Bybit Testnet account
4. ✅ Configure `.env` file
5. ✅ Run `docker compose up -d`
6. ✅ Test connection
7. ✅ Run backtest
8. ✅ Start paper trading
9. ⚠️ Live trading (sau khi pass paper trading)

**Happy Trading! 📈**
