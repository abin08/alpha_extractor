.PHONY: install format lint test commit clean lock up down logs run

install:
	uv sync

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
	DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run pytest -v --cov-report=xml

coverage-html:
	DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run pytest -v --cov-report=html
