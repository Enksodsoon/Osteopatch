# Local educational demo verification - 2026-10-07

The local educational workflow is verified on this host, including real recovered-model inference, attribution and uploaded WSI viewing. Other tissues/stains demonstrate software only; no clinical or production readiness is claimed.

Implementation: `wt/educational-demo`, branch `codex/osteopatch-educational-demo`. Both original project copies are preserved.

## Reproduced failures repaired

- Dead preview server: a fresh disposable workspace now serves the built UI and authenticated API from one origin.
- Gallery search ignored its query: both gallery aliases now use the existing scoped search.
- Reports containing recorded tiles raised `KeyError: scores_json`: reports now consume the existing decoded scores.
- Concurrent review updates raised HTTP 500: the shared proxy now returns the actual validation/conflict status and revision; browser retry preserves the draft.
- Passive mouse-wheel handlers produced console errors; pointer capture also swallowed retry clicks. Both viewers now use a removable non-passive wheel listener and capture the stage correctly.
- Report history could not reopen a saved report; failures discarded the editing surface. Reopen, retry, draft retention and reader export are exercised.
- Expired sessions stayed on broken authenticated screens; media, JSON and download requests now expire the shared session consistently.
- Back navigation lost search/page context; hidden workbench state now survives returning from patch review.
- Dark form/class colors, missing gallery grid styles, oversized viewer height and narrow report fields were repaired and checked visually.

Earlier repairs retained: Analysis imports/exports, stale-response guards, authenticated media/project headers, current membership authorization, signer identity checks, self-check reveal and recorded artifact verification.

## Executed checks

| Check | Result |
|---|---|
| G6 component tests | 30 passed |
| Enterprise component tests | 45 passed |
| G6 Chromium journeys | 18 passed |
| Enterprise Chromium journeys | 17 passed, including real SVS workflow |
| Backend + tooling, with locked model/WSI extras | 322 passed, 6 environment skips |
| Locked npm installation and full dependency audit, both frontends | passed; zero reported vulnerabilities |
| Both frontend production builds | passed |
| Scoped Ruff / mypy | passed; mypy covers 23 configured source files |
| Repository / requirement shims / dependency register / diff whitespace | passed |

Browser journeys cover sign-in and role switching; all gallery filters/sorts/paging/search and return context; patch next/previous, zoom/pan/reset; self-check/reveal/reset; analysis and honest unavailable attribution; accept/correct/defer, concurrent conflict/retry and reload; CSV/JSON downloads; verified recorded replay and tile inspection; signed and unsigned report creation, history reopening and HTML/Markdown exports. Fault injection covers API failures, expired sessions, missing pixels, absent recorded detail and failed downloads. Rapid navigation discards obsolete responses. Request bounds are asserted for gallery navigation. Unexpected HTTP errors and JavaScript errors fail the enterprise recovery suite; injected responses and the explicitly asserted real 409 are distinguished.

Responsive checks cover 1440, 768, 390 and 320 pixels in light/dark themes, including patch review. Keyboard activation, focus outline and reduced-motion operation pass. Rendered screenshots were inspected after repairs and recaptured in the confirmation pass. This is Chromium verification; Firefox/WebKit and real-device hardware were not run.

The six backend skips are five tests requiring the absent original frozen G4 binary and one Windows symlink-permission test. The recovered model tests were executed successfully. The original frozen G4 model remains distinct from the recovered model. Production registry promotion/rollback and infrastructure activation are outside the accepted local-demo scope and are not qualified by this report.

## Repeat locally

From this implementation checkout:

```powershell
$env:OSTEOPATCH_RUNTIME_ARTIFACTS = 'C:\path\to\verified\runtime-artifacts'
uv run --locked --extra dev --extra model --extra wsi python scripts/demo.py --runtime-artifacts $env:OSTEOPATCH_RUNTIME_ARTIFACTS --port 8140
```

Keep the command running. Open its printed URL and use `reviewer@demo`; Sign out switches personas. Ctrl+C then rerunning resets the disposable workspace. Port and process identifiers may change on each restart. Logs are outside the repository in `%TEMP%/osteopatch-demo.stdout.log` and `%TEMP%/osteopatch-demo.stderr.log`.

Backend model tests require a disposable full runtime copy: set `OSTEOPATCH_RUNTIME_ARTIFACTS` to that copy, `OSTEOPATCH_ATTRIB_IMAGES` to its images folder, and `OSTEOPATCH_RECOVERED_MODEL` to its recovered model file. Never run write-capable tests against canonical data.

Verification commands:

```powershell
uv run --locked --extra dev --extra model --extra wsi python -m pytest app/g6/backend/tests app/g7-enterprise/backend/tests tests/tooling -q -rs
# Each frontend directory:
npm.cmd test -- --run
npm.cmd run build
# Enterprise frontend:
$env:OSTEOPATCH_DEMO_URL='http://127.0.0.1:8140'
npx.cmd playwright test --workers=1 --output="$env:TEMP/osteopatch-qa-final-confirmed"
# Repository root; use the verified source bundle for the disposable G6 harness:
$env:OSTEOPATCH_RUNTIME_ARTIFACTS='C:\path\to\verified\runtime-artifacts'
uv run --locked --extra dev --extra model --extra wsi python scripts/e2e_ui.py --skip-prepare
```

The G6 harness uses the existing source snapshot rather than regenerating canonical data: its historical expected DB hash differs from the current handoff before these repairs. Frozen constants were not changed to make that check pass. Demo preparation verifies the actual snapshot, immutable corpus rows, copied images and recorded artifacts instead.

## Preserved evidence

Canonical DB SHA-256 before and after all journeys and final reset:
`2b18cdec2a9169ce88ff79e7f714662f7898cdb4d804fe34ed4119d31219d46b`.
Corpus digest: `f75f42509212a16de33133a3d969690216bf0259c2262cca823ac09384db252b` (1144 source rows, 1144 predictions, 5 existing review events). The fresh demo copies 50 patch pairs and one verified recorded run. All demo writes affect temporary copies.

Screenshots: `%TEMP%/osteopatch-ui-evidence`; failure traces remain outside the repository. G6 durable browser result: `docs/evidence/e2e-ui-result.json`.

## Uploaded WSI workflow

A byte-identical local educational SVS copy (20,414 x 27,401 pixels, three pyramid levels) exercised upload, authenticated preview/original download, zoom/pan/fit, rectangle annotations, annotation/region/analysis downloads, real ROI inference, report creation and HTML export, returning to the same workspace, whole-slide analysis of the first 16 tiles, tile inspection, reload and sign out. No new public data or training was needed. Browser annotations use session storage and original-image coordinates; exporting JSON preserves observations outside that session. Uploads are limited to 512 MB. View/annotation remains usable without a model; inference is role/capability gated.

Reproduced scanner ICC metadata caused generated PNG decode failures. The shared PNG exporter now strips derived-image metadata while preserving RGB pixels and leaving the original source unchanged; a regression checks both. CPU forwards and attribution hooks share the existing model lock. Windows reset cleanup releases the preparation connection. The real attribution selector now fits 320-pixel layouts. Native SVG and existing dependencies implement the viewer; no component library was added.

Final confirmation: 17 enterprise browser journeys and 18 G6 journeys passed without unexplained browser errors. The learning guide provides sourced study material, diagrams, synthetic H&E-style illustrations, and knowledge checks. WSI screenshots were inspected at desktop and mobile sizes in light and dark themes; tablet and 320-pixel overflow assertions passed. Both component suites (30 and 45 tests) and both builds passed after the existing Vitest upgrade to 4.1.11; locked npm installs and full audits passed with zero vulnerabilities. This remains Chromium-only engineering evidence, not model qualification on this non-osteosarcoma specimen.

WSI primary controls use the existing accent token; the browser regression asserts at least 4.5:1 text contrast in both themes. A final disposable reset completed without cleanup errors, and the authenticated original WSI download was SHA-256 identical to the local copy. The user browser was left on an uploaded WSI with a practice annotation and actual recovered-model output.
