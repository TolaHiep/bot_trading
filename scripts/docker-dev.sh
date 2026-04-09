#!/bin/bash
# Development helper script for Docker

case "$1" in
  start)
    echo "🚀 Starting all services..."
    docker compose up -d
    echo "✅ Services started!"
    echo "📊 Check status: ./scripts/docker-dev.sh status"
    ;;
  
  stop)
    echo "🛑 Stopping all services..."
    docker compose down
    echo "✅ Services stopped!"
    ;;
  
  restart)
    echo "🔄 Restarting services..."
    docker compose restart
    echo "✅ Services restarted!"
    ;;
  
  status)
    echo "📊 Service Status:"
    docker compose ps
    ;;
  
  logs)
    if [ -z "$2" ]; then
      echo "📜 Showing all logs (Ctrl+C to exit):"
      docker compose logs -f
    else
      echo "📜 Showing logs for $2 (Ctrl+C to exit):"
      docker compose logs -f "$2"
    fi
    ;;
  
  shell)
    SERVICE=${2:-trading_bot}
    echo "🐚 Opening shell in $SERVICE..."
    docker compose exec "$SERVICE" /bin/bash
    ;;
  
  test)
    echo "🧪 Running tests in Docker..."
    docker compose exec trading_bot pytest tests/ -v
    ;;
  
  build)
    echo "🔨 Building Docker images..."
    docker compose build
    echo "✅ Build complete!"
    ;;
  
  clean)
    echo "🧹 Cleaning up Docker resources..."
    docker compose down -v
    docker system prune -f
    echo "✅ Cleanup complete!"
    ;;
  
  db)
    echo "🗄️  Connecting to database..."
    docker compose exec timescaledb psql -U trading_user -d trading_bot
    ;;
  
  *)
    echo "Usage: $0 {start|stop|restart|status|logs|shell|test|build|clean|db}"
    echo ""
    echo "Commands:"
    echo "  start    - Start all services"
    echo "  stop     - Stop all services"
    echo "  restart  - Restart all services"
    echo "  status   - Show service status"
    echo "  logs     - Show logs (logs [service_name] for specific service)"
    echo "  shell    - Open shell in container (shell [service_name])"
    echo "  test     - Run tests"
    echo "  build    - Build Docker images"
    echo "  clean    - Clean up Docker resources"
    echo "  db       - Connect to database"
    exit 1
    ;;
esac
