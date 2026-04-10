# Multi-Symbol Scanner Setup Guide

## Tổng quan

Multi-symbol scanner cho phép bot monitor và trade nhiều cryptocurrency symbols đồng thời thay vì chỉ 1 symbol (BTCUSDT).

## Cấu hình

### 1. Bật Multi-Symbol Mode

Mở `config/config.yaml` và chỉnh sửa:

```yaml
multi_symbol:
  enabled: true  # Đổi từ false sang true
  volume_threshold: 10000000  # $10M USD minimum 24h volume
  max_symbols: 100
  refresh_interval: 21600  # 6 hours
  max_position_pct: 0.05  # 5% per position
  max_total_exposure: 0.80  # 80% total exposure
```

### 2. Filters (Tùy chọn)

Điều chỉnh filters để lọc symbols:

```yaml
multi_symbol:
  filters:
    max_spread_pct: 0.001  # 0.1% maximum spread
    min_atr_multiplier: 1.0  # Minimum volatility
    min_listing_age_hours: 48  # Minimum 48h since listing
    blacklist: ["BTCDOMUSDT", "USDCUSDT"]  # Symbols to exclude
```

## Test trong Docker

### 1. Build Docker image

```bash
docker-compose build trading_bot
```

### 2. Chạy test script

```bash
docker-compose run --rm trading_bot python scripts/test_multi_symbol.py
```

Kết quả mong đợi:
```
✅ Configuration: PASS
✅ Imports: PASS
✅ TradingLoop: PASS
✅ All tests passed! Multi-symbol mode is ready.
```

### 3. Chạy bot với multi-symbol mode

```bash
docker-compose up trading_bot
```

## Monitoring

### Status Display

Bot sẽ hiển thị status mỗi 10 giây:

**Single-symbol mode:**
```
Mode: SINGLE-SYMBOL
Symbol: BTCUSDT
Current Price: 43250.50
Balance: 100.00 USDT
```

**Multi-symbol mode:**
```
Mode: MULTI-SYMBOL
Monitored Symbols: 73
Open Positions: 3

Portfolio:
  Balance: 100.00 USDT
  Equity: 102.50 USDT
  Total P&L: +2.50 USDT (+2.50%)

Open Positions:
  ETHUSDT: BUY 0.0500 @ 2250.00 (current: 2260.00, P&L: +0.50 USDT)
  SOLUSDT: BUY 2.0000 @ 95.00 (current: 96.00, P&L: +2.00 USDT)
```

### Telegram Commands

- `/status` - Xem system status và monitored symbols
- `/positions` - Xem tất cả open positions với P&L
- `/pnl` - Xem tổng P&L và performance

### Logs

Logs được ghi vào `logs/trading.log`:
```bash
docker-compose logs -f trading_bot
```

Memory usage được log mỗi 60 giây:
```
Memory usage: 450.23 MB
```

## Cấu trúc Capital Allocation

- **Max position size**: 5% equity per position (configurable 2-5%)
- **Max total exposure**: 80% equity
- **Max concurrent positions**: 16 positions (80% / 5%)

Ví dụ với 100 USDT:
- Mỗi position tối đa: 5 USDT
- Tổng exposure tối đa: 80 USDT
- Số positions tối đa: 16 positions

## Symbol Refresh

Bot tự động refresh symbol list mỗi 6 giờ:
- Thêm symbols mới đạt volume threshold
- Loại bỏ symbols không còn đạt criteria
- Tự động đóng positions của symbols bị loại

## Troubleshooting

### Bot không start

1. Check logs:
```bash
docker-compose logs trading_bot
```

2. Verify config:
```bash
docker-compose run --rm trading_bot python -c "import yaml; print(yaml.safe_load(open('config/config.yaml')))"
```

### Memory warning

Nếu thấy warning "Memory usage exceeds threshold":
- Giảm `max_symbols` trong config
- Giảm số timeframes monitor
- Restart bot để clear memory

### Không có symbols nào được scan

1. Check volume threshold (có thể quá cao):
```yaml
volume_threshold: 5000000  # Giảm xuống $5M
```

2. Check filters (có thể quá strict):
```yaml
filters:
  max_spread_pct: 0.002  # Tăng lên 0.2%
```

## Rollback về Single-Symbol Mode

Nếu gặp vấn đề, đổi lại về single-symbol mode:

```yaml
multi_symbol:
  enabled: false  # Đổi về false
```

Restart bot:
```bash
docker-compose restart trading_bot
```

## Performance Tips

1. **Start small**: Test với `max_symbols: 20` trước
2. **Monitor memory**: Theo dõi memory usage trong logs
3. **Adjust filters**: Điều chỉnh filters để có số symbols phù hợp
4. **Volume threshold**: Tăng threshold nếu có quá nhiều symbols

## Support

Nếu gặp vấn đề, check:
1. Logs: `docker-compose logs trading_bot`
2. Config: `config/config.yaml`
3. Memory: Xem memory warnings trong logs
4. Telegram: `/status` command để xem bot status
