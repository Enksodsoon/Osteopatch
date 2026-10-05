# Core review application

The current reviewer-facing application: FastAPI, React/TypeScript, source/QC metadata, immutable three-class predictions, revision-aware accept/correct/defer, export, model card and qualified attribution.

**Educational/research prototype. Not for diagnosis, treatment decisions, treatment-response prediction or prognosis. Scores are uncalibrated class scores.**

## Current instructions
Use the central [getting-started guide](../../docs/getting-started.md), [architecture](../../docs/architecture.md) and [model-evidence guide](../../docs/model-evidence.md). Python dependencies are canonical in root `pyproject.toml`/`uv.lock`; `backend/requirements.txt` is a generated compatibility shim, not an independently maintained environment.

```sh
# From repository root, after restoring and verifying the runtime:
uv sync --locked --extra dev
uv run --locked python scripts/prepare_runtime.py
uv run --locked uvicorn osteopatch.app:app --app-dir app/g6/backend --host 127.0.0.1 --port 8137
# Separate terminal:
npm --prefix app/g6/frontend ci
npm --prefix app/g6/frontend run dev
```

## Boundaries
Canonical outputs are `NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`. Source/QC, immutable prediction and append-only review events are distinct. Corrections do not automatically retrain a model. Contrastive attribution is implemented but requires its optional dependencies and verified recovered-head artifacts; it is not segmentation or a diagnosis.

The original G4 binary is absent. The recovered head has a separate identity and cannot inherit original-model claims. The weak viable-tumor result and full limitation catalog remain visible through `/v1/model-card`.

The historical AWS deployment under `deploy/` is a separate runtime from local development. See the [deployment runbook](../../docs/deployment.md); no local setup command provisions AWS resources.
