# 🤖 Quantitative Trading Bot

Multi-strategy cryptocurrency trading bot với 3 bots độc lập chạy song song.

## 🌟 Tính năng

### 3 Bots Độc Lập
- **Wyckoff Bot** (Main): Phân tích Wyckoff, multi-symbol, $100 wallet
- **Scalping V1**: Scalping cơ bản, 1m timeframe, $100 wallet  
- **Scalping V2**: Scalping nâng cao với ATR-based SL/TP, $100 wallet

### Chiến lược Trading
- ✅ Wyckoff accumulation/distribution detection
- ✅ Multi-timeframe analysis (5m, 15m, 1h)
- ✅ Order flow analysis
- ✅ Support/Resistance detection
- ✅ RSI, EMA, Bollinger Bands
- ✅ Volume profile analysis

### Risk Management
- ✅ Cross margin (unrealized PnL dùng làm margin)
- ✅ ATR-based stop loss
- ✅ Multiple take profit targets
- ✅ Breakeven logic
- ✅ Trailing stop
- ✅ Auto-reset khi liquidation

### Monitoring & Alerts
- ✅ Telegram bot với commands
- ✅ Real-time dashboard (Streamlit)
- ✅ Liquidation reports
- ✅ Performance metrics
- ✅ Position tracking

## 🚀 Quick Start

### Cài đặt nhanh (5 phút)

```bash
# 1. Chạy setup
setup.bat

# 2. Điền API keys vào .env
notepad .env

# 3. Khởi động bot
start.bat
```

📖 **Chi tiết**: Xem [QUICK_START.md](QUICK_START.md)

## 📊 Telegram Commands

```
/all          - Báo cáo tổng hợp cả 3 bot
/wyckoff      - Báo cáo bot Wyckoff
/scalp        - Báo cáo bot Scalping V1
/scalp_v2     - Báo cáo bot Scalping V2
/status       - Trạng thái hệ thống
```

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────┐
│         Trading Bot System              │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │ Wyckoff  │  │ Scalp V1 │  │Scalp V2││
│  │  $100    │  │  $100    │  │ $100   ││
│  └────┬─────┘  └────┬─────┘  └───┬────┘│
│       │             │             │     │
│       └─────────────┴─────────────┘     │
│                     │                   │
│              ┌──────▼──────┐            │
│              │  Bybit API  │            │
│              │  (Mainnet)  │            │
│              └──────┬──────┘            │
│                     │                   │
│       ┌─────────────┴─────────────┐     │
│       │                           │     │
│  ┌────▼─────┐              ┌──────▼───┐│
│  │ Telegram │              │Dashboard ││
│  │   Bot    │              │(Streamlit││
│  └──────────┘              └──────────┘│
│                                         │
└─────────────────────────────────────────┘
```

## 📁 Cấu trúc Project

```
Trading_bot/
├── src/
│   ├── alpha/              # Trading strategies
│   │   ├── wyckoff.py
│   │   ├── scalping_engine.py
│   │   └── scalping_engine_v2.py
│   ├── core/               # Core trading loops
│   │   ├── trading_loop.py
│   │   ├── scalping_loop.py
│   │   ├── scalping_loop_v2.py
│   │   └── multi_bot_manager.py
│   ├── execution/          # Order execution
│   │   ├── paper_trader.py
│   │   └── order_manager.py
│   ├── monitoring/         # Monitoring & alerts
│   │   ├── telegram_bot.py
│   │   └── account_monitor.py
│   └── risk/               # Risk management
│       ├── stop_loss.py
│       └── position_sizing.py
├── config/
│   └── config.yaml         # Bot configuration
├── docs/                   # Documentation
├── tests/                  # Unit & property tests
├── docker-compose.yml      # Docker setup
├── setup.bat              # Setup script
├── start.bat              # Start bot
└── .env                   # API keys (create this)
```

## ⚙️ Cấu hình

### config.yaml

```yaml
# Symbol
symbol: BTCUSDT

# Multi-symbol trading
multi_symbol:
  enabled: true
  max_symbols: 10

# Risk management
risk:
  risk_per_trade: 0.02      # 2% per trade
  max_positions: 3
  max_drawdown_pct: 0.15    # 15% max drawdown

# Scalping settings
scalping:
  enabled: true
  risk:
    leverage: 20.0          # 20x leverage
    risk_per_trade: 0.05    # 5% per trade
```

### .env

```env
# Bybit API
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret

# Telegram
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_IDS=your_chat_id

# Database
POSTGRES_PASSWORD=secure_password
```

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/

# Property-based tests
pytest tests/property/

# All tests
pytest
```

## 📈 Performance Metrics

Bot tự động track:
- Total P&L (realized + unrealized)
- Win rate
- Average win/loss
- Max drawdown
- Sharpe ratio
- Trade frequency

Metrics được lưu tại:
- `logs/metrics_wyckoff.json`
- `logs/metrics_scalp.json`
- `logs/metrics_scalp_v2.json`

## 🔒 Bảo mật

- ✅ Paper trading mặc định (an toàn)
- ✅ API keys trong .env (không commit)
- ✅ IP whitelist khuyến nghị
- ✅ Read-only API cho monitoring
- ⚠️ KHÔNG bật live trading nếu chưa hiểu rõ

## 📚 Documentation

- [QUICK_START.md](QUICK_START.md) - Hướng dẫn cài đặt nhanh
- [START_HERE_DOCKER.md](START_HERE_DOCKER.md) - Docker setup chi tiết
- [docs/LIQUIDATION_HANDLING.md](docs/LIQUIDATION_HANDLING.md) - Xử lý liquidation
- [docs/SCALPING_STRATEGY.md](docs/SCALPING_STRATEGY.md) - Chiến lược scalping

## 🛠️ Tech Stack

- **Language**: Python 3.11
- **Exchange**: Bybit (mainnet)
- **Database**: TimescaleDB (PostgreSQL)
- **Dashboard**: Streamlit
- **Alerts**: Telegram Bot
- **Deployment**: Docker Compose

## 📊 Dashboard

Mở http://localhost:8501 để xem:
- Real-time price charts
- Portfolio performance
- Open positions
- P&L charts
- Trade history

## 🐛 Troubleshooting

### Bot không khởi động
```bash
docker logs trading_bot_app
```

### Telegram không hoạt động
```bash
docker logs trading_bot_telegram
```

### Reset database
```bash
docker-compose down -v
docker-compose up -d
```

## 🤝 Contributing

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

## ⚠️ Disclaimer

- Bot này chỉ dùng cho mục đích học tập và nghiên cứu
- Paper trading (mô phỏng) là mặc định và được khuyến nghị
- Live trading có rủi ro cao, có thể mất tiền
- Tác giả không chịu trách nhiệm về bất kỳ tổn thất nào
- Luôn test kỹ trước khi dùng tiền thật
- Không phải lời khuyên tài chính

## 📝 License

MIT License - Xem [LICENSE](LICENSE) để biết thêm chi tiết

## 📞 Support

- 📧 Email: support@example.com
- 💬 Telegram: @your_support_channel
- 🐛 Issues: GitHub Issues

---

**Made with ❤️ for the crypto trading community**

🚀 Happy Trading! 📈
