# F001 — Real baseline inventory

**Task:** F001 · **Kind:** audit · **Branch:** `task/F001`
**Audited baseline:** `44fed1d72b5ab5c65c872b438caf8386b121d078` (first measured at `b40bf34e…`; see below)
**Re-measured:** 2026-10-05, 09:02–09:10 UTC · **Product code changed:** none.
**Machine-readable companion:** [`F001-baseline.json`](F001-baseline.json) · **Receipt:** [`F001-receipt.json`](F001-receipt.json)

> **The baseline moved during this audit.** `origin/main` advanced three commits from another
> worker (repository professionalization) after the first pass. That merge changed the tracked
> file count, the `Makefile` targets, the CI workflow list and added repository/site gates.
> `origin/main` was **merged** into this branch (not rebased, no force-push) and **every gate
> below was re-run at the new HEAD**. Nothing is carried over from `b40bf34e` unmeasured.

> **Educational / research prototype only. Not for diagnosis, treatment decisions, or predicting treatment response.**

This is an evidence document, not a product API. Every number below was measured in this
session on this machine. Nothing is copied from `README.md`, from `docs/current-state-audit.md`,
or from the committed `docs/evidence/*.json`, all of which are earlier runs.

---

## 1. Identity and isolation

| Fact | Value |
|---|---|
| Audited checkout | `../wt/F001` (dedicated worktree) |
| Primary checkout | `../OsteoPatch_Kiro_Handoff` on `main`, left untouched |
| Branch / HEAD | `task/F001` @ `912eb25` (F001 evidence commit `19bd5e0` + merge of `origin/main`) |
| Audited baseline | `44fed1d72b5ab5c65c872b438caf8386b121d078` |
| `origin/main` at audit time | `44fed1d…`; F001 was subsequently merged as `a4a976d` |
| Remote | `https://github.com/Enksodsoon/Osteopatch.git` |
| Tracked files | 323 |

The repository was identified from `.git/config`, not from the folder name. The prompt pack
names `Enksodsoon/osteopatch-review`; that repository was **renamed** to `Osteopatch` and the old
URL redirects.

The task pack itself was verified before use: **all 150 files listed in its `SHA256_MANIFEST.json`
recompute to the recorded digest — 0 mismatched, 0 missing.** It was treated as read-only and was
never modified.

### The pack's premise is stale, and that is why F001 exists

The pack declares baseline `57c1efc`, which is now **8 commits behind `main`**. Its
`PACK_VALIDATION.json` and task files describe a partly-built repository; the real one already has
a `Makefile` with 18 targets, a locked `uv.lock`, a `.venv`, six CI workflows, two FastAPI apps,
four test suites and a documentation site. **0 of its 129 tasks had ever been executed here** —
`docs/task-evidence/` did not exist before this task.

---

## 2. Working-tree state (acceptance check F001-AT01)

`git status --porcelain` was captured before any work and again after every gate:

| Tree | Before | After |
|---|---|---|
| `wt/F001` (`task/F001`) | empty | empty except the three task-owned evidence files |
| `OsteoPatch_Kiro_Handoff` (`main`) | empty | empty |

The gates that write anything (`npm run build`, smoke, browser E2E) write only gitignored output or
a temp directory. Both smoke and E2E were pointed at a **temp** `--out` path so that even the
committed `docs/evidence/*.json` files were not rewritten by this audit.

---

## 3. Concurrent workers and pre-existing branches

`git worktree list` showed only the primary checkout before this task; there is no second task
branch and no other worktree. Two listeners pre-date this task and were **left running**:

| Port | Bind | PID | Role | Action |
|---|---|---|---|---|
| 8137 | 127.0.0.1 | 44564 | G6 review API (uvicorn) | left running |
| 5173 | 127.0.0.1 | 14196 | Vite dev server | left running; observed read-only in a browser |
| 18080 | 0.0.0.0 | 26152 | unidentified | recorded only |

Two local branches carry commits **not** on `main`. Per the agreed scope they were compared with
`log`, `diff --stat` and `git cherry` only. **No merge, rebase, cherry-pick or delete was performed.**

| Branch | SHA | Ahead | Touches | Comparison with `main` |
|---|---|---|---|---|
| `feat/professional-ui-readme` | `1065d2d` | 2 | `scripts/e2e_ui.py`, `docs/evidence/e2e-ui-result.json` | `main` contains the same functional fix (`remove_workspace(attempts=5)` with the `onerror=_unlock` retry, `spawn()` returning log handles) **plus** `--browser edge`, per-engine evidence paths and `browser_version()` recording that the branch lacks. `git cherry` marks both commits `+` only because `main` later rewrote the same lines. |
| `backup/post-merge-evidence` | `037ce60` | 2 | `docs/evidence/e2e-ui-result.json` only | The branch's evidence is **older** (`03:50:00Z` vs `main`'s `04:02:33Z`) and lacks the `browser` / `browser_version` fields. `main`'s copy is strictly more informative. |

`feat/unified-platform-p0` (`5479248`) and `feat/enterprise-e1-e6` (`75c98fd`) are fully contained in
`main` — `git log main..<branch>` is empty for both.

**This is a comparison, not a verdict.** Deciding whether those branches should be kept or deleted is
the integrator's call.

---

## 4. Code inventory

323 tracked files: `app` 112 · `aidlc-docs` 104 · `docs` 35 · `.github` 14 · `scripts` 11 ·
`site` 9 · `prompts` 9 · `templates` 6 · `tests` 2 · `.kiro` 2 · `config` 1 · root files 28.

Repository tooling added by the newer `main`: `scripts/check_repository.py`,
`scripts/build_site.py`, `scripts/check_site.py`, `tests/tooling/` (2 files) and `site/pages/`
(5 HTML pages).

- **G6 review API — 13 routes**, all under `/v1/`: `health`, `meta`, `model-card`, `images`,
  `images/{id}`, `full`, `thumbnail`, `review`, `reviews`, `attribution`, `attribution/meta`,
  `predictions/{prediction_id}`, `exports/reviews`.
- **Enterprise layer — 23 routes**, 16 modules (identity, RBAC, registry, governance, drift,
  audit chain, ingestion, inference).
- **Migrations:** `0001_initial.sql`, `0002_project_scope.sql` — two, both recorded in
  `schema_migrations`.
- **G6 frontend:** 7 components (`Workbench`, `PatchReview`, `ImageViewer`, `AttributionPanel`,
  `ModelCard`, `ReviewPanel`, `Shared`); 29 vitest tests; 17 Playwright browser specs.
- **Entry points:** `Makefile` (setup, test, test-backend, test-enterprise, test-frontend,
  test-tooling, repo-check, lint, typecheck, runtime, bake, verify-bake, smoke, serve, docs,
  docs-check, docs-serve), `scripts/prepare_runtime.py`, `app/local-tester.py`,
  `scripts/e2e_ui.py`, `scripts/build_site.py`, `scripts/check_repository.py`,
  `scripts/check_site.py`, and six workflows under `.github/workflows/`.

### Two commands that must be invoked in the right place

These are properties of an isolated checkout, not defects — both were verified to pass once
invoked correctly:

- `verify_bake.py` must run where `app/g6/deploy/_bake` exists. That directory is gitignored and
  therefore **absent from a fresh worktree**; run there it reports all three artifacts missing.
  In the primary checkout it verifies 3/3.
- `check_site.py` must run **after** `build_site.py` — the order CI and `make docs` use. Run
  alone it reports 12 false "missing published file" errors. In order: 0 errors.

### The four load-bearing defects from the earlier audit are addressed on `main`

The 5 October `docs/current-state-audit.md` recorded defects D1–D4 against an older SHA. Inspected
on `main` today:

| Defect | State on `main` | Evidence |
|---|---|---|
| D1 worker preprocessing contradicted the frozen `[384, 384]` contract | **addressed** | `cpu_worker.py` reads the bundle's own preprocessing spec and refuses to guess when neither bundle nor caller supplies one |
| D2 a second, divergent `prediction_id` scheme | **addressed** | `cpu_worker.py:226` calls the canonical `repo.prediction_id_for(image_id, hash)` |
| D3 tenancy by process-global mutation | **addressed** | `osteopatch/projects.py` replaces it; migration `0002` adds `project_id`; `prediction.project_id` has **0 NULL rows** |
| D4 hardcoded dead machine-specific scratch paths under the user home directory (path redacted under F001-AT05) | **addressed** | `config.py` resolves through `OSTEOPATCH_*` env vars, then repo/`runtime-artifacts`, then `app/`-relative |

`docs/current-state-audit.md` is **not** edited by this task; it is prior art pinned at its own SHA.

---

## 5. Frozen artifacts

| Artifact | SHA-256 | State |
|---|---|---|
| Canonical database `db/osteopatch_g6.sqlite3` | `0e4524db91f7a6e22dfbdc3395cf0fce6b7bf1b5628ac4cd1198be291d01ac40` | **verified** against the committed manifest |
| Original frozen bundle `baseline-frozen-g4` | `01727fb8…df63` | **ABSENT FROM DISK** — a checked absence, not unknown |
| Recovered attribution head `g4-behavioral-recovery-r1` | `ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73` | **verified**, 21,785 bytes, separately identified |
| G8 demo subset `recovery/g8-subset-image-ids.json` | `78ecd2f703913cef8d3c5f298489f741cc96f9d99a8a9c526290ec85c6ef005f` | **verified**, 50 unique image ids |

`scripts/prepare_runtime.py` printed `original frozen G4 bundle present: False` and then verified
the database, the recovered head, the subset, 1,144 images and 1,144 thumbnails — exit 0.
`app/g6/deploy/verify_bake.py` re-verified all three baked artifacts — exit 0.

The absence is recorded as **absent**, distinct from unknown, and the original hash is never
reassigned to the recovered head.

Read-only SQLite inspection (`file:…?mode=ro`) of the canonical database:

- `source_qc` 1,144 · `prediction` 1,144 · `review_event` **0** · `schema_migrations` 2
- all 1,144 predictions carry `model_bundle_hash = 01727fb8…`, `model_version = baseline-frozen-g4`
- predicted classes: NON_TUMOR 510 · VIABLE_TUMOR 330 · NECROSIS 304
- `prediction.project_id`: **0 NULL rows**
- source groups are `Case-3`, `Case-4`, `Case-48`, `P9` — **case/slide groups**, with no patient
  identity implied anywhere

Runtime root is 433 MB and gitignored by policy: a durable runtime dependency, never committed.

---

## 6. Verification results

Interpreter, environment and working directories: Python gates ran with the **primary checkout's
locked `.venv`** and `cwd` = the F001 worktree, so `pyproject.toml`'s `pythonpath` imported the
worktree's `osteopatch` package. `OSTEOPATCH_RUNTIME_ARTIFACTS` pointed at the primary checkout's
artifacts, read-only. Node gates ran in the primary checkout because a fresh worktree has no
`node_modules` and `npm ci` is an unauthorized install — a documented deviation, recorded rather
than silently omitted.

| # | Command | Exit | Outcome | Observed (UTC) | Summary |
|---|---|---|---|---|---|
| 1 | `pytest app/g6/backend/tests -q` | **0** | PASS | 09:05:44 | 84 passed, 10 skipped |
| 2 | `pytest app/g7-enterprise/backend/tests -q` | **0** | PASS | 09:05:46 | 28 passed, 1 skipped |
| 3 | `pytest tests/tooling -q` | **0** | PASS | 09:09:09 | 16 passed, 1 skipped |
| 4 | `unittest discover -s tests/tooling` (CI's runner) | **0** | PASS | 09:09:10 | Ran 17 tests, OK |
| 5 | `ruff check <Makefile blocking paths>` | **0** | PASS | 09:05:50 | All checks passed |
| 6 | `ruff check app --statistics` | **1** | FAIL (informational) | 09:05:50 | 48 pre-existing findings; non-blocking in the Makefile |
| 7 | `mypy` | **0** | PASS | 09:05:50 | no issues in 19 source files |
| 8 | `scripts/check_repository.py` | **0** | PASS | 09:09:09 | 0 errors |
| 9 | `scripts/build_site.py` → `scripts/check_site.py` | **0** | PASS | 09:09:10 | 12 files built; 0 site errors (order matters — §4) |
| 10 | `scripts/prepare_runtime.py` | **0** | PASS | 09:05:51 | 5 artifacts OK; original bundle absent |
| 11 | `verify_bake.py …` | **0** | PASS | 09:05:51 | 3/3 baked artifacts verified |
| 12 | `git diff --check` | **0** | PASS | 09:09:10 | no whitespace errors |
| 13 | `app/local-tester.py` (smoke) | **0** | PASS | 09:03:31 | **104/104** checks over real HTTP |
| 14 | `scripts/e2e_ui.py` (browser E2E) | **0** | PASS | 09:03:35 | **17/17** specs in real Chromium |
| 15 | `npm test` (G6) | **0** | PASS | 09:02:49 | 29 tests |
| 16 | `npm run build` (G6) | **0** | PASS | 09:03:07 | 0 TypeScript errors |
| 17 | `npm test` (enterprise) | **0** | PASS | 09:03:15 | 2 tests |
| 18 | `npm run build` (enterprise) | **0** | PASS | 09:03:24 | 0 TypeScript errors |
| 19 | read-only SQLite inspection | **0** | PASS | 09:06:04 | see §5 |
| 20 | canonical DB SHA-256, before/after every write-bearing gate | **0** | PASS | 09:06:04 | unchanged, see §5 |
| 21 | live UI + `/v1/health` + `/v1/meta` | **0** | PASS | **07:47:40** | see §7 — **pre-merge**, against the owner's own long-running dev stack, and not re-claimed at the audited baseline |

**Totals:** backend **112 passed, 11 skipped, 0 failed**; frontend **31 passed**; browser
**17 passed**; smoke **104/104**.

`README.md` claims "Backend: 110 passed, 11 intentional environment-gated skips". The observed
count is **112 passed / 11 skipped** — the README is stale by two. This task does not edit the
README; the discrepancy is recorded instead.

### What was NOT run, and why

| Check | State | Reason |
|---|---|---|
| 11 torch-gated tests (9 attribution + 1 real-bundle + 1 cpu-worker) | **SKIPPED** | `torch` is absent from the locked serve venv; installing it is not authorized by this task. Real Grad-CAM heatmap production is therefore **unverified** — only the honest-refusal path is verified. |
| Anything needing the original G4 weights | **NOT_RUN** | that bundle file is absent from disk |
| Real whole-slide reading | **NOT_RUN** | `openslide 1.4.3` imports fine, but no real slide with coordinates is in scope |
| Is the CloudFront deployment live? | **UNVERIFIED** | no AWS credentials in the environment and no authorization to use any; a `~/.aws` directory exists but was deliberately not read. Nothing is asserted in either direction. |
| GitHub Actions run for this SHA | **NOT_RUN** | no push/PR authorization; the workflow was read, not executed |

---

## 7. What the live application actually shows

Observed read-only against the already-running dev stack (`:5173` → `:8137`), not started by this
task:

- Gallery renders **"Page 1 · 1144 patches"** with real H&E thumbnails, ordered by ascending
  top-two score margin `0.000 → 0.330` — the uncertainty-first queue is real, not a label.
- `/v1/health` → `status ok`, `images_indexed 1144`, `predictions 1144`,
  `model_bundle_sha256 01727fb8…`, `image_subset_scoped false`.
- `/v1/meta` → `canonical_classes` exactly `["NON_TUMOR","VIABLE_TUMOR","NECROSIS"]`;
  `review_actions` exactly `["ACCEPT","CORRECT","DEFER"]`; attribution advertised as
  `contrastive-grad-cam` with the explicit reconstruction disclosure and
  `recovered_model_id: g4-behavioral-recovery-r1`.
- Cards show `Training eligible: yes/no` and `QC REVIEW (data quality)` as **metadata**, never as a
  fourth class. Source groups appear as `Case-3 / Case-4 / Case-48 / P9`.
- Console clean apart from Vite HMR and the React DevTools notice.

The browser E2E independently drove the reviewer journey in Chromium — ACCEPT, CORRECT and DEFER
each recording an append-only event while leaving the model prediction intact, the model-card
catalog rendering, attribution either real or honestly refusing, and CSV export carrying the
disclaimer.

**Canonical data unchanged:** the database SHA-256 was
`0e4524db91f7a6e22dfbdc3395cf0fce6b7bf1b5628ac4cd1198be291d01ac40` before smoke, after smoke, and
after the browser E2E. Both runners copy it to a temp workspace and re-assert the hash themselves;
smoke printed *"canonical review store is byte-identical after the run"*. No pixel or model binary
was written.

---

## 8. Capability maturity

`deployed` is **UNVERIFIED for every row** — see §6.

| Capability | Code | Unit-tested | Real-data | Running locally |
|---|:--:|:--:|:--:|:--:|
| Three-class frozen predictions | ✅ | ✅ | ✅ | ✅ |
| Uncertainty-first priority queue | ✅ | ✅ | ✅ | ✅ |
| Review ACCEPT/CORRECT/DEFER, append-only | ✅ | ✅ | ✅ | ✅ |
| Contrastive attribution (Grad-CAM) | ✅ | ⚠️ skipped, no torch | ❌ | honest refusal only |
| Model card + limitations catalog | ✅ | ✅ | ✅ | ✅ |
| CSV/JSON export with provenance | ✅ | ✅ | ✅ | ✅ |
| Project scoping / tenancy | ✅ | ✅ | ✅ | enterprise stack only |
| Identity, RBAC, audit chain | ✅ | ✅ | ✅ | enterprise stack only |
| Registry, promotion gate, rollback, drift | ✅ | ✅ | ✅ | enterprise stack only |
| SQLite connection lifetime / concurrency | ✅ | ✅ | ❌ | unverified |
| Whole-slide reading | ✅ | unverified | ❌ | ❌ |
| 50-image demo subset | ✅ | ✅ | ✅ | allowlist mechanism only |
| Local dev/verification entry points | ✅ | n/a | ✅ | ✅ |

Two honest caveats on that table: the canonical `review_event` table holds **0 rows** (the review
path is only ever exercised against throwaway copies), and the local single-user G6 endpoint is
**not** a protected multi-user endpoint.

---

## 9. Acceptance checks

| ID | Result | Evidence |
|---|:--:|---|
| **F001-AT01** dirty paths identical before and after | **PASS** | §2 — both trees empty before and after; only the three task-owned evidence files are new |
| **F001-AT02** an unavailable runtime dependency recorded BLOCKED/NOT_RUN, not PASS | **PASS** | §6 — 11 torch-gated tests recorded SKIPPED with their skip reasons (`torch not installed in this venv`), the original G4 bundle recorded ABSENT, WSI recorded NOT_RUN, cloud deployment recorded UNVERIFIED |
| **F001-AT03** concrete commit SHA and real test counts | **PASS** | §1 (audited baseline `44fed1d…`, first measured at `b40bf34e…`) and §6 (112 passed / 11 skipped / 16 tooling / 31 frontend / 17 browser / 104 smoke), all measured in this session, with the stale README count called out rather than copied |
| **F001-AT04** sources called case/slide groups | **PASS** | §5 and §7 — `Case-3 / Case-4 / Case-48 / P9`, with an explicit statement that no patient identity is implied |
| **F001-AT05** no credentials, private outside paths or medical identifiers | **PASS** | §10 — no credential values; paths recorded are the two project checkouts; AWS env vars recorded only as `unset`; aggregate counts only, no per-patch identifiers |

### Boundary and failure review

F001 is an audit, so the pack's behavioural matrix is largely not applicable. The cases that *do*
apply were exercised by the existing gates: no rows (`review_event` = 0), duplicate input/retry
(smoke verifies enterprise enqueue idempotency and the e2e no-leak invariant), unavailable artifact
(missing torch, missing G4 bundle, missing WSI slide), unauthorized object (smoke verifies a
reviewer gets 403 on drift and cross-project scope is denied), changed model/session (smoke verifies
promotion, single-serving and rollback), and partial failure (E2E fails closed on a non-canonical
label with HTTP 400). No null metric is reported as zero anywhere in this inventory.

---

## 10. Limitations and disclosures

1. All figures are from this session; the committed `docs/evidence/*.json` files are older runs and
   were not treated as current.
2. `README.md`'s backend count (110) is stale against the observed 112.
3. `deployed` is UNVERIFIED everywhere — no AWS credentials were present or used, and none were
   sought.
4. Real attribution, calibration, WSI, research and deployment work were **not** performed. F001 is
   an inventory and it stops here.
5. Node gates ran in the primary checkout (shared `node_modules`) rather than in the worktree.
6. The two branches ahead of `main` were compared, never modified; the decision is the integrator's.

**No credential value, no path outside the project, and no medical identifier appears in this file or
its JSON companion.** The only absolute paths recorded are the two project checkouts themselves, which
the inventory contract requires (`repo_root`); the prompt pack's Desktop location and the historical
dead scratch paths were deliberately redacted rather than reproduced.

---

## 11. Next action for the integrator

Review this inventory against `templates/REVIEW_ONE_TASK.md`, then pick the next task **from §8** —
not from the pack's stale `57c1efc` manifest. On this evidence, the pack's foundation track is
mostly already satisfied: F001 through F007 have existing code and passing tests behind them and
will mostly close as `NO_CHANGE_VERIFIED` after tracing to the rows above. Do not start that work
until this receipt is accepted.