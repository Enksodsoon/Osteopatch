# Phase 0 baseline record — prompt-pack run

**Captured:** 2026-10-06T00:51:49Z (date -u, at record write time)
**Worktree:** `wt/pack` · **Branch:** `feat/prompt-pack-run` · **HEAD:** `626aaadc9e4282b470b74fe94893a412cf7d127a`
**Purpose:** the durable state record required before any new prompt-pack task may start.
This run is Phase 0 only: no task from the topological order is started here.

## 1. Branch and HEAD

| Field | Value |
|---|---|
| Branch | `feat/prompt-pack-run` |
| HEAD | `626aaadc9e4282b470b74fe94893a412cf7d127a` |
| Baseline of record | `626aaadc9e4282b470b74fe94893a412cf7d127a` (= HEAD; no task committed yet) |
| Worktrees | 3 registered |

## 2. Dirty-path inventory (verbatim `git status --porcelain`)

**59 paths pre-existed this record** (20 modified, 39 untracked). The block below shows **60**,
because it also lists this file: the shell expanded the here-document after the redirect had
already created it. The pre-existing 59 are the block minus its own final
`?? docs/evidence/phase0-baseline.md` line. Stated rather than quietly reconciled, because a
record that miscounts its own contents is the defect class `F001-receipt.json` already documents.

```
 M .gitignore
 M app/g6/backend/osteopatch/app.py
 M app/g6/backend/osteopatch/db.py
 M app/g6/backend/osteopatch/queries.py
 M app/g6/frontend/src/App.tsx
 M app/g6/frontend/src/api.ts
 M app/g6/frontend/src/components/Workbench.tsx
 M app/g6/frontend/src/main.tsx
 M app/g6/frontend/src/strings.ts
 M app/g6/frontend/src/styles.css
 M app/g7-enterprise/backend/enterprise/review_proxy.py
 M app/local-tester.py
 M docs/evidence/README.md
 M docs/evidence/e2e-ui-result.json
 M docs/task-evidence/F001-baseline.json
 M docs/task-evidence/F001-baseline.md
 M docs/task-evidence/F001-receipt.json
 M scripts/check_repository.py
 M scripts/e2e_ui.py
 M tests/tooling/test_repository.py
?? aidlc-docs/prompt-pack/
?? app/g6/backend/osteopatch/scope.py
?? app/g6/backend/tests/fixtures/
?? app/g6/backend/tests/test_connection_lifecycle.py
?? app/g6/backend/tests/test_fixture_contract.py
?? app/g6/backend/tests/test_scope_contract.py
?? app/g6/frontend/src/apiErrors.ts
?? app/g6/frontend/src/components/AsyncState.tsx
?? app/g6/frontend/src/components/ThemeControl.tsx
?? app/g6/frontend/src/navigation.ts
?? app/g6/frontend/src/styles/
?? app/g6/frontend/src/test/api-client.test.ts
?? app/g6/frontend/src/test/async-state.test.tsx
?? app/g6/frontend/src/test/design-tokens.test.tsx
?? app/g6/frontend/src/test/navigation.test.tsx
?? app/g6/frontend/src/test/theme.test.tsx
?? app/g6/frontend/src/theme.ts
?? docs/evidence/gates/
?? docs/evidence/phase0-baseline.md
?? docs/task-evidence/F002-receipt.json
?? docs/task-evidence/F002.md
?? docs/task-evidence/F003-receipt.json
?? docs/task-evidence/F003.md
?? docs/task-evidence/F004-receipt.json
?? docs/task-evidence/F004.md
?? docs/task-evidence/F007-receipt.json
?? docs/task-evidence/F007.md
?? docs/task-evidence/STATUS.md
?? docs/task-evidence/TURN0-setup-baseline.md
?? docs/task-evidence/TURN0-setup-receipt.json
?? docs/task-evidence/U001-receipt.json
?? docs/task-evidence/U001.md
?? docs/task-evidence/U002-receipt.json
?? docs/task-evidence/U002.md
?? docs/task-evidence/U003-receipt.json
?? docs/task-evidence/U003.md
?? scripts/run_gate.py
?? scripts/task_env.sh
?? scripts/verify_prompt_pack.py
?? tests/tooling/test_run_gate.py
```

### 2.1 Which task owns what

| Task | Owned paths present in the inventory above |
|---|---|
| TURN0 | `scripts/task_env.sh`, `scripts/verify_prompt_pack.py`, `aidlc-docs/prompt-pack/`, `TURN0-setup-*` |
| F001 | `docs/task-evidence/F001-baseline.md`, `.json`, `-receipt.json` (modified) |
| F002 | `app/g6/backend/tests/fixtures/`, `app/g6/backend/tests/fixtures/test_fixture_contract.py`, `docs/task-evidence/F002.md`, `docs/task-evidence/F002-receipt.json` |
| F003 | `app/g6/backend/osteopatch/scope.py`, `app/g6/backend/osteopatch/queries.py`, `app/g6/backend/tests/fixtures/test_scope_contract.py`, `docs/task-evidence/F003.md`, `docs/task-evidence/F003-receipt.json` |
| F004 | `app/g6/frontend/src/apiErrors.ts`, `src/test/api-client.test.ts`, `F004-*` |
| F007 | `app/g6/backend/osteopatch/db.py`, `app/g6/backend/tests/fixtures/test_connection_lifecycle.py`, `docs/task-evidence/F007.md`, `docs/task-evidence/F007-receipt.json` |
| U001 | `app/g6/frontend/src/navigation.ts`, `src/test/navigation.test.tsx`, `U001-*` |
| U002 | `app/g6/frontend/src/styles/`, `src/test/design-tokens.test.tsx`, `U002-*` |
| U003 | `app/g6/frontend/src/components/AsyncState.tsx`, `src/test/async-state.test.tsx`, `U003-*` |
| **U005** | `app/g6/frontend/src/theme.ts`, `src/components/ThemeControl.tsx`, `src/test/theme.test.tsx`, `src/main.tsx`, `src/App.tsx` — **code present, receipt absent** |
| integration-owned | `scripts/run_gate.py`, `tests/tooling/test_run_gate.py`, `scripts/check_repository.py`, `tests/tooling/test_repository.py`, `.gitignore`, `STATUS.md`, `docs/evidence/*`, `app/local-tester.py`, `scripts/e2e_ui.py` |

## 3. Canonical review store

Read-only source: `runtime-artifacts/db/osteopatch_g6.sqlite3` in the primary checkout.
Writable store: a seeded throwaway copy under `scratch/throwaway-db/` — the canonical file is
never opened for writing.

| When | SHA-256 |
|---|---|
| before Phase 0 gates | `0e4524db91f7a6e22dfbdc3395cf0fce6b7bf1b5628ac4cd1198be291d01ac40` |

## 4. Why Phase 0 exists

`EXECUTION_ORDER.md` requires that "code and its prerequisite receipts must be available to
every new task." At capture time nine tasks' worth of code sat in the working tree with
**zero commits**, and U005 had code with no receipt at all. No task from the topological
order may be started until this inventory is committed per task and U005 is resolved.
