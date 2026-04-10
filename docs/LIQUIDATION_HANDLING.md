# Xử Lý Tự Động Khi Cháy Tài Khoản

## Tổng Quan

Hệ thống tự động phát hiện khi tài khoản cháy (equity ≤ $5), tạo báo cáo chi tiết, gửi qua Telegram, và reset lại tài khoản về $100.

## Tính Năng

### 1. Phát Hiện Tự Động
- Kiểm tra equity mỗi 10 giây (khi print status)
- Trigger khi equity ≤ $5 (có thể cấu hình)
- Không cần can thiệp thủ công

### 2. Báo Cáo Chi Tiết

**Thông tin tài khoản:**
- Initial balance vs Final equity
- Total loss và % loss
- Realized vs Unrealized PnL

**Thống kê giao dịch:**
- Tổng số lệnh
- Win rate
- Average win vs Average loss
- Total profit vs Total loss

**Top 10 lệnh tệ nhất:**
- Symbol, side, entry/exit price
- P&L của từng lệnh
- Lý do đóng lệnh

**Top 10 lệnh tốt nhất:**
- Để so sánh và học hỏi

**Phân tích theo symbol:**
- Symbols nào loss nhiều nhất
- Số lệnh và win rate mỗi symbol
- Total P&L mỗi symbol

**Phân tích theo strategy:**
- Main strategy vs Scalping
- Win rate và P&L mỗi strategy

**Phân tích nguyên nhân:**
- Consecutive losses
- Overtrading specific symbols
- Poor strategy performance
- Large single losses
- Poor risk/reward ratio

**Khuyến nghị cải thiện:**
- Giảm leverage
- Giảm risk per trade
- Tighter stop loss
- Limit trades per symbol
- Optimize strategy parameters
- Add stricter kill switch
- Implement max loss per trade

### 3. Gửi Telegram

**Message tóm tắt:**
```
🚨 ACCOUNT LIQUIDATED #1 🚨

Account Summary:
Initial: $100.00
Final: $2.50
Loss: $97.50 (97.5%)

Trading Summary:
Total Trades: 45
Win Rate: 35.6%
Wins: 16 ($45.20)
Losses: 29 ($-142.70)
Avg Win: $2.83
Avg Loss: $-4.92

Failure Analysis:
1. Consecutive losses: 8 trades in a row
2. Overtrading BTCUSDT: 25 trades, $-65.30 loss
3. Poor risk/reward: Avg loss $4.92 > 2x avg win $2.83

Top Recommendations:
1. Reduce leverage from 20x to 5-10x
2. Reduce risk per trade from 5% to 2-3%
3. Implement stricter stop loss (0.5-1% instead of 2%)

📄 Full report: liquidation_20260410_230530_#1.json

✅ Account reset to $100
```

### 4. Reset Tự Động

**Sau khi gửi báo cáo:**
1. Đóng tất cả positions đang mở (nếu có)
2. Reset balance về $100
3. Reset trade history
4. Bot tiếp tục chạy bình thường
5. Học hỏi từ sai lầm và trade tiếp!

## Cấu Hình

### Trong `trading_loop.py`:

```python
self.account_monitor = AccountMonitor(
    paper_trader=self.paper_trader,
    initial_balance=Decimal("100"),  # Reset về $100
    liquidation_threshold=Decimal("5.0")  # Trigger khi < $5
)
```

### Thay đổi threshold:

```python
# Trigger sớm hơn (khi còn $10)
liquidation_threshold=Decimal("10.0")

# Trigger muộn hơn (khi còn $1)
liquidation_threshold=Decimal("1.0")

# Trigger ngay khi về 0
liquidation_threshold=Decimal("0.0")
```

### Thay đổi reset balance:

```python
# Reset về $200
initial_balance=Decimal("200")

# Reset về $50
initial_balance=Decimal("50")
```

## Báo Cáo

### Vị trí lưu:
```
reports/liquidations/
├── liquidation_20260410_230530_#1.json
├── liquidation_20260410_235530_#2.json
└── liquidation_20260411_010530_#3.json
```

### Cấu trúc JSON:

```json
{
  "timestamp": "2026-04-10T23:05:30.123456",
  "liquidation_number": 1,
  "account": {
    "initial_balance": 100.0,
    "final_equity": 2.5,
    "total_loss": 97.5,
    "loss_percentage": 97.5,
    "realized_pnl": -95.0,
    "unrealized_pnl": -2.5
  },
  "trading_summary": {
    "total_trades": 45,
    "winning_trades": 16,
    "losing_trades": 29,
    "win_rate": 35.6,
    "total_profit": 45.2,
    "total_loss": -142.7,
    "net_pnl": -97.5,
    "average_win": 2.83,
    "average_loss": -4.92
  },
  "worst_trades": [...],
  "best_trades": [...],
  "symbol_performance": {...},
  "strategy_performance": {...},
  "open_positions": [...],
  "analysis": {
    "reasons": [...],
    "max_consecutive_losses": 8,
    "recommendations": [...]
  }
}
```

## Ví Dụ Thực Tế

### Scenario 1: Overtrading

```
Liquidation #1
Reason: Overtrading BTCUSDT (35 trades, $-75 loss)
Recommendation: Limit trades per symbol to 5 per day

→ Sau reset: Thêm logic limit trades per symbol
```

### Scenario 2: Poor Risk/Reward

```
Liquidation #2
Reason: Avg loss $5.20 > 2x avg win $2.10
Recommendation: Increase take profit targets to 3-5%

→ Sau reset: Thêm take profit tự động
```

### Scenario 3: Consecutive Losses

```
Liquidation #3
Reason: 10 consecutive losses
Recommendation: Add kill switch for 3 consecutive losses

→ Sau reset: Giảm kill switch threshold từ 5 xuống 3
```

## Test Liquidation

### Chạy test:

```bash
# Trong Docker
docker exec -it trading_bot_app python scripts/test_liquidation.py

# Local
python scripts/test_liquidation.py
```

### Kết quả mong đợi:

```
============================================================
Testing Liquidation Detection and Reporting
============================================================

1. Opening multiple losing positions...
   Trade 1: Opened BUY position @ 70010
   Trade 1: Closed with P&L: $-2.01
   Balance: $97.99, Equity: $97.99
   
   Trade 2: Opened BUY position @ 70010
   Trade 2: Closed with P&L: $-2.01
   Balance: $95.98, Equity: $95.98
   
   ...
   
   Trade 10: Opened BUY position @ 70010
   Trade 10: Closed with P&L: $-2.01
   Balance: $3.50, Equity: $3.50

============================================================
LIQUIDATION DETECTED AND HANDLED!
============================================================

New balance after reset: $100.00
Total liquidations: 1
Last liquidation: 2026-04-10T23:05:30.123456

============================================================
Test completed!
============================================================

Check reports/liquidations/ for detailed report
```

## Thống Kê Liquidation

### Xem số lần cháy:

```python
stats = account_monitor.get_liquidation_stats()
print(f"Total liquidations: {stats['total_liquidations']}")
print(f"Last liquidation: {stats['last_liquidation']}")
```

### Trong Telegram bot:

```
/stats

Liquidation Stats:
Total: 3 times
Last: 2026-04-10 23:05:30
Average time between: 2.5 hours
```

## Lợi Ích

### 1. Học Hỏi Từ Sai Lầm
- Báo cáo chi tiết giúp hiểu tại sao cháy
- Recommendations cụ thể để cải thiện
- So sánh giữa các lần cháy để thấy tiến bộ

### 2. Không Mất Thời Gian
- Tự động reset, không cần can thiệp
- Bot tiếp tục chạy ngay
- Không phải setup lại từ đầu

### 3. Theo Dõi Tiến Bộ
- Số lần cháy giảm dần = đang cải thiện
- Thời gian giữa các lần cháy tăng = tốt hơn
- Win rate tăng dần qua các lần reset

### 4. An Toàn
- Chỉ mất $100 mỗi lần (paper trading)
- Học được nhiều mà không mất tiền thật
- Test strategies an toàn

## Khuyến Nghị

### Sau mỗi lần liquidation:

1. **Đọc kỹ báo cáo**
   - Hiểu nguyên nhân chính
   - Xem worst trades
   - Phân tích symbol/strategy performance

2. **Áp dụng recommendations**
   - Giảm leverage nếu cần
   - Giảm risk per trade
   - Tighter stop loss
   - Limit trades per symbol

3. **Điều chỉnh config**
   - Update `config/config.yaml`
   - Test với settings mới
   - Monitor kết quả

4. **Theo dõi cải thiện**
   - So sánh với lần trước
   - Win rate có tăng không?
   - Thời gian sống lâu hơn không?

### Mục tiêu:

```
Lần 1: Cháy sau 2 giờ, 45 trades, 35% win rate
Lần 2: Cháy sau 4 giờ, 38 trades, 42% win rate ✅ Cải thiện
Lần 3: Cháy sau 8 giờ, 30 trades, 48% win rate ✅ Cải thiện
Lần 4: Không cháy, profitable! 🎉
```

## Kết Luận

Hệ thống liquidation handling giúp:
- ✅ Tự động phát hiện và xử lý
- ✅ Báo cáo chi tiết để học hỏi
- ✅ Reset nhanh để tiếp tục
- ✅ Theo dõi tiến bộ qua thời gian
- ✅ An toàn và không mất thời gian

**Mục tiêu cuối cùng:** Không bao giờ cháy nữa! 🚀
