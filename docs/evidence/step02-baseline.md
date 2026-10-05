# STEP 2 — Post-Bootstrap Test Baseline

**Date:** 2026-10-05 · **Branch:** `feat/unified-platform-p0` · **SHA at run:** `81c7859` (plus the pyproject/bootstrap commit)
**Python:** 3.12.10 (`.venv`) · **Node:** 24.19.0 · **npm:** 11.17.0 · **uv:** 0.12.23

Every exit code below was captured **immediately after** the tested command, not
from a pipeline filter.

---

## Result summary

| Suite | Command | Exit | Result |
|---|---|---|---|
| G6 backend | `.venv/Scripts/python -m pytest -q` | **0** | **53 passed, 10 skipped** |
| Enterprise backend | `.venv/Scripts/python -m pytest -q` | **0** | **28 passed, 1 skipped** |
| G6 frontend | `npm test` | **0** | 18 passed |
| G6 frontend build | `npm run build` | **0** | `dist/` produced, 0 TS errors |
| Enterprise frontend | `npm test` | **0** | 2 passed |
| Enterprise frontend build | `npm run build` | **0** | `dist/` produced, 0 TS errors |

**All six gates green. Zero failures.**

---

## What changed from the pre-bootstrap baseline

| Suite | Before (audit) | After (this run) |
|---|---|---|
| G6 backend | exit **1** — 34 passed, 10 skipped, 1 failed, 18 errors | exit **0** — 53 passed, 10 skipped |
| Enterprise backend | exit **2** — collection error, 13 never ran | exit **0** — 28 passed, 1 skipped |
| G6 frontend build | **not executed** | exit **0** |

The 19 G6 failures and the enterprise collection error were **one** root cause:
`fastapi` was not installed. No source change was needed to fix them.

The resulting G6 figure — **53 passed / 10 skipped (torch-free venv)** —
**exactly reproduces** the independently recorded G7 certification figures in
`runtime-artifacts/evidence/backend-test-report.json`. This is a meaningful
confirmation: the suite was never broken, only unbootstrapped.

### The 10 remaining G6 skips

All `torch not installed in this venv`, by design:
`test_real_bundle.py:15` (1) and `test_attribution.py` lines 139, 149, 156,
170, 180, 190, 203, 213, 224 (9).

These are **not** expected to skip in the model venv and **must not** be
suppressed to make the torch-free job green — they are the seam that keeps the
web serve path free of a 200 MB dependency.

### The 1 enterprise skip

Pre-existing and unrelated to bootstrap; left as-is pending its own step.

---

## Dependency resolution — three real conflicts, all resolved

These were found by attempting the install, not guessed at:

1. **`pytorch-grad-cam` does not exist on PyPI.** The distribution is
   **`grad-cam`**; `pytorch_grad_cam` is only the *import* name. The mismatch is
   upstream's and must not be "corrected" back.
2. **`tiatoolbox>=2.1.3` requires `numpy>=2.0.0,<2.4.4`**, which is incompatible
   with the previous exact pin `numpy==2.5.3`.
3. **`tiatoolbox>=2.1.3` requires `openslide-python>=1.4.0,<1.4.6`**, which is
   incompatible with a `>=1.4.6` request.

### Documented deviation: numpy

The pin changed from `numpy==2.5.3` to `numpy>=2.0.0,<2.4.4` (resolved: 2.4.3).

**Why this is safe and not a contract break:** the frozen G4 preprocessing
contract (`384x384` bilinear antialias, ImageNet mean/std) is *data carried
inside the bundle*, not a property of the numpy build. Nothing in OsteoPatch
compiles against a numpy ABI. The historical evaluation numbers are read from
frozen CSV/JSON artifacts and are not recomputed, so they cannot drift.

This is recorded rather than silently absorbed.

---

## OpenSlide is now genuinely available (supersedes the audit)

The audit recorded that `import openslide` failed with
`Couldn't locate OpenSlide DLL` and that the fix was untested.

**It now works:**

```
openslide 1.4.3 | lib 4.0.1
```

This was achieved by the `wsi` extra carrying `openslide-bin` on Windows —
which the upstream error message itself recommends. Consequence: the WSI engine
is **real and testable locally**, not a permanently-skipped path. The pure-Python
fallback reader is still required for environments without it.

---

## Venv cost — extras split by weight

Installing `tiatoolbox` alongside `openslide-python` produced a **1.7 GB**
environment, because tiatoolbox transitively pulls torch, jupyterlab, sphinx,
transformers, and matplotlib.

Extras are therefore split by **cost**, not feature area:

| Extra | Contents | Serve venv? |
|---|---|---|
| *(core)* | fastapi, uvicorn, pydantic, pillow, numpy, PyJWT | yes |
| `dev` | pytest, httpx, coverage, ruff, mypy | yes |
| `wsi` | openslide-python (+ openslide-bin on Windows) | yes |
| `tissue` | tiatoolbox | **no — heavy** |
| `model` | torch, torchvision, grad-cam | **no — heavy** |

The serve venv is now **142 MB and contains no torch**, which is what keeps the
architectural claim ("the web API never imports torch") true rather than
aspirational. Verified explicitly: `import torch` fails in `.venv`.

---

## Not covered by this baseline

- **`model` extra / torch tests.** Not run here; they are a separate CI job
  (§15 requires it be optional until proven).
- **`tissue` extra / tiatoolbox.** Installs cleanly per the resolver but was
  not exercised at runtime.
- **The local smoke test and `_bake` reconstruction.** Built in the following
  steps; not part of this baseline.