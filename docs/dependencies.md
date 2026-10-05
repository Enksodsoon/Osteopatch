# Dependency Register

Every third-party dependency OsteoPatch introduces or already ships, with the
nine fields required by the handoff brief.

**Licenses are recorded from authoritative sources, never from memory.** Where a
license was read from installed package metadata or the upstream LICENSE file,
that is stated. Two licenses were initially asserted from memory and both were
wrong; this register is the correction.

> Permissive licenses (Apache-2.0 / BSD / MIT) are preferred. Copyleft
> dependencies are permitted only behind an optional extra, with the linking
> consequence recorded explicitly.

---

## Status legend

| Status | Meaning |
|---|---|
| `runtime` | imported on a normal request path |
| `dev` | test / lint / build only |
| `optional` | behind an extras group, never required to start |
| `worker` | imported only by the offline inference worker |

---

## A. Backend — web and review stack

### A1. fastapi

| Field | Value |
|---|---|
| **Name / version** | `fastapi` 0.115.6 |
| **Source** | https://github.com/fastapi/fastapi · https://pypi.org/project/fastapi/ |
| **License** | MIT |
| **Why needed** | ASGI application framework for the G6 review API and the enterprise layer. Provides routing, validation, dependency injection for RBAC. |
| **Depended on by** | `osteopatch/app.py`, `enterprise/app.py`, both test suites |
| **Runtime footprint** | pure-Python + `pydantic`/`starlette`; no compiled extension |
| **Fallback** | none — the API cannot run without it. This is the single cause of all 19 current backend test failures. |
| **Security** | Binds `127.0.0.1` only (frozen constraint in `config.HOST`). No auth in G6 by design; enterprise layers JWT on top. Pydantic v2 request validation is part of the security boundary. |

### A2. uvicorn[standard]

| Field | Value |
|---|---|
| **Name / version** | `uvicorn` 0.34.0 |
| **Source** | https://github.com/encode/uvicorn |
| **License** | BSD-3-Clause |
| **Why needed** | ASGI server for local development and the Lambda adapter path. |
| **Depended on by** | `osteopatch/server.py`, enterprise run instructions |
| **Runtime footprint** | light; `[standard]` adds `httptools`/`uvloop`/`watchfiles` compiled wheels |
| **Fallback** | any ASGI server; not load-bearing for logic |
| **Security** | local-only binding. `uvloop`/`httptools` are optional accelerators. |

### A3. pydantic

| Field | Value |
|---|---|
| **Name / version** | `pydantic` 2.10.4 |
| **Source** | https://github.com/pydantic/pydantic |
| **License** | MIT |
| **Why needed** | Request/response validation, including review-action validation at the HTTP edge. |
| **Depended on by** | `osteopatch/app.py`, `enterprise/app.py` |
| **Runtime footprint** | `pydantic-core` compiled wheel (~2 MB) |
| **Fallback** | none |
| **Security** | Validation is a security control — it is what turns a malformed `ACCEPT`/`CORRECT`/`DEFER` body into a 422 before domain logic runs. Must not be bypassed or loosened. |

### A4. pillow

| Field | Value |
|---|---|
| **Name / version** | `pillow` 11.0.0 (host has 12.3.0 — drift recorded) |
| **Source** | https://github.com/python-pillow/Pillow |
| **License** | MIT-CMU (HPND-derived; permissive) |
| **Why needed** | Patch decode/resize, thumbnail generation, and the WSI fallback reader. |
| **Depended on by** | `osteopatch/images.py`, `precompute.py`, attribution overlay rendering, planned `pathology/reader.py` |
| **Runtime footprint** | compiled, ~4–8 MB with bundled zlib/libjpeg/libtiff |
| **Fallback** | none for patch pixels. Pillow **is** the fallback reader for WSI when OpenSlide is absent. |
| **Security** | Decoding untrusted image bytes is an attack surface. `MAX_IMAGE_PIXELS` decompression-bomb guard must stay enabled; ingestion limits are enforced in the upload path. |

### A5. numpy

| Field | Value |
|---|---|
| **Name / version** | `numpy` 2.5.3 (host has 2.5.2 — drift recorded) |
| **Source** | https://github.com/numpy/numpy |
| **License** | BSD-3-Clause |
| **Why needed** | Score arrays, CAM arrays, and tissue-mask computation. |
| **Depended on by** | `osteopatch/scoring.py`, `attribution.py`, planned `pathology/tissue_mask.py` |
| **Runtime footprint** | compiled, ~15–20 MB |
| **Fallback** | none for the review API |
| **Security** | pinned for reproducibility (avoids the numpy 1.x/2.x ABI break). No user input reaches numpy directly. |

### A6. PyJWT

| Field | Value |
|---|---|
| **Name / version** | `PyJWT` 2.10.1 |
| **Source** | https://github.com/jpadilla/pyjwt |
| **License** | MIT |
| **Why needed** | Local development identity issuer and JWT verification for the enterprise layer. |
| **Depended on by** | `enterprise/auth.py`, `enterprise/deps.py` |
| **Runtime footprint** | pure Python, negligible |
| **Fallback** | external OIDC (Cognito/other) via `OSTEOPATCH_OIDC_JWKS_URL` |
| **Security** | Default secret is `e1-local-dev-not-a-real-secret` and is **development-only**. Production must set `OSTEOPATCH_JWT_SECRET` or use external OIDC. Never commit a real secret. |

### A7. httpx

| Field | Value |
|---|---|
| **Name / version** | `httpx` 0.28.1 |
| **Source** | https://github.com/encode/httpx |
| **License** | BSD-3-Clause |
| **Why needed** | `TestClient` transport in tests; HTTP client in the local smoke tester. |
| **Depended on by** | both `conftest.py` files, `app/local-tester.py` |
| **Runtime footprint** | dev only |
| **Fallback** | none needed |
| **Security** | local-only calls to `127.0.0.1`. |

---

## B. Backend — test and tooling

| Name | Version | Source | License | Why | Depends on | Footprint | Fallback | Security |
|---|---|---|---|---|---|---|---|---|
| `pytest` | 8.3.4 (host 9.1.1) | github.com/pytest-dev/pytest | MIT | test runner, fixtures, markers (`torch_only`, `wsi`) | CI + local | dev | none | n/a |
| `ruff` | (to be pinned) | github.com/astral-sh/ruff | MIT | lint + import hygiene; `ruff format` deliberately **not** enabled to avoid whole-repo churn | CI | dev | none | n/a |
| `mypy` | (to be pinned) | github.com/python/mypy | MIT | type check scoped to the canonical domain package | CI | dev | none | n/a |
| `coverage` | — | github.com/nedbat/coveragepy | Apache-2.0 | coverage reporting | CI | dev | none | n/a |

---

## C. Model / inference (worker only)

### C1. torch

| Field | Value |
|---|---|
| **Name / version** | `torch` (CPU wheel; G7 certification previously used 2.14.1+cpu) |
| **Source** | https://pytorch.org · https://download.pytorch.org/whl/cpu |
| **License** | BSD-3-Clause |
| **Why needed** | Model forward pass, frozen-encoder embeddings, and Grad-CAM. |
| **Depended on by** | `osteopatch/model.py`, `osteopatch/attribution.py`, `precompute.py`, `enterprise/cpu_worker.py` |
| **Runtime footprint** | **~200 MB CPU build.** Never imported on the web serve path — the API imports torch lazily, by design. |
| **Fallback** | precomputed predictions; the review API serves entirely without torch. |
| **Security** | `torch.load` on a bundle executes pickled code. Loading is gated by a **mandatory SHA-256 check** before any `torch.load` call, and only registry/bundle paths are ever loaded. This guard must never be bypassed. |

### C2. torchvision

| Field | Value |
|---|---|
| **Name / version** | matching torch |
| **Source** | https://github.com/pytorch/vision |
| **License** | BSD-3-Clause |
| **Why needed** | MobileNetV3-Small architecture and the v2 transform pipeline that rebuilds the frozen preprocessing from the bundle spec. |
| **Depended on by** | `model.py`, `attribution.py` |
| **Runtime footprint** | ~10 MB |
| **Fallback** | none for torch paths |
| **Security** | `mobilenet_v3_small(weights=...)` would download ImageNet weights at runtime. In Lambda this is impossible (no egress, read-only FS), so weights are baked at **build** time into `TORCH_HOME`. Never enable runtime download in a deployed image. |

### C3. pytorch-grad-cam

| Field | Value |
|---|---|
| **Name / version** | 1.5.5 (per prior certification) |
| **Source** | https://github.com/jacobgil/pytorch-grad-cam |
| **License** | MIT |
| **Why needed** | The Grad-CAM engine behind contrastive attribution. |
| **Depended on by** | `osteopatch/attribution.py` |
| **Runtime footprint** | pulls in `opencv-python` |
| **Fallback** | attribution degrades to a labelled error; review/prediction never depend on it |
| **Security** | **Build note:** `opencv-python` links `libGL`/`libxcb`, absent on the Lambda base image. The Dockerfile removes `cv2` after install and installs `opencv-python-headless` instead. Preserve this. |

---

## D. WSI / pathology — optional extras

### D1. openslide-python  *(optional extra: `wsi`)*

| Field | Value |
|---|---|
| **Name / version** | `openslide-python` (1.4.6 observed installed) |
| **Source** | https://github.com/openslide/openslide-python · https://openslide.org/ |
| **License** | **`LGPL-2.1-only AND BSD-3-Clause AND MIT AND LicenseRef-Public-Domain`** — read from installed `openslide_python-1.4.6.dist-info/METADATA`, not from memory |
| **Why needed** | Whole-slide metadata, pyramid levels, dimensions, downsample factors, and efficient random-access region reads. **No custom WSI binary parser will be written.** |
| **Depended on by** | planned `osteopatch/pathology/reader.py` (`OpenSlideReader`) |
| **Runtime footprint** | thin Python ctypes wrapper; the heavy part is the native `libopenslide` shared library, loaded from the OS |
| **Fallback** | `PillowTiffReader` — a pure-Python reader for tiled/striped TIFF. It reports **only what the file genuinely contains**; `mpp`, `objective_power`, and `vendor` are `null` when absent. Metadata is never invented. |
| **Security** | LGPL-2.1 on the *bindings* is weak copyleft, satisfied by dynamic linking to a system library without distributing a modified OpenSlide. OsteoPatch ships **no** OpenSlide source. BSD-3/MIT cover the bundled deepzoom examples. **Status: not yet installable here** — `import openslide` fails with `Couldn't locate OpenSlide DLL`; the library's own error suggests `pip install openslide-bin` on Windows. Untested; CI uses Linux. |

### D2. tiatoolbox  *(optional extra: `wsi`)*

| Field | Value |
|---|---|
| **Name / version** | `tiatoolbox` **2.1.3** (latest on PyPI; an earlier probe of 1.2.1 showed stale `Pre-Alpha` / Python ≤3.10 classifiers that do **not** apply to 2.x) |
| **Source** | https://github.com/TissueImageAnalytics/tiatoolbox |
| **License** | **`BSD 3-Clause`** — read from the upstream `LICENSE` on `develop`, *not* from memory. I previously asserted Apache-2.0 and was wrong. |
| **Why needed** | Preferred implementation for tissue masking and pathology preprocessing, ahead of any custom segmentation. |
| **Depended on by** | planned `osteopatch/pathology/tissue_mask.py` (`TiatoolboxMasker`) |
| **Runtime footprint** | **large** — pulls scikit-image and torch-adjacent scientific stack; ~hundreds of MB with dependencies |
| **Fallback** | `ThresholdMasker` — a clearly-labelled Pillow+numpy tissue/background masker. Persisted with `algorithm`/`version`/`parameters` so a mask's provenance is never ambiguous. |
| **Security** | Supplies **preprocessing only — tissue vs background. NOT tumour segmentation.** This distinction must remain in code, docs, and UI. |
| **License caveat** | The upstream LICENSE states *"Model weights are provided under a different license."* Code and weights are **not** the same grant. Do not assume a pretrained weight is BSD-3-Clause; resolve its license before use. |

---

## E. Frontend

| Name | Version | Source | License | Why | Footprint | Fallback | Security |
|---|---|---|---|---|---|---|---|
| `react` / `react-dom` | ^18.3.1 | github.com/facebook/react | MIT | UI runtime | ~140 kB gz bundle | none | standard XSS hygiene; no `dangerouslySetInnerHTML` used |
| `typescript` | ^5.7.2 | github.com/microsoft/TypeScript | Apache-2.0 | type safety + `tsc -b` build gate | dev | none | n/a |
| `vite` | ^6.0.7 | github.com/vitejs/vite | MIT | dev server / bundler | dev | none | dev only |
| `vitest` | ^2.1.9 | github.com/vitest-dev/vitest | MIT | test runner | dev | none | n/a |
| `@testing-library/react` | ^16.1.0 | github.com/testing-library | MIT | UI tests | dev | none | n/a |
| `@testing-library/jest-dom` | ^6.6.3 | github.com/testing-library | MIT | DOM matchers | dev | none | n/a |
| `@testing-library/user-event` | ^14.5.2 | github.com/testing-library | MIT | realistic input simulation | dev | none | n/a |
| `jsdom` | ^25.0.1 | github.com/jsdom/jsdom | MIT | DOM environment for tests | dev | none | n/a |

*(enterprise frontend additionally uses `@testing-library/react` ^16.1.0;
`user-event` and `jest-dom` are present there too.)*

---

## F. Infrastructure (not shipped in the application image)

| Name | Version | Source | License | Why | Fallback | Security |
|---|---|---|---|---|---|---|
| `aws-cdk-lib` | see `deploy/cdk/requirements.txt` | github.com/aws/aws-cdk-python | Apache-2.0 | IaC for the G8 stack | manual console | deploy-time only; **no credentials in git** |
| `mangum` | see `deploy/requirements-lambda.txt` | github.com/Kludex/mangum | MIT | Lambda ↔ ASGI adapter | none in container images | none |
| `boto3` / `botocore` | runtime-provided | github.com/boto/boto3 | Apache-2.0 | DynamoDB review adapter + S3 asset reads | SQLite review store (default) | IAM least privilege; public S3 access is **not** enabled |

---

## G. Rejected / not adopted

| Option | Why not |
|---|---|
| `scikit-image` direct use for tissue mask | TIAToolbox (BSD-3) is preferred first per the reuse-before-reimplementation rule; it wraps it anyway |
| Custom WSI binary parser | explicitly forbidden; OpenSlide covers 14 vendor formats |
| QuPath source | **GPL** — not copied into the product. Interoperability (coordinate export) only. Maintain license separation. |
| GPU cloud instances | cost rule; CPU + local execution suffices for this dataset scale |

---

## Governance rule

Any new third-party dependency **must** add a row to this file *in the same
commit that introduces it*, and must carry its license as read from upstream
metadata or the LICENSE file. `scripts/check_deps.py` fails CI when a
dependency present in `pyproject.toml` has no row here.