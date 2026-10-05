# Contributing

Start with the [developer setup](docs/getting-started.md), [repository guide](docs/repository-guide.md) and [agent contract](AGENTS.md). This is an educational research prototype. Contributions must preserve its intended-use boundaries and inspectable evidence.

## A small, reviewable change
Create a focused branch from current `main`. Inspect existing work before editing; never discard another contributor's changes. Write a regression test for behavioral changes. Keep formatting-only work separate. Open a pull request describing the problem, approach, evidence, risks and rollback. Do not merge until the required `quality-gate` succeeds.

Use descriptive commits such as `fix: preserve review revision conflicts`, `docs: clarify runtime prerequisites` or `ci: pin maintained build actions`. Avoid generated noise, unexplained binaries and machine-local paths.

## Required checks
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
For each frontend, run `npm ci`, `npm test` and `npm run build` in its directory. Use `make lint` for the blocking Ruff scope. Intentional runtime-dependent skips must be explained, not hidden.

## Data, dependencies and safety
Do not commit patient data, secrets, model binaries, databases or the runtime image collection. Curated screenshots already approved for the public repository may be reused. New datasets, screenshots or scientific claims require provenance and license review. Keep dependency updates in reviewed PRs and update `docs/dependencies.md` when changing the declared Python dependency set.

Historical evaluations in `aidlc-docs/` are immutable records. Record a new evaluation separately rather than replacing old values. Corrections are append-only review events, never silent changes to predictions.

## Rights and security
The project currently retains a [proprietary license declaration](LICENSE); public visibility is not an open-source grant. Do not contribute material you cannot lawfully provide. Third-party licenses remain separate. See [SECURITY.md](SECURITY.md) for private reporting and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for participation expectations.
