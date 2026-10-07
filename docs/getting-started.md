# Getting started

## Choose the path
A clean clone can run software tests, build both React interfaces and publish the documentation website. It does **not** contain the 1,144-patch image collection, review database or model binaries. A working real-image reviewer requires an approved, verified runtime bundle. `prepare_runtime.py` locates and verifies existing files; it does not download or regenerate them.

Use Python 3.12, Node 24, Git and uv. The Python package supports 3.11–3.13; the standard development/CI baseline is 3.12. Installation downloads dependencies but does not create cloud resources. The runtime serves ordinary precomputed review requests without torch; optional model/WSI extras are separate.

## Install
From the repository root, in PowerShell, bash or zsh:

```sh
uv sync --locked --extra dev
npm --prefix app/g6/frontend ci
npm --prefix app/g7-enterprise/frontend ci
```

The `--locked` flag refuses implicit dependency changes. Do not use `uv lock --upgrade` or `npm audit fix --force` as setup steps. Optional engines should be installed deliberately:

```sh
uv sync --locked --extra dev --extra wsi
# Heavy; required only for model/attribution work:
uv sync --locked --extra dev --extra model
```

Running `uv sync` with a different extra set can remove previously selected extras; include all extras you intend to retain.

## Verify the clean checkout
```sh
uv run --locked pytest app/g6/backend/tests app/g7-enterprise/backend/tests -q
python -m unittest discover -s tests/tooling -v
python scripts/check_repository.py
python scripts/sync_requirements.py --check
python scripts/check_deps.py
uv run --locked mypy
npm --prefix app/g6/frontend test
npm --prefix app/g6/frontend run build
npm --prefix app/g7-enterprise/frontend test
npm --prefix app/g7-enterprise/frontend run build
```

`make lint` contains the deliberately scoped blocking Ruff command. `make test` combines backend, frontend and repository/tooling checks on systems with GNU Make. The commands above do not require Make.

A runtime-dependent skip is expected on a clean checkout and is not evidence that a model or real-data browser path passed. Record exact skip reasons from pytest. Review the [model-evidence guide](model-evidence.md) before interpreting any test count as scientific validation.

## Restore and verify runtime artifacts
Place an authorized runtime bundle in `runtime-artifacts/`. An external bundle can be selected explicitly:

```powershell
$env:OSTEOPATCH_RUNTIME_ARTIFACTS = 'D:\approved-data\osteopatch-runtime'
```

```sh
export OSTEOPATCH_RUNTIME_ARTIFACTS=/path/to/approved/osteopatch-runtime
```

Then run:

```sh
uv run --locked python scripts/prepare_runtime.py
```

Expected file paths and hashes are in [runtime-artifacts.expected.json](../app/g6/deploy/runtime-artifacts.expected.json). `--strict` additionally requires nonempty bulk image/thumbnail directories; it is not a new per-image validation of the full collection. Keep the canonical reference bundle unchanged. For experimentation, copy the database to a separate working location and set `OSTEOPATCH_DB` to that copy. Do not reassign an expected hash merely because a working review database changed.

The original G4 model binary is absent from the recovered project. A separate behaviorally recovered head may support qualified attribution; it is not a replacement with the original identity. Do not run new-image inference or reconstruction while claiming exact original-model reproducibility.

## Start the reviewer
In terminal 1:

```sh
uv run --locked uvicorn osteopatch.app:app --app-dir app/g6/backend --host 127.0.0.1 --port 8137
```

In terminal 2:

```sh
npm --prefix app/g6/frontend run dev
```

Open `http://127.0.0.1:5173`. Health: `http://127.0.0.1:8137/v1/health`. Stop each process with Ctrl+C. A responding health route alone does not prove the image/model artifacts are available; inspect its reported capabilities.

The optional root `.env.example` is a reference, not a loaded configuration. Copy it to ignored `.env` and explicitly add `--env-file .env` to the uvicorn command to load it. Never put credentials into a tracked file. Frontend Vite configuration is separate; `VITE_API_TARGET` selects a local proxy target and must not contain secrets.

## Run the local educational demo
From the repository root, run `make unified-app` (or `uv run --locked --extra dev --extra model --extra wsi python scripts/demo.py`). It installs the existing locked model and OpenSlide extras, verifies the local review data and required patch pixels, copies them into a disposable workspace, builds the frontend, and serves the UI and API from one origin. Open the printed URL and sign in as `reviewer@demo`. Press Ctrl+C to stop; rerunning the command creates a clean workspace without changing canonical data. Real inference is available only when local capability checks pass; verified recorded runs remain available when present.

Open **Images** and choose **Add image or slide** to import SVS, NDPI, TIFF, PNG, or JPEG files up to 512 MB. Open the thumbnail, zoom or pan, and draw an annotation or select an area to explore. Whole-slide analysis scores at most 16 areas. Download the original image, a region, annotations, or analysis; create an educational case report and export it as HTML or Markdown. Annotation observations stay in this browser session. **Sign out** is in the header. Other tissues and stains demonstrate software only and are outside the osteosarcoma model evidence.
Use `--port 8140` to reuse the same URL across restarts. When the verified bundle lives outside the checkout, add `--runtime-artifacts "C:\path\to\runtime-artifacts"`. Keep the command running during the demonstration; a closed server cannot accept sign-ins. Use **Sign out** to switch between the seeded demo roles.
## Real-data tests and enterprise extensions
`uv run --locked python app/local-tester.py` exercises real HTTP on an appropriately prepared host. `uv run --locked python scripts/e2e_ui.py` requires the verified runtime plus browser prerequisites and uses a disposable review database. Neither is implied by clean-clone CI. See [app/g7-enterprise/README.md](../app/g7-enterprise/README.md) for the extension's commands; its local identity provider is development-only, not production authentication.

## Website only
```sh
python scripts/build_site.py
python scripts/check_site.py
python -m http.server 8765 --bind 127.0.0.1 --directory _site
```

Open `http://127.0.0.1:8765`. No application/model runtime is needed.

## Troubleshooting
| Symptom | What to check |
|---|---|
| Runtime not found | Restore the authorized bundle or set the runtime-root environment variable. No automatic download exists. |
| Hash mismatch | Check the exact expected file and use an untouched reference bundle; do not bypass integrity checks. |
| Missing attribution | Inspect optional torch dependencies, recovered-head identity, image availability and the explicit limitation returned by the API. |
| Port already occupied | Stop only your own service or choose a free port and matching `VITE_API_TARGET`. Do not kill another worker's process. |
| Missing `uv` or `npm` | Install the tool through its official distribution, then reopen the terminal. Do not install global agent packages as a workaround. |
| AWS authentication fails | Follow the deployment runbook; local software verification remains independent of AWS. |
