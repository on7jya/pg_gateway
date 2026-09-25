.PHONY: up down logs test lint export-openapi demo install install-dev openapi test-image

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f gateway

test-image:
	docker build -f Dockerfile.test -t pg_gateway_test .

test: test-image
	docker compose up -d postgres
	docker run --rm --network $${COMPOSE_PROJECT_NAME:-pg_gateway}_default \
		-v "$$(pwd)":/app -w /app \
		-e DATABASE_URL=postgresql://gateway:gateway@postgres:5432/gateway \
		-e CONFIG_PATH=/app/config/config.yaml \
		-e ACCOUNTS_CONFIG_PATH=/app/config/accounts.example.yaml \
		-e PYTHONPATH=/app:/app/src \
		pg_gateway_test pytest -q

lint: test-image
	docker run --rm -v "$$(pwd)":/app -w /app -e PYTHONPATH=/app:/app/src pg_gateway_test ruff check src tests

export-openapi openapi: test-image
	docker run --rm -v "$$(pwd)":/out -w /app \
		-e CONFIG_PATH=/app/config/config.yaml \
		-e ACCOUNTS_CONFIG_PATH=/app/config/accounts.example.yaml \
		-e PYTHONPATH=/app:/app/src \
		pg_gateway_test python -c "from pathlib import Path; from pg_gateway.export_openapi import export_openapi; print(export_openapi(Path('/out/openapi.yaml')))"

demo:
	@echo "Демо ТУЗ (admin): CN=admin,OU=tuz,O=Acme,C=RU"
	@echo "Заголовок: -H 'X-Client-Cert-DN: CN=admin,OU=tuz,O=Acme,C=RU'"
	@echo "Список users:"
	@echo "  curl -s 'http://localhost:8000/api/v1/users' -H 'X-Client-Cert-DN: CN=admin,OU=tuz,O=Acme,C=RU' | jq"
	@echo "Полные сценарии — в README.md."
