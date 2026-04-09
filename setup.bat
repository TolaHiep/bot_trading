@echo off
REM Complete System Setup Script for Trading Bot (Windows)
REM This script will set up everything from scratch

echo ==========================================
echo 🚀 Trading Bot - Complete Setup
echo ==========================================
echo.

REM Step 1: Check prerequisites
echo ==========================================
echo Step 1: Checking Prerequisites
echo ==========================================
echo.

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed
    echo    Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo ✅ Docker is installed

docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose is not installed
    pause
    exit /b 1
)
echo ✅ Docker Compose is installed

docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running
    echo    Please start Docker Desktop
    pause
    exit /b 1
)
echo ✅ Docker is running

if not exist ".env" (
    echo ❌ .env file not found
    echo    Please create .env file from .env.example
    echo    Run: copy .env.example .env
    echo    Then edit .env with your Bybit API credentials
    pause
    exit /b 1
)
echo ✅ .env file exists

echo.

REM Step 2: Stop existing containers
echo ==========================================
echo Step 2: Cleaning Up Old Containers
echo ==========================================
echo.

echo 📝 Stopping existing containers...
docker compose down 2>nul
echo ✅ Cleanup completed
echo.

REM Step 3: Build and start containers
echo ==========================================
echo Step 3: Building and Starting Containers
echo ==========================================
echo.

echo 📝 Building Docker images...
docker compose build

echo 📝 Starting containers...
docker compose up -d

echo 📝 Waiting for database to be ready - 30 seconds...
timeout /t 30 /nobreak >nul

docker compose ps | findstr "Up" >nul
if %errorlevel% neq 0 (
    echo ❌ Containers failed to start
    echo    Check logs: docker compose logs
    pause
    exit /b 1
)
echo ✅ Containers are running
echo.

REM Step 4: Setup database
echo ==========================================
echo Step 4: Setting Up Database
echo ==========================================
echo.

echo 📝 Creating database 'trading_db'...
docker compose exec -T timescaledb psql -U trading_user -d postgres -c "CREATE DATABASE trading_db;" 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  Database already exists
)

echo 📝 Enabling TimescaleDB extension...
docker compose exec -T timescaledb psql -U trading_user -d trading_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >nul

echo 📝 Creating tables...
(
echo CREATE TABLE IF NOT EXISTS klines ^(
echo     timestamp TIMESTAMPTZ NOT NULL,
echo     symbol TEXT NOT NULL,
echo     timeframe TEXT NOT NULL,
echo     open NUMERIC NOT NULL,
echo     high NUMERIC NOT NULL,
echo     low NUMERIC NOT NULL,
echo     close NUMERIC NOT NULL,
echo     volume NUMERIC NOT NULL,
echo     PRIMARY KEY ^(timestamp, symbol, timeframe^)
echo ^);
echo.
echo SELECT create_hypertable^('klines', 'timestamp', if_not_exists =^> TRUE^);
echo CREATE INDEX IF NOT EXISTS idx_klines_symbol_timeframe ON klines ^(symbol, timeframe, timestamp DESC^);
echo.
echo CREATE TABLE IF NOT EXISTS trades ^(
echo     timestamp TIMESTAMPTZ NOT NULL,
echo     symbol TEXT NOT NULL,
echo     trade_id TEXT NOT NULL,
echo     price NUMERIC NOT NULL,
echo     quantity NUMERIC NOT NULL,
echo     side TEXT NOT NULL,
echo     PRIMARY KEY ^(timestamp, symbol, trade_id^)
echo ^);
echo.
echo SELECT create_hypertable^('trades', 'timestamp', if_not_exists =^> TRUE^);
echo CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades ^(symbol, timestamp DESC^);
echo.
echo CREATE TABLE IF NOT EXISTS signals ^(
echo     id SERIAL PRIMARY KEY,
echo     timestamp TIMESTAMPTZ NOT NULL,
echo     symbol TEXT NOT NULL,
echo     direction TEXT NOT NULL,
echo     confidence INTEGER NOT NULL,
echo     reasons JSONB NOT NULL,
echo     indicators JSONB NOT NULL,
echo     order_flow JSONB NOT NULL,
echo     wyckoff_phase TEXT NOT NULL
echo ^);
echo.
echo CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals ^(timestamp DESC^);
echo.
echo CREATE TABLE IF NOT EXISTS completed_trades ^(
echo     id SERIAL PRIMARY KEY,
echo     trade_id TEXT UNIQUE NOT NULL,
echo     symbol TEXT NOT NULL,
echo     side TEXT NOT NULL,
echo     entry_price NUMERIC NOT NULL,
echo     exit_price NUMERIC NOT NULL,
echo     quantity NUMERIC NOT NULL,
echo     opened_at TIMESTAMPTZ NOT NULL,
echo     closed_at TIMESTAMPTZ NOT NULL,
echo     pnl NUMERIC NOT NULL,
echo     pnl_percentage NUMERIC NOT NULL,
echo     commission NUMERIC NOT NULL,
echo     slippage NUMERIC NOT NULL,
echo     exit_reason TEXT NOT NULL
echo ^);
echo.
echo CREATE INDEX IF NOT EXISTS idx_completed_trades_closed_at ON completed_trades ^(closed_at DESC^);
) | docker compose exec -T timescaledb psql -U trading_user -d trading_db >nul

echo ✅ Database setup completed
echo.

REM Step 5: Verify setup
echo ==========================================
echo Step 5: Verifying Setup
echo ==========================================
echo.

echo 📝 Checking database tables...
for /f %%i in ('docker compose exec -T timescaledb psql -U trading_user -d trading_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"') do set TABLE_COUNT=%%i
if %TABLE_COUNT% geq 4 (
    echo ✅ Database tables created ^(%TABLE_COUNT% tables^)
) else (
    echo ❌ Database tables not created properly
    pause
    exit /b 1
)

echo 📝 Testing Bybit connection...
docker compose exec -T trading_bot python scripts/test_connection_docker.py >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Bybit connection successful
) else (
    echo ⚠️  Bybit connection test failed
    echo    This might be due to:
    echo    1. API keys not configured in .env
    echo    2. System time not synchronized
    echo    3. Network issues
    echo.
    echo    Run this to test manually:
    echo    docker compose exec trading_bot python scripts/test_connection_docker.py
)

echo.

REM Step 6: Summary
echo ==========================================
echo 🎉 Setup Completed Successfully!
echo ==========================================
echo.
echo 📊 System Status:
docker compose ps
echo.
echo 🌐 Access Points:
echo    Dashboard: http://localhost:8501
echo    Telegram Bot: Send /start to your bot
echo.
echo ✅ All services are running automatically:
echo    - TimescaleDB ^(Database^)
echo    - Trading Bot ^(Main application^)
echo    - Telegram Bot ^(Alerts ^& commands^)
echo    - Dashboard ^(Monitoring UI^)
echo.
echo 📚 Next Steps:
echo.
echo 1. Download historical data ^(for backtesting, ~6-7 minutes^):
echo    docker compose exec trading_bot python scripts/download_historical_data.py
echo.
echo 2. Run backtest ^(see USER_GUIDE.md for details^):
echo    Follow 'Trading Workflow' section in USER_GUIDE.md
echo.
echo 3. View logs:
echo    docker compose logs -f trading_bot      # Main bot
echo    docker compose logs -f telegram_bot     # Telegram alerts
echo    docker compose logs -f dashboard        # Dashboard
echo.
echo 4. Stop all services:
echo    docker compose down
echo.
echo 5. Restart all services:
echo    docker compose restart
echo.
echo 📖 Documentation:
echo    - User Guide: USER_GUIDE.md
echo    - Installation: docs/INSTALLATION_GUIDE.md
echo    - Troubleshooting: docs/TROUBLESHOOTING.md
echo.
echo ⚠️  Important Notes:
echo    - If Telegram bot not responding: Check TELEGRAM_BOT_TOKEN in .env
echo    - Dashboard shows mock data until you start trading
echo    - Always test on Testnet before Live trading
echo.
echo ✅ Your trading bot is ready to use!
echo.
pause
