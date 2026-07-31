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
	@# The plotter group as well as dev: without vpype the four tests that
	@# check this optimizer against vpype's skip themselves, and a skipped
	@# test reads as a passing one.
	$(UV) sync --group dev --group plotter

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
	$(UV) run pytest --cov=geomotif --cov-report=term-missing

.PHONY: check
check: lint format-check typecheck test ## Run all checks (lint, format-check, typecheck, test) -- what CI runs

.PHONY: fix
fix: lint-fix format ## Auto-fix lint issues and formatting in place

.PHONY: docs
docs: ## Build the documentation site into site/
	$(UV) run --group docs mkdocs build --strict

.PHONY: docs-serve
docs-serve: ## Serve the documentation at http://127.0.0.1:8000 with live reload
	$(UV) run --group docs mkdocs serve

.PHONY: docs-gen
docs-gen: ## Regenerate the derived docs (reference, gallery, catalogue, README images)
	$(UV) run --group docs python tools/gendocs.py

.PHONY: docs-check
docs-check: docs-gen ## Fail if the committed generated docs are out of date
	@# --porcelain rather than `git diff --exit-code`, so that a *new* generated
	@# file -- an added motif's image -- counts as drift too.
	@drift=$$(git status --porcelain -- docs/catalogue.md docs/assets); \
	if [ -n "$$drift" ]; then \
		echo "$$drift"; \
		echo; \
		echo "The committed documentation is behind the code."; \
		echo "Run 'make docs-gen' and commit the result."; \
		exit 1; \
	fi

.PHONY: build
build: ## Build the sdist and wheel into dist/
	$(UV) build

.PHONY: demo
demo: ## Run the geomotif demo (requires the plot extra)
	$(UV) run --group dev geomotif demo

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
