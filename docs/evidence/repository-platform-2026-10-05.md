# Repository platform verification — 5 October 2026

**Branch:** `chore/repository-platform-20261005`
**Starting revision:** `b6b1a083ff39fbbec4e60543bbba56837fb64954`
**Purpose:** repository/documentation/automation professionalization only. No model training, AWS mutation, dataset download or paid API use.

## Workspace isolation
This work was performed in the independent `OsteoPatch_Repo_Professional` checkout. The pre-existing `OsteoPatch_Kiro_Handoff` checkout contained another worker's uncommitted work and was not used for source or Git mutations.

## Clean-clone baseline
Before implementation:
- Backend: **110 passed, 11 skipped**. Skips were optional torch/attribution/worker tests because the torch stack/runtime was absent.
- Reviewer frontend: **29 passed** and production build passed.
- Enterprise frontend: **2 passed** and production build passed.

## Final local software verification
The feature branch was rebased onto `main` revision `b40bf34e11a821880ebe2216b4303bbf1685d2ee` after four upstream commits landed, including the repository rename and additional cleanup regression tests. The full verification below was rerun after that rebase.

Executed from the isolated checkout after the repository changes:
- `python -m unittest discover -s tests/tooling -v`: **16 passed, 1 skipped**. The skipped test only attempts to create a filesystem symlink to prove the publication guard rejects it; Windows did not permit symlink creation for this process.
- `python scripts/check_repository.py`: **0 errors**.
- `python scripts/build_site.py`: **12 explicitly allowlisted publication files**.
- `python scripts/check_site.py`: **0 errors**.
- Backend pytest after rebasing onto current `main`: **112 passed, 11 skipped**, with the same optional torch/runtime reasons as the baseline.
- Blocking Ruff scope: passed.
- Mypy: passed across the configured 19 source files.
- Requirements compatibility shims: current.
- Dependency register: all 17 declared Python dependencies covered.
- Reviewer UI: **29 passed**; production Vite/TypeScript build passed.
- Enterprise UI: **2 passed**; production Vite/TypeScript build passed.
- `actionlint 1.7.12`: all workflow YAML passed syntax/static validation.
- `git diff --check`: no whitespace errors.

These are software/repository results. They are not clinical model validation and do not replace the frozen scientific evaluation.

## Static-site browser QA
Because the dedicated Browser plugin was unavailable in this session, the generated site was tested using the repository's installed Playwright package with **installed Microsoft Edge in an isolated headless context**. The QA server used an ephemeral loopback port; no internet-hosted site was modified.

Every page — Overview, Get started, Architecture, Model evidence, Operations and 404 — was exercised at:
- Desktop: **1440 × 1000**
- Mobile: **390 × 844**

Checks passed for:
- exactly one primary heading and meaningful rendered content;
- no horizontal overflow;
- no broken images after intentionally lazy images were scrolled into view;
- body type size at least 17 px desktop / 16 px mobile;
- keyboard skip-link focus;
- navigation from Overview → Model evidence → Get started;
- visible frozen viable-tumor recall `0.110345`;
- visible locked setup command `uv sync --locked`;
- no page errors or failed HTTP resources.

Temporary screenshots/report were kept under ignored `.maintenance/site-qa/` and are not part of the repository.

### QA harness incident
The first mobile QA run timed out because the temporary harness waited for **all** images to report `complete`, including below-the-fold images intentionally marked `loading="lazy"`. The site itself had no failing resource. The harness was corrected to scroll each image into view before testing completion; the same desktop/mobile suite then passed.

A separate fixed-port diagnostic also revealed that local port `8765` was already owned by an unrelated DENSER-WSI process. The final QA used an ephemeral port and did not stop or alter that unrelated process.

## Publication and deployment boundaries
- GitHub Pages workflow publishes only the static allowlist, never runtime images, model binaries, databases, credentials or arbitrary repository content.
- The AWS frontend workflow is **manual and fail-closed**. It does not create infrastructure, deploy the API/model container or upload the dataset. The protected `aws-demo` environment and non-secret resource identifiers are configured, but `AWS_DEPLOY_ENABLED=false` and no `AWS_ROLE_ARN` is present, so no AWS deployment can occur.
- Optional model/WSI capability workflows are manual and do not claim real-data validation.
- MCP examples are credential-free in Git, Kiro profiles are disabled by default and no tools are auto-approved.
- Draft release automation produces a prerelease for maintainer review; it is not clinical certification.

## Post-merge verification
- Pull request **#12** merged by squash to `main` as `9f3c9bca1c2241abc098fe37c6f7419a118bd55d`; the feature branch was automatically deleted.
- Pull-request CI and CodeQL passed. The push-to-`main` CI run also passed, and a manual post-merge CodeQL run passed for both Python and JavaScript/TypeScript.
- GitHub Pages build and deploy jobs passed for the exact merge SHA. The public site is `https://enksodsoon.github.io/Osteopatch/` with HTTPS enforced.
- The live public site was re-tested in isolated Microsoft Edge at 1440×1000 and 390×844. All six pages passed the same rendered-content, overflow, image, keyboard-navigation and resource-error checks as the local build.
- `main` is protected with strict required `quality-gate`, admin enforcement, linear history, and force-push/deletion disabled. Merge commits are disabled; squash and rebase remain available.
- Actions default to read-only tokens, only selected action families are allowed, and full-SHA pinning is enforced server-side. Secret scanning, push protection and Dependabot security updates are enabled.
- `aws-demo` is restricted to protected branches and now requires an explicit reviewer. Existing account/region/web-bucket/distribution identifiers are stored as environment variables; deployment remains disabled and the OIDC role is intentionally absent.

No AWS resource, model, dataset or paid API was modified during these post-merge checks.
