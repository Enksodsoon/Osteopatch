# OsteoPatch — developer entry points.
#
# Everything here works on a clean clone and needs no AWS account.
#
# Educational research prototype only. Not for diagnosis, treatment decisions,
# or predicting treatment response.

PY := .venv/Scripts/python.exe
PY_UNIX := .venv/bin/python
UV := uv

.DEFAULT_GOAL := help
.PHONY: help setup test test-backend test-enterprise test-frontend \
        lint typecheck smoke e2e e2e-edge runtime bake verify-bake serve clean

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- environment -------------------------------------------------------------

setup:  ## create .venv and install the locked serve environment
	$(UV) sync --extra dev
	@echo "serve venv ready. Add --extra wsi for OpenSlide, --extra model for torch."

# --- gates -------------------------------------------------------------------

test: test-backend test-frontend  ## run every test gate

test-backend:  ## both backends (torch-free)
	.venv/Scripts/python.exe -m pytest app/g6/backend/tests -q
	.venv/Scripts/python.exe -m pytest app/g7-enterprise/backend/tests -q

test-enterprise:  ## enterprise backend only
	.venv/Scripts/python.exe -m pytest app/g7-enterprise/backend/tests -q

test-frontend:  ## both frontends: test + TypeScript build
	cd app/g6/frontend            && npm ci && npm test && npm run build
	cd app/g7-enterprise/frontend && npm ci && npm test && npm run build

lint:  ## ruff on newly-authored code (blocking) + legacy tree (informational)
	.venv/Scripts/python.exe -m ruff check scripts app/g6/backend/osteopatch/pathology app/g6/backend/osteopatch/app.py app/g6/backend/osteopatch/limitations.py app/g6/backend/osteopatch/projects.py app/g6/backend/osteopatch/modelcard.py app/g6/backend/tests/test_connection_concurrency.py app/g6/deploy/verify_bake.py
	-@.venv/Scripts/python.exe -m ruff check app --statistics

typecheck:  ## mypy over the canonical G6 backend package
	.venv/Scripts/python.exe -m mypy

# --- runtime artifacts -------------------------------------------------------

runtime:  ## locate + hash-verify the runtime artifacts
	.venv/Scripts/python.exe scripts/prepare_runtime.py

bake:  ## rebuild deploy/_bake from verified artifacts
	.venv/Scripts/python.exe scripts/prepare_runtime.py
	.venv/Scripts/python.exe scripts/prepare_bake.py

verify-bake:  ## verify the existing deploy/_bake build context
	.venv/Scripts/python.exe app/g6/deploy/verify_bake.py \
		app/g6/deploy/_bake app/g6/deploy/runtime-artifacts.expected.json

# --- the one command ---------------------------------------------------------

smoke:  ## full local end-to-end over real HTTP against real data (no AWS)
	.venv/Scripts/python.exe scripts/prepare_runtime.py
	.venv/Scripts/python.exe app/local-tester.py --out docs/evidence/smoke-result.json
	@echo
	@echo "smoke PASSED — evidence written to docs/evidence/smoke-result.json"

# --- the browser one ---------------------------------------------------------

e2e:  ## whole-app BROWSER end-to-end (real Chromium, real UI, throwaway DB)
	.venv/Scripts/python.exe scripts/e2e_ui.py --out docs/evidence/e2e-ui-result.json
	@echo
	@echo "e2e PASSED — evidence written to docs/evidence/e2e-ui-result.json"
	@echo "watch it run instead: .venv/Scripts/python.exe scripts/e2e_ui.py --headed"
	@echo "run it in installed Edge instead: make e2e-edge"

e2e-edge:  ## same suite driven in the INSTALLED Microsoft Edge (no download)
	.venv/Scripts/python.exe scripts/e2e_ui.py --browser edge \
		--out docs/evidence/e2e-edge-result.json
	@echo
	@echo "e2e-edge PASSED — evidence written to docs/evidence/e2e-edge-result.json"

# --- running -----------------------------------------------------------------

serve:  ## run the G6 review API on 127.0.0.1:8137
	.venv/Scripts/python.exe -m uvicorn osteopatch.app:app \
		--app-dir app/g6/backend --host 127.0.0.1 --port 8137

clean:  ## remove build/test caches (never touches runtime artifacts)
	rm -rf app/g6/frontend/dist app/g7-enterprise/frontend/dist
	rm -rf app/g6/frontend/test-results app/g6/frontend/playwright-report
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	find . -name .pytest_cache -type d -prune -exec rm -rf {} + 2>/dev/null || true