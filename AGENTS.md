# OsteoPatch Review — contributor and agent contract

## Read first
1. `README.md` and `docs/README.md` describe the current product and repository.
2. `docs/project-status.md` separates implemented features from operational gaps.
3. `PROJECT_BRIEF.md` defines intended use; `aidlc-docs/` preserves historical evidence.

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

Report exact changed paths, commands/results, skipped tests, commit/PR and remaining operational gaps. Keep durable run evidence in `docs/evidence/`. Never describe this project as production-ready or clinically validated on the strength of software tests.
