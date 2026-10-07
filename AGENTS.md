# OsteoPatch Review — contributor and agent contract

## Read first
1. `README.md` and `docs/README.md` describe the current product and repository.
2. [`docs/agent-handoff.md`](docs/agent-handoff.md) is the current detailed setup, workflow, test and safety guide for a new coding agent.
3. [`docs/data-inventory.md`](docs/data-inventory.md) records the source cohort, model identities, evaluation, tracked evidence and host-local artifacts. [`docs/evidence/demo-readiness.md`](docs/evidence/demo-readiness.md) records the latest end-to-end demo verification.
4. `docs/project-status.md` is an earlier maintained scope statement; `PROJECT_BRIEF.md` defines intended use; `aidlc-docs/` preserves stage-specific historical evidence.

This is an implemented educational/research prototype, not an Inception-only scaffold and not a clinical device. Do not restart the original workshop plan or treat historical approval questions as current instructions.

## Working rules
- Inspect the branch, status, relevant source and existing tests before changing anything. Preserve other workers' uncommitted work; use a separate branch/checkout when necessary.
- Keep code in `app/g6` and `app/g7-enterprise`. Their names are compatibility paths, not permission to duplicate domain logic. Enterprise delegates review operations to `osteopatch`.
- `pyproject.toml` + `uv.lock` are authoritative for Python; component `package-lock.json` files govern JavaScript. Keep generated requirements shims synchronized.
- No paid APIs, cloud resource creation, training, account switching, global MCP installation or broad cleanup without specific authorization. Never print credentials.
- No fabricated test results, predictions, heatmaps, patient identifiers or performance claims. A configured workflow is not an executed deployment.
- Do not change the license, erase history, force-push shared branches, delete PRs or rewrite frozen research records as housekeeping.

## Scientific and review invariants
Exactly three outputs, in order: `NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`. Mixed, uncertain, deferred and poor-quality are review/QC states, not learned classes. Unknown source labels must fail rather than be guessed.

Source labels, immutable predictions and append-only reviewer events are separate. Human correction never silently retrains a model. Scores are uncalibrated class scores, not disease probabilities. Review priority is not clinical urgency. Grad-CAM is not segmentation, a diagnosis or a causal explanation.

The original `baseline-frozen-g4` binary is absent. The `g4-behavioral-recovery-r1` head has its own identity and cannot inherit the original hash or evaluation claims. Preserve hashes, data splits and the explicit viable-tumor weakness. Read `docs/model-evidence.md` before model-related changes.

## Verification from repository root
```sh
uv sync --locked --extra dev
uv run --locked pytest app/g6/backend/tests app/g7-enterprise/backend/tests -q
python -m unittest discover -s tests/tooling -v
python scripts/check_repository.py
python scripts/build_site.py
python scripts/check_site.py
python scripts/sync_requirements.py --check
python scripts/check_deps.py
uv run --locked mypy
```
Run `npm ci`, `npm test`, `npm run build` in each changed frontend. `make lint` names the deliberately scoped blocking Ruff gate. Real-image/browser attribution checks need verified, gitignored runtime artifacts; a clean-clone skip is not a model-validation pass.

## Publication and handoff
Pages contains only the allowlisted static website, never the app backend, credentials, databases or full image collection. AWS deploys are manual, protected and disabled until the required configuration is available. MCP profiles are opt-in with no blanket auto-approval.

The current unified local demo is launched by `scripts/demo.py` (`make unified-app` when GNU Make is available). It is the supported full-demo path: it snapshots the review database into a disposable workspace, verifies the demo pixels and recorded-run artifacts, starts the authenticated API and built G7 UI on one localhost origin, and removes the workspace on exit. Do not run demo seeding against the source database; it changes project scope. A fresh Git clone does not include `runtime-artifacts/`; restore an authorized bundle locally and follow `docs/agent-handoff.md`.

Report exact changed paths, commands/results, skipped tests, commit/PR and remaining operational gaps. Keep durable run evidence in `docs/evidence/`. Never describe this project as production-ready or clinically validated on the strength of software tests.
