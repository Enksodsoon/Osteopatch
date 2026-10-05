# STEP 4 — Static Analysis Baseline

**Date:** 2026-10-05 · **SHA:** `feat/unified-platform-p0`

## Result

| Gate | Scope | Exit | Result |
|---|---|---|---|
| `ruff check` | `scripts/` + `osteopatch/pathology/` + `osteopatch/domain/` | **0** | All checks passed |
| `mypy` | `osteopatch/` (17 source files) | **0** | Success: no issues found |
| `ruff check app` | legacy tree | 1 | **51 violations — informational, not gating** |

Regression check after the typing fixes: G6 backend **53 passed / 10 skipped
(exit 0)**, enterprise backend **28 passed / 1 skipped (exit 0)**.

---

## Why the legacy gate does not block

The repository carried **82** ruff violations before any of this work — 28
unsorted import blocks, 11 unused imports, 7 `raise`-without-`from` inside
`except`, plus assorted style issues. Most are in files this work does not
touch.

The brief is explicit: *"Do not allow formatting-tool churn across the entire
repository during the first CI commit."* Running `ruff --fix` across 51 sites
would rewrite modules unrelated to the unification work and bury the real diff.

So the rule set is enforced **blocking on newly-authored code** and
**reported informationally on the legacy tree**. The legacy job carries
`continue-on-error: true` and exists to show the debt shrinking, not to gate.

Six rules were excluded outright because the existing code is *right* and the
linter is wrong for this codebase:

| Rule | Excluded because |
|---|---|
| `UP017` | `datetime.UTC` alias; legacy code uses `timezone.utc`, equivalent |
| `UP042` | `str + Enum` → `StrEnum` would alter the enterprise `Role` model |
| `UP031` | percent-format for building SQL `IN (...)` placeholders is clearer here |
| `E731` | demo scripts intentionally use terse lambdas |
| `E702` | demo scripts intentionally pack statements per line |
| `B008` | FastAPI `Depends()`/`Query()` in defaults is the framework idiom |

---

## Typing fixes actually made (not suppressed)

Three real annotation defects were fixed at the source rather than silenced:

1. **`osteopatch/model.py`** — `LoadedModel.model` and `.eval_transform` were
   typed `object`, but the dataclass then *calls* them, so mypy correctly
   reported `"object" not callable` at lines 134/136. Retyped to `Any` with a
   comment explaining that torch is imported lazily and must not become a hard
   type dependency for the torch-free serve path.

2. **`osteopatch/config.py`** — the module-global `_IMAGE_ALLOWLIST_CACHE`
   sentinel pattern defeated type inference. Annotated as `object` and narrowed
   with an `assert` on the read path.

3. **`osteopatch/pathology/reader.py`** — a stale `# type: ignore` and an
   imprecise `tuple[int, ...]` from `tuple(map(...))`.

Two `type: ignore` comments were added during this work and then **removed
again** once mypy showed them to be unnecessary — `warn_unused_ignores = true`
is what surfaced them.

---

## Toolchain note: my exit-code discipline

Three times during this audit a piped command's exit code was read after an
intervening `echo`, or `$?` was taken from a pipeline, yielding the *filter's*
status rather than the tested command's. One of those reported a failing suite
as passing.

Every gate in this document records an exit code captured **immediately after
the tested command**, with no pipeline in between. Where a pipeline was used
for readability, the exit code was captured separately and verified.