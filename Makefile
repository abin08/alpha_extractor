.PHONY: install format lint test commit clean lock

install:
	uv pip install -e ".[dev]"
	pre-commit install
	pre-commit install --hook-type commit-msg

format:
	ruff format src tests

lint:
	ruff check src tests --fix

test:
	pytest tests/ -v

commit:
	cz commit

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ src/__pycache__ tests/__pycache__

lock:
	uv pip compile pyproject.toml -o requirements.txt
