.PHONY: install format lint test commit clean lock

install:
	uv sync

format:
	ruff format src tests

lint:
	ruff check src tests --fix

commit:
	cz commit

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ src/__pycache__ tests/__pycache__

lock:
	uv pip compile pyproject.toml -o requirements.txt

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
	uv run pytest -v
