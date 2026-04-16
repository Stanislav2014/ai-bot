.PHONY: build up down logs test lint shell pull-models list-models restart clean

build:
	docker compose build

up:
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

pull-models:
	docker compose exec lemonade lemonade-server-dev pull Qwen3-0.6B-GGUF

list-models:
	docker compose exec lemonade lemonade-server-dev list

restart:
	docker compose up -d --force-recreate bot

clean:
	docker compose down -v
