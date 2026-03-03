.PHONY: lint format check test install-hooks help frontend-install frontend-dev frontend-build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run ruff linter and formatter (with auto-fix)
	uv run --project core ruff check --fix core/ tools/
	uv run --project core ruff format core/ tools/

format: ## Run ruff formatter
	uv run --project core ruff format core/ tools/

check: ## Run all checks without modifying files (CI-safe)
	uv run --project core ruff check core/
	uv run --project core ruff check tools/
	uv run --project core ruff format --check core/
	uv run --project core ruff format --check tools/

test: ## Run core and tools tests (matches CI)
	cd core && uv sync && uv run pytest tests/ -v
	cd tools && uv sync --extra dev && uv run pytest tests/ -v

install-hooks: ## Install pre-commit hooks
	uv pip install pre-commit
	pre-commit install

frontend-install: ## Install frontend npm packages
	cd core/frontend && npm install

frontend-dev: ## Start frontend dev server
	cd core/frontend && npm run dev

frontend-build: ## Build frontend for production
	cd core/frontend && npm run build