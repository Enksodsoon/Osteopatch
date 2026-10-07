# AI agent handoff: current app and local demo

**Current as of 7 October 2026.** This is the operating guide for an agent opening the implemented OsteoPatch repository. It supersedes the pre-implementation workflow in `README_START_HERE.md` for day-to-day work. Read [AGENTS.md](../AGENTS.md) first; it is the policy contract.

## What this project is

OsteoPatch Review is a local educational and research prototype for browsing osteosarcoma H&E patches, comparing source labels with frozen model predictions, learning from uncertainty, recording reviewer decisions and exporting educational case reports. The demonstration also accepts local patch/WSI files and can run a bounded recovered-model inference when verified local runtime capability allows it.

It is not a diagnostic tool and does not support treatment decisions, treatment-response prediction, prognosis or clinical reporting. The three outputs are exactly `NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`. Mixed, uncertain, deferred and poor-quality are review or quality states. Model scores are uncalibrated class scores, never probabilities. Attribution is not segmentation, proof of cause or a diagnosis.

The repository is implemented. Do not restart the historical Inception or AI-DLC proposal as if this were a blank scaffold. The current full-demo entry point is `scripts/demo.py`; `make unified-app` wraps it for hosts with GNU Make.

## Start with these sources

Use this order when investigating a claim or changing behavior:

1. `AGENTS.md` for constraints, ownership, safety and verification rules.
2. This guide and [data-inventory.md](data-inventory.md) for current architecture, demo workflow and data provenance.
3. Source code and tests in `app/g6` and `app/g7-enterprise` for behavior.
4. [demo-readiness.md](evidence/demo-readiness.md) for the latest dated full-stack and browser run on the implementation host.
5. [model-evidence.md](model-evidence.md) and the frozen records under `aidlc-docs/` for scientific evidence.

`docs/project-status.md` is a 5 October 2026 maintained snapshot; the README's headline verification table is dated 6 October. The 7 October demo-readiness record is newer. `README_START_HERE.md`, the numbered planning documents and portions of `app/g7-enterprise/README.md` preserve older implementation stages. Read their historical notes, but follow this guide for the current demo.

## Application map

| Area | Source | Responsibility |
|---|---|---|
| Unified learner/reviewer UI | `app/g7-enterprise/frontend` | Sign-in, review set, slide library/viewer, reports, learning guide, dark/light appearance and responsive controls |
| Unified auth/API | `app/g7-enterprise/backend/enterprise` | Local demo identity, project membership, roles, API authorization, audit and the authenticated `/v1/*` surface |
| Shared review API and domain | `app/g6/backend/osteopatch` | Source/QC metadata, immutable predictions, patch pixels, review events, exports, model limitations and attribution |
| Original G6 UI | `app/g6/frontend` | Earlier review UI; remains supported and tested, but is not the unified demo frontend |
| Local demo launcher | `scripts/demo.py` | Verifies and copies runtime inputs, builds G7, starts one-origin API/UI, runs preflight, then cleans its temporary workspace on exit |
| Runtime inventory and verification | `scripts/prepare_runtime.py`, `scripts/runtime_capability.py`, `app/g6/deploy/runtime-artifacts.expected.json` | Reports available artifacts/capabilities and pins artifacts used by the older bake/deploy path; see the data inventory before interpreting a mismatch |
| Current and historical records | `docs/`, `docs/evidence/`, `aidlc-docs/` | Current guides, dated software evidence, dataset provenance, frozen evaluations and historical workflow records |

The G6/G7 names are compatibility paths. G7 delegates review operations to the G6 domain and API; do not create a second implementation of predictions or reviews.

## Full demo workflow

The intended teaching journey is:

1. Sign in with one of the local seeded personas. `reviewer@demo` is the default walkthrough account. Sign out to switch personas. This is a deterministic local identity stub, not an external identity provider and not a password-bearing production login.
2. Search, filter, sort and page the deterministic 50-patch teaching scope. Open a patch, inspect its thumbnail/full image and source/QC context, and move between patches.
3. Make an optional learner self-check before revealing prediction scores and attribution. The learner's choice stays in browser session state; it does not create a reviewer event or change the model. Agreement is described as agreement, not as a correct answer.
4. Compare the source label, immutable prediction, three uncalibrated scores and score margin. Accept, correct or defer as a reviewer. Review events are append-only; correction never overwrites the source label or prediction and never trains a model.
5. Open **Images** to add a local image or slide (SVS, NDPI, TIFF, PNG or JPEG, up to 512 MB), view it with zoom/pan/fit, make practice annotations and inspect an area. Annotations remain browser-session observations and can be exported. Original pixels remain unchanged.
6. Optionally request real inference when role and verified runtime capability permit it. A slide scan is bounded to at most 16 tiles/areas; the result is not a whole-slide diagnostic read. Otherwise, open a verified **Recorded demo** run. Replay reads the original saved result and artifacts; it runs no inference and invents no progress. The original time, model identity and provenance remain attached.
7. Inspect score separation and model/run evidence. Attribution may be unavailable if its dependencies, pixels or model are unavailable; the UI reports that state rather than synthesizing a heatmap. Class-map overlays are not attention maps or segmentation masks.
8. Create a case report by selecting images/results, writing observations in the rich-text editor, and optionally signing as the authenticated reviewer. Saved reports can be reopened and revised as new saved revisions. Exports include HTML or Markdown with the selected analyzed image attached when available. CSV/JSON export remains available for the review set.
9. Read the **Learn** guide for the three model classes, source-label versus prediction distinction, score margin, uncertainty, human review and attribution limits. Its disease-study sections and visual material are for education and link to their sources.

Role checks remain server-side. The live-analysis capability is granted to reviewer, pathologist, ML engineer and admin roles; live-result reading is available to all six seeded personas. Student and auditor workflows are read-only. Other mutation permissions are determined by the route-level role and current project membership checks; do not infer them from hidden or disabled UI controls.

## Install and launch on a new agent host

Use Python 3.11–3.13 (the checked baseline is 3.12), `uv`, Node.js/npm and Git. The Python lock and each frontend's npm lockfile are authoritative. From the repository root, install the demo dependencies and the unified frontend:

```powershell
uv sync --locked --extra dev --extra model --extra wsi
npm.cmd --prefix app/g7-enterprise/frontend ci
```

On bash/zsh, use `npm` instead of `npm.cmd`. On this implementation host, the populated and gitignored source bundle is `runtime-artifacts/`; the repository-root launcher selects it by default. Start the app with the same command on Windows, macOS or Linux:

```powershell
uv run --locked --extra dev --extra model --extra wsi python scripts/demo.py --runtime-artifacts runtime-artifacts --port 8140
```

The launcher rebuilds the frontend, snapshots the database into a disposable temporary directory, verifies the 50 required TIFF/thumbnail pairs, checks replay source hashes and PNGs, starts the API on `127.0.0.1`, exercises health/login/gallery/media/replay preflight, verifies the source database did not change, and prints the URL. Keep that process running while presenting. Open the printed URL and sign in as `reviewer@demo`. Press Ctrl+C to stop; run the same command again for a clean workspace. Use `--port 0` if 8140 is occupied. The port printed by the launcher is the actual URL.

For a clean Git clone, `runtime-artifacts/` will be absent because it is intentionally ignored and too large/provenance-sensitive to publish. Restore an authorized verified bundle outside Git, then pass it explicitly:

```powershell
$env:OSTEOPATCH_RUNTIME_ARTIFACTS = 'D:\approved-data\osteopatch-runtime'
uv run --locked --extra dev --extra model --extra wsi python scripts/demo.py --runtime-artifacts $env:OSTEOPATCH_RUNTIME_ARTIFACTS --port 8140
```

`scripts/prepare_runtime.py` is a separate exact-hash verifier for the pinned runtime manifest used by existing bake/deployment paths; it does not download data. The local demo launcher has its own copied-database and selected-artifact preflight. If a local database differs from the older pinned manifest, do not regenerate a pin to silence the mismatch: identify which runtime path is being checked and preserve the frozen evidence. See [data-inventory.md](data-inventory.md).

## Verification commands

The latest executed counts and environment skips are recorded in [demo-readiness.md](evidence/demo-readiness.md). To repeat the main software gates:

```powershell
uv run --locked --extra dev --extra model --extra wsi pytest app/g6/backend/tests app/g7-enterprise/backend/tests tests/tooling -q -rs
npm.cmd --prefix app/g6/frontend test -- --run
npm.cmd --prefix app/g6/frontend run build
npm.cmd --prefix app/g7-enterprise/frontend test -- --run
npm.cmd --prefix app/g7-enterprise/frontend run build
python scripts/check_repository.py
python scripts/sync_requirements.py --check
python scripts/check_deps.py
uv run --locked mypy
```

On a full runtime host, the current browser journey can be run against the active local URL using the commands in `docs/evidence/demo-readiness.md`. Those journeys write to disposable copies, not the source bundle. Run `python scripts/e2e_ui.py` only with its documented disposable runtime setup. Do not call `enterprise.seed` with a nonzero `scope_size` against a source/canonical database: it mutates project scope in the G6 read model.

## Agent workflow and boundaries

- Start with `git status -sb`, the current branch, and relevant tests. Keep the original project copies and other workers' edits intact.
- Read `docs/model-evidence.md` before touching labels, scores, data splits or model presentation. Source labels, immutable predictions, recovered-model inference and append-only review events are four distinct evidence layers.
- Preserve class order and identity hashes. The original `baseline-frozen-g4` binary is absent; `g4-behavioral-recovery-r1` is a distinct recovered head. Never attach the old model hash or evaluation result to the recovered head.
- Keep WSI uploads local and use only de-identified educational material. The uploaded slide is not automatically de-identified. Do not commit user scans, image collections, runtime databases, model weights, local logs, credentials or MCP configuration.
- Keep scientific claims grounded in `aidlc-docs/inception/model/g4/` and `docs/model-evidence.md`. Software tests establish software behavior, not clinical validity or model accuracy.
- Keep GitHub Pages, the historical workshop deployment and this local app distinct. A green CI run or a working localhost app does not deploy or qualify the cloud service.
- Make focused changes in existing React/CSS and Python code; the completed UI uses installed dependencies and native SVG/CSS. Do not add a component library without a concrete need.

For artifact counts, data lineage, evaluation denominators and local-versus-clone availability, see [data-inventory.md](data-inventory.md). For the canonical class and evidence caveats, see [model-evidence.md](model-evidence.md).
