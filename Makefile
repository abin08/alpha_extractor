.PHONY: install format lint test commit clean lock up down logs run coverage coverage-html

install:
	uv sync

install-dev:
	uv sync --extra dev

format:
	uvx ruff format src tests

lint:
	uvx ruff check src tests --fix
	uvx ruff format src tests

commit:
	uv run cz commit

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ src/__pycache__ tests/__pycache__

lock:
	uv lock

# --- Docker Commands ---
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# --- App Commands ---
run:
	uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run pytest -v

coverage:
	DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run pytest -v --cov=src --cov-report=term-missing --cov-report=xml

coverage-html:
	DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run pytest -v --cov=src --cov-report=html

.PHONY: test-ingestion
test-ingestion:
	uv run python -m scripts.run_ingestion $(ARGS)

.PHONY: worker
worker:
	uv run celery -A src.tasks.celery_app worker --loglevel=info --pool=threads --concurrency=4

.PHONY: beat
beat:
	uv run celery -A src.tasks.celery_app beat --loglevel=info
