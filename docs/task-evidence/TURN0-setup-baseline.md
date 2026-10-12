# Turn 0 — prompt-pack execution setup and re-measured baseline

**Generated:** 2026-10-05 · **Branch:** `feat/prompt-pack-run` · **HEAD:** `626aaadc9e4282b470b74fe94893a412cf7d127a`

> **Educational research prototype only. Not for diagnosis, treatment decisions, or predicting
> treatment response.** Model scores are uncalibrated class scores, never disease probabilities.

This is the setup record for prompt-pack execution, not a product change. Every number below was
measured in the dedicated worktree during this turn. No count is carried over from the README or
from F001 without being re-run here.

---

## 1. Baseline reconciliation

The plan this turn executes named `b40bf34` as the baseline. That was wrong, and using it would
have discarded five commits — including F001's own evidence. The verified refs were:

| Ref | SHA before this turn | Note |
|---|---|---|
| local `main` | `b40bf34` | clean, **5 commits behind `origin/main`** |
| `origin/main` | `626aaad` | 3 x `professionalize repository platform` + F001 evidence |
| `task/F001` | `ac489b1` | worktree `wt/F001`, clean; 1 receipt line beyond `origin/main` |

Actions taken, in order:

1. `git fetch origin` → confirmed `origin/main` = `626aaad`.
2. `git merge --ff-only origin/main` on the primary checkout → `b40bf34..626aaad`, exit 0,
   clean fast-forward. **No reset was performed at any point**, and the pack's stale reference
   snapshot `57c1efc` was never checked out.
3. `git worktree add ../wt/pack -b feat/prompt-pack-run 626aaad` → exit 0, branch at `626aaad`,
   clean.
4. `task/F001` @ `ac489b1` was **left untouched** — not deleted, not merged, not modified.

Local `main` is now `626aaad`; the primary checkout is no longer stale.

## 2. The prompt pack is now versioned

The 129-task pack lived only on the owner's Desktop, outside git — one reset from being lost. It
is vendored at `aidlc-docs/prompt-pack/` (151 files, including all 129 task files).

`scripts/verify_prompt_pack.py` proves the vendored copy is byte-identical to the authored pack by
recomputing every digest in the pack's own `SHA256_MANIFEST.json`:

```
OK: 150/150 prompt-pack files match SHA256_MANIFEST.json   (exit 0)
```

The vendored `TASK_MANIFEST.json` is deliberately **not** edited to mark F001 complete: its
digests are covered by that manifest, so editing it would break the integrity check above. Task
status lives in `docs/task-evidence/STATUS.md` instead.

## 3. Environment

`scripts/task_env.sh` is the single source of the task environment. Sourcing it prints what it
resolved:

| Setting | Value |
|---|---|
| `OSTEOPATCH_RUNTIME_ARTIFACTS` | primary checkout `runtime-artifacts/` — **read-only assets** |
| `OSTEOPATCH_DB` | `wt/pack/scratch/throwaway-db/throwaway.sqlite3` — **throwaway, writable** |
| `OSTEOPATCH_SCRATCH` | `wt/pack/scratch/task` (rebuildable caches stay inside the worktree) |

The canonical store is never opened for writing. A fresh worktree carries none of the gitignored
runtime data, so the script fails closed rather than letting a task run against missing pixels.

`scratch/` was added to `.gitignore`; the throwaway database and its WAL/SHM siblings are
regenerable scratch state, never source artifacts.

### Defect found and fixed: runners ignored the artifact override

The first smoke run **failed, exit 2**:

```
FATAL: canonical review store not found:
       .../wt/pack/runtime-artifacts/db/osteopatch_g6.sqlite3
```

Root cause: `app/local-tester.py` and `scripts/e2e_ui.py` both hardcoded
`RUNTIME = REPO / "runtime-artifacts"` and ignored `OSTEOPATCH_RUNTIME_ARTIFACTS`, so neither
runner could work in any checkout that does not own the gitignored runtime data.
`osteopatch.config` already resolved this env var first; the two runners simply never adopted it.

Both now resolve `OSTEOPATCH_RUNTIME_ARTIFACTS` first and fall back to the repo default. The
fallback was verified explicitly, so the primary checkout's behaviour is unchanged:

| Invocation | Resolved `CANON_DB` | Exists |
|---|---|---|
| no env var | `wt/pack/runtime-artifacts/db/...` | `False` (repo default, as before) |
| env var set | `OsteoPatch_Kiro_Handoff/runtime-artifacts/db/...` | `True` |

## 4. Measured verification results

All runs are in `wt/pack` on `feat/prompt-pack-run` @ `626aaad`.

| # | Command | Exit | Result |
|---|---|:--:|---|
| 1 | `uv sync --locked --extra dev` | **0** | Python 3.12.10, torch-free confirmed |
| 2 | `npm ci` (G6 frontend) | **0** | lockfile-exact |
| 3 | `npm ci` (enterprise frontend) | **0** | lockfile-exact |
| 4 | `scripts/verify_prompt_pack.py` | **0** | 150/150 files match |
| 5 | `scripts/prepare_runtime.py` | **0** | db, recovered model, g8 subset OK; images 1144, thumbnails 1144 |
| 6 | `pytest app/g6/backend/tests -q -rs` | **0** | **84 passed, 10 skipped** |
| 7 | `pytest app/g7-enterprise/backend/tests -q -rs` | **0** | **28 passed, 1 skipped** |
| 8 | `pytest tests/tooling -q -rs` | **0** | **16 passed, 1 skipped** |
| 9 | `unittest discover -s tests/tooling` (CI runner) | **0** | Ran 17 tests, OK (skipped=1) |
| 10 | `ruff check` (CI blocking set) | **0** | All checks passed |
| 11 | `mypy` | **0** | no issues in 19 source files |
| 12 | `scripts/check_repository.py` | **0** | 0 error(s) |
| 13 | `scripts/build_site.py` then `check_site.py` | **0** | 0 site errors (order matters) |
| 14 | `scripts/check_deps.py` | **0** | 17 declared dependencies have register rows |
| 15 | `scripts/sync_requirements.py --check` | **0** | shims current |
| 16 | `npm test` (G6) | **0** | **29 passed** |
| 17 | `npm run build` (G6) | **0** | 0 TypeScript errors |
| 18 | `npm test` (enterprise) | **0** | **2 passed** |
| 19 | `npm run build` (enterprise) | **0** | 0 TypeScript errors |
| 20 | `app/local-tester.py` — **before** the runner fix | **2** | **FAIL** — artifact root not honoured |
| 21 | `app/local-tester.py` — **after** the runner fix | **0** | **104/104** over real HTTP |
| 22 | `scripts/e2e_ui.py` | **0** | **17/17** specs, real Chromium 153.0.8010.12 |
| 23 | `pytest app/g6/backend/tests/test_e2e_workspace_cleanup.py` (post-fix regression) | **0** | 2 passed |
| 24 | `pytest app/g6/backend/tests` (post-fix regression) | **0** | 84 passed, 10 skipped |

**Totals:** backend **112 passed / 11 skipped / 0 failed** (G6 84 + enterprise 28); tooling
**16 passed / 1 skipped**; frontend **31 passed** (29 + 2); browser **17 passed**; smoke
**104/104**.

### Agreement with the README

`README.md` "Repository verification snapshot" claims backend 112 passed / 11 skips, G6 UI 29
tests, enterprise UI 2 tests, and 1,144 patches. **Every one of those numbers matches what was
measured here.** The README was made stale-and-correct by the professionalization commits at
`626aaad`; no edit was required and none was made.

The snapshot does not mention the tooling suite (16), the smoke run (104/104), or the browser
suite (17). Those are recorded here instead of being written into the README uninvited.

## 5. Canonical data immutability

`runtime-artifacts/db/osteopatch_g6.sqlite3` was hashed before the first gate and after every
write-bearing gate:

| Point | SHA-256 |
|---|---|
| baseline | `0e4524db91f7a6e22dfbdc3395cf0fce6b7bf1b5628ac4cd1198be291d01ac40` |
| after `prepare_runtime.py` | identical |
| after smoke (both runs) | identical |
| after browser E2E | identical |
| final | identical |

Both runners independently printed `canonical review store is byte-identical after the run`.
No pixel, thumbnail, or model binary was written.

## 6. What was NOT verified, and why

| Check | State | Reason |
|---|---|---|
| Real Grad-CAM heatmaps | **NOT_RUN** | `torch` absent from the locked serve venv; installing it is unauthorized. Only the honest-refusal path is exercised. |
| Anything needing the original G4 weights | **NOT_RUN** | `original frozen G4 bundle present: False` — that file is absent from disk. |
| Real whole-slide reading | **NOT_RUN** | `openslide 1.4.3` imports, but no real slide with coordinates is in scope. |
| CloudFront deployment is live | **UNVERIFIED** | no AWS credentials present or used, and none were sought. Nothing asserted either way. |
| GitHub Actions on this SHA | **NOT_RUN** | no push/PR authorization; the workflow was read, not executed. |
| Windows-symlink site case | **SKIPPED** | `Creating symlinks is not permitted on this host`. |

## 7. Changed files

| Path | Why |
|---|---|
| `scripts/task_env.sh` | New. Single source of the task environment: read-only artifact root, throwaway writable database, worktree-local caches. Fails closed when no artifact root is found. |
| `scripts/verify_prompt_pack.py` | New. Proves the vendored pack is byte-identical to its authored manifest, so the roadmap cannot silently drift or be lost. |
| `app/local-tester.py` | 9 lines. Honour `OSTEOPATCH_RUNTIME_ARTIFACTS` before the repo default. Without this the smoke gate cannot run outside the checkout that owns the gitignored artifacts. |
| `scripts/e2e_ui.py` | 9 lines. Same defect, same fix. |
| `.gitignore` | 4 lines. Ignore `scratch/` — throwaway integration databases and per-task caches. |
| `aidlc-docs/prompt-pack/` | New. The vendored 129-task roadmap (151 files, integrity-verified). |

**No product code changed.** No model, label, prediction, or review event was altered.
