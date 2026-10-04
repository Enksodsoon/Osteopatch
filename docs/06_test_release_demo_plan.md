# 06 — Test, release and demonstration plan

**Status:** no application tests have been run in this handoff. This is the required verification plan for Kiro. Requirement IDs come from [03](03_product_ux_and_acceptance.md).

## Test matrix

| Layer | Failure to exercise | Required result |
|---|---|---|
| Data | Unknown/blank class, CSV mismatch, duplicate key, corrupt image | Import fails with actionable error; no silent viable-tumor fallback |
| Independence | Patient/source/derivative/duplicate overlap | Split validation rejects the claim or requires an explicit reduced-scope design |
| Model | Wrong class order, NaN scores, incompatible bundle | No prediction is presented as successful |
| Serving | Training and serving resize/normalization differ | Contract test fails before deployment |
| Evaluation | Missing class, zero selected/flagged images | Undefined metrics explicitly unavailable; no fabricated denominator |
| Calibration | No validation data/uncalibrated output | UI shows the correct score type; no false probability guarantee |
| Review policy | Exact threshold equality, ties, known flags | Versioned deterministic flagging and order |
| Attribution | Wrong target class, disabled gradients, flat or failed map | Explicit failure or qualified output; no fake replacement overlay |
| Viewer | Resized map alignment, toggle off, zoom reset | Original remains inspectable; target/version visible |
| Audit | Double click, network retry, repeated idempotency key | One event for one accepted request |
| Concurrency | Two reviewers save the same revision | First succeeds; stale request receives conflict with recovery path |
| Security | Missing/expired token, cross-project object, arbitrary URL/path | Rejected; no unauthorized prediction, source label or review access |
| Resilience | Worker failure, timeout, duplicate event delivery | Bounded retries, explicit final error, no loss of prior reviews |
| Persistence | Local restart / cloud worker recycling | Saved state and event history remain intact |
| Export | Quoted notes, Unicode Thai, CSV formulas, broken model references | Valid UTF-8 export; escape formula-leading cells; preserve provenance |
| UX | Keyboard-only, narrow screen, slow response | Usable review flow with progress/errors and focus feedback |
| Cost | Job allowance exhausted, too many parallel jobs | Admission denied clearly; no unbounded background work |
| Operations | Export/restore, rollback, stack-scoped teardown | Evidence of restored content; only approved resources affected |

CSV export must neutralize spreadsheet formula injection in free-text cells while preserving the original value in an appropriate safe JSON export. Bound note length and avoid PHI.

## Evaluation report structure

Describe source/version, independent grouping, exclusions, class support, model configuration and selection procedure first. Then report actual baseline and selected-model metrics, confusion counts, per-patient results where meaningful, calibration limitations and review coverage/error trade-offs. Include example failures selected transparently; do not only show attractive heatmaps.

Do not compare published accuracy numbers as if they used identical patients, split units, preprocessing and targets. Label exploratory split results honestly. Post-review performance is not an independent benchmark unless the reference and study procedure were specified separately.

## Small usability demonstration — proposal

Ask an available domain reviewer to perform a defined patch-review task with gallery ordering and uncertainty ordering. Define the image set and procedure before observing results. Record review completion, saved/deferred counts, navigation errors and elapsed task time. This is an exploratory usability check, not proof of clinical efficiency or diagnostic safety. No user interview quotes or time savings are invented.

## Demonstration sequence

1. State the educational scope, actual data source and narrow three-class task.
2. Open the gallery and show multiple classes and unreviewed/flagged counts.
3. Select a curated image and run a real model job; identify cached output separately when used.
4. Show all class scores, calibration status and the concrete reason the image is prioritized.
5. Toggle actual attribution against original H&E; explain that the overlay is not segmentation or proof.
6. Make a deliberate correction or defer; save and reload to prove persistence.
7. Open history/export to show original prediction, human event, reviewer, versions and timestamp.
8. Show actual evaluation, a failure case, patient-independence limitations, and the local/export fallback.

The sequence is a script, not a claim these features already exist. Do not use a prerecorded UI as if it were a live system. A fallback recording can be used if labelled accurately, but it does not replace the required deployment evidence.

## Release criteria

All applicable data, model-contract, audit, authorization and safety tests must pass. Record exact commands, environment, commits and output. A failed usability/performance target may be accepted only with an explicit visible limitation and revised scope; a broken authorization or silent label-mapping error cannot be waved through.

A reproducible model and truthful reporting are required even if achieved accuracy is modest. Public sharing must not precede license/source and authentication review.

## Portable release inventory

Application source and dependency locks; official workflow version reference; source/reuse citations; data/retrieval manifest and permitted derivatives; trained bundle and hashes; exact split; evaluation; review-event exports; secret-free configuration; deployment/rollback/teardown instructions; actual test evidence and a list of unverified claims.

Restore in a new local directory before approving deletion. Confirm the owner can access the export outside the expiring workshop account. Review cloud storage, ECR images, logs and retained resources after stack deletion; a successful stack deletion is not proof of zero residual cost.
