# OsteoPatch Review (G6) — Local Educational Prototype

A local, image-first pathology-review workbench over the frozen **`baseline-frozen-g4`**
osteosarcoma patch classifier (3 classes: NON_TUMOR, VIABLE_TUMOR, NECROSIS).

> **Educational / research prototype — NOT for diagnosis, treatment decisions,
> treatment-response prediction, or prognosis. Model scores are uncalibrated class
> scores, never disease probabilities.**

The app lets a reviewer browse patches, see the model's suggested class and all three
**uncalibrated** scores, work the most ambiguous patches first (deterministic
review-priority ranking), and ACCEPT / CORRECT / DEFER each — recording every decision
as an append-only event while the model's original prediction stays immutable. Reviews
export to CSV/JSON with both the model prediction and the human action preserved.

## Architecture
- **Backend:** FastAPI + SQLite, torch-free at serve time (predictions are precomputed once).
- **Precompute:** a one-time PyTorch pass over the decoded patches, run under a torch venv.
- **Frontend:** React + TypeScript + Vite.
- Server binds **127.0.0.1 only**. No AWS, no Docker, no auth, no external services.

The G4 bundle hash is re-verified at load; the app refuses to start on mismatch.

## Run OsteoPatch locally

### 0. One-time: precompute predictions (torch venv)
Runs G4 inference over all decoded patches into the SQLite DB. Needs the torch venv
(the one with torch/torchvision; e.g. the project's ingestion `.venv`). Reuses existing
rows keyed by `(image_id, model_bundle_hash)` — safe to re-run.

```powershell
cd app\g6\backend
# <torch venv python> = the venv containing torch + torchvision
& <torch-venv>\Scripts\python.exe precompute.py
```

Paths (bundle, TIFFs, DB) default to the parent-verified scratch locations and are
overridable via environment variables: `OSTEOPATCH_BUNDLE`, `OSTEOPATCH_TIFFS`,
`OSTEOPATCH_DB`, `OSTEOPATCH_QC_DIR`, `OSTEOPATCH_MODEL_CARD_DIR`.

### 1. Backend (web venv — no torch needed)
```powershell
cd app\g6\backend
python -m venv .webvenv
.webvenv\Scripts\python.exe -m pip install -r requirements.txt
.webvenv\Scripts\python.exe -m uvicorn osteopatch.app:app --host 127.0.0.1 --port 8137
```
Health check: open [http://127.0.0.1:8137/v1/health](http://127.0.0.1:8137/v1/health).

### 2. Frontend
```powershell
cd app\g6\frontend
npm install
npm run dev
```
Vite serves the workbench (default [http://127.0.0.1:5173](http://127.0.0.1:5173)); its
dev server proxies `/v1/*` to the backend on 8137 (see `vite.config.ts`).

## Tests
```powershell
# Backend — torch tests (torch venv) + API/safety/scoring tests (web venv)
cd app\g6\backend
<torch-venv>\Scripts\python.exe -m pytest -q tests\test_real_bundle.py
.webvenv\Scripts\python.exe  -m pytest -q tests\test_api_export.py tests\test_review_safety.py tests\test_scoring_contract.py

# Frontend
cd app\g6\frontend
npm run test
```

## Data model (three separate, non-overwriting concepts)
1. **Source/QC metadata** (`source_qc`) — source id, group, original label, QC status,
   `training_eligible`, `qc_review_flag`. `training_eligible=false` is not a biological
   class; MIXED is excluded metadata, never a 4th model output.
2. **Prediction** (`prediction`, immutable) — 3 scores + `top1_score` + `top_two_margin`
   + `normalized_entropy` + `inference_kind="prototype_inference"`, keyed by image + bundle hash.
3. **ReviewEvent** (`review_event`, append-only) — ACCEPT / CORRECT / DEFER with
   revision number + idempotency key. A correction is a new event; the prediction row never changes.

## Scope & limitations
Exploratory, **case/slide-group-independent** classification over four groups; P9 is
single-class; **VIABLE_TUMOR is the model's weak class** (see the G4 OOF evaluation —
the authoritative performance evidence, kept separate from this app's prototype inference).
Scores are uncalibrated. The "Model attribution" tab is reserved for G7 (Grad-CAM) and is
intentionally empty here — no attribution image is fabricated.
