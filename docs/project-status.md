# Project status

**Repository maintenance baseline: 5 October 2026.** This is a maintained scope statement, not a live service-health monitor. Exact run evidence belongs in [docs/evidence](evidence/README.md); current Actions results are authoritative for a particular commit.

## Implemented in source
The core application includes H&E patch browsing, uncertainty-first ordering, three uncalibrated class scores, accept/correct/defer decisions, revision history, export, model-card limitations and qualified attribution. Enterprise extensions add project scope, capability-based roles, audit, registry and governance surfaces. Both interfaces have unit tests and production builds.

Repository infrastructure adds current guides, contributor/security policies, ownership and issue templates, portable commands, static-site tests, commit-pinned CI, Pages publication, reviewed dependency updates and opt-in MCP profiles. Manual workflows distinguish capability checks, frontend deployment and draft prereleases.

## What a clean clone proves
On the current rebased repository verification, **with the optional `model` extra installed** (`uv sync --locked --extra dev --extra wsi --extra model`): **228 backend tests passed with 5 environment-gated skips** (all "G4 bundle not present"), **17 tooling tests passed**, mypy and the blocking Ruff gate were clean, and both frontend production builds passed. Without that extra the torch-gated tests skip and the count is lower — a smaller number from a *different* environment, not a regression. Which optional runtimes a given machine actually has is recorded per-machine in [docs/evidence/runtime-capability.json](evidence/runtime-capability.json).

These are software results, not evidence of clinical model performance. New repository/site checks are reported in the dated maintenance evidence record and current CI.

## Attribution and the torch-free serve path
Contrastive Grad-CAM over the recovered head returns real 384×384 overlay PNGs once the `model` extra is installed; this was verified over HTTP, including that the same (image, pair) is byte-identical on a second call and that a different pair is not. The encoder weights are cached under `runtime-artifacts/models/torch-hub` so a demo run needs no network. A subprocess import hook (`test_serve_path_torch_free.py`) proves the ordinary review routes never resolve torch — the promise in [dependencies.md C1](dependencies.md) is measured, not assumed. A torch-free machine remains fully supported; attribution then degrades to an honest 503 rather than a fabricated heatmap.

## Unified authenticated surface
The enterprise app fronts the whole review surface at the G6-shaped `/v1/*` paths, reusing the existing project-scoped handlers rather than reimplementing them. Every route was exercised over real HTTP as all six demo personas against a COPY of the read model; see [docs/evidence/unified-surface.json](evidence/unified-surface.json). Tenant scope is enforced before the G6 handler runs, so an out-of-scope image is 404 on the pixel and attribution paths too — not just on the JSON detail route.

## Live inference on an imported slide
An uploaded patch or slide now runs a real forward pass through the recovered head `g4-behavioral-recovery-r1` and is stored in new `live_run` / `live_tile` tables. These are structurally separate from the frozen corpus: live rows carry `is_live_inference`, their own model identity, and DB-level CHECK constraints that make it impossible to record `baseline-frozen-g4` or the absent original bundle's hash on a live row. Nothing is written to `source_qc`, `prediction` or `review_event`; `osteopatch.integrity.corpus_row_digest` proves it by comparing the frozen tables row-by-row before and after a run.

Import and inference are gated by `live:analyze` (reviewer, pathologist, ml_engineer, admin); reading a result back is `live:read` (all six roles). The routes are in enterprise and delegate down into `osteopatch`, so the dependency direction is unchanged. Torch is imported lazily inside only the inference and attribution handlers; `test_serve_path_torch_free.py` enforces that and covers the new read paths.

The round trip was driven over real HTTP as all six personas against a COPY of the read model — 43 checks, see [docs/evidence/live-inference.json](evidence/live-inference.json). The canonical store was never opened for writing, and the frozen corpus came out byte-identical.

Honesty is enforced in the response, not just documented. Scores are labelled uncalibrated; a small top-two margin is reported as `confidence: low` or `indeterminate` with a plain-English caveat instead of a smoothed number; mpp, objective power and vendor are `null` when the file carries none and are never estimated; a slide past the tile cap reports `truncated: true` with both counts rather than silently dropping tiles. Grad-CAM remains attribution and is never presented as segmentation.

## The demo slide is not a pyramid
`scripts/make_demo_slide.py` assembles real corpus patches into a tiled TIFF and then re-opens it through the *same* reader the application uses, reporting what that reader actually returns. For the current artefact it reports **level_count = 1**, `mpp` null, `vendor` null: the file carries no vendor SVS/NDPI tags and no OME-XML, so it is not a pyramid as far as any reader can see. The script says so, records it in [docs/evidence/demo-slide.json](evidence/demo-slide.json), and `--require-pyramid` exits non-zero. It remains valid live-inference input — all 120 grid tiles were scored from it. A demo slide that is honestly single-level is a valid artefact; one that claims a pyramid it does not have is not.

## The unified app
`app/g7-enterprise/frontend` is the single app a user logs into. It reaches the Phase 1 `/v1/*` surface and the Phase 2 live routes, keeps the educational-prototype disclosure bar visible on every screen, and was exercised in a real browser against the running backend as both a writer and a reader-only persona: login, the deterministic 50-image gallery, opening an image with real H&E pixels and a real contrastive Grad-CAM overlay, importing a patch, importing a slide, and reading back a stored 120-tile run.

**How it is served.** The backend mounts the built `dist/` at `/` when it exists, so API and UI share one origin. That is deliberately preferred over a CORS allowlist: with a credentialed `X-File-Name` / `X-Project-Id` request on a 127.0.0.1 prototype, an origin allowlist is a real widening, and same-origin removes the decision entirely. When `dist/` is absent the mount is inert and the API behaves exactly as before; the Vite dev server proxies the same paths during development. An unknown API path still 404s rather than falling through to the SPA shell.

**How it refuses to overstate.** A large coloured class name reads as a conclusion regardless of the footnote below it, so an indeterminate result has no class name at all: the headline reads "Not determined", the tile is hatched, and the raw scores stay visible. The margin ribbon draws the 0.05 and 0.20 band edges so thresholds are visible rather than asserted. Missing input properties render as "not in file" — never 0, never blank, never estimated. Truncation always reports both counts. A role that cannot import is told why in words and gets no button that would 403, while reading every run stays open to all six personas.

The browser run wrote to a copy of the read model, never the canonical store. Frontend suite: 23 tests passed, plus the production TypeScript/Vite build.

## Operational and scientific prerequisites
| Area | Remaining boundary |
|---|---|
| Real-data reviewer | Requires a separately restored, hash-verified runtime bundle; Git does not include pixels/models/databases. |
| Original model | Original G4 binary is absent. A recovered head has a separate identity and does not restore original-model provenance or generalization claims. |
| Model reliability | Viable-tumor recall is 0.110345 in the frozen exploratory evaluation; no clinical use. |
| Torch stack | The `model` extra is ~1–2 GB and optional. It is not required to start or serve the app; only attribution and live inference load it. |
| Live inference scope | A live pass scores a fixed grid at one level. It is not a diagnostic read of a real case, it has no clinical validation, and the recovered head's known viable-tumor weakness applies to it unchanged. Uploaded files are written under `runtime-artifacts/` and are not de-identified for you — do not submit patient data. |
| Enterprise security | Local issuer/dev key and prototype governance are not production authentication or a security audit. |
| Existing AWS demo | Source and deployed revisions can differ. The protected `aws-demo` GitHub environment, reviewer gate and non-secret resource identifiers are configured; frontend deployment remains disabled (`AWS_DEPLOY_ENABLED=false`) and no OIDC role is configured. Workshop access/cost approval is still required before enabling it. |
| Public demo writes | Authentication, abuse controls, budget limits and backup/retention require review before wider exposure. Do not submit private information. |
| Demo seeding | `enterprise.seed`'s demo path re-scopes 50 real corpus rows so the gallery is populated. Idempotent, but it is a write to the G6 read model — do not run it against a store whose scope must stay as-is. |
| Uploaded files | Live imports are written under `runtime-artifacts/` and are not de-identified. Do not submit patient data through the demo. |
| MCP | Profiles are installed but disabled by default. Authentication and per-tool authorization must be performed in the client; no server connection is implied by a config file. |
| License | Proprietary declaration retained. Open-source dependencies do not make the project itself open source. |

## Release gate
A broader release needs verified runtime distribution rights, current artifact identities, appropriate access control, an explicitly approved cost plan, tested backup/restore and a documented threat review. Clinical-use expansion would require a separate scientific and regulatory program; it is not delivered by repository cleanup.
