# OsteoPatch — 129-task index

**All tasks are planning briefs, not completed implementation.** Choose a release track in `EXECUTION_ORDER.md`, then obey dependencies and acceptance gates. Numerical filename order is not dependency order.

## Foundation, contracts, and safe integration — 10 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [F001](tasks/00_foundation/F001__inventory-the-real-baseline-without-changing-product-code.md) | Inventory the real baseline without changing product code | DEMO | None |
| [F002](tasks/00_foundation/F002__create-deterministic-test-fixtures-and-a-throwaway-integration-database.md) | Create deterministic test fixtures and a throwaway integration database | DEMO | F001 |
| [F003](tasks/00_foundation/F003__centralize-authorization-scope-and-explicit-prediction-selection.md) | Centralize authorization scope and explicit prediction selection | DEMO | F001, F002 |
| [F004](tasks/00_foundation/F004__add-a-typed-api-client-with-cancellation-and-honest-errors.md) | Add a typed API client with cancellation and honest errors | DEMO | F001 |
| [F005](tasks/00_foundation/F005__define-a-shared-read-snapshot-adapter-for-sqlite-and-cloud-review-state.md) | Define a shared read-snapshot adapter for SQLite and cloud review state | DEMO | F002, F003 |
| [F006](tasks/00_foundation/F006__report-real-capabilities-instead-of-optimistic-feature-flags.md) | Report real capabilities instead of optimistic feature flags | DEMO | F001, F003 |
| [F007](tasks/00_foundation/F007__verify-and-bound-database-connection-lifetime-and-concurrent-writes.md) | Verify and bound database connection lifetime and concurrent writes | DEMO | F002 |
| [F008](tasks/00_foundation/F008__make-schema-changes-versioned-and-test-migration-recovery.md) | Make schema changes versioned and test migration recovery | PLATFORM | F002, F007 |
| [F009](tasks/00_foundation/F009__lock-model-image-and-review-provenance-invariants-in-tests.md) | Lock model, image, and review provenance invariants in tests | DEMO | F002, F003 |
| [F010](tasks/00_foundation/F010__accept-the-foundation-interfaces-before-adding-feature-screens.md) | Accept the foundation interfaces before adding feature screens | DEMO | F003, F004, F005, F006, F007, F009 |

## Navigation and shared user interface — 8 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [U001](tasks/01_interface/U001__add-stable-navigation-deep-links-and-browser-history.md) | Add stable navigation, deep links, and browser history | DEMO | F004 |
| [U002](tasks/01_interface/U002__consolidate-the-editorial-design-tokens-without-redesigning-behavior.md) | Consolidate the editorial design tokens without redesigning behavior | DEMO | F001 |
| [U003](tasks/01_interface/U003__standardize-loading-empty-offline-and-retry-states.md) | Standardize loading, empty, offline, and retry states | DEMO | F004, U002 |
| [U004](tasks/01_interface/U004__make-the-core-reviewer-layout-accessible-on-tablet-and-phone.md) | Make the core reviewer layout accessible on tablet and phone | DEMO | U002, R002, R008 |
| [U005](tasks/01_interface/U005__add-light-and-dark-themes-with-safe-local-preferences.md) | Add light and dark themes with safe local preferences | PLATFORM | U002 |
| [U006](tasks/01_interface/U006__create-consistent-dialogs-keyboard-focus-and-safe-confirmations.md) | Create consistent dialogs, keyboard focus, and safe confirmations | PLATFORM | U002, U003 |
| [U007](tasks/01_interface/U007__add-discoverable-shortcut-help-and-a-bounded-command-menu.md) | Add discoverable shortcut help and a bounded command menu | PLATFORM | U001, U006 |
| [U008](tasks/01_interface/U008__build-the-system-and-capability-status-screen.md) | Build the system and capability status screen | DEMO | F006, U001, U003 |

## Patch viewer, queue, and human review — 15 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [R001](tasks/02_review/R001__make-queue-navigation-cover-the-complete-filtered-result.md) | Make queue navigation cover the complete filtered result | DEMO | F003, F005 |
| [R002](tasks/02_review/R002__connect-the-workbench-and-reviewer-to-persistent-queue-context.md) | Connect the workbench and reviewer to persistent queue context | DEMO | R001, U001, F004 |
| [R003](tasks/02_review/R003__prevent-stale-images-predictions-and-forms-during-rapid-navigation.md) | Prevent stale images, predictions, and forms during rapid navigation | DEMO | F004, R002 |
| [R004](tasks/02_review/R004__make-accept-correct-and-defer-explicit-and-scientifically-consistent.md) | Make ACCEPT, CORRECT, and DEFER explicit and scientifically consistent | DEMO | R003, F009 |
| [R005](tasks/02_review/R005__preserve-per-patch-note-drafts-without-autosubmitting-decisions.md) | Preserve per-patch note drafts without autosubmitting decisions | DEMO | R003, R004 |
| [R006](tasks/02_review/R006__make-save-retries-idempotent-and-reconcile-unknown-outcomes.md) | Make save retries idempotent and reconcile unknown outcomes | DEMO | F004, R004, F007 |
| [R007](tasks/02_review/R007__add-safe-review-keyboard-shortcuts.md) | Add safe review keyboard shortcuts | PLATFORM | R004, U007 |
| [R008](tasks/02_review/R008__harden-patch-zoom-pan-fit-fullscreen-and-reset.md) | Harden patch zoom, pan, fit, fullscreen, and reset | DEMO | F004, U002 |
| [R009](tasks/02_review/R009__handle-thumbnail-and-full-image-loading-failures-explicitly.md) | Handle thumbnail and full-image loading failures explicitly | DEMO | R008, U003 |
| [R010](tasks/02_review/R010__display-source-metadata-and-physical-scale-without-inventing-magnification.md) | Display source metadata and physical scale without inventing magnification | DEMO | F006, R008 |
| [R011](tasks/02_review/R011__make-the-review-timeline-and-save-receipt-auditable.md) | Make the review timeline and save receipt auditable | DEMO | R006, F009 |
| [R012](tasks/02_review/R012__add-bounded-bulk-review-with-per-item-outcomes.md) | Add bounded bulk review with per-item outcomes | PLATFORM | R006, U006, F003 |
| [R013](tasks/02_review/R013__refresh-dependent-views-after-a-confirmed-review-without-fake-optimism.md) | Refresh dependent views after a confirmed review without fake optimism | DEMO | R006, A001 |
| [R014](tasks/02_review/R014__bound-image-prefetching-and-keep-large-queues-responsive.md) | Bound image prefetching and keep large queues responsive | PLATFORM | R001, R009 |
| [R015](tasks/02_review/R015__add-patch-native-annotations-and-screenshot-export-without-requiring-wsi.md) | Add patch-native annotations and screenshot export without requiring WSI | PLATFORM | W010, R008, R009, A011, U006 |

## Dashboard, statistics, and failure analysis — 13 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [A001](tasks/03_analytics/A001__implement-the-authoritative-review-statistics-snapshot.md) | Implement the authoritative review statistics snapshot | DEMO | F005, F009 |
| [A002](tasks/03_analytics/A002__build-the-overview-dashboard-from-real-snapshot-data.md) | Build the Overview dashboard from real snapshot data | DEMO | A001, U001, U002, U003 |
| [A003](tasks/03_analytics/A003__add-class-distribution-and-review-progress-charts-with-tables.md) | Add class distribution and review-progress charts with tables | DEMO | A001, A002 |
| [A004](tasks/03_analytics/A004__create-a-precise-ai-human-disagreement-query.md) | Create a precise AI–human disagreement query | DEMO | A001, F003 |
| [A005](tasks/03_analytics/A005__build-the-disagreement-explorer-with-evidence-drill-down.md) | Build the Disagreement Explorer with evidence drill-down | DEMO | A004, U001, U003 |
| [A006](tasks/03_analytics/A006__compute-review-comparison-matrices-and-per-class-operational-counts.md) | Compute review comparison matrices and per-class operational counts | DEMO | A001, A004 |
| [A007](tasks/03_analytics/A007__render-comparison-matrices-and-per-class-drill-downs.md) | Render comparison matrices and per-class drill-downs | DEMO | A006, A005, U002 |
| [A008](tasks/03_analytics/A008__measure-review-yield-across-priority-bands-without-claiming-causal-benefit.md) | Measure review yield across priority bands without claiming causal benefit | PLATFORM | A001 |
| [A009](tasks/03_analytics/A009__capture-bounded-active-review-timing-and-productivity-events.md) | Capture bounded active-review timing and productivity events | PLATFORM | R013, F003 |
| [A010](tasks/03_analytics/A010__create-a-reproducible-research-review-report-page.md) | Create a reproducible research review report page | DEMO | A002, A003, A007 |
| [A011](tasks/03_analytics/A011__harden-csv-json-exports-and-include-exact-provenance.md) | Harden CSV/JSON exports and include exact provenance | DEMO | A001, F009 |
| [A012](tasks/03_analytics/A012__accept-the-dashboard-to-correction-to-report-workflow-end-to-end.md) | Accept the dashboard-to-correction-to-report workflow end to end | DEMO | A010, A011, R011, R013, A005 |
| [A013](tasks/03_analytics/A013__generate-a-paginated-research-review-pdf-from-an-accepted-snapshot.md) | Generate a paginated research-review PDF from an accepted snapshot | PLATFORM | A010, A011, U004 |

## Dataset, source groups, provenance, and quality — 12 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [D001](tasks/04_data/D001__add-versioned-dataset-and-source-group-metadata-without-inventing-patients.md) | Add versioned dataset and source-group metadata without inventing patients | PLATFORM | F003, F008 |
| [D002](tasks/04_data/D002__build-source-group-list-and-group-detail-pages.md) | Build source-group list and group-detail pages | PLATFORM | D001, A001, U001 |
| [D003](tasks/04_data/D003__expose-an-inspectable-per-asset-provenance-card.md) | Expose an inspectable per-asset provenance card | DEMO | F003, R010 |
| [D004](tasks/04_data/D004__validate-a-dataset-manifest-before-any-import.md) | Validate a dataset manifest before any import | PLATFORM | F003, F009 |
| [D005](tasks/04_data/D005__implement-private-bounded-upload-quarantine-for-approved-images.md) | Implement private, bounded upload quarantine for approved images | PLATFORM | D004, F003 |
| [D006](tasks/04_data/D006__build-upload-progress-validation-preview-and-import-confirmation.md) | Build upload progress, validation preview, and import confirmation | PLATFORM | D005, U006 |
| [D007](tasks/04_data/D007__run-deterministic-decode-dimensions-and-duplicate-checks.md) | Run deterministic decode, dimensions, and duplicate checks | PLATFORM | D004 |
| [D008](tasks/04_data/D008__add-configurable-image-quality-heuristics-without-claiming-pathology-diagnosis.md) | Add configurable image-quality heuristics without claiming pathology diagnosis | RESEARCH | D007 |
| [D009](tasks/04_data/D009__add-a-manual-qc-decision-queue-with-versioned-reasons.md) | Add a manual QC decision queue with versioned reasons | PLATFORM | D007, D008, U006, F003 |
| [D010](tasks/04_data/D010__build-the-dataset-explorer-and-integrity-summary.md) | Build the dataset explorer and integrity summary | DEMO | F003, D003, D007, A001, U001 |
| [D011](tasks/04_data/D011__add-project-scoped-global-search-over-existing-records.md) | Add project-scoped global search over existing records | PLATFORM | F003, D002, U001 |
| [D012](tasks/04_data/D012__save-and-restore-personal-filtered-views.md) | Save and restore personal filtered views | PLATFORM | R002, D011, F003 |

## Attribution, similar patches, and embeddings — 10 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [X001](tasks/05_explainability/X001__make-contrastive-attribution-race-safe-and-honest-in-every-state.md) | Make contrastive attribution race-safe and honest in every state | DEMO | F004, R003, F009 |
| [X002](tasks/05_explainability/X002__synchronize-original-and-attribution-side-by-side-views.md) | Synchronize original and attribution side-by-side views | PLATFORM | X001, R008 |
| [X003](tasks/05_explainability/X003__persist-and-verify-attribution-artifact-provenance-and-cache-keys.md) | Persist and verify attribution artifact provenance and cache keys | PLATFORM | F009, X001 |
| [X004](tasks/05_explainability/X004__extract-versioned-embeddings-with-the-existing-approved-encoder.md) | Extract versioned embeddings with the existing approved encoder | PLATFORM | F009, D004 |
| [X005](tasks/05_explainability/X005__implement-exact-similar-patch-retrieval-over-approved-embeddings.md) | Implement exact similar-patch retrieval over approved embeddings | PLATFORM | X004, F003 |
| [X006](tasks/05_explainability/X006__show-similar-reviewed-patches-as-an-educational-comparison-panel.md) | Show similar reviewed patches as an educational comparison panel | PLATFORM | X005, R002 |
| [X007](tasks/05_explainability/X007__precompute-a-reproducible-two-dimensional-embedding-projection.md) | Precompute a reproducible two-dimensional embedding projection | PLATFORM | X004 |
| [X008](tasks/05_explainability/X008__build-an-interactive-embedding-explorer-with-linked-image-inspection.md) | Build an interactive embedding explorer with linked image inspection | PLATFORM | X007, X005, U001 |
| [X009](tasks/05_explainability/X009__flag-representation-outliers-as-research-review-candidates.md) | Flag representation outliers as research review candidates | RESEARCH | X005, X007 |
| [X010](tasks/05_explainability/X010__add-optional-umap-or-t-sne-projections-as-explicitly-exploratory-artifacts.md) | Add optional UMAP or t-SNE projections as explicitly exploratory artifacts | RESEARCH | X004, X007, M006 |

## Teaching, quizzes, and approved knowledge — 8 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [T001](tasks/06_teaching/T001__create-faculty-approved-teaching-references-and-explanations.md) | Create faculty-approved teaching references and explanations | PLATFORM | F003, F008, D003 |
| [T002](tasks/06_teaching/T002__implement-blind-first-learner-response-contracts.md) | Implement blind-first learner response contracts | PLATFORM | T001, F003 |
| [T003](tasks/06_teaching/T003__build-the-blind-first-quiz-and-staged-feedback-screen.md) | Build the blind-first quiz and staged feedback screen | PLATFORM | T002, U004 |
| [T004](tasks/06_teaching/T004__create-bounded-quiz-sets-from-approved-teaching-items.md) | Create bounded quiz sets from approved teaching items | PLATFORM | T001, T002 |
| [T005](tasks/06_teaching/T005__add-teaching-case-discussion-and-faculty-notes.md) | Add teaching-case discussion and faculty notes | PLATFORM | T001, T003 |
| [T006](tasks/06_teaching/T006__report-learning-activity-without-overstating-educational-efficacy.md) | Report learning activity without overstating educational efficacy | PLATFORM | T002, T004 |
| [T007](tasks/06_teaching/T007__implement-an-approved-content-help-assistant-with-allowlisted-actions.md) | Implement an approved-content help assistant with allowlisted actions | PLATFORM | T001, F006, U001, U007 |
| [T008](tasks/06_teaching/T008__accept-teaching-privacy-blinding-and-reference-integrity.md) | Accept teaching privacy, blinding, and reference integrity | PLATFORM | T003, T004, T005, T006, T007 |

## Real whole-slide imaging and annotations — 14 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [W001](tasks/07_whole_slide/W001__establish-the-real-slide-capability-and-spatial-provenance-gate.md) | Establish the real-slide capability and spatial provenance gate | PLATFORM | F006, D004 |
| [W002](tasks/07_whole_slide/W002__add-a-provenance-bearing-local-conversion-adapter-for-one-approved-format.md) | Add a provenance-bearing local conversion adapter for one approved format | RESEARCH | W001, D005 |
| [W003](tasks/07_whole_slide/W003__implement-a-level-0-tile-and-coordinate-manifest.md) | Implement a level-0 tile and coordinate manifest | PLATFORM | W001, D001 |
| [W004](tasks/07_whole_slide/W004__serve-authorized-deep-zoom-tiles-with-bounded-caching.md) | Serve authorized Deep Zoom tiles with bounded caching | PLATFORM | W003, F003 |
| [W005](tasks/07_whole_slide/W005__build-the-real-wsi-viewer-with-navigator-and-honest-scale.md) | Build the real WSI viewer with navigator and honest scale | PLATFORM | W004, U002, U001 |
| [W006](tasks/07_whole_slide/W006__create-a-low-resolution-tissue-background-mask-as-a-qc-artifact.md) | Create a low-resolution tissue/background mask as a QC artifact | RESEARCH | W003, D008 |
| [W007](tasks/07_whole_slide/W007__plan-and-execute-bounded-patch-extraction-jobs.md) | Plan and execute bounded patch extraction jobs | PLATFORM | W003, W006, M001 |
| [W008](tasks/07_whole_slide/W008__overlay-real-tile-predictions-on-the-whole-slide.md) | Overlay real tile predictions on the whole slide | PLATFORM | W005, W007, M002 |
| [W009](tasks/07_whole_slide/W009__summarize-analyzed-tile-counts-and-conditional-area-coverage-safely.md) | Summarize analyzed tile counts and conditional area coverage safely | RESEARCH | W007, M002, A001 |
| [W010](tasks/07_whole_slide/W010__store-point-and-rectangle-annotations-with-revisions-and-coordinate-integrity.md) | Store point and rectangle annotations with revisions and coordinate integrity | PLATFORM | F003, F008, R010 |
| [W011](tasks/07_whole_slide/W011__build-a-point-rectangle-annotation-editor-and-overlay-toggle.md) | Build a point/rectangle annotation editor and overlay toggle | PLATFORM | W010, W005, U006 |
| [W012](tasks/07_whole_slide/W012__export-annotated-screenshots-and-machine-readable-spatial-provenance.md) | Export annotated screenshots and machine-readable spatial provenance | PLATFORM | W011, A011 |
| [W013](tasks/07_whole_slide/W013__extend-annotation-storage-with-validated-polygon-geometry.md) | Extend annotation storage with validated polygon geometry | PLATFORM | W010, F008 |
| [W014](tasks/07_whole_slide/W014__build-a-keyboard-accessible-polygon-editor-for-patches-and-real-slides.md) | Build a keyboard-accessible polygon editor for patches and real slides | PLATFORM | W013, R015, W011, U006 |

## Inference, evaluation, calibration, and research — 12 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [M001](tasks/08_model/M001__define-bounded-inference-jobs-and-durable-progress-without-running-a-model.md) | Define bounded inference jobs and durable progress without running a model | PLATFORM | F003, F008, F009 |
| [M002](tasks/08_model/M002__connect-a-bounded-cpu-worker-to-approved-model-inference.md) | Connect a bounded CPU worker to approved model inference | PLATFORM | M001, F009, D004 |
| [M003](tasks/08_model/M003__load-frozen-model-evaluation-evidence-with-exact-provenance.md) | Load frozen model evaluation evidence with exact provenance | DEMO | F009 |
| [M004](tasks/08_model/M004__build-the-model-performance-and-limitation-detail-pages.md) | Build the Model Performance and limitation-detail pages | DEMO | M003, U001, U002 |
| [M005](tasks/08_model/M005__compute-calibration-diagnostics-without-fitting-or-changing-the-model.md) | Compute calibration diagnostics without fitting or changing the model | RESEARCH | M003 |
| [M006](tasks/08_model/M006__create-a-group-aware-research-split-and-experiment-protocol-gate.md) | Create a group-aware research split and experiment protocol gate | RESEARCH | D001, F009 |
| [M007](tasks/08_model/M007__add-an-optional-calibration-experiment-behind-a-strict-approval-gate.md) | Add an optional calibration experiment behind a strict approval gate | RESEARCH | M005, M006 |
| [M008](tasks/08_model/M008__create-a-curated-training-candidate-pool-from-reviewed-data.md) | Create a curated training-candidate pool from reviewed data | RESEARCH | D009, E006, M006 |
| [M009](tasks/08_model/M009__build-an-active-learning-selection-proposal-not-automatic-labeling.md) | Build an active-learning selection proposal, not automatic labeling | RESEARCH | M008, X004, M006 |
| [M010](tasks/08_model/M010__build-a-reproducible-candidate-model-experiment-runner.md) | Build a reproducible candidate-model experiment runner | RESEARCH | M006, M008, M001 |
| [M011](tasks/08_model/M011__display-model-and-artifact-lineage-as-an-evidence-graph.md) | Display model and artifact lineage as an evidence graph | PLATFORM | M003, F009 |
| [M012](tasks/08_model/M012__create-versioned-input-output-drift-summaries-with-limited-claims.md) | Create versioned input/output drift summaries with limited claims | RESEARCH | M001, X004, A001 |

## Identity, collaboration, governance, and operations — 14 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [E001](tasks/09_enterprise/E001__separate-demo-identity-from-real-shared-deployment-authentication.md) | Separate demo identity from real shared-deployment authentication | PLATFORM | F001, F003 |
| [E002](tasks/09_enterprise/E002__enforce-a-complete-permission-matrix-across-reads-and-mutations.md) | Enforce a complete permission matrix across reads and mutations | PLATFORM | E001, F003 |
| [E003](tasks/09_enterprise/E003__build-project-membership-and-user-administration-screens.md) | Build project, membership, and user administration screens | PLATFORM | E002, U006 |
| [E004](tasks/09_enterprise/E004__add-local-in-app-notifications-without-external-scheduling.md) | Add local in-app notifications without external scheduling | PLATFORM | E002, R013 |
| [E005](tasks/09_enterprise/E005__store-independent-reviewer-assessments-for-multi-rater-studies.md) | Store independent reviewer assessments for multi-rater studies | RESEARCH | E002, F008, R006 |
| [E006](tasks/09_enterprise/E006__add-adjudication-research-batch-sign-off-and-agreement-reporting.md) | Add adjudication, research batch sign-off, and agreement reporting | RESEARCH | E005, U006 |
| [E007](tasks/09_enterprise/E007__connect-the-model-registry-ui-to-real-artifact-and-evidence-records.md) | Connect the model registry UI to real artifact and evidence records | PLATFORM | E002, M003, F009 |
| [E008](tasks/09_enterprise/E008__verify-promotion-and-rollback-gates-against-the-actual-inference-runtime.md) | Verify promotion and rollback gates against the actual inference runtime | PLATFORM | E007, M002, M006, E010 |
| [E009](tasks/09_enterprise/E009__build-a-drift-and-operational-alert-dashboard.md) | Build a drift and operational-alert dashboard | PLATFORM | M012, E002, E004 |
| [E010](tasks/09_enterprise/E010__expose-a-verifiable-audit-log-without-claiming-tamper-proof-storage.md) | Expose a verifiable audit log without claiming tamper-proof storage | PLATFORM | E002, F009 |
| [E011](tasks/09_enterprise/E011__implement-a-verified-backup-and-restore-rehearsal.md) | Implement a verified backup and restore rehearsal | PLATFORM | F008, E010 |
| [E012](tasks/09_enterprise/E012__create-retention-controls-and-deletion-dry-runs-with-safe-holds.md) | Create retention controls and deletion dry-runs with safe holds | PLATFORM | E011, E010 |
| [E013](tasks/09_enterprise/E013__add-an-approval-gated-external-notification-delivery-adapter.md) | Add an approval-gated external notification delivery adapter | PLATFORM | E004, E002, E010 |
| [E014](tasks/09_enterprise/E014__publish-accurate-openapi-documentation-and-a-read-only-developer-status-view.md) | Publish accurate OpenAPI documentation and a read-only developer status view | PLATFORM | F006, E002, U001 |

## Guided demo, packaging, deployment, and handoff — 13 tasks

| Task | Deliverable | Track | Required accepted tasks |
|---|---|---|---|
| [Z001](tasks/10_demo_release/Z001__select-real-curated-demo-scenarios-and-verify-every-claim.md) | Select real curated demo scenarios and verify every claim | DEMO | F006, F009, D003, M003 |
| [Z002](tasks/10_demo_release/Z002__create-isolated-repeatable-demo-review-sessions.md) | Create isolated, repeatable demo review sessions | DEMO | Z001, F005, F007 |
| [Z003](tasks/10_demo_release/Z003__build-an-honest-start-screen-and-first-run-onboarding.md) | Build an honest start screen and first-run onboarding | DEMO | Z002, U008, U001 |
| [Z004](tasks/10_demo_release/Z004__add-a-guided-walkthrough-that-drives-real-application-state.md) | Add a guided walkthrough that drives real application state | DEMO | Z003, A012, M004, X001 |
| [Z005](tasks/10_demo_release/Z005__create-a-safe-one-command-local-demo-launcher.md) | Create a safe one-command local demo launcher | DEMO | Z002, F006, U008 |
| [Z006](tasks/10_demo_release/Z006__package-an-offline-rehearsal-and-clearly-labeled-replay-fallback.md) | Package an offline rehearsal and clearly labeled replay fallback | DEMO | Z005, Z001, A011 |
| [Z007](tasks/10_demo_release/Z007__run-a-complete-browser-demo-acceptance-suite-on-the-exact-release-candidate.md) | Run a complete browser demo acceptance suite on the exact release candidate | DEMO | Z004, Z006, R009, A012, M004, D010 |
| [Z008](tasks/10_demo_release/Z008__measure-demo-performance-and-enforce-bounded-resource-use.md) | Measure demo performance and enforce bounded resource use | DEMO | Z005, Z007, R014 |
| [Z009](tasks/10_demo_release/Z009__create-accurate-github-documentation-screenshots-and-demo-presentation-materials.md) | Create accurate GitHub documentation, screenshots, and demo presentation materials | DEMO | Z007, M004, A010 |
| [Z010](tasks/10_demo_release/Z010__prepare-and-gate-a-compatible-frontend-plus-backend-deployment.md) | Prepare and gate a compatible frontend-plus-backend deployment | GATED_DEPLOY | Z007, Z008, Z009, F006 |
| [Z011](tasks/10_demo_release/Z011__issue-a-scoped-release-acceptance-and-an-exact-next-task-handoff.md) | Issue a scoped release acceptance and an exact next-task handoff | DEMO | Z007, Z008, Z009 |
| [Z012](tasks/10_demo_release/Z012__build-the-animated-html-demo-presentation-using-real-application-evidence.md) | Build the animated HTML demo presentation using real application evidence | PLATFORM | Z009, A010, M004 |
| [Z013](tasks/10_demo_release/Z013__record-a-reproducible-application-only-demo-video-and-fallback-manifest.md) | Record a reproducible application-only demo video and fallback manifest | PLATFORM | Z007, Z009, Z006 |

