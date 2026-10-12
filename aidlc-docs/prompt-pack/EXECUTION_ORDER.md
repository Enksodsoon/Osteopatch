# Execution order and safe task assignment

This pack has 129 tasks because each feature is split at meaningful interface and acceptance boundaries. It is not a requirement to implement all 129 before showing a demo. Verify existing behavior and mark it NO_CHANGE_VERIFIED where justified. Never invent an acceptance receipt for a prerequisite simply to unblock a screen.

## Recommended working method

Start F001 in the actual checkout. Then use F002 and the foundation contracts to establish a reproducible, non-destructive test baseline. Assign one whole task file to one fresh agent session. A coordinator reviews each result and integrates only the accepted diff. Code and its prerequisite receipts must be available to every new task; the task prompt alone cannot supply files that have not been built.

Use one writer by default. Parallel work is permitted only after contracts are accepted, with separate worktrees, disjoint file ownership, independent databases/test output directories, and a designated integrator. App.tsx, central API/types files, schema migrations, global styles, lockfiles, and task status are integration-owned shared surfaces. A task branch in the same folder is NOT adequate isolation.

## Dependency-led demo route

The following closure includes core hardening, dashboard, disagreement/reporting, frozen model metrics, dataset integrity, real-image review, and a guided isolated demo. It omits new model training, calibrator fitting, WSI conversion, shared clinical deployment, and advanced governance. Many current features should require verification or a narrow extension, not reimplementation.

**52 prerequisite/feature/gate tasks in this proposed full demo closure.** This is a dependency count, not a duration estimate.

1. **F001** — Inventory the real baseline without changing product code.
2. **F002** — Create deterministic test fixtures and a throwaway integration database.
3. **F004** — Add a typed API client with cancellation and honest errors.
4. **U002** — Consolidate the editorial design tokens without redesigning behavior.
5. **F003** — Centralize authorization scope and explicit prediction selection.
6. **F007** — Verify and bound database connection lifetime and concurrent writes.
7. **U001** — Add stable navigation, deep links, and browser history.
8. **U003** — Standardize loading, empty, offline, and retry states.
9. **R008** — Harden patch zoom, pan, fit, fullscreen, and reset.
10. **F005** — Define a shared read-snapshot adapter for SQLite and cloud review state.
11. **F006** — Report real capabilities instead of optimistic feature flags.
12. **F009** — Lock model, image, and review provenance invariants in tests.
13. **R009** — Handle thumbnail and full-image loading failures explicitly.
14. **R001** — Make queue navigation cover the complete filtered result.
15. **U008** — Build the system and capability status screen.
16. **R010** — Display source metadata and physical scale without inventing magnification.
17. **F010** — Accept the foundation interfaces before adding feature screens.
18. **A001** — Implement the authoritative review statistics snapshot.
19. **D004** — Validate a dataset manifest before any import.
20. **M003** — Load frozen model evaluation evidence with exact provenance.
21. **R002** — Connect the workbench and reviewer to persistent queue context.
22. **R014** — Bound image prefetching and keep large queues responsive.
23. **D003** — Expose an inspectable per-asset provenance card.
24. **A002** — Build the Overview dashboard from real snapshot data.
25. **A004** — Create a precise AI–human disagreement query.
26. **A011** — Harden CSV/JSON exports and include exact provenance.
27. **D007** — Run deterministic decode, dimensions, and duplicate checks.
28. **M004** — Build the Model Performance and limitation-detail pages.
29. **U004** — Make the core reviewer layout accessible on tablet and phone.
30. **R003** — Prevent stale images, predictions, and forms during rapid navigation.
31. **Z001** — Select real curated demo scenarios and verify every claim.
32. **A003** — Add class distribution and review-progress charts with tables.
33. **A005** — Build the Disagreement Explorer with evidence drill-down.
34. **A006** — Compute review comparison matrices and per-class operational counts.
35. **D010** — Build the dataset explorer and integrity summary.
36. **R004** — Make ACCEPT, CORRECT, and DEFER explicit and scientifically consistent.
37. **X001** — Make contrastive attribution race-safe and honest in every state.
38. **Z002** — Create isolated, repeatable demo review sessions.
39. **A007** — Render comparison matrices and per-class drill-downs.
40. **R006** — Make save retries idempotent and reconcile unknown outcomes.
41. **Z003** — Build an honest start screen and first-run onboarding.
42. **Z005** — Create a safe one-command local demo launcher.
43. **A010** — Create a reproducible research review report page.
44. **R011** — Make the review timeline and save receipt auditable.
45. **R013** — Refresh dependent views after a confirmed review without fake optimism.
46. **Z006** — Package an offline rehearsal and clearly labeled replay fallback.
47. **A012** — Accept the dashboard-to-correction-to-report workflow end to end.
48. **Z004** — Add a guided walkthrough that drives real application state.
49. **Z007** — Run a complete browser demo acceptance suite on the exact release candidate.
50. **Z008** — Measure demo performance and enforce bounded resource use.
51. **Z009** — Create accurate GitHub documentation, screenshots, and demo presentation materials.
52. **Z011** — Issue a scoped release acceptance and an exact next-task handoff.

A smaller review-only rehearsal can stop after the core-review closure below. Do not call it the full dashboard/report/demo release. An existing equivalent can satisfy a dependency only after its contract and tests are recorded and accepted.

## Core-review closure

F001 → F002 → F004 → U002 → F003 → F007 → U001 → U003 → R008 → F005 → F006 → F009 → R009 → R001 → F010 → R002 → R014 → U004 → R003 → R004 → R006 → R011

## Public/shared deployment gate

Z010 is prepare-only unless separately authorized. Before any shared/public deployment, include E001/E002 and their dependencies, actual authentication, full object authorization tests, private asset access, and a compatible backend. An anonymous isolated demonstration may be read-only; do not add unauthenticated public writes just to demonstrate persistence.

## Optional modules

Similarity/embeddings: X004–X008 after their dependency closure. Teaching: T001–T008. True WSI: W001 first, then only approved spatial work. Research: M005–M010 and X009 with separate data/model approval. Enterprise: E001–E012 as required, rather than enabling unused administration menus.

## When a task is blocked

Return task ID, exact missing artifact/symbol/approval, actions already verified, and a minimal resolution. Do not invent outputs, skip the prerequisite, silently use a different model/data source, or consume paid resources. Independent unblocked work may be assigned by the coordinator, not self-started by the worker.

## Complete topological ordering

The ordering below is one valid serialization of the entire directed acyclic task graph. Phase folders are an organizational view; they do not override this ordering.

F001 → F002 → F004 → U002 → F003 → F007 → U001 → U003 → U005 → R008 → F005 → F006 → F009 → E001 → F008 → U006 → R009 → R001 → U008 → R010 → F010 → A001 → D004 → M003 → E002 → D001 → M001 → U007 → R002 → R014 → D003 → W010 → A002 → A004 → A008 → A011 → D005 → D007 → X004 → W001 → M004 → M005 → M011 → E003 → E007 → E010 → E014 → D002 → M006 → M002 → U004 → R003 → T001 → Z001 → W013 → A003 → A005 → A006 → R015 → D006 → D008 → D010 → X005 → X007 → M012 → W002 → W003 → E011 → D011 → M007 → E008 → R004 → X001 → T002 → T007 → Z002 → A007 → D009 → X006 → X008 → X009 → X010 → W004 → W006 → E012 → D012 → R005 → R006 → R007 → X002 → X003 → T003 → T004 → Z003 → Z005 → A010 → W005 → W007 → R011 → R012 → R013 → E005 → T005 → T006 → Z006 → A013 → W011 → W008 → W009 → A009 → A012 → E004 → E006 → T008 → W012 → W014 → Z004 → E009 → E013 → M008 → Z007 → M009 → M010 → Z008 → Z009 → Z010 → Z011 → Z012 → Z013
