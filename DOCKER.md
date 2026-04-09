# Docker Development Guide

## Tổng Quan

Project này sử dụng Docker để đảm bảo môi trường phát triển đồng nhất. Tất cả services (Database, Trading Bot, Dashboard) đều chạy trong Docker containers.

## Kiến Trúc Docker

```
┌─────────────────────────────────────────────┐
│           Docker Network                     │
│                                              │
│  ┌──────────────┐      ┌──────────────┐    │
│  │ TimescaleDB  │◄─────┤ Trading Bot  │    │
│  │   (Port      │      │              │    │
│  │    5432)     │      │              │    │
│  └──────────────┘      └──────────────┘    │
│         ▲                                    │
│         │                                    │
│  ┌──────────────┐                           │
│  │  Dashboard   │                           │
│  │  (Port 8501) │                           │
│  └──────────────┘                           │
└─────────────────────────────────────────────┘
```

## Services

### 1. TimescaleDB
- **Container**: `trading_bot_db`
- **Port**: 5432
- **Purpose**: Lưu trữ OHLCV data, trades, signals
- **Auto-start**: Yes

### 2. Trading Bot
- **Container**: `trading_bot_app`
- **Purpose**: Main trading application
- **Auto-start**: Yes (development mode)
- **Volumes**: Code được mount để hot-reload

### 3. Dashboard (Optional)
- **Container**: `trading_bot_dashboard`
- **Port**: 8501
- **Purpose**: Streamlit monitoring dashboard
- **Auto-start**: No (start manually khi cần)

## Quick Start

### Bước 1: Chuẩn Bị

Đảm bảo bạn đã:
- ✅ Cài Docker Desktop
- ✅ Tạo file `.env` với API credentials
- ✅ Update API Key và Secret trong `.env`

### Bước 2: Build và Start Services

**Windows (PowerShell)**:
```powershell
# Build Docker images
.\scripts\docker-dev.ps1 build

# Start all services
.\scripts\docker-dev.ps1 start

# Check status
.\scripts\docker-dev.ps1 status
```

**Linux/macOS (Bash)**:
```bash
# Make script executable
chmod +x scripts/docker-dev.sh

# Build Docker images
./scripts/docker-dev.sh build

# Start all services
./scripts/docker-dev.sh start

# Check status
./scripts/docker-dev.sh status
```

**Hoặc dùng Docker Compose trực tiếp**:
```bash
# Build
docker compose build

# Start
docker compose up -d

# Check status
docker compose ps
```

### Bước 3: Verify Setup

**Test Bybit Connection**:
```powershell
# Windows
.\scripts\docker-dev.ps1 shell trading_bot
python scripts/test_connection_docker.py
exit

# Linux/macOS
./scripts/docker-dev.sh shell trading_bot
python scripts/test_connection_docker.py
exit
```

**Test Database Connection**:
```powershell
# Windows
.\scripts\docker-dev.ps1 db

# Linux/macOS
./scripts/docker-dev.sh db
```

Trong PostgreSQL shell:
```sql
-- Check tables
\dt

-- Check TimescaleDB extension
SELECT * FROM timescaledb_information.hypertables;

-- Exit
\q
```

## Development Workflow

### 1. Start Development

```powershell
# Start services
.\scripts\docker-dev.ps1 start

# View logs
.\scripts\docker-dev.ps1 logs trading_bot
```

### 2. Code Changes

Code trong `src/` được mount vào container, nên:
- ✅ Sửa code trên máy local (VS Code)
- ✅ Changes tự động sync vào container
- ✅ Không cần rebuild image

### 3. Run Tests

```powershell
# Run all tests
.\scripts\docker-dev.ps1 test

# Or run specific tests
docker compose exec trading_bot pytest tests/unit/ -v
docker compose exec trading_bot pytest tests/property/ -v
```

### 4. Access Container Shell

```powershell
# Open bash shell in trading_bot container
.\scripts\docker-dev.ps1 shell trading_bot

# Inside container, you can:
python scripts/download_historical_data.py
pytest tests/
python -m src.main
```

### 5. View Logs

```powershell
# All services
.\scripts\docker-dev.ps1 logs

# Specific service
.\scripts\docker-dev.ps1 logs trading_bot
.\scripts\docker-dev.ps1 logs timescaledb
```

### 6. Stop Services

```powershell
# Stop all services (keep data)
.\scripts\docker-dev.ps1 stop

# Stop and remove volumes (delete data)
.\scripts\docker-dev.ps1 clean
```

## Helper Scripts

### Windows (PowerShell)

```powershell
.\scripts\docker-dev.ps1 <command> [service]
```

### Linux/macOS (Bash)

```bash
./scripts/docker-dev.sh <command> [service]
```

### Available Commands

| Command | Description |
|---------|-------------|
| `start` | Start all services |
| `stop` | Stop all services |
| `restart` | Restart all services |
| `status` | Show service status |
| `logs` | Show logs (add service name for specific) |
| `shell` | Open shell in container |
| `test` | Run tests |
| `build` | Build Docker images |
| `clean` | Clean up Docker resources |
| `db` | Connect to database |

## Common Tasks

### Run Trading Bot

```powershell
# Start bot in container
docker compose exec trading_bot python -m src.main
```

### Download Historical Data

```powershell
docker compose exec trading_bot python scripts/download_historical_data.py
```

### Run Backtest

```powershell
docker compose exec trading_bot python -m src.backtest.engine
```

### Start Dashboard

```powershell
# Start dashboard service
docker compose --profile monitoring up -d dashboard

# Access at http://localhost:8501
```

### Database Operations

```powershell
# Connect to database
.\scripts\docker-dev.ps1 db

# Backup database
docker compose exec timescaledb pg_dump -U trading_user trading_bot > backup.sql

# Restore database
docker compose exec -T timescaledb psql -U trading_user trading_bot < backup.sql
```

## Troubleshooting

### Issue: Container won't start

```powershell
# Check logs
.\scripts\docker-dev.ps1 logs trading_bot

# Rebuild image
.\scripts\docker-dev.ps1 build
.\scripts\docker-dev.ps1 start
```

### Issue: Database connection failed

```powershell
# Check if database is healthy
docker compose ps

# Restart database
docker compose restart timescaledb

# Check database logs
.\scripts\docker-dev.ps1 logs timescaledb
```

### Issue: Port already in use

```powershell
# Check what's using port 5432
netstat -ano | findstr :5432

# Stop conflicting service or change port in docker-compose.yml
```

### Issue: Code changes not reflected

```powershell
# Restart trading_bot container
docker compose restart trading_bot

# Or rebuild if needed
.\scripts\docker-dev.ps1 build
```

### Issue: Out of disk space

```powershell
# Clean up unused Docker resources
.\scripts\docker-dev.ps1 clean

# Or manually
docker system prune -a --volumes
```

## Environment Variables

File `.env` được load vào containers. Các biến quan trọng:

```bash
# Bybit API
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret
BYBIT_TESTNET=true

# Database (auto-configured in docker-compose)
DATABASE_URL=postgresql://trading_user:trading_pass@timescaledb:5432/trading_bot

# Trading
TRADING_MODE=testnet
LOG_LEVEL=INFO
```

**Lưu ý**: `DATABASE_URL` trong container khác với local:
- **Local**: `localhost:5432`
- **Docker**: `timescaledb:5432` (service name)

## Production Deployment

Khi deploy lên production:

1. **Update docker-compose.yml**:
   - Remove volume mounts (use code in image)
   - Change restart policy
   - Add resource limits

2. **Build production image**:
   ```bash
   docker compose build --no-cache
   ```

3. **Use environment-specific configs**:
   ```bash
   docker compose --env-file .env.production up -d
   ```

4. **Enable monitoring**:
   ```bash
   docker compose --profile monitoring up -d
   ```

## Best Practices

1. **Development**:
   - ✅ Use volume mounts for hot-reload
   - ✅ Keep containers running with `tail -f /dev/null`
   - ✅ Use helper scripts for common tasks

2. **Testing**:
   - ✅ Run tests in container (same environment as production)
   - ✅ Use separate test database if needed

3. **Production**:
   - ✅ Remove volume mounts
   - ✅ Use specific image tags (not `latest`)
   - ✅ Set resource limits
   - ✅ Enable health checks
   - ✅ Use secrets management (not .env file)

## Next Steps

1. ✅ Verify Docker setup: `.\scripts\docker-dev.ps1 status`
2. ✅ Test Bybit connection: Run `test_connection_docker.py` in container
3. ✅ Test database: `.\scripts\docker-dev.ps1 db`
4. 🚀 Start development: Open `.kiro/specs/quantitative-trading-bot/tasks.md`

---

**Happy Dockering! 🐳**
