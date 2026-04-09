.PHONY: help build start stop restart status logs shell test clean db format lint type-check

help:
	@echo "Available commands:"
	@echo "  make build       - Build Docker images"
	@echo "  make start       - Start all services"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make status      - Show service status"
	@echo "  make logs        - Show logs (add SERVICE=name for specific service)"
	@echo "  make shell       - Open shell in trading_bot container"
	@echo "  make test        - Run all tests"
	@echo "  make test-unit   - Run unit tests only"
	@echo "  make test-prop   - Run property tests only"
	@echo "  make test-int    - Run integration tests only"
	@echo "  make clean       - Clean up Docker resources"
	@echo "  make db          - Connect to database"
	@echo "  make format      - Format code with black and isort"
	@echo "  make lint        - Run flake8 linter"
	@echo "  make type-check  - Run mypy type checker"
	@echo "  make check       - Run all checks (format, lint, type-check, test)"

build:
	docker compose build

start:
	docker compose up -d

stop:
	docker compose down

restart:
	docker compose restart

status:
	docker compose ps

logs:
ifdef SERVICE
	docker compose logs -f $(SERVICE)
else
	docker compose logs -f
endif

shell:
	docker compose exec trading_bot /bin/bash

test:
	docker compose exec trading_bot pytest tests/ -v

test-unit:
	docker compose exec trading_bot pytest tests/unit/ -v

test-prop:
	docker compose exec trading_bot pytest tests/property/ -v

test-int:
	docker compose exec trading_bot pytest tests/integration/ -v

test-cov:
	docker compose exec trading_bot pytest --cov=src --cov-report=html --cov-report=term

clean:
	docker compose down -v
	docker system prune -f

db:
	docker compose exec timescaledb psql -U trading_user -d trading_bot

format:
	docker compose exec trading_bot black src/ tests/
	docker compose exec trading_bot isort src/ tests/

lint:
	docker compose exec trading_bot flake8 src/ tests/

type-check:
	docker compose exec trading_bot mypy src/

check: format lint type-check test
	@echo "All checks passed!"

# Development helpers
dev-setup:
	cp .env.example .env
	@echo "Please update .env with your API credentials"

test-connection:
	docker compose exec trading_bot python scripts/test_connection_docker.py

backup-db:
	docker compose exec timescaledb pg_dump -U trading_user trading_bot > backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Database backed up to backup_$$(date +%Y%m%d_%H%M%S).sql"

restore-db:
	@echo "Usage: make restore-db FILE=backup.sql"
ifdef FILE
	docker compose exec -T timescaledb psql -U trading_user trading_bot < $(FILE)
else
	@echo "Error: FILE parameter required"
endif
