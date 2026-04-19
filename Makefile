.PHONY: build up down logs test lint shell restart clean network

# Одноразовая подготовка: общая docker-сеть для подключения к lemonade-server
network:
	docker network inspect llm-net >/dev/null 2>&1 || docker network create llm-net

build:
	docker compose build

up: network
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f bot

logs-all:
	docker compose logs -f

test:
	python3 -m pytest tests/ -v

lint:
	python3 -m ruff check app/ tests/

lint-fix:
	python3 -m ruff check --fix app/ tests/

shell:
	docker compose exec bot /bin/bash

restart:
	docker compose up -d --force-recreate bot

clean:
	docker compose down -v
