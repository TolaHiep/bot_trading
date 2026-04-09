#!/bin/bash
# Complete System Setup Script for Trading Bot
# This script will set up everything from scratch

set -e

echo "=========================================="
echo "🚀 Trading Bot - Complete Setup"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}📝 $1${NC}"
}

# Step 1: Check prerequisites
echo "=========================================="
echo "Step 1: Checking Prerequisites"
echo "=========================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    echo "   Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi
print_success "Docker is installed"

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed"
    echo "   Please install Docker Compose"
    exit 1
fi
print_success "Docker Compose is installed"

# Check if Docker is running
if ! docker ps &> /dev/null; then
    print_error "Docker is not running"
    echo "   Please start Docker Desktop"
    exit 1
fi
print_success "Docker is running"

# Check .env file
if [ ! -f ".env" ]; then
    print_error ".env file not found"
    echo "   Please create .env file from .env.example"
    echo "   Run: cp .env.example .env"
    echo "   Then edit .env with your Bybit API credentials"
    exit 1
fi
print_success ".env file exists"

# Check API keys in .env
if grep -q "your_testnet_api_key" .env || grep -q "your_api_key_here" .env; then
    print_warning "API keys not configured in .env"
    echo "   Please update BYBIT_API_KEY and BYBIT_API_SECRET in .env file"
    read -p "   Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# Step 2: Stop existing containers
echo "=========================================="
echo "Step 2: Cleaning Up Old Containers"
echo "=========================================="
echo ""

print_info "Stopping existing containers..."
docker compose down 2>/dev/null || true
print_success "Cleanup completed"
echo ""

# Step 3: Build and start containers
echo "=========================================="
echo "Step 3: Building and Starting Containers"
echo "=========================================="
echo ""

print_info "Building Docker images..."
docker compose build

print_info "Starting containers..."
docker compose up -d

print_info "Waiting for database to be ready (30 seconds)..."
sleep 30

# Check if containers are running
if ! docker compose ps | grep -q "Up"; then
    print_error "Containers failed to start"
    echo "   Check logs: docker compose logs"
    exit 1
fi
print_success "Containers are running"
echo ""

# Step 4: Setup database
echo "=========================================="
echo "Step 4: Setting Up Database"
echo "=========================================="
echo ""

print_info "Creating database 'trading_db'..."
docker compose exec -T timescaledb psql -U trading_user -d postgres -c "CREATE DATABASE trading_db;" 2>/dev/null || print_warning "Database already exists"

print_info "Enabling TimescaleDB extension..."
docker compose exec -T timescaledb psql -U trading_user -d trading_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" > /dev/null

print_info "Creating tables..."
docker compose exec -T timescaledb psql -U trading_user -d trading_db << 'EOF' > /dev/null
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
EOF

print_success "Database setup completed"
echo ""

# Step 5: Verify setup
echo "=========================================="
echo "Step 5: Verifying Setup"
echo "=========================================="
echo ""

print_info "Checking database tables..."
TABLE_COUNT=$(docker compose exec -T timescaledb psql -U trading_user -d trading_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d ' ')
if [ "$TABLE_COUNT" -ge 4 ]; then
    print_success "Database tables created ($TABLE_COUNT tables)"
else
    print_error "Database tables not created properly"
    exit 1
fi

print_info "Testing Bybit connection..."
if docker compose exec -T trading_bot python scripts/test_connection_docker.py > /dev/null 2>&1; then
    print_success "Bybit connection successful"
else
    print_warning "Bybit connection test failed"
    echo "   This might be due to:"
    echo "   1. API keys not configured in .env"
    echo "   2. System time not synchronized"
    echo "   3. Network issues"
    echo ""
    echo "   Run this to test manually:"
    echo "   docker compose exec trading_bot python scripts/test_connection_docker.py"
fi

echo ""

# Step 6: Summary
echo "=========================================="
echo "🎉 Setup Completed Successfully!"
echo "=========================================="
echo ""
echo "📊 System Status:"
docker compose ps
echo ""
echo "📚 Next Steps:"
echo ""
echo "1. Test Bybit connection:"
echo "   docker compose exec trading_bot python scripts/test_connection_docker.py"
echo ""
echo "2. View Dashboard:"
echo "   docker compose --profile monitoring up -d dashboard"
echo "   Open: http://localhost:8501"
echo ""
echo "3. Download historical data (for backtesting):"
echo "   docker compose exec trading_bot python scripts/download_historical_data.py"
echo ""
echo "4. Run tests:"
echo "   docker compose exec trading_bot pytest tests/unit/ -v"
echo ""
echo "5. View logs:"
echo "   docker compose logs -f trading_bot"
echo ""
echo "📖 Documentation:"
echo "   - User Guide: USER_GUIDE.md"
echo "   - Installation: docs/INSTALLATION_GUIDE.md"
echo "   - Troubleshooting: docs/TROUBLESHOOTING.md"
echo ""
echo "✅ Your trading bot is ready to use!"
