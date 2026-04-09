# Development helper script for Docker (PowerShell version for Windows)

param(
    [Parameter(Mandatory=$true)]
    [string]$Command,
    [string]$Service = ""
)

switch ($Command) {
    "start" {
        Write-Host "🚀 Starting all services..." -ForegroundColor Green
        docker compose up -d
        Write-Host "✅ Services started!" -ForegroundColor Green
        Write-Host "📊 Check status: .\scripts\docker-dev.ps1 status" -ForegroundColor Cyan
    }
    
    "stop" {
        Write-Host "🛑 Stopping all services..." -ForegroundColor Yellow
        docker compose down
        Write-Host "✅ Services stopped!" -ForegroundColor Green
    }
    
    "restart" {
        Write-Host "🔄 Restarting services..." -ForegroundColor Yellow
        docker compose restart
        Write-Host "✅ Services restarted!" -ForegroundColor Green
    }
    
    "status" {
        Write-Host "📊 Service Status:" -ForegroundColor Cyan
        docker compose ps
    }
    
    "logs" {
        if ($Service -eq "") {
            Write-Host "📜 Showing all logs (Ctrl+C to exit):" -ForegroundColor Cyan
            docker compose logs -f
        } else {
            Write-Host "📜 Showing logs for $Service (Ctrl+C to exit):" -ForegroundColor Cyan
            docker compose logs -f $Service
        }
    }
    
    "shell" {
        if ($Service -eq "") {
            $Service = "trading_bot"
        }
        Write-Host "🐚 Opening shell in $Service..." -ForegroundColor Cyan
        docker compose exec $Service /bin/bash
    }
    
    "test" {
        Write-Host "🧪 Running tests in Docker..." -ForegroundColor Cyan
        docker compose exec trading_bot pytest tests/ -v
    }
    
    "build" {
        Write-Host "🔨 Building Docker images..." -ForegroundColor Yellow
        docker compose build
        Write-Host "✅ Build complete!" -ForegroundColor Green
    }
    
    "clean" {
        Write-Host "🧹 Cleaning up Docker resources..." -ForegroundColor Yellow
        docker compose down -v
        docker system prune -f
        Write-Host "✅ Cleanup complete!" -ForegroundColor Green
    }
    
    "db" {
        Write-Host "🗄️  Connecting to database..." -ForegroundColor Cyan
        docker compose exec timescaledb psql -U trading_user -d trading_bot
    }
    
    default {
        Write-Host "Usage: .\scripts\docker-dev.ps1 <command> [service]" -ForegroundColor Red
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor Cyan
        Write-Host "  start    - Start all services"
        Write-Host "  stop     - Stop all services"
        Write-Host "  restart  - Restart all services"
        Write-Host "  status   - Show service status"
        Write-Host "  logs     - Show logs (add service name for specific service)"
        Write-Host "  shell    - Open shell in container (add service name)"
        Write-Host "  test     - Run tests"
        Write-Host "  build    - Build Docker images"
        Write-Host "  clean    - Clean up Docker resources"
        Write-Host "  db       - Connect to database"
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor Yellow
        Write-Host "  .\scripts\docker-dev.ps1 start"
        Write-Host "  .\scripts\docker-dev.ps1 logs trading_bot"
        Write-Host "  .\scripts\docker-dev.ps1 shell trading_bot"
        exit 1
    }
}
