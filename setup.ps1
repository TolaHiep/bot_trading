# Complete System Setup Script for Trading Bot (Windows PowerShell)
# This script will set up everything from scratch

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 Trading Bot - Complete Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Print-Success {
    param($Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Print-Error {
    param($Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Print-Warning {
    param($Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Print-Info {
    param($Message)
    Write-Host "📝 $Message" -ForegroundColor Cyan
}

# Step 1: Check prerequisites
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 1: Checking Prerequisites" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
try {
    $null = docker --version
    Print-Success "Docker is installed"
} catch {
    Print-Error "Docker is not installed"
    Write-Host "   Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
}

# Check Docker Compose
try {
    $null = docker compose version
    Print-Success "Docker Compose is installed"
} catch {
    Print-Error "Docker Compose is not installed"
    Write-Host "   Please install Docker Compose"
    exit 1
}

# Check if Docker is running
try {
    $null = docker ps 2>$null
    Print-Success "Docker is running"
} catch {
    Print-Error "Docker is not running"
    Write-Host "   Please start Docker Desktop"
    exit 1
}

# Check .env file
if (-not (Test-Path ".env")) {
    Print-Error ".env file not found"
    Write-Host "   Please create .env file from .env.example"
    Write-Host "   Run: Copy-Item .env.example .env"
    Write-Host "   Then edit .env with your Bybit API credentials"
    exit 1
}
Print-Success ".env file exists"

# Check API keys in .env
$envContent = Get-Content ".env" -Raw
if ($envContent -match "your_testnet_api_key" -or $envContent -match "your_api_key_here") {
    Print-Warning "API keys not configured in .env"
    Write-Host "   Please update BYBIT_API_KEY and BYBIT_API_SECRET in .env file"
    $continue = Read-Host "   Continue anyway? (y/n)"
    if ($continue -ne "y") {
        exit 1
    }
}

Write-Host ""

# Step 2: Stop existing containers
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 2: Cleaning Up Old Containers" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Print-Info "Stopping existing containers..."
docker compose down 2>$null
Print-Success "Cleanup completed"
Write-Host ""

# Step 3: Build and start containers
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 3: Building and Starting Containers" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Print-Info "Building Docker images..."
docker compose build

Print-Info "Starting containers..."
docker compose up -d

Print-Info "Waiting for database to be ready (30 seconds)..."
Start-Sleep -Seconds 30

# Check if containers are running
$status = docker compose ps
if ($status -notmatch "Up") {
    Print-Error "Containers failed to start"
    Write-Host "   Check logs: docker compose logs"
    exit 1
}
Print-Success "Containers are running"
Write-Host ""

# Step 4: Setup database
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 4: Setting Up Database" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Print-Info "Creating database 'trading_db'..."
docker compose exec -T timescaledb psql -U trading_user -d postgres -c "CREATE DATABASE trading_db;" 2>$null
if ($LASTEXITCODE -ne 0) {
    Print-Warning "Database already exists"
}

Print-Info "Enabling TimescaleDB extension..."
docker compose exec -T timescaledb psql -U trading_user -d trading_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" | Out-Null

Print-Info "Creating tables..."
$sql = @"
CREATE TABLE IF NOT EXISTS klines (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    PRIMARY KEY (timestamp, symbol, timeframe)
);

SELECT create_hypertable('klines', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_klines_symbol_timeframe ON klines (symbol, timeframe, timestamp DESC);

CREATE TABLE IF NOT EXISTS trades (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    side TEXT NOT NULL,
    PRIMARY KEY (timestamp, symbol, trade_id)
);

SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    reasons JSONB NOT NULL,
    indicators JSONB NOT NULL,
    order_flow JSONB NOT NULL,
    wyckoff_phase TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals (timestamp DESC);

CREATE TABLE IF NOT EXISTS completed_trades (
    id SERIAL PRIMARY KEY,
    trade_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC NOT NULL,
    quantity NUMERIC NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL,
    pnl NUMERIC NOT NULL,
    pnl_percentage NUMERIC NOT NULL,
    commission NUMERIC NOT NULL,
    slippage NUMERIC NOT NULL,
    exit_reason TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_completed_trades_closed_at ON completed_trades (closed_at DESC);
"@

$sql | docker compose exec -T timescaledb psql -U trading_user -d trading_db | Out-Null

Print-Success "Database setup completed"
Write-Host ""

# Step 5: Verify setup
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Step 5: Verifying Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Print-Info "Checking database tables..."
$tableCount = docker compose exec -T timescaledb psql -U trading_user -d trading_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"
$tableCount = $tableCount.Trim()
if ([int]$tableCount -ge 4) {
    Print-Success "Database tables created ($tableCount tables)"
} else {
    Print-Error "Database tables not created properly"
    exit 1
}

Print-Info "Testing Bybit connection..."
$testResult = docker compose exec -T trading_bot python scripts/test_connection_docker.py 2>$null
if ($LASTEXITCODE -eq 0) {
    Print-Success "Bybit connection successful"
} else {
    Print-Warning "Bybit connection test failed"
    Write-Host "   This might be due to:"
    Write-Host "   1. API keys not configured in .env"
    Write-Host "   2. System time not synchronized (Run: w32tm /resync)"
    Write-Host "   3. Network issues"
    Write-Host ""
    Write-Host "   Run this to test manually:"
    Write-Host "   docker compose exec trading_bot python scripts/test_connection_docker.py"
}

Write-Host ""

# Step 6: Summary
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🎉 Setup Completed Successfully!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 System Status:" -ForegroundColor Yellow
docker compose ps
Write-Host ""
Write-Host "🌐 Access Points:" -ForegroundColor Yellow
Write-Host "   Dashboard: http://localhost:8501" -ForegroundColor Green
Write-Host "   Telegram Bot: Send /start to your bot" -ForegroundColor Green
Write-Host ""
Write-Host "✅ All services are running automatically:" -ForegroundColor Yellow
Write-Host "   - TimescaleDB (Database)"
Write-Host "   - Trading Bot (Main application)"
Write-Host "   - Telegram Bot (Alerts & commands)"
Write-Host "   - Dashboard (Monitoring UI)"
Write-Host ""
Write-Host "📚 Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Download historical data (for backtesting, ~6-7 minutes):"
Write-Host "   docker compose exec trading_bot python scripts/download_historical_data.py"
Write-Host ""
Write-Host "2. Run backtest (see USER_GUIDE.md for details):"
Write-Host "   Follow 'Trading Workflow' section in USER_GUIDE.md"
Write-Host ""
Write-Host "3. View logs:"
Write-Host "   docker compose logs -f trading_bot      # Main bot"
Write-Host "   docker compose logs -f telegram_bot     # Telegram alerts"
Write-Host "   docker compose logs -f dashboard        # Dashboard"
Write-Host ""
Write-Host "4. Stop all services:"
Write-Host "   docker compose down"
Write-Host ""
Write-Host "5. Restart all services:"
Write-Host "   docker compose restart"
Write-Host ""
Write-Host "📖 Documentation:" -ForegroundColor Yellow
Write-Host "   - User Guide: USER_GUIDE.md"
Write-Host "   - Installation: docs/INSTALLATION_GUIDE.md"
Write-Host "   - Troubleshooting: docs/TROUBLESHOOTING.md"
Write-Host ""
Write-Host "⚠️  Important Notes:" -ForegroundColor Yellow
Write-Host "   - If Telegram bot not responding: Check TELEGRAM_BOT_TOKEN in .env"
Write-Host "   - Dashboard shows mock data until you start trading"
Write-Host "   - Always test on Testnet before Live trading"
Write-Host ""
Write-Host "✅ Your trading bot is ready to use!" -ForegroundColor Green
