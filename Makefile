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
		-e GATEWAY_TRUST_TOKEN=demo-trust-token \
		-e PYTHONPATH=/app:/app/src \
		pg_gateway_test pytest -q

lint: test-image
	docker run --rm -v "$$(pwd)":/app -w /app -e PYTHONPATH=/app:/app/src pg_gateway_test ruff check src tests

export-openapi openapi: test-image
	docker run --rm -v "$$(pwd)":/out -w /app \
		-e CONFIG_PATH=/app/config/config.yaml \
		-e GATEWAY_TRUST_TOKEN=demo-trust-token \
		-e PYTHONPATH=/app:/app/src \
		pg_gateway_test python -c "from pathlib import Path; from pg_gateway.export_openapi import export_openapi; print(export_openapi(Path('/out/openapi.yaml')))"

demo:
	@echo "Демо trust-токен: demo-trust-token"
	@echo "Демо tenant A: 11111111-1111-1111-1111-111111111111"
	@echo "Заголовки: -H 'X-Gateway-Token: demo-trust-token' -H 'X-Tenant-Id: 11111111-1111-1111-1111-111111111111' -H 'X-Roles: admin'"
	@echo "Список users:"
	@echo "  curl -s 'http://localhost:8000/api/v1/users' -H 'X-Gateway-Token: demo-trust-token' -H 'X-Tenant-Id: 11111111-1111-1111-1111-111111111111' -H 'X-Roles: admin' | jq"
	@echo "Полные сценарии — в README.md."
