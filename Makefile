.DEFAULT_GOAL := help
.SHELLFLAGS := -eu -o pipefail -c
SHELL := bash

UV := uv

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install/sync the dev environment (creates .venv via uv)
	$(UV) sync --group dev

.PHONY: lint
lint: ## Lint the code with ruff
	$(UV) run ruff check .

.PHONY: lint-fix
lint-fix: ## Lint and auto-fix what ruff can fix
	$(UV) run ruff check --fix .

.PHONY: format
format: ## Format the code with ruff
	$(UV) run ruff format .

.PHONY: format-check
format-check: ## Check formatting without writing changes
	$(UV) run ruff format --check .

.PHONY: typecheck
typecheck: ## Type-check with mypy
	$(UV) run mypy

.PHONY: test
test: ## Run the test suite
	$(UV) run pytest

.PHONY: test-cov
test-cov: ## Run the test suite with a coverage report
	$(UV) run pytest --cov=spiralgen --cov-report=term-missing

.PHONY: check
check: lint format-check typecheck test ## Run all checks (lint, format-check, typecheck, test) -- what CI runs

.PHONY: fix
fix: lint-fix format ## Auto-fix lint issues and formatting in place

.PHONY: build
build: ## Build the sdist and wheel into dist/
	$(UV) build

.PHONY: demo
demo: ## Run the spiralgen demo (requires the plot extra)
	$(UV) run --group dev spiralgen-demo

.PHONY: precommit-install
precommit-install: ## Install the pre-commit git hook
	$(UV) run --with pre-commit pre-commit install

.PHONY: precommit-run
precommit-run: ## Run pre-commit hooks against all files
	$(UV) run --with pre-commit pre-commit run --all-files

.PHONY: clean
clean: ## Remove build artifacts and tool caches
	rm -rf dist build *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name '__pycache__' -not -path './.venv/*' -exec rm -rf {} +

.PHONY: clean-all
clean-all: clean ## clean, plus remove the virtualenv
	rm -rf .venv
