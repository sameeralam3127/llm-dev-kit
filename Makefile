# Local commands, matching what CI runs. `make help` lists them.
# Run from an activated virtualenv (pip install -r requirements-dev.txt).

PYTHON ?= python

.DEFAULT_GOAL := help
.PHONY: help install lint typecheck test test-python test-web build-web check up down smoke e2e

help: ## List the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

install: ## Install the Python dev tools and the web app's dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt
	cd web && npm ci

lint: ## ruff and ESLint
	ruff check services tests
	ruff format --check services tests
	cd web && npm run lint

typecheck: ## mypy and tsc
	mypy
	cd web && npm run typecheck

test-python: ## Python tests (Postgres-backed tests need Docker running)
	$(PYTHON) -m pytest

test-web: ## Web unit tests
	cd web && npm test

test: test-python test-web ## All unit and integration tests

build-web: ## Production build of the web app, as CI does it
	cd web && DATABASE_URL=file:/tmp/build.db AUTH_SECRET=build-placeholder-not-a-real-credential npm run build

check: lint typecheck test ## Everything CI checks before a merge, except the image builds

up: ## Build and start the stack, waiting until every service is healthy
	docker compose up -d --build --wait

down: ## Stop the stack (volumes are kept)
	docker compose down

smoke: ## Read-only smoke test of the running stack, through the gateway
	scripts/smoke.sh

e2e: up smoke ## Start the stack, then smoke-test it
