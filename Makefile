SHELL := /bin/bash
# Anchor commands to this checkout, including invocation with make -f from elsewhere.
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FRONTEND_DIR := $(PROJECT_ROOT)/frontend
BACKEND_DIR := $(PROJECT_ROOT)/backend
.PHONY: help setup models migrate run status demo check backend-check frontend-check build ui-test audit generate-api release-check

help:
	@printf '%s\n' 'Cluster Grouper local commands:' '  make setup        Install locked project dependencies' '  make models       Download verified local face models' '  make run          Build and start local app (Control-C stops both services)' '  make status       Check local service availability' '  make demo         Start isolated synthetic API on port 8787' '  make check        Lint, typecheck, and backend tests' '  make build        Build frontend for production' '  make ui-test      Run browser smoke tests' '  make audit        Check dependencies for advisories' '  make generate-api Generate TypeScript schema from running backend'
	@printf '%s\n' '  make release-check Check shared version metadata and release policy'

setup:
	uv sync --directory "$(BACKEND_DIR)" --python 3.13 --locked --extra dev
	npm --prefix "$(FRONTEND_DIR)" ci

models:
	uv run --locked --directory "$(BACKEND_DIR)" python -m app.models_setup

migrate:
	uv run --locked --directory "$(BACKEND_DIR)" alembic upgrade head

run:
	bash "$(PROJECT_ROOT)/scripts/run-local.sh"

status:
	bash "$(PROJECT_ROOT)/scripts/status.sh"

demo:
	uv run --locked --directory "$(BACKEND_DIR)" python -m app.demo_server --port 8787 --token synthetic

check: release-check backend-check frontend-check

release-check:
	uv run --locked --directory "$(BACKEND_DIR)" python "$(PROJECT_ROOT)/scripts/check-release.py"

backend-check:
	uv run --locked --directory "$(BACKEND_DIR)" ruff check .
	uv run --locked --directory "$(BACKEND_DIR)" ruff format --check .
	uv run --locked --directory "$(BACKEND_DIR)" mypy app
	uv run --locked --directory "$(BACKEND_DIR)" pytest

frontend-check:
	npm --prefix "$(FRONTEND_DIR)" run lint
	npm --prefix "$(FRONTEND_DIR)" run test:lint
	npm --prefix "$(FRONTEND_DIR)" run typecheck

build:
	npm --prefix "$(FRONTEND_DIR)" run build

ui-test:
	npm --prefix "$(FRONTEND_DIR)" run test:smoke

audit:
	uv run --locked --directory "$(BACKEND_DIR)" pip-audit
	npm --prefix "$(FRONTEND_DIR)" audit

generate-api:
	npm --prefix "$(FRONTEND_DIR)" run generate:api
