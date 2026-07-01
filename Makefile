.DEFAULT_GOAL := help
export PYTHONPATH := src

.PHONY: install run-local run-docker dev dev-api dev-frontend test lint format typecheck preprocess clean help

install:  ## Create .venv and install all dependencies (including dev)
	uv sync
	cd frontend && npm install
	@echo ""
	@echo "Dependencies installed. Activate the virtual environment with:"
	@echo "  Linux/Mac : source .venv/bin/activate"
	@echo "  Windows   : .venv\\Scripts\\Activate.ps1"

run-local:  ## Start API + frontend dev servers (visit http://localhost:5173)
ifeq ($(OS),Windows_NT)
	@echo ""
	@echo "Windows detected. Run each in a separate terminal:"
	@echo "  make dev-api       (backend  -> http://localhost:8000)"
	@echo "  make dev-frontend  (frontend -> http://localhost:5173)"
	@echo ""
else
	uv run uvicorn mobile_coverage.main:app --reload --host 0.0.0.0 --port 8000 &
	cd frontend && npm run dev
endif

run-docker:  ## Build and start the full stack with Docker Compose (visit http://localhost:8000)
	@test -f .env || cp .env.example .env
	docker compose up --build

dev-api:  ## Run backend dev server with auto-reload (port 8000)
	uv run uvicorn mobile_coverage.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:  ## Run frontend Vite dev server (port 5173, proxies API to :8000)
	cd frontend && npm run dev

dev:  ## Print instructions for running both dev servers
	@echo ""
	@echo "Run each in a separate terminal:"
	@echo "  make dev-api       (backend  → http://localhost:8000)"
	@echo "  make dev-frontend  (frontend → http://localhost:5173)"
	@echo ""

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
