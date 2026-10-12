# Prompt-pack task status

**Integration-owned roll-up.** One line per prompt-pack task, maintained by the integrator so
progress across 129 tasks stays glanceable without reading every receipt.

- Source of truth for *task content*: `aidlc-docs/prompt-pack/` (integrity-verified against its own
  `SHA256_MANIFEST.json`; run `scripts/verify_prompt_pack.py`).
- Source of truth for *status*: this file, plus `docs/task-evidence/<TASK>-receipt.json`.
- The vendored `TASK_MANIFEST.json` is **not** edited to record status: its digests are covered by
  the pack's own manifest, so editing it would break the integrity check.

## Execution environment

| Setting | Value |
|---|---|
| Worktree | `C:/Users/enkso/.kiro/crew/workspace/osteopatch/wt/pack` |
| Branch | `feat/prompt-pack-run` |
| Baseline | `626aaad` (`origin/main`) |
| Environment | `source scripts/task_env.sh` — read-only artifacts, throwaway writable DB |
| Protocol | one task per turn; receipt; hard stop |

## Progress

**8 of 129 complete, 1 in progress (`U005`, `PARTIAL`), 120 untouched.**

> **Phase 0 correction, 2026-10-06.** This file previously said **“U005 is NOT started”**
> and listed it as `NEXT`. That was wrong: U005's four declared files, its wiring in
> `main.tsx` and `App.tsx`, its 36-test suite, its red-first record and its build were all
> already in the working tree, along with five gate records under `docs/evidence/gates/`.
> Only the receipt was missing — because **the browser rehearsal had failed**
> (`u005-rehearsal.json`, exit 1, `REHEARSAL FAILURES: 4`), so the previous session stopped
> without writing one. U005 is therefore `PARTIAL`, not complete. See
> [U005-receipt.json](U005-receipt.json). Triage so far: 1 of the 4 failures is a real
> invisible-text defect (AT05, a 1:1 contrast label in dark mode), 1 is a miscalibrated check
> that ignored React `StrictMode` double-mounting, and 2 remain unverified.

> **Evidence-integrity audit, 2026-10-05T11:20Z.** Every `observed_at_utc` in this directory was
> audited against the only sources that can actually establish a time: artifacts the **runners**
> timestamped themselves (`generated_at` / `generated_at_utc`), file mtimes, and `date -u`.
>
> | Receipt | Timestamps as written | Counts / exit codes as written |
> |---|---|---|
> | **U002** | **Trustworthy** after its own in-turn repair | Trustworthy |
> | **F004** | **Partly** — 3 DERIVED, 1 corrected to its anchor, 7 UNAVAILABLE | Trustworthy |
> | **F001** | **Not trustworthy** — all 21 UNAVAILABLE | Trustworthy for that baseline |
> | **TURN0** | **Not trustworthy** — e2e stamp was 2m05s *later* than its own artifact | Trustworthy |
> | **F002** | **Not trustworthy** — internally impossible | Trustworthy |
>
> What was wrong: F001, F002, F004 and TURN0 all wrote **round-minute values with no source behind
> them**. Three were contradicted by hard evidence — F002's stamps ran up to 13 minutes *after* the
> receipt that reports them was last written; TURN0's e2e stamp postdated its own runner artifact by
> 2m05s; F004's e2e stamp was 42s later than the runner's own artifact, now `docs/evidence/gates/f004-e2e-f004.json`. F001 also had six commands
> sharing one identical second and its two files disagreeing about the same run. **U002's first draft
> was worse**: it wrote vitest's local `+0700` clock into a field named `observed_at_utc`, putting
> every stamp ~7 hours into the future.
>
> **Every recorded pass count, exit code and byte-identical claim re-verified exactly on
> 2026-10-05T11:17Z** — backend G6 115 passed / 10 skipped, enterprise 28, tooling 16 (+17 via the
> CI runner), frontend G6 89 / enterprise 2, smoke 104/104, browser E2E 17/17, ruff blocking set and
> mypy clean, canonical store `0e4524db…` unchanged. The defect was confined to **when** things were
> claimed, not **what** they claimed.
>
> ### Standing rule for every future receipt
>
> 1. **Every timestamp traces to a captured source.** Each `observed_at_utc` is `ANCHORED` (a
>    runner-timestamped artifact names it), `DERIVED` (arithmetic on a real captured value, with
>    the arithmetic written down), or `UNAVAILABLE`. A round minute is never an observation.
> 2. **No measured-sounding claim without a measurement.** If it was not run, it is `NOT_RUN`; if it
>    was run but not compared, it says so. "Pixel-identical" is not a thing anyone may assert after
>    looking at two pictures.
> 3. **Nothing is backdated.** A re-run establishes that a claim still holds *now*; it never dates a
>    historical run.
> 4. Run suite-producing gates behind a `date -u` wrapper. `scripts/run_gate.py` does this
>    permanently:
>
>    ```sh
>    python scripts/run_gate.py --name backend --out <record>.json -- python -m pytest app/g6/backend/tests -q
>    ```
>
>    It stamps the record at spawn time with `date -u`, records the gate's real exit code, quotes
>    the real output, and **mirrors that exit code** so a red gate cannot read as green. It has no
>    option to accept a timestamp, and a command that cannot be spawned produces **no record at all**
>    (exit 3) rather than a fabricated one. Windows note: a relative executable path written with
>    forward slashes cannot be spawned — use backslashes or a command already on `PATH`. The tool
>    deliberately does not rewrite the path, because a record whose `command` disagrees with what the
>    operator typed would be exactly the dishonesty it exists to prevent.

| # | Task | Title | Status | Receipt |
|---|---|---|---|---|
| — | TURN0 | Prompt-pack execution setup and re-measured baseline | `IMPLEMENTED_VERIFIED` | [TURN0-setup-receipt.json](TURN0-setup-receipt.json) |
| 1 | F001 | Inventory the real baseline without changing product code | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [F001-receipt.json](F001-receipt.json) |
| 2 | F002 | Create deterministic test fixtures and a throwaway integration database | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [F002-receipt.json](F002-receipt.json) |
| 3 | F004 | Add a typed API client with cancellation and honest errors | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [F004-receipt.json](F004-receipt.json) |
| 4 | U002 | Consolidate the editorial design tokens without redesigning behavior | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [U002-receipt.json](U002-receipt.json) |
| 5 | F003 | Centralize authorization scope and explicit prediction selection | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [F003-receipt.json](F003-receipt.json) |
| 6 | F007 | Verify and bound database connection lifetime and concurrent writes | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [F007-receipt.json](F007-receipt.json) |
| 7 | U001 | Add stable navigation, deep links, and browser history | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [U001-receipt.json](U001-receipt.json) |
| 8 | U003 | Standardize loading, empty, offline, and retry states | `IMPLEMENTED_VERIFIED`, **NOT_REVIEWED** | [U003-receipt.json](U003-receipt.json) |
| 9 | U005 | Add light and dark themes with safe local preferences | `PARTIAL` — rehearsal failed; 1 of 4 failures confirmed a real defect | [U005-receipt.json](U005-receipt.json) |
| 10 | R008 | Harden patch zoom, pan, fit, fullscreen, and reset | **NEXT once U005 is repaired** | — |

Remaining 120 tasks are `PLANNED_NOT_EXECUTED`, in the pack's topological order.

> **Counting note.** The manifest declares 129 tasks and `TURN0` is **not** one of them — it is a
> setup step from the pack's own harness, which is why it appears as an unnumbered row above.
> 8 complete + 1 in progress (`U005`) + 120 untouched = 129, verified against
> `TASK_MANIFEST.json` rather than by hand.

> **Route note.** `U005` is in the pack's full `topological_order` but **not** in its
> 52-task demo closure, and it is the only task in the run whose implementation preceded its
> own receipt. The next task on the demo route is `R008`. Starting `R008` before `U005` is
> repaired would stack new work on a task the integrator has not accepted, which
> `EXECUTION_ORDER.md` forbids — so the order is: repair `U005`, then `R008`.

> **Ordering note.** Every task so far was resolved from `TASK_MANIFEST.json`'s own
> `topological_order` (`F001 → F002 → F004 → U002 → F003 → F007 → U001 → U003 → …`), cross-checked
> against that task's own `dependencies`, not picked by hand. `F007` declares
> `dependencies: [F002]`, satisfied. U003 declares `dependencies: [F004, U002]`, both already
> `IMPLEMENTED_VERIFIED` with contracts confirmed present in code. **U005 is NOT complete:**
> its code and tests are present and green, but its rehearsal exited 1 with four failures and
> it has no integrator acceptance. It stays `PARTIAL` until those are resolved.

### U002's consolidated design tokens

`app/g6/frontend/src/styles/tokens.css` is now the single source of truth; `styles.css` imports
it first and declares **no** `:root` of its own. The file previously declared `:root` twice,
which silently overwrote 11 properties — the first block was dead code that read like the real
theme. 26 colour values consolidated (89 → 63 hex literals); 12 legacy custom properties renamed
to the semantic contract; the 4/8/12/16/24/32 spacing scale added.

Two live accessibility defects fixed and measured in a real browser:

- **Focus ring was 1.42:1** (`rgba(139,63,39,.22)` composited) — effectively invisible. Now the
  solid `--focus` `#6b2c17` at **10.35:1**, verified with real Tab presses so `:focus-visible`
  genuinely matches.
- **No `prefers-reduced-motion` block existed at all**, despite an infinite loading shimmer and a
  hover lift. Now `animationName: osteo-shimmer → none`, duration `0s`.

Known remaining gap, disclosed rather than papered over: neither `--border` (1.43:1) nor
`--border-strong` (1.80:1) meets the 3:1 non-text floor. They render as decorative dividers, but
a control relying on a border alone to convey state would fail 1.4.11.

## Measured baseline at `626aaad`

Every gate re-run in the worktree. Each carries its own exit code in its receipt.

| Suite | Result |
|---|---|
| Backend (G6) | **155 passed**, 10 skipped, 0 failed — 115 baseline + F002's 31 fixture-contract + F003's 23 scope-contract + F007's 17 lifecycle |
| Backend (enterprise) | 28 passed, 1 skipped |
| Tooling | **27 passed**, 1 skipped (28 via the CI unittest runner) — includes 11 new `run_gate` tests |
| Frontend (G6 + enterprise) | **91 passed** (G6 89 = 61 pre-existing + 28 U002; enterprise 2), both builds 0 TypeScript errors |
| Browser E2E | 17/17 Playwright specs, real Chromium 153.0.8010.12 |
| U002 browser sweep | 5/5 (focus contrast, reduced motion, grayscale labels, 390/768/1440 + 200% zoom overflow) |
| Smoke (real HTTP) | 104/104 |
| Static | `ruff` clean on the CI blocking set, `mypy` clean in 20 files |

### F004's typed API client

`app/g6/frontend/src/apiErrors.ts` is the single source of truth for failure handling.
`ApiError{status, code, message, request_id?, outcome}` distinguishes a definite server
rejection from an **unknown outcome** after a write whose connection dropped — the client never
claims a review "was not saved" when it may have committed. Reads accept an `AbortSignal`; a body
is read at most once; mutations are never auto-retried; 401/403 are never retried and the URL is
never rewritten to the unauthenticated local `/v1/` endpoint. Existing exports and signatures are
unchanged, so no integration-owned component needed editing.

### F003's centralized authorization scope

`app/g6/backend/osteopatch/scope.py` answers one question — which rows may this caller see — and
every read in `queries.py` answers from that one selection. Step 01 found two **latent** defects
first (both invisible on today's data, which has one bundle and one project):

- the gallery ranked via `_priority_rank_map(conn)` with **no `project_id`**, while the detail view
  passed one — so the same image got different rank numbers per endpoint, and the gallery's
  numbering counted other tenants' rows;
- `model_bundle_hash` appeared in the SELECT list and in the output dict and in **no WHERE clause**,
  while the join was `LEFT JOIN prediction ON image_id` — so a second bundle produced a second
  gallery card and an inflated `total`.

Measured after: 16 predictions over 8 images → **8** cards, one model hash each; a 50-image
allowlist over a 1,144-image project → **50** rows, total and export all 50; empty intersection →
**0** with no unscoped fallback; a duplicate `(image_id, model_bundle_hash)` →
`PredictionSelectionIntegrityError` rather than a silent pick. 23 new tests, all 5 acceptance IDs
PASS. Canonical store unchanged across four hashings.

Two judgement calls left open for the integrator, both recorded in the receipt: the documented
`MODE_PROJECT_ONLY` compatibility adapter (pre-F003 `project_id=` argument, no dataset version —
nil on the real corpus, where manifest membership == store membership at 1,144/1,144), and the
model-scoped review-state adaptation, which keeps `revision` image-global because
`repo.submit_review` compares against the image-global maximum.

### F007's bounded connection lifetime

It looked like a `NO_CHANGE_VERIFIED` — `test_connection_concurrency.py` already exists. Measuring
first said otherwise: three real defects sat next to it.

- **No bounded release at all.** 200 requests over 8 threads left **8 of 8 handles open**, and the
  app's lifespan was Starlette's `_DefaultLifespan`, so nothing in the code could ever close them.
- **A dead write held the write lock.** A handler exception after an `INSERT` left
  `in_transaction == True` on that thread's connection, and an independent writer's
  `BEGIN IMMEDIATE` came back **`database is locked`**. One failed request could block unrelated
  writers.
- **Migrations ran once per thread.** 8 threads meant 8 full migration scans of the same database.

Built: `release_conn` / `open_connection_count` / `close_all_connections` / `request_connection`
plus a FastAPI lifespan in `app.py`, and `db.initialize` + `db.close` in `db.py`. Review writes and
export take the per-request scope; read-only handlers keep their thread-local handle and are
released at shutdown — that split is a judgement call and is flagged in the receipt.

Measured after: lifespan shutdown 4 open → **0**; write and export requests return to **0** open
connections immediately; 8 racing writers at revision 0 → 1 created, 7 conflicts, revision 1 stored
**once**; 8 threads → **1** migration run; a handler exception mid-write leaves the next request
with `in_transaction == False` and writable. 17 new tests, all 5 acceptance IDs PASS.

The boundary sweep caught a footgun in the first implementation — a nested `request_connection()`
closed the handle its caller was still using — fixed with a per-thread depth counter plus a test.
Canonical store `0e4524db…` unchanged across 35 hashings (before and after each of 17 gates).

### Gate evidence is durable

Every receipt in this directory cites per-gate records, and until now those records
lived in `scratch/gates/` — which `.gitignore` covers. A fresh checkout had no way
to read the evidence F003's and F007's receipts pointed at.

`scripts/run_gate.py` now defaults to `docs/evidence/gates/<name>.json` (the
versioned home AGENTS.md already asks for) and **refuses a git-ignored record path
with exit 4, before the gate runs** — a gate whose output has nowhere durable to
land is evidence nobody can check. The directory is **accumulated**, one per repo,
named `<task>-<gate>.json`, so a later run of the same gate cannot silently
overwrite an earlier task's evidence.

| | Before | After |
|---|---|---|
| F007's 17 records | `scratch/gates/`, gitignored | `docs/evidence/gates/f007-*.json`, all `durability: VERSIONED`; gates **re-run**, stamps describe that run |
| F003's 10 records | `scratch/gates/`, gitignored | copied **byte-identically** (sha256 checked) to `f003-*.json` and repointed; nothing re-dated |
| 2 KB `output_tail` | implied completeness | `output_chars` + `output_truncated` on every record; the 2 gates over the cap have full output in `f007-smoke.log` and `f007-tooling-tests.log` |

8 new tests in `tests/tooling/test_run_gate.py` cover the contract, including the
negatives: an ignored path is refused with nothing written, a failing gate still
records its real exit code, and a gate that never ran leaves no record and no log.
One existing test changed because this fix inverts what it asserted — omitting
`--out` is now the supported default, so the refusal still tested is "no command
given" (exit 2). `exit 2` and `exit 3` keep their meanings; the new refusal is a
distinct `exit 4`.

### F004's and TURN0's anchoring artifacts, and a check that keeps them readable

The gate records were durable after the pass above, but two receipts still cited
*other* artifacts out of `scratch/task/`: F004's browser-E2E result and TURN0's E2E
and smoke results. Those are exactly the files that make those receipts' stamps
`ANCHORED` rather than `DERIVED`/`UNAVAILABLE`, so their loss quietly weakened the
strongest claims in the base. All three are now in `docs/evidence/gates/` as
`f004-e2e-f004.json`, `turn0-e2e-setup.json` and `turn0-smoke-setup.json`, each copied
byte-identically with sha256 verified either side of the copy. **Nothing was re-run
and no digest was recomputed** — moving evidence is not new evidence, so F004's and
TURN0's `diff_sha256` and every recorded stamp still describe the original run, and
each receipt's `timestamp_audit.durability_repair` records where the copy came from.

`scripts/check_repository.py` now closes the loop: it walks every
`docs/task-evidence/*.json`, resolves each artifact the receipt cites (following each
cited gate record one level down to its `output_log`), and fails when a citation is
git-ignored or absent. It runs in CI (`ci.yml:117`) and in `make lint`, so a receipt
citing evidence that vanishes now fails the build instead of passing review.

| Decision | Verdict | Why |
|---|---|---|
| exists, git-ignored | **error** | it disappears on a clean checkout — the exact failure being prevented |
| absent | **error** | nothing to read, same outcome |
| exists, untracked, not ignored | **accepted** (`untracked`) | tracked-ness is a commit-time property; the failure is *unreadable* evidence, not uncommitted evidence |
| exists, tracked | accepted (`tracked`) | the intended state |

A citation is a repo-relative path to a *data* artifact. What a receipt names in order
to **run** something is not a citation: programs and databases, bare directories,
globs, generated trees (`.venv`, `node_modules`, `_site`), and the `command`/`argv`/
`cwd` fields — a `command` records what ran, faithfully and as it ran, and rewriting
one to satisfy the check would falsify it. A gate record's own `command` still names
`scratch/task/…` for exactly that reason, and that is correct.

**Found by the check, pre-existing and not caused by this work:** five receipts
(F001-baseline, F001, F002, F004, TURN0) told the integrator to review "against
`templates/REVIEW_ONE_TASK.md`". That file is not in the repository and never was
committed. The receipts now say so plainly and point at the governing brief instead;
no file was invented to satisfy the check.

The same pass fixed a defect it introduced earlier: `*.log` in `.gitignore` was
covering the two gate transcripts, so last pass's "durable full logs" were not
durable. `.gitignore` now negates them under `docs/evidence/`, and both are addable.

Gates for this pass are recorded as `durability-*.json` in `docs/evidence/gates/`.

### run_gate capture — the evidence wrapper no longer loses output

`run_gate.py` ran gates with `subprocess.run(..., text=True)`. That decodes in a
reader *thread* using the host locale, and `subprocess` does not report that
thread dying. One undecodable byte therefore produced a `CompletedProcess` with
empty streams, and the wrapper wrote a healthy-looking record claiming
`output_chars: 0`, `summary: "(no output)"`, `exit 0` for a gate that had
printed plenty. Every receipt citing such a record pointed at nothing.

It now captures **bytes** and decodes them itself, per stream: UTF-8 strictly
first, locale with replacement only as a declared fallback. The record states
which codec produced the stored text.

| field | meaning |
|---|---|
| `output_capture` | `EMPTY` only when zero bytes arrived — now a **provable** claim. A capture failure writes **no record** (exit 3), so the two can never be conflated |
| `output_bytes` | bytes actually captured |
| `output_encoding` | `utf-8`, the fallback codec, `mixed`, or `none` |
| `output_decode_lossy` / `output_undecodable` | whether decoding was clean, and how many characters were invented |

Three further defects surfaced while fixing it, each fixed at the cause and
pinned by a test:

- **Clean output was corrupted by the other stream.** Decoding `stdout+stderr`
  as one blob let a single bad byte in stderr push stdout's good UTF-8 through
  the fallback codec — measured: `ARROW → 4711 passed` came out as
  `ARROW â†’`. Each stream is now decoded on its own, and mixed
  codecs are reported as `mixed` rather than flattened.
- **A record could name a log that did not exist.** The sidecar was written
  *after* the record; a failure in between left a record citing a missing file.
  The log is now written first.
- **The wrapper stopped mirroring the gate's exit code.** A lossy decode puts
  U+FFFD in `summary`; printing that to a cp1252 console raised
  `UnicodeEncodeError` *after* the record was written, so it exited 1 instead of
  the gate's code. Found by running the suite the wrong way: four new tests were
  green only because of the ambient `PYTHONUTF8=1`. Console streams are now
  reconfigured with `errors="replace"`, and a test pins the mirroring under a
  forced cp1252 console.

### Audit of the records already on disk

58 JSON files walked; 43 are `run_gate` records (the other 15 are smoke/e2e
runner artifacts that never had an `output_tail`). Findings:

| finding | which | verdict |
|---|---|---|
| `output_chars: 0` | `durability-diff-check.json`, `u001-diff-check.json`, `u003-diff-check.json` | **Not data loss.** All three are `git diff --check`, which prints nothing on a clean tree. Before the fix these were indistinguishable from a lost capture; now `output_capture` settles it. |
| truncated but no readable log | none | — |
| `output_chars > 0` with an empty tail | none | — |
| log attached that the tool did not write | `u001-rehearsal.json` | Hand-attached transcript with `output_truncated: false`. Given a `record_note` declaring its provenance; no measured value changed. |
| silent cp1252 mojibake | `u001-rehearsal.json` (7 occurrences) | The old path did not only lose output, it **corrupted** it whenever the bytes happened to be cp1252-decodable: `output_tail` reads `â€”` where the transcript has an em-dash. The transcript file is authoritative. |

**No surviving record had its output silently emptied** — the one empty record
U003 hit was overwritten by its `PYTHONUTF8=1` re-run. The corruption above is
the real residue.

**`PYTHONUTF8=1` is obsolete.** It is no longer needed for capture and must not
be carried forward as an instruction; U003's receipt and narrative have been
annotated rather than rewritten. Gates recorded before the fix are unaffected —
the captured bytes are unchanged, only the decode is now stated.

Gates for this pass: `run-gate-fix-tooling.json` (30 `run_gate` tests + full
tooling suite), `run-gate-fix-repository.json`, `run-gate-fix-diff-check.json`,
all exit 0 and run **without** the workaround, with canonical store
`0e4524db…` unchanged before and after.

### U003 — one vocabulary for read states

`Workbench.tsx` held read state as three independent booleans (`data` / `loading` / `failed`).
That shape cannot say "refreshing" or "offline", and the consequences were real: the previous
query's cards rendered beside the loading skeleton as if they were the new query's answer; a
failed refresh called `setData(null)` and discarded the reviewer's page; a 403 offered "Try
again"; nothing was announced to a screen reader; requests were never aborted, only ignored;
and `reloadKey` retries were unbounded.

`app/g6/frontend/src/components/AsyncState.tsx` (new, 278 lines) now holds the brief's §6
contract as one discriminated union — `idle | loading | refreshing{data} | ready{data} |
empty{reason,data} | failed{error} | offline{error,data}` — with the transitions as pure
functions and `AsyncStatus` to render them. `Workbench.tsx` holds one `AsyncState<ImageList>`,
passes a real `AbortSignal`, and publishes `data-async-state` for browser tests.

| | |
|---|---|
| acceptance tests | `U003-AT01..AT05` plus the transition table, boundary review and Step 08 handle — **40 tests** in `src/test/async-state.test.tsx`, red first (**39/39**: 19 missing-module, 4 no `AbortSignal`, 5 crashing on a malformed payload) |
| frontend suite | **138 passed** — 89 pre-existing, unchanged, plus 9 U001 and the 40 new |
| §10 gates | 40 passed · `tsc -b && vite build` 5.47 s · `git diff --check` clean |
| boundary sweep | **86 hostile inputs** outside the harness (malformed payloads, throwing getters, null rows, NaN/Infinity totals, non-`ApiError` throwables, prototype pollution), 0 unstable |
| §11 rehearsal | **32 Chromium checks, 0 failures**, real store (1,144 images, bundle `01727fb8…`); transcript in [u003-rehearsal-output.txt](../evidence/gates/u003-rehearsal-output.txt) |
| canonical store | `0e4524db…` identical before and after all six gates, including the write-bearing rehearsal |
| CSS | **none added.** Reuses `inline-error`, `empty-state`, `gallery-skeleton`, `muted`, `small` |
| `diff_sha256` | computed as this task's final write and stable across repeated runs. The literal is in [U003-receipt.json](U003-receipt.json) only: this file is itself inside the digest, so any value quoted here would be stale the moment it was written. |

**A real defect the §11 rehearsal caught.** The stale banner said "Offline" unconditionally, so
a server that answered with a 500 or a 403 was reported to the reviewer as a dropped
connection. Fixed at the cause (`isOffline` / `staleTitle`): only `code === "network"` is
offline, and a fourth AT03 test now pins it.

**A defect in the evidence machinery itself.** `run_gate.py` uses `subprocess(text=True)`, which
decodes as cp1252 on this host; when a child emits a byte the locale cannot decode the reader
thread dies and the record is written with **no output at all**. That is an evidence record with
no evidence. Worked around per invocation with `PYTHONUTF8=1`, which enables UTF-8 text I/O
even though `locale.getencoding()` still reports cp1252. Not fixed in place — `run_gate.py` is
not U003's file. **Since fixed — see "run_gate capture" below.**

**Deliberately not done.** §8 step 03 says wire the workbench first, so `PatchReview`,
`ModelCard` and `AttributionPanel` keep their own ad-hoc loading and error markup: the
standardization is **workbench-only**, and adopting it elsewhere is the judgement the integrator
is asked to make. `strings.ts` keeps four now-unused keys (`workbench.loadError`,
`workbench.empty`, `workbench.emptyHint`, `common.retry`) because that file is outside §5's
boundary. Stale cards stay clickable — there is no bulk action to disable, and the ids are real.
The three parked integrator items (PatchReview's unfiltered prev/next, the unstyled skip link,
F003's `MODE_PROJECT_ONLY`) were not touched.

### U001 — the location is now the route

Before U001 the app kept the current screen in `useState` and there was no URL anywhere: a
reload always returned to the workbench and a patch could not be linked at all. Now the hash
is the source of truth (`app/g6/frontend/src/navigation.ts`, 147 lines and no React), with one
`hashchange` listener removed on unmount, a typed route union covering the brief's eight
destinations plus the pre-existing `attribution` route, and query validation that falls back
to safe defaults for anything unrecognized.

| | |
|---|---|
| acceptance tests | `U001-AT01..AT05`, 9 tests in `src/test/navigation.test.tsx`, red first (9 failures: 5 on the missing module, 4 behavioural) |
| frontend suite | **98 passed** — 89 pre-existing, unchanged, plus the 9 new |
| G6 backend | 155 passed, 10 skipped (torch-gated) |
| smoke / §11 rehearsal | 104/104 · 13 Chromium checks, 0 failures, real store (1,144 images, bundle `01727fb8…`) |
| boundary sweep | 19 hostile inputs, 0 throws, 0 unstable round trips, no prototype pollution |
| canonical store | `0e4524db…` identical before and after the write-bearing gate and the rehearsal |
| `diff_sha256` | recomputed after the last content edit and stable across repeated runs. The literal is in [U001-receipt.json](U001-receipt.json) only: this file is itself inside the digest, so any value quoted here would be stale the moment it was written. |

**One hook outside the task's allowed surface, declared in the receipt.**
`app/g6/frontend/src/components/Workbench.tsx` keeps its filter/sort/search/page in local
state with no way in or out, so AT01's "and queue context" and the rehearsal's "return to the
original filtered workbench" are unreachable without it. The change is two *optional* props
plus moving the sort/filter vocabulary into `navigation.ts` so the URL validator and the
rendered options cannot drift. The integrator is asked to accept or re-scope it.

**Not fixed, and said so:** `PatchReview` still builds its prev/next queue from hardcoded
`listImages({sort: "priority", filter: "all", page: 1})` and ignores the queue context the
patch route now carries; and the skip link has no visual treatment because that needs one
rule in `styles.css`, outside this task's surface. Search text does travel in the URL, capped
at 200 characters — that is step 3's explicit instruction, but it is a product decision worth
an integrator's eye.

### F002's reusable hand-check fixture

`make_review_fixture(root, variant)` in `app/g6/backend/tests/fixtures/review_fixture.py` builds
the pack's 8-image example as a real throwaway database, with seven variants and an
`expected_snapshot.json`. Measured: total 8, decided 3, deferred 2, unreviewed 3, corrected 1,
disagreement 1; completion 3/8, agreement 2/3, correction 1/3, defer 2/5. These are **test
values**, never production statistics.

Canonical store `0e4524db91f7a6e22dfbdc3395cf0fce6b7bf1b5628ac4cd1198be291d01ac40` — identical
before and after every write-bearing gate.

## Standing constraints

- **`Z010` is prepare-only.** Deploying or mutating any cloud resource needs separate, explicit
  authorization. The prior AWS session's credentials expired and were never retested.
- **RESEARCH-tier tasks** (15 of them: `M005`–`M010`, `X009`, `X010`, `W002`, `W006`, `W009`,
  `D008`, `M012`, `E005`, `E006`) each carry their own approval gate.
- **Additional AWS spend: USD 0.**
- **torch stays out of the serve venv.** Real Grad-CAM heatmaps are unverified until that changes
  under separate authorization.
