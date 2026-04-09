-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Klines hypertable
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

-- Trades hypertable
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

-- Orderbooks hypertable
CREATE TABLE IF NOT EXISTS orderbooks (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    PRIMARY KEY (timestamp, symbol)
);

SELECT create_hypertable('orderbooks', 'timestamp', if_not_exists => TRUE);

-- Signals table
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

-- Completed trades table
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

-- Compression policy for older data (after 7 days)
SELECT add_compression_policy('klines', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('trades', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('orderbooks', INTERVAL '7 days', if_not_exists => TRUE);

-- Retention policy (keep 90 days)
SELECT add_retention_policy('klines', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('trades', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('orderbooks', INTERVAL '90 days', if_not_exists => TRUE);
