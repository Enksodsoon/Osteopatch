# Portable developer entrypoints; GNU Make is optional.
# Direct PowerShell/bash equivalents are in docs/getting-started.md.
UV ?= uv
PY := $(UV) run --locked python
.DEFAULT_GOAL := help
.PHONY: help setup test test-backend test-enterprise test-frontend test-tooling repo-check lint typecheck runtime capability unified unified-app demo-slide verify-live bake verify-bake smoke e2e serve docs docs-check docs-serve

help:
	@echo "setup | test | lint | typecheck | repo-check | docs | docs-serve"
	@echo "Demo: unified-app | runtime | capability | unified | demo-slide | verify-live"
	@echo "Also: serve | smoke | e2e | bake | verify-bake"
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

# Which OPTIONAL runtimes this machine can actually use (torch stack, WSI
# engines, frozen artifact hashes). Records capability; never gates on it.
capability:
	$(PY) scripts/runtime_capability.py --out docs/evidence/runtime-capability.json

# Authenticated unified /v1/* surface over real HTTP, as each demo persona.
# Copies the review store; the canonical database is never written.
unified:
	$(PY) scripts/verify_unified_surface.py

# Assemble the repeatable demo WSI from real corpus patches, then report what the
# slide reader ACTUALLY reports about it. Honest by construction: it does not
# claim a pyramid unless the reader confirms >1 level (--require-pyramid exits 1).
demo-slide:
	$(PY) scripts/make_demo_slide.py --report docs/evidence/demo-slide.json

# Live inference over real HTTP: authenticated upload -> forward pass -> read
# back, per persona. Copies the read model; the canonical database is never
# written, and the frozen corpus is compared by ROW digest before and after.
verify-live:
	$(PY) scripts/verify_live_inference.py

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

# The demo snapshots runtime evidence into a disposable workspace. Ctrl+C stops
# it; rerunning creates a clean reset without changing canonical data.
unified-app demo:
	$(UV) run --locked --extra dev --extra model --extra wsi python scripts/demo.py

docs:
	$(PY) scripts/build_site.py
	$(PY) scripts/check_site.py

docs-check: test-tooling docs

docs-serve: docs
	$(PY) -m http.server 8765 --bind 127.0.0.1 --directory _site
