# Portable developer entrypoints; GNU Make is optional.
# Direct PowerShell/bash equivalents are in docs/getting-started.md.
UV ?= uv
PY := $(UV) run --locked python
.DEFAULT_GOAL := help
.PHONY: help setup test test-backend test-enterprise test-frontend test-tooling repo-check lint typecheck runtime bake verify-bake smoke e2e serve docs docs-check docs-serve

help:
	@echo "setup | test | lint | typecheck | repo-check | docs | docs-serve"
	@echo "Runtime required: runtime | serve | smoke | e2e | bake | verify-bake"
	@echo "No target creates cloud resources or deletes runtime evidence."

setup:
	$(UV) sync --locked --extra dev
	 npm --prefix app/g6/frontend ci
	 npm --prefix app/g7-enterprise/frontend ci

test: test-backend test-frontend test-tooling repo-check

test-backend:
	$(PY) -m pytest app/g6/backend/tests app/g7-enterprise/backend/tests -q

test-enterprise:
	$(PY) -m pytest app/g7-enterprise/backend/tests -q

test-frontend:
	npm --prefix app/g6/frontend test
	npm --prefix app/g6/frontend run build
	npm --prefix app/g7-enterprise/frontend test
	npm --prefix app/g7-enterprise/frontend run build

test-tooling:
	$(PY) -m unittest discover -s tests/tooling -v

repo-check:
	$(PY) scripts/check_repository.py
	$(PY) scripts/sync_requirements.py --check
	$(PY) scripts/check_deps.py

lint:
	$(UV) run --locked ruff check scripts tests/tooling app/g6/backend/osteopatch/pathology app/g6/backend/osteopatch/app.py app/g6/backend/osteopatch/limitations.py app/g6/backend/osteopatch/projects.py app/g6/backend/osteopatch/modelcard.py app/g6/backend/tests/test_connection_concurrency.py app/g6/deploy/verify_bake.py

typecheck:
	$(UV) run --locked mypy

runtime:
	$(PY) scripts/prepare_runtime.py

bake: runtime
	$(PY) scripts/prepare_bake.py

verify-bake:
	$(PY) app/g6/deploy/verify_bake.py app/g6/deploy/_bake app/g6/deploy/runtime-artifacts.expected.json

smoke: runtime
	$(PY) app/local-tester.py --out docs/evidence/smoke-result.json

e2e:
	$(PY) scripts/e2e_ui.py --out docs/evidence/e2e-ui-result.json

serve:
	$(UV) run --locked uvicorn osteopatch.app:app --app-dir app/g6/backend --host 127.0.0.1 --port 8137

docs:
	$(PY) scripts/build_site.py
	$(PY) scripts/check_site.py

docs-check: test-tooling docs

docs-serve: docs
	$(PY) -m http.server 8765 --bind 127.0.0.1 --directory _site
