.DEFAULT_GOAL := help
export PYTHONPATH := src

.PHONY: install dev test lint format typecheck preprocess clean help

install:  ## Create .venv and install all dependencies (including dev)
	uv sync
	@echo ""
	@echo "Dependencies installed. Activate the virtual environment with:"
	@echo "  Linux/Mac : source .venv/bin/activate"
	@echo "  Windows   : .venv\\Scripts\\Activate.ps1"

dev:  ## Run development server with auto-reload
	uv run uvicorn coverage.main:app --reload --host 0.0.0.0 --port 8000

test:  ## Run test suite with coverage report
	uv run pytest --cov --cov-report=term-missing

lint:  ## Check code with ruff
	uv run ruff check src/ tests/

format:  ## Format code and auto-fix lint issues with ruff
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:  ## Run mypy strict type checks
	uv run mypy src/

check:  ## Run all pre-commit hooks against every file
	uv run pre-commit run --all-files

preprocess:  ## Download antenna CSV and build data/processed/antennas.parquet
	uv run python scripts/preprocess.py

clean:  ## Remove build artefacts and caches
	$(RM) -rf .venv .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
