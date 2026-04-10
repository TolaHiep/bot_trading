# Chiến Lược Scalping Cải Tiến

## Tổng Quan
Chiến lược scalping được thiết kế dựa trên lý thuyết giao dịch nhanh với các nguyên tắc:
- Tỉ lệ R:R (Risk:Reward): 1:1 đến 1:2
- Stop Loss cực kỳ chặt chẽ: 0.2% - 0.5% giá trị vị thế
- Take Profit nhanh: 0.3% - 1.0% tùy điều kiện thị trường
- Vào lệnh dựa trên Order Flow và cấu trúc giá

## Cấu Hình Mới

### 1. Entry Logic (Vào Lệnh)
**Điều kiện BUY:**
- Order Flow Delta > 0 (mua mạnh hơn bán)
- Giá chạm vùng hỗ trợ (Support) trên M1/M3
- RSI < 40 (oversold ngắn hạn)
- Volume tăng đột biến (> 1.5x trung bình)
- Bollinger Bands: Giá chạm dải dưới và bật lên

**Điều kiện SELL:**
- Order Flow Delta < 0 (bán mạnh hơn mua)
- Giá chạm vùng kháng cự (Resistance) trên M1/M3
- RSI > 60 (overbought ngắn hạn)
- Volume tăng đột biến (> 1.5x trung bình)
- Bollinger Bands: Giá chạm dải trên và giảm xuống

### 2. Stop Loss (Cắt Lỗ)
**Phương pháp:**
- **ATR-based**: SL = 1.0 × ATR(14) trên M1
- **Fixed %**: 0.3% - 0.5% giá trị vị thế
- **Cấu trúc**: Đặt dưới đáy gần nhất (BUY) hoặc trên đỉnh gần nhất (SELL)

**Breakeven Logic:**
- Khi lãi đạt 0.3% (1:1 R:R), dời SL về điểm vào lệnh
- Khi lãi đạt 0.5%, dời SL lên +0.2% để bảo vệ lợi nhuận

### 3. Take Profit (Chốt Lời)
**Phương pháp:**
- **Target 1**: 0.3% - 0.5% (R:R = 1:1)
- **Target 2**: 0.6% - 1.0% (R:R = 1:2)
- **Bollinger Bands**: Chốt khi giá chạm dải trên (BUY) hoặc dải dưới (SELL)
- **Resistance/Support**: Chốt trước khi chạm vùng kháng cự/hỗ trợ mạnh

**Trailing Stop:**
- Kích hoạt khi lãi > 0.5%
- Khoảng cách trailing: 0.2% (giữ lại 40% lợi nhuận nếu đảo chiều)

### 4. Risk Management
**Position Sizing:**
- Risk per trade: 2% - 3% equity (giảm từ 5%)
- Leverage: 10x - 15x (giảm từ 20x)
- Max positions: 3-5 cùng lúc
- Max exposure: 50% equity

**Kill Switch:**
- 3 lệnh thua liên tiếp → Dừng 15 phút
- Daily drawdown > 3% → Dừng giao dịch trong ngày
- Equity < $10 → Báo cáo và reset

### 5. Phí Giao Dịch
**Tính toán:**
- Bybit Taker Fee: 0.055% (0.00055)
- Với leverage 10x: Phí thực tế = 0.055% × 2 (vào + ra) = 0.11%
- Lợi nhuận tối thiểu: 0.3% (> 3× phí giao dịch)

**Ví dụ:**
- Entry: $100 × 10x = $1000 position → Phí = $0.55
- Exit: $1000 position → Phí = $0.55
- Tổng phí: $1.10
- Lợi nhuận 0.3%: $3.00
- Net profit: $3.00 - $1.10 = $1.90 ✅

## Cấu Hình Config

```yaml
scalping:
  enabled: true
  symbols: []  # Empty = use multi_symbol scanner
  
  # Entry Signals
  entry:
    rsi_period: 14
    rsi_oversold: 40
    rsi_overbought: 60
    volume_multiplier: 1.5  # Volume > 1.5x average
    delta_threshold: 100  # Order flow delta threshold
    bb_period: 20
    bb_std: 2
    
  # Stop Loss
  stop_loss:
    method: "atr"  # "atr", "fixed", "structure"
    atr_period: 14
    atr_multiplier: 1.0
    fixed_pct: 0.004  # 0.4%
    breakeven_profit_pct: 0.003  # 0.3% - Move to breakeven
    breakeven_lock_pct: 0.005  # 0.5% - Lock profit at +0.2%
    
  # Take Profit
  take_profit:
    target1_pct: 0.004  # 0.4% (R:R 1:1)
    target2_pct: 0.008  # 0.8% (R:R 1:2)
    use_bb_exit: true  # Exit at Bollinger Bands
    use_resistance_exit: true  # Exit before resistance/support
    trailing_activation_pct: 0.005  # 0.5%
    trailing_distance_pct: 0.002  # 0.2%
    
  # Risk Management
  risk:
    risk_per_trade: 0.025  # 2.5%
    leverage: 12.0  # 12x
    max_positions: 5
    max_exposure_pct: 0.50  # 50%
    
  # Kill Switch
  kill_switch:
    max_consecutive_losses: 3
    cooldown_minutes: 15
    daily_drawdown_limit: 0.03  # 3%
    
  # Fees
  fees:
    taker_fee: 0.00055  # 0.055%
    min_profit_multiplier: 3.0  # Min profit = 3x fees
```

## Ưu Điểm Của Chiến Lược Mới

1. **R:R Hợp Lý**: 1:1 đến 1:2 phù hợp với scalping
2. **SL Chặt Chẽ**: 0.3-0.5% giúp bảo vệ vốn
3. **TP Nhanh**: 0.4-0.8% dễ đạt được trong biến động ngắn
4. **Phí Tối Ưu**: Lợi nhuận > 3x phí giao dịch
5. **Breakeven Logic**: Bảo vệ lợi nhuận sớm
6. **Kill Switch**: Ngăn chặn thua lỗ liên tiếp

## Kết Quả Kỳ Vọng

**Với 100 lệnh:**
- Win rate: 55-60%
- Average win: +$2.00 (0.4% × $500 position)
- Average loss: -$2.00 (0.4% × $500 position)
- Net profit: (60 × $2) - (40 × $2) = $40
- ROI: 40% trên $100 vốn

**Lưu ý:**
- Cần backtest trên dữ liệu thực
- Điều chỉnh tham số theo từng coin
- Theo dõi slippage và fees thực tế
