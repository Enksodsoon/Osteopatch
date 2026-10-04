# OsteoPatch — Current-State Audit

**Generated:** 2026-10-05 · **Branch:** `feat/unified-platform-p0` · **SHA audited:** `a180c7e62ae40e8049bfc646c585a0100f691564`

> **Educational research prototype only. Not for diagnosis, treatment
> decisions, or predicting treatment response.**

This document records what was **observed by direct inspection**, not what any
planning document claims. Every hash, count, and exit code below was computed or
executed during the audit. Where a claim could not be checked, it is listed
explicitly under [Claims I could not verify](#claims-i-could-not-verify) rather
than repeated as fact.

---

## 1. Git baseline

| Fact | Value |
|---|---|
| `origin/main` | `a180c7e62ae40e8049bfc646c585a0100f691564` |
| Local `main` before this work | `de41ce737ac22d8008b63451731ca4de18887529` (**stale, 5 commits behind**) |
| Branch created for this work | `feat/unified-platform-p0` @ `a180c7e` |
| Working tree at audit time | clean (`git status --porcelain` empty) |
| Tracked files | 231 |
| `git diff --stat origin/main HEAD` | **empty** — feature branch and `origin/main` had identical trees |

Tracked files by area: `aidlc-docs` 103 · `app` 99 · `docs` 11 · `prompts` 8 ·
`templates` 5 · root 5.

---

## 2. Existing applications (two, in parallel)

The repository contains **two independent FastAPI + React applications**, not one.

### 2.1 `app/g6` — the review MVP (the real product)

| Area | Files | LOC |
|---|---|---|
| Backend (`osteopatch/`) | 14 modules | 1,995 |
| Backend tests | 6 files | 787 |
| Frontend (React/TS/Vite) | 11 files | 1,267 |
| Deploy (Dockerfile, CDK, Lambda) | 6 files | 377 |

Backend modules: `app` (13 routes) · `attribution` (contrastive Grad-CAM, 400
LOC) · `config` · `db` · `dynamo_review` · `images` · `metadata` · `modelcard` ·
`queries` · `repo` · `review_store` · `scoring` · `server`.

### 2.2 `app/g7-enterprise` — identity, RBAC, tenancy, governance

| Area | Files | LOC |
|---|---|---|
| Backend (`enterprise/`) | 15 modules | 1,993 |
| Backend tests | 3 files | 502 |
| Frontend | 8 files | 479 |
| Demo drivers | (in `demo_full*.py`) | 251 |

23 routes. Enterprise **imports** the G6 package rather than forking it —
this is the correct seam and the basis of the unification plan.

### 2.3 Architecture consequence

The two apps share no domain implementation. Enterprise reaches G6's logic
through `review_proxy.py`, which imports `osteopatch` at runtime and delegates.
Duplicated domain logic exists in at least four places (see §6).

---

## 3. Model artifacts

### 3.1 Identity — two distinct models, never conflated

| Model | SHA-256 | Status |
|---|---|---|
| `baseline-frozen-g4` (original) | `01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63` | **Bundle file ABSENT from disk** (reclaimable scratch was lost) |
| `g4-behavioral-recovery-r1` (recovered head) | `ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73` | Present, 21,785 bytes |

The recovered head is a **behavioural** reconstruction fitted to the surviving
immutable predictions (score parity `max_abs_diff 2.38e-07`, 1144/1144 class
agreement). It is **not** the original absolute classifier. The original hash is
never reassigned to it.

**Gap:** `app/` references the recovered model **by path only**
(`config.RECOVERED_MODEL_PATH`). Its hash `ffff1282…` appears nowhere in code —
only in documentation. There is no runtime hash guard for it.

### 3.2 Frozen evaluation evidence (durable, in git)

From `aidlc-docs/inception/model/g4/overall-oof-metrics.json`:

| Metric | Value |
|---|---|
| macro-F1 (3 classes) | **0.562311** |
| balanced accuracy | **0.626460** |
| log loss | 1.194723 |
| Brier | 0.496084 |
| `NON_TUMOR` P/R/F1 | 0.788809 / 0.902893 / 0.842004 (support 484) |
| **`VIABLE_TUMOR` P/R/F1** | **0.477612 / 0.110345 / 0.179272** (support 290) |
| `NECROSIS` P/R/F1 | 0.540541 / 0.866142 / 0.665658 (support 254) |

Supports sum to 1,028 = the `training_eligible` count. Internally consistent.

> **`VIABLE_TUMOR` recall is 0.110.** The model misses ~89% of viable tumour
> patches. This is the dominant limitation and must never be hidden.

### 3.3 Frozen preprocessing contract (from `final-bundle.json`)

```json
{"resize": [384, 384], "interpolation": "bilinear", "antialias": true,
 "crop": "none (full-field)", "color_space": "RGB",
 "normalize_mean": [0.485, 0.456, 0.406],
 "normalize_std":  [0.229, 0.224, 0.225]}
```

Canonical class order, confirmed in code at `config.py:20`:
`("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")`.

---

## 4. Data artifacts

### 4.1 Canonical database

`runtime-artifacts/db/osteopatch_g6.sqlite3` — SHA-256
`705ce5c5858ca56c70d3027b74e4094df18bb42926d4755d3ca54e5e294acbab`

| Table | Rows |
|---|---|
| `source_qc` | 1,144 |
| `prediction` | 1,144 |
| `review_event` | **0** |

All 1,144 predictions carry `model_bundle_hash = 01727fb8…`,
`model_version = baseline-frozen-g4`. Predicted classes: NON_TUMOR 510,
VIABLE_TUMOR 330, NECROSIS 304 (prototype inference over all 1,144, including
116 training-ineligible rows).

`training_eligible`: 1,028 / 116. Groups: Case-3 285 · Case-4 277 · Case-48 370 ·
P9 212 (= 1,144).

### 4.2 Pixel artifacts (gitignored by policy)

`runtime-artifacts/images/` — **1,144 TIFFs**; `thumbnails/` — 1,144 PNGs;
`models/` — 7 files; `recovery/` — 12 evidence files; `evidence/` — 11 files.

`runtime-artifacts/` is gitignored (~287 MB). It is a durable *runtime
dependency*, not a source artifact, and is reconstructible from the frozen
manifest + recovery recipe.

### 4.3 Three copies of the database exist

`runtime-artifacts/db/`, `deploy/_bake/db/`, and (historically) reclaimable
scratch. The first two are byte-identical (same hash above).

---

## 5. Working and broken tests (executed)

All runs used exit-code capture taken **immediately after** the tested command.

| Suite | Exit | Result |
|---|---|---|
| `app/g6/backend` (`pytest -q tests`) | **1** | 34 passed, 10 skipped, **1 failed**, **18 errors** |
| `app/g7-enterprise/backend` (`pytest -q`) | **2** | **collection error**; 13 tests never ran |
| `app/g6/frontend` (`npm test`) | **0** | **18/18 passed** |
| `app/g7-enterprise/frontend` (`npm test`) | **0** | **2/2 passed** |

### 5.1 Root cause of every backend failure

All 19 G6 failures and the enterprise collection error are the **same** cause:

```
ModuleNotFoundError: No module named 'fastapi'
  conftest.py:58   -> from fastapi.testclient import TestClient
  osteopatch/app.py:13
```

This is an **unbootstrapped environment, not a broken suite.** No genuine logic
defect is implicated by any current backend failure.

### 5.2 Skips (G6, exactly 10)

All `torch not installed in this venv`:
`test_real_bundle.py:15` (1) and `test_attribution.py` lines 139, 149, 156, 170,
180, 190, 203, 213, 224 (9).

### 5.3 Not run

- **Torch-dependent tests** — `torch` is not installed; no venv exists.
- **`npm run build` (both frontends)** — the TypeScript compile gate is
  **unverified**. Frontend *tests* pass; the build gate has not been executed.

### 5.4 No test evidence is committed

Every prior green result lives in gitignored
`runtime-artifacts/evidence/` and was produced with venvs that no longer exist.
A clean clone cannot reproduce any of it.

---

## 6. Known gaps — four load-bearing defects

### D1 — Worker preprocessing contradicts the frozen contract

`app/g7-enterprise/backend/enterprise/cpu_worker.py:180`

```python
img = Image.open(tiff).convert("RGB").resize((224, 224))   # contract says [384, 384]
```

Normalization is also inlined rather than read from the bundle. The correct
implementation already exists — `osteopatch/model.py:69` reads
`cfg["preprocessing"]` — and was simply never reused.

Secondary: the worker's `_entropy_normalized` can return a tiny **negative**
value (e.g. `-1e-12` for `[1.0, 0, 0]`), failing the canonical clamp invariant
asserted by `test_scoring_contract.py::test_normalized_entropy_negative_scores_clamped`.

### D2 — Divergent `prediction_id` schemes

| Source | Scheme | Example |
|---|---|---|
| `osteopatch/repo.py:42` (canonical) | `pred-{image_id}-{hash[:12]}` | `pred-Case-3-A17-15765-20926-01727fb832f9` |
| `enterprise/cpu_worker.py:148` | `pred_{sha1(image_id+hash)[:16]}` | `pred_8fb67b36c55816bf` |

Verified **not identical**. Combined with `UNIQUE(image_id, model_bundle_hash)`,
a worker-written row can be invisible to the G6 read path while still blocking a
canonical insert. This is a correctness bug, not a style issue.

### D3 — Multi-tenancy via process-global mutation

`app/g7-enterprise/backend/enterprise/review_proxy.py:107, 121, 122`

```python
os.environ["OSTEOPATCH_IMAGE_ALLOWLIST"] = str(path)
g6_config.IMAGE_ALLOWLIST_PATH = str(path)
g6_config._IMAGE_ALLOWLIST_CACHE = g6_config._ALLOWLIST_UNSET
```

Never restored. Under concurrency, project A's scope can be read while serving
project B, and the last-touched project leaks into subsequent unscoped reads.

**Root cause (verified):** no table has a `project_id` column — `PRAGMA
table_info` across `source_qc`, `prediction`, `review_event` returns **zero**
matching columns. Tenancy is entirely external, which is *why* the global
mutation exists. It is a symptom of a schema gap, not an isolated bug.

### D4 — Hardcoded, non-existent, user-specific paths

`app/g6/backend/osteopatch/config.py:80, 89, 95`

```
C:\Users\enkso\.kiro\crew\scratch\runtime-0a306834\osteopatch_g6
C:\Users\enkso\.kiro\crew\scratch\runtime-0a306834\osteopatch_g4\final_bundle\...
C:\Users\enkso\.kiro\crew\scratch\runtime-0a306834\osteopatch_full_ingestion\tiffs
```

That scratch directory no longer exists. Committed source carries a dead path
belonging to one machine.

### D5 — Duplicated domain logic (drift risk, *not* currently divergent)

| Logic | Canonical | Duplicate |
|---|---|---|
| softmax | `scoring.py` | `attribution.py:167`, `cpu_worker.py:72` |
| normalized entropy | `scoring.normalized_entropy` | `cpu_worker.py:80` |
| `prediction` DDL | `migrations/0001_initial.sql` | `_ensure_prediction_table` in `cpu_worker.py` |
| review-status mapping | `repo._review_status` | `review_store.review_status` (delegates — OK) |

The duplicated entropy was checked numerically against the canonical
implementation over five representative score vectors: **max absolute
difference `2.7e-12`**. Behaviourally equivalent today. Recorded as maintainability
risk, deliberately **not** claimed as a bug.

---

## 7. Missing runtime assets

| Missing | Consequence |
|---|---|
| Original G4 bundle `01727fb8…` | `precompute.py` and `test_real_bundle.py` cannot run; only the recovered head is executable |
| `torch` / any venv | 10 attribution + real-bundle tests skip; attribution endpoint untestable |
| `fastapi`, `pydantic`, `PyJWT` | both backends cannot import |
| `deploy/_bake/` reconstruction script | `_bake` exists locally (hashes verified identical to `runtime-artifacts/`) but **no committed script rebuilds it** |
| CI (`.github/`) | **no status checks exist on `main`** |
| `scripts/`, `Makefile`, root `pyproject.toml`, `uv.lock` | no reproducible entry point |
| eslint / ruff / mypy config | no static gates |

---

## 8. Deployment architecture (claimed)

Per `aidlc-docs/g8-deployment-summary.md`: CloudFront → S3 (frontend) + API
Gateway → Lambda container (FastAPI) → DynamoDB (reviews) + private S3
(pixel assets). Stack `OsteoPatchG8`, region `us-east-1`, account `153485202811`.
50-image deterministic subset (verified: 50 unique ids, SHA-256
`78ecd2f703913cef8d3c5f298489f741cc96f9d99a8a9c526290ec85c6ef005f`).

**Reproducibility defect:** `deploy/Dockerfile` `COPY`s three files from
`deploy/_bake/`, which is gitignored and built by no committed script. A clean
clone cannot build the image.

**This stack is not touched by the current work.**

---

## 9. Stale documentation (contradicted by inspection)

| Document | Claim | Reality |
|---|---|---|
| `README_START_HERE.md:6` | package contains "no … application implementation" | `app/` has 99 tracked files |
| `app/g7-enterprise/README.md:73` | "TIFF pixels + the G4 bundle were reclaimed from scratch" | 1,144 TIFFs re-recovered in `runtime-artifacts/images/` |

---

## 10. Cloud assumptions

- The G8 deployment is asserted live at `https://dgv0wpd8tglrw.cloudfront.net`.
- **No AWS credentials are present in this environment.** The claim is neither
  confirmed nor refuted here, and no AWS resource is modified by this work.

---

## Claims I could not verify

1. **That the G8 AWS deployment is live**, or matches its documented shape.
   No credentials; `git remote` points at
   `https://github.com/Enksodsoon/osteopatch-review.git` but push access is
   neither used nor assumed.
2. **Whether the backend suites pass once `fastapi` is installed.** The 19
   current failures are environmental; the suite's true state is unknown until
   bootstrapped.
3. **`npm run build` (both frontends)** — the TypeScript compile gate was not
   executed.
4. **TIAToolbox model-weights license** — the code is BSD-3-Clause, but the
   weights carry a separate license that was not resolved.
5. **OpenSlide runtime** — `openslide-python` is installed but
   `import openslide` fails: `Couldn't locate OpenSlide DLL`. The error itself
   suggests `pip install openslide-bin` as the Windows remedy; untested.

---

## 11. Toolchain (observed)

Python 3.12.10 · Node 24.19.0 · npm 11.17.0 · uv 0.12.23 · git 2.55.0.
**No virtual environments exist** anywhere in the repository.

Version pins drift from what is installed on the host (each package is pinned
in `requirements.txt` and differs from the system install):

| Package | Pinned | Installed |
|---|---|---|
| numpy | 2.5.3 | 2.5.2 |
| pillow | 11.0.0 | 12.3.0 |
| pytest | 8.3.4 | 9.1.1 |

`numpy==2.5.3` was confirmed to **exist** on PyPI (HTTP 200), so the pin is
valid and resolvable.

---

## 12. Honest baseline

The repository is a **substantially real implementation** — ~7,800 LOC of
application code, a frozen and honestly-documented model, 1,144 immutable
predictions, and a working review workflow. The prior audit's central claim is
confirmed.

What it lacks is **reproducibility**: no CI, no committed evidence, no
reconstruction script, a dead hardcoded path, and a tenancy mechanism that
cannot survive concurrency. Those are the P0 targets.