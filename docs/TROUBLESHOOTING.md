# Troubleshooting Guide - Xử lý sự cố

## Mục lục
1. [Docker Issues](#docker-issues)
2. [Network Connection Issues](#network-connection-issues)
3. [API Issues](#api-issues)
4. [Database Issues](#database-issues)
5. [Trading Issues](#trading-issues)
6. [Performance Issues](#performance-issues)
7. [Data Issues](#data-issues)
8. [Common Error Messages](#common-error-messages)

---

## Docker Issues

### Lỗi: Docker daemon not running

**Triệu chứng**:
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**Nguyên nhân**: Docker Desktop chưa khởi động

**Giải pháp**:

**Windows**:
```powershell
# Mở Docker Desktop từ Start Menu
# Đợi icon Docker màu xanh (running)

# Verify
docker ps
```

**macOS**:
```bash
# Mở Docker.app từ Applications
# Đợi icon Docker trên menu bar

# Verify
docker ps
```

**Linux**:
```bash
# Start Docker service
sudo systemctl start docker

# Enable auto-start
sudo systemctl enable docker

# Verify
docker ps
```

---

### Lỗi: Port already in use

**Triệu chứng**:
```
Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind: address already in use
```

**Nguyên nhân**: Port 5432 (PostgreSQL) hoặc 8501 (Streamlit) đang được dùng

**Giải pháp**:

**Option 1: Kill process đang dùng port**

**Windows**:
```powershell
# Tìm process
netstat -ano | findstr :5432

# Kill process (thay PID)
taskkill /PID <PID> /F
```

**Linux/macOS**:
```bash
# Tìm process
lsof -i :5432

# Kill process
kill -9 <PID>
```

**Option 2: Đổi port trong docker-compose.yml**

```yaml
services:
  timescaledb:
    ports:
      - "5433:5432"  # Đổi từ 5432 sang 5433
```

Sau đó update `.env`:
```bash
POSTGRES_PORT=5433
```

---

### Lỗi: Container keeps restarting

**Triệu chứng**:
```bash
docker compose ps
# NAME            STATUS
# trading_bot     Restarting (1) 10 seconds ago
```

**Nguyên nhân**: Container crash ngay sau khi start

**Giải pháp**:

1. **Check logs**:
```bash
docker compose logs trading_bot
```

2. **Common causes**:
   - Missing environment variables
   - Invalid configuration
   - Database connection failed
   - Python import errors

3. **Debug**:
```bash
# Run container interactively
docker compose run --rm trading_bot bash

# Test imports
python -c "import src"

# Test config
python -c "from src.config.config_manager import ConfigManager; cm = ConfigManager(); print(cm.config)"
```

---

### Lỗi: Out of disk space

**Triệu chứng**:
```
no space left on device
```

**Nguyên nhân**: Docker images/volumes chiếm hết disk

**Giải pháp**:

```bash
# Check disk usage
docker system df

# Clean up
docker system prune -a --volumes

# Remove specific images
docker image ls
docker image rm <IMAGE_ID>

# Remove specific volumes
docker volume ls
docker volume rm <VOLUME_NAME>
```

---

## Network Connection Issues

### Lỗi: Cannot reach Bybit API

**Triệu chứng**:
```
requests.exceptions.ConnectionError: Failed to establish a new connection
```

**Nguyên nhân**: Không kết nối được Bybit servers

**Giải pháp**:

1. **Check internet connection**:
```bash
# Ping Bybit
ping api.bybit.com

# Nếu không ping được
ping 8.8.8.8  # Test internet
```

2. **Check DNS**:
```bash
# Test DNS resolution
nslookup api.bybit.com

# Nếu fail, đổi DNS sang Google DNS (8.8.8.8)
```

3. **Check firewall**:
```bash
# Windows: Tắt Windows Firewall tạm thời
# Linux: Check iptables
sudo iptables -L

# Allow outbound HTTPS
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
```

4. **Check Bybit status**:
- Visit: https://bybit-exchange.github.io/docs/status
- Check Twitter: @Bybit_Official
- Check: https://status.bybit.com

5. **Use VPN** (nếu Bybit bị block ở quốc gia bạn):
```bash
# Connect VPN trước khi start bot
```

---

### Lỗi: Timeout errors

**Triệu chứng**:
```
requests.exceptions.Timeout: Read timed out
```

**Nguyên nhân**: Network latency cao hoặc Bybit servers chậm

**Giải pháp**:

1. **Check latency**:
```bash
# Ping Bybit
ping api.bybit.com

# Nên < 200ms
```

2. **Increase timeout** trong code:
```python
# src/connectors/bybit_rest.py
self.session.timeout = 30  # Tăng từ 10 lên 30
```

3. **Use closer server**:
- Nếu ở Châu Á: api.bybit.com
- Nếu ở Châu Âu: api-eu.bybit.com

---

### Lỗi: SSL Certificate errors

**Triệu chứng**:
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Nguyên nhân**: SSL certificate không valid hoặc system time sai

**Giải pháp**:

1. **Check system time**:
```bash
# Linux/macOS
date

# Windows
date /t && time /t

# Nếu sai, sync time
sudo ntpdate -s time.nist.gov  # Linux
```

2. **Update CA certificates**:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install ca-certificates

# macOS
brew install ca-certificates
```

3. **Temporary workaround** (KHÔNG khuyến nghị cho production):
```python
# Disable SSL verification (INSECURE)
import requests
requests.get(url, verify=False)
```

---

## API Issues

### Lỗi: Invalid API key

**Triệu chứng**:
```
APIError: Invalid API key
```

**Nguyên nhân**: API key sai hoặc đã bị revoke

**Giải pháp**:

1. **Verify API key trong .env**:
```bash
cat .env | grep BYBIT_API_KEY
cat .env | grep BYBIT_API_SECRET
```

2. **Check testnet vs mainnet**:
```bash
cat .env | grep BYBIT_TESTNET

# Nếu testnet=true, phải dùng testnet API key
# Nếu testnet=false, phải dùng mainnet API key
```

3. **Regenerate API key**:
- Login Bybit (testnet hoặc mainnet)
- API Management → Delete old key
- Create new key với quyền:
  - ✅ Read-Write
  - ✅ Contract Trading
  - ✅ Wallet
- Copy key mới vào `.env`

4. **Restart bot**:
```bash
docker compose restart trading_bot
```

---

### Lỗi: API rate limit exceeded

**Triệu chứng**:
```
APIError: Rate limit exceeded
```

**Nguyên nhân**: Quá nhiều requests trong thời gian ngắn

**Giải pháp**:

1. **Check rate limiter config**:
```yaml
# config/config.yaml
rate_limiter:
  max_requests: 600
  window_seconds: 5
```

2. **Reduce request frequency**:
```python
# src/connectors/rate_limiter.py
# Tăng delay giữa requests
await asyncio.sleep(0.1)  # 100ms delay
```

3. **Use WebSocket thay vì REST** cho real-time data:
```python
# Dùng WebSocket cho klines, trades, orderbook
# Chỉ dùng REST cho placing orders
```

4. **Wait và retry**:
```bash
# Bot sẽ tự động retry với exponential backoff
# Đợi 1-2 phút rồi requests sẽ hoạt động lại
```

---

### Lỗi: API signature invalid

**Triệu chứng**:
```
APIError: Invalid signature
```

**Nguyên nhân**: System time sai hoặc signature generation lỗi

**Giải pháp**:

1. **Sync system time**:
```bash
# Linux
sudo ntpdate -s time.nist.gov

# macOS
sudo sntp -sS time.apple.com

# Windows
w32tm /resync
```

2. **Check time drift**:
```bash
docker compose exec trading_bot python -c "
from src.connectors.ntp_sync import NTPSync

ntp = NTPSync()
drift = ntp.get_time_drift()
print(f'Time drift: {drift}ms')
"

# Nếu drift > 1000ms, sync lại
```

3. **Verify API secret**:
```bash
# Đảm bảo không có space hoặc newline
cat .env | grep BYBIT_API_SECRET | od -c
```

---

### Lỗi: Insufficient balance

**Triệu chứng**:
```
APIError: Insufficient balance
```

**Nguyên nhân**: Không đủ tiền trong account

**Giải pháp**:

1. **Check balance trên Bybit UI**:
- Login Bybit
- Assets → Contract Account
- Verify balance

2. **Check bot balance**:
```bash
docker compose exec trading_bot python scripts/test_connection_docker.py
```

3. **Deposit thêm tiền** (nếu mainnet)

4. **Reduce position size**:
```yaml
# config/strategy_params.yaml
risk:
  max_position_size: 0.05  # Giảm từ 0.10 xuống 0.05
```

---

## Database Issues

### Lỗi: Database connection refused

**Triệu chứng**:
```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**Nguyên nhân**: TimescaleDB container chưa ready hoặc crashed

**Giải pháp**:

1. **Check container status**:
```bash
docker compose ps timescaledb

# Nên thấy: Up (healthy)
```

2. **Check logs**:
```bash
docker compose logs timescaledb

# Tìm errors
```

3. **Restart database**:
```bash
docker compose restart timescaledb

# Đợi 30 giây cho DB khởi động
sleep 30
```

4. **Verify connection**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -c "SELECT 1"

# Nên thấy: 1
```

5. **Restart bot**:
```bash
docker compose restart trading_bot
```

---

### Lỗi: Database authentication failed

**Triệu chứng**:
```
psycopg2.OperationalError: FATAL: password authentication failed
```

**Nguyên nhân**: Username/password sai trong `.env`

**Giải pháp**:

1. **Check credentials**:
```bash
cat .env | grep POSTGRES_USER
cat .env | grep POSTGRES_PASSWORD
cat .env | grep POSTGRES_DB
```

2. **Reset database** (⚠️ MẤT DATA):
```bash
# Stop containers
docker compose down

# Remove volumes
docker volume rm bot_trading_timescaledb_data

# Start lại
docker compose up -d

# Chạy migrations
docker compose exec trading_bot python -c "
from src.data.timescaledb_writer import TimescaleDBWriter
import asyncio

async def init():
    writer = TimescaleDBWriter()
    await writer.connect()
    await writer.create_tables()

asyncio.run(init())
"
```

---

### Lỗi: Table does not exist

**Triệu chứng**:
```
psycopg2.errors.UndefinedTable: relation "klines" does not exist
```

**Nguyên nhân**: Database schema chưa được tạo

**Giải pháp**:

1. **Run migrations**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -f /migrations/001_init.sql
```

2. **Hoặc tạo tables qua Python**:
```bash
docker compose exec trading_bot python -c "
from src.data.timescaledb_writer import TimescaleDBWriter
import asyncio

async def init():
    writer = TimescaleDBWriter()
    await writer.connect()
    await writer.create_tables()
    print('Tables created')

asyncio.run(init())
"
```

3. **Verify tables**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -c "\dt"

# Nên thấy: klines, trades, orderbooks, positions, orders
```

---

### Lỗi: Disk full (database)

**Triệu chứng**:
```
ERROR: could not extend file: No space left on device
```

**Nguyên nhân**: Database volume đầy

**Giải pháp**:

1. **Check disk usage**:
```bash
docker compose exec timescaledb df -h
```

2. **Clean old data**:
```bash
# Delete data older than 6 months
docker compose exec timescaledb psql -U trading_user -d trading_db -c "
DELETE FROM klines WHERE timestamp < NOW() - INTERVAL '6 months';
DELETE FROM trades WHERE timestamp < NOW() - INTERVAL '6 months';
DELETE FROM orderbooks WHERE timestamp < NOW() - INTERVAL '6 months';
"
```

3. **Vacuum database**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -c "VACUUM FULL"
```

4. **Increase disk space** (Docker Desktop Settings → Resources → Disk image size)

---

## Trading Issues

### Lỗi: No signals generated

**Triệu chứng**: Bot chạy nhưng không có signals

**Nguyên nhân**: 
- Confidence threshold quá cao
- Market không có setup
- Indicators chưa đủ data

**Giải pháp**:

1. **Check logs**:
```bash
docker compose logs trading_bot | grep "Signal"
```

2. **Lower confidence threshold**:
```yaml
# config/strategy_params.yaml
signal:
  min_confidence: 50  # Giảm từ 60 xuống 50
```

3. **Check indicator data**:
```bash
docker compose exec trading_bot python -c "
from src.alpha.indicators import IndicatorEngine

engine = IndicatorEngine()
# Check if indicators have enough data
print(engine.get_indicator_values())
"
```

4. **Wait for data accumulation**:
- Bot cần ít nhất 200 candles để tính indicators
- Đợi 3-4 giờ cho 1m timeframe

---

### Lỗi: Orders not filling

**Triệu chứng**: Orders pending quá lâu, không fill

**Nguyên nhân**:
- Limit order price quá xa market
- Low liquidity
- Order size quá lớn

**Giải pháp**:

1. **Check order price**:
```bash
# Verify order price vs current market price
docker compose logs trading_bot | grep "Order placed"
```

2. **Reduce timeout**:
```yaml
# config/strategy_params.yaml
execution:
  order_timeout: 3  # Giảm từ 5 xuống 3 giây
```

3. **Use market orders**:
```python
# src/execution/order_manager.py
# Đổi từ limit sang market order
order_type = "Market"
```

4. **Reduce position size**:
```yaml
risk:
  max_position_size: 0.05  # Giảm size
```

---

### Lỗi: Slippage too high

**Triệu chứng**: Orders bị reject vì slippage > threshold

**Nguyên nhân**: Low liquidity hoặc volatile market

**Giải pháp**:

1. **Increase slippage tolerance**:
```yaml
# config/strategy_params.yaml
execution:
  max_slippage: 0.002  # Tăng từ 0.001 lên 0.002
```

2. **Trade liquid pairs**:
- BTCUSDT, ETHUSDT có liquidity tốt
- Tránh altcoins ít volume

3. **Avoid volatile times**:
- Không trade khi có news lớn
- Tránh market open/close

---

### Lỗi: Stop loss not triggered

**Triệu chứng**: Price đi qua SL nhưng không close position

**Nguyên nhân**:
- SL order bị cancel
- API lag
- Price gap

**Giải pháp**:

1. **Check SL orders trên Bybit UI**:
- Verify SL order exists
- Check order status

2. **Enable emergency close**:
```python
# src/risk/stop_loss.py
# Emergency market close nếu SL fail
if sl_order_cancelled:
    await self.emergency_close_position()
```

3. **Use tighter SL**:
```yaml
risk:
  stop_loss_pct: 0.015  # Chặt hơn
```

4. **Monitor positions**:
```bash
# Check positions every second
docker compose logs -f trading_bot | grep "Position"
```

---

## Performance Issues

### Lỗi: High CPU usage

**Triệu chứng**: Docker container dùng > 80% CPU

**Nguyên nhân**:
- Quá nhiều calculations
- Inefficient code
- Memory leak

**Giải pháp**:

1. **Check CPU usage**:
```bash
docker stats trading_bot
```

2. **Profile code**:
```bash
docker compose exec trading_bot python -m cProfile -o profile.stats main.py

# Analyze
python -m pstats profile.stats
```

3. **Optimize calculations**:
```python
# Use numpy vectorized operations
# Cache indicator values
# Reduce calculation frequency
```

4. **Limit resources**:
```yaml
# docker-compose.yml
services:
  trading_bot:
    deploy:
      resources:
        limits:
          cpus: '2.0'
```

---

### Lỗi: High memory usage

**Triệu chứng**: Container dùng > 4GB RAM

**Nguyên nhân**:
- Memory leak
- Too much data in memory
- Large dataframes

**Giải pháp**:

1. **Check memory**:
```bash
docker stats trading_bot
```

2. **Find memory leaks**:
```bash
docker compose exec trading_bot python -c "
import tracemalloc
tracemalloc.start()

# Run bot
# ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
"
```

3. **Limit data retention**:
```python
# Keep only last 1000 candles in memory
self.klines = self.klines[-1000:]
```

4. **Use generators**:
```python
# Instead of loading all data
for chunk in pd.read_csv('data.csv', chunksize=1000):
    process(chunk)
```

---

### Lỗi: Slow backtest

**Triệu chứng**: Backtest 1 năm mất > 10 phút

**Nguyên nhân**:
- Inefficient data loading
- Too many calculations
- Not using vectorization

**Giải pháp**:

1. **Use TimescaleDB continuous aggregates**:
```sql
-- Pre-aggregate 1m to 5m, 15m, 1h
CREATE MATERIALIZED VIEW klines_5m AS
SELECT time_bucket('5 minutes', timestamp) AS timestamp,
       symbol,
       first(open, timestamp) AS open,
       max(high) AS high,
       min(low) AS low,
       last(close, timestamp) AS close,
       sum(volume) AS volume
FROM klines
GROUP BY time_bucket('5 minutes', timestamp), symbol;
```

2. **Vectorize calculations**:
```python
# Use pandas/numpy operations
df['sma'] = df['close'].rolling(20).mean()
```

3. **Parallel processing**:
```python
# Use multiprocessing for grid search
from multiprocessing import Pool
with Pool(4) as p:
    results = p.map(backtest, param_combinations)
```

---

## Data Issues

### Lỗi: Missing candles

**Triệu chứng**: Gaps trong time-series data

**Nguyên nhân**:
- WebSocket disconnect
- Data validation reject
- Bybit data issue

**Giải pháp**:

1. **Detect gaps**:
```bash
docker compose exec trading_bot python -c "
from src.data.gap_detector import GapDetector

detector = GapDetector()
gaps = detector.detect_gaps('BTCUSDT', '1m')
print(f'Found {len(gaps)} gaps')
"
```

2. **Fill gaps**:
```bash
docker compose exec trading_bot python -c "
from src.data.gap_detector import GapDetector

detector = GapDetector()
detector.fill_gaps('BTCUSDT', '1m')
print('Gaps filled')
"
```

3. **Enable auto gap filling**:
```yaml
# config/config.yaml
data:
  auto_fill_gaps: true
  gap_check_interval: 3600  # Check every hour
```

---

### Lỗi: Duplicate data

**Triệu chứng**: Same timestamp appears multiple times

**Nguyên nhân**: Deduplication not working

**Giải pháp**:

1. **Check duplicates**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -c "
SELECT timestamp, symbol, timeframe, COUNT(*)
FROM klines
GROUP BY timestamp, symbol, timeframe
HAVING COUNT(*) > 1;
"
```

2. **Remove duplicates**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -c "
DELETE FROM klines a USING klines b
WHERE a.ctid < b.ctid
  AND a.timestamp = b.timestamp
  AND a.symbol = b.symbol
  AND a.timeframe = b.timeframe;
"
```

3. **Add unique constraint**:
```sql
ALTER TABLE klines ADD CONSTRAINT klines_unique 
UNIQUE (timestamp, symbol, timeframe);
```

---

### Lỗi: Invalid data

**Triệu chứng**: Negative prices, zero volume, etc.

**Nguyên nhân**: Data validation not catching errors

**Giải pháp**:

1. **Find invalid data**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -c "
SELECT * FROM klines 
WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 OR volume < 0
LIMIT 10;
"
```

2. **Delete invalid data**:
```bash
docker compose exec timescaledb psql -U trading_user -d trading_db -c "
DELETE FROM klines 
WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 OR volume < 0;
"
```

3. **Strengthen validation**:
```python
# src/data/validator.py
def validate_kline(kline):
    assert kline['open'] > 0
    assert kline['high'] >= kline['open']
    assert kline['low'] <= kline['open']
    assert kline['close'] > 0
    assert kline['volume'] >= 0
    assert kline['high'] >= kline['low']
```

---

## Common Error Messages

### `ModuleNotFoundError: No module named 'src'`

**Giải pháp**:
```bash
# Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/app"

# Hoặc trong Dockerfile
ENV PYTHONPATH=/app
```

---

### `KeyError: 'BYBIT_API_KEY'`

**Giải pháp**:
```bash
# Check .env file exists
ls -la .env

# Check variable exists
cat .env | grep BYBIT_API_KEY

# Restart container
docker compose restart trading_bot
```

---

### `ValueError: Invalid configuration`

**Giải pháp**:
```bash
# Validate config
docker compose exec trading_bot python -c "
from src.config.validator import ConfigValidator

validator = ConfigValidator()
validator.validate_config('config/strategy_params.yaml')
"
```

---

### `RuntimeError: Event loop is closed`

**Giải pháp**:
```python
# Use asyncio.run() instead of loop.run_until_complete()
import asyncio

async def main():
    # Your async code
    pass

asyncio.run(main())
```

---

### `MemoryError: Unable to allocate array`

**Giải pháp**:
```bash
# Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory → 8GB

# Reduce data size
# Keep only last N candles
df = df.tail(10000)
```

---

## Getting Help

Nếu vẫn không giải quyết được:

1. **Collect information**:
```bash
# System info
docker compose version
docker --version
python --version

# Logs
docker compose logs trading_bot > logs.txt
docker compose logs timescaledb > db_logs.txt

# Config
cat .env > env.txt  # Remove sensitive data first
cat config/strategy_params.yaml > config.txt
```

2. **Create GitHub issue**:
- Title: Brief description
- Body: 
  - What you were trying to do
  - What happened
  - What you expected
  - Logs (attach files)
  - System info

3. **Check existing issues**:
- https://github.com/TolaHiep/bot_trading/issues

4. **Community resources**:
- Bybit API docs: https://bybit-exchange.github.io/docs/
- TimescaleDB docs: https://docs.timescale.com/
- Docker docs: https://docs.docker.com/

---

## Prevention Tips

### Regular Maintenance

```bash
# Weekly
docker compose logs trading_bot | grep ERROR > weekly_errors.txt
docker system prune -f

# Monthly
docker compose exec timescaledb psql -U trading_user -d trading_db -c "VACUUM ANALYZE"
docker compose exec timescaledb pg_dump -U trading_user trading_db > backup_$(date +%Y%m%d).sql
```

### Monitoring

```bash
# Setup cron job to check health
*/5 * * * * docker compose ps | grep -q "Up" || echo "Bot down!" | mail -s "Alert" your@email.com
```

### Backups

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec timescaledb pg_dump -U trading_user trading_db > backup_$DATE.sql
docker compose exec trading_bot tar -czf config_$DATE.tar.gz config/
```

---

**Lưu ý**: Luôn backup data trước khi thực hiện các thao tác có thể mất data (DROP, DELETE, TRUNCATE, etc.)
