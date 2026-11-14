SHELL := /bin/bash
COMPOSE := docker compose -f deploy/docker-compose.yml --env-file .env

.PHONY: help env up down logs ps migrate seed backup test lint format typecheck build-web install-web dev-api dev-web

help:
	@echo "Thesium development targets"
	@echo "  make up          Build and start Postgres + API + worker + web"
	@echo "  make down        Stop the stack"
	@echo "  make logs        Follow container logs"
	@echo "  make migrate     Run Alembic migrations"
	@echo "  make seed        Seed the local user, BTC asset and BTCUSDT instrument"
	@echo "  make backup      Dump Postgres into backups/"
	@echo "  make test        Run backend tests"
	@echo "  make lint        Run ruff"
	@echo "  make typecheck   Type-check the frontend"
	@echo "  make build-web   Production build of the frontend"
	@echo "  make dev-api     Run FastAPI locally (needs Postgres)"
	@echo "  make dev-web     Run Vite dev server"
	@echo "  make env         Show pyenv / nvm usage"

env:
	@echo "Python: $$(python --version 2>&1) (pyenv: $$(cat .python-version))"
	@echo "Node:   $$(node --version 2>/dev/null || echo 'not loaded; run: nvm use') (nvmrc: $$(cat .nvmrc))"
	@echo "Activate Python: pyenv activate thesium"
	@echo "Activate Node:   nvm use"

up:
	@test -f .env || cp .env.example .env
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

migrate:
	@test -f .env || cp .env.example .env
	$(COMPOSE) run --rm api alembic upgrade head

seed:
	@test -f .env || cp .env.example .env
	$(COMPOSE) run --rm api python -m app.scripts.seed

backup:
	@test -f .env || cp .env.example .env
	@mkdir -p backups
	@$(COMPOSE) exec -T postgres sh -c 'pg_dump -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' > "backups/thesium-$$(date +%Y%m%d-%H%M%S).sql"
	@echo "backup written to backups/"

test:
	cd backend && python -m pytest -q

lint:
	cd backend && python -m ruff check .

format:
	cd backend && python -m ruff format .

typecheck:
	cd frontend && npm run typecheck

build-web:
	cd frontend && npm run build

install-web:
	cd frontend && npm install

dev-api:
	cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	cd frontend && npm run dev