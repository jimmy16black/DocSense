.PHONY: help install dev test lint format up down db-migrate mobile-install mobile-run mobile-analyze

help:
	@echo "Available commands:"
	@echo "  make install         - Install backend dependencies with uv"
	@echo "  make dev             - Run backend FastAPI dev server"
	@echo "  make test            - Run backend tests"
	@echo "  make lint            - Run ruff linter and mypy"
	@echo "  make format          - Run ruff formatter and fix"
	@echo "  make up              - Start local Docker infrastructure (postgres, redis)"
	@echo "  make down            - Stop local Docker infrastructure"
	@echo "  make mobile-install  - Install Flutter app dependencies"
	@echo "  make mobile-run      - Run Flutter mobile application"
	@echo "  make mobile-analyze  - Analyze Flutter mobile Dart code"

install:
	cd backend && uv sync

dev:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

db-migrate:
	cd backend && uv run python scripts/migrate.py

test:
	cd backend && uv run pytest -v

lint:
	cd backend && uv run ruff check .
	cd backend && uv run mypy app

format:
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .

mobile-install:
	cd mobile && flutter pub get

mobile-run:
	cd mobile && flutter run

mobile-analyze:
	cd mobile && flutter analyze

up:
	docker compose up -d postgres redis

down:
	docker compose down
