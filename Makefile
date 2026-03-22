.PHONY: up down logs db-migrate db-upgrade test lint fmt api \
        cli-bootstrap-security-master cli-sync-eod cli-sync-corporate-actions \
        cli-sync-fundamentals cli-run-dq

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

db-migrate:
	alembic -c infra/alembic.ini revision --autogenerate -m "$(msg)"

db-upgrade:
	alembic -c infra/alembic.ini upgrade head

db-downgrade:
	alembic -c infra/alembic.ini downgrade -1

test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short -m unit

test-integration:
	pytest tests/integration/ -v --tb=short -m integration

test-smoke:
	pytest tests/smoke/ -v --tb=short -m smoke

lint:
	ruff check .

fmt:
	ruff format .

api:
	uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

cli-bootstrap-security-master:
	python -m apps.cli.main bootstrap-security-master

cli-sync-eod:
	python -m apps.cli.main sync-eod-prices

cli-sync-corporate-actions:
	python -m apps.cli.main sync-corporate-actions

cli-sync-fundamentals:
	python -m apps.cli.main sync-fundamentals

cli-run-dq:
	python -m apps.cli.main run-dq
