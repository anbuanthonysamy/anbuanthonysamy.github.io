SHELL := /bin/bash

BACKEND = docker compose exec -T backend
FRONTEND = docker compose exec -T frontend

.PHONY: help dev build up down demo seed test test-backend test-frontend backtest lint reset-db logs

help:
	@echo "Common targets:"
	@echo "  make dev         - start stack (docker compose up --build)"
	@echo "  make up          - start stack detached"
	@echo "  make down        - stop stack"
	@echo "  make demo        - seed fixtures + synth and run all four pipelines"
	@echo "  make seed        - seed fixtures only"
	@echo "  make test        - run backend tests"
	@echo "  make backtest    - run CS1/CS2 backtest on historical deals"
	@echo "  make lint        - ruff + eslint"
	@echo "  make reset-db    - stop stack and drop postgres volume"

dev:
	docker compose up --build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=120

demo: up
	@echo "Waiting for backend to become healthy…"
	@until curl -fsS http://localhost:8000/health >/dev/null 2>&1; do sleep 1; done
	$(BACKEND) python -m scripts.demo
	@echo "Open http://localhost:3000"

seed: up
	@until curl -fsS http://localhost:8000/health >/dev/null 2>&1; do sleep 1; done
	$(BACKEND) python -m scripts.seed_demo

test: test-backend

test-backend: up
	$(BACKEND) pytest -q

test-frontend: up
	$(FRONTEND) npm run typecheck

backtest: up
	$(BACKEND) python -m scripts.backtest

lint: up
	$(BACKEND) ruff check app tests scripts
	-$(FRONTEND) npm run lint

reset-db:
	docker compose down -v
