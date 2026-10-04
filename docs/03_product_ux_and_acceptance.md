# 03 — Product, UX and numbered acceptance criteria

These are **proposed requirements**, not an implemented interface. See [the brief](../PROJECT_BRIEF.md) for fixed scope and [the contracts](08_data_and_api_contracts.md) for data structures.

## Product story

A reviewer opens a project containing many patches. A gallery gives a quick overview of suggested classes and which images need attention. The reviewer opens a patch, compares original H&E with optional attribution, reads the score distribution and review reasons, then accepts, corrects or defers the result. The history preserves exactly what the model originally returned and what the human did later.

The differentiating demonstration is not “an AI knows the answer.” It is “a model offers a testable suggestion, makes uncertainty visible, and supports accountable human review.”

## Screens

**Workbench.** A gallery/list with thumbnails, canonical class label, model score, review flag and review status. Filters cover predicted class, unresolved/accepted/corrected/deferred, and flagged/unflagged. Sort by review priority, score or image ID. Show counts as dataset/workflow counts, not patient outcomes.

**Image detail.** Desktop uses three areas: image list/navigation; large original-image viewer; scores and review controls. The original view supports zoom/pan and a reset control. An attribution toggle, opacity control and legend expose its target class and limitations. The original H&E coloration is not restyled. The sidebar displays all three scores, calibration status and why review was suggested.

**Review history/export.** Show model version, original prediction, human actions, reason, reviewer role, timestamps and revisions. Corrections are new events. Export CSV/JSON with provenance and disclaimer. A “revert” creates another event rather than deleting history.

**Model and dataset card.** Present intended use, actual source, independent-patient limitation, split method, metrics, calibration limitations, source attribution, model version and known failures. Missing measurements remain explicitly unavailable.

## Interaction rules

Proposed shortcuts: left/right move between images; 1/2/3 choose a human class; U marks uncertainty; Enter saves the current deliberate action. Avoid autosaving accidental keypresses. Show the active selection and a clear saved/unsaved state. A skip navigates without implying agreement.

Use text/icons as well as color. Controls have accessible names and visible focus. Keyboard navigation must not trap users inside the image viewer. Small screens place the viewer above review controls; important buttons never disappear behind a fixed toolbar.

The reviewer can accept, correct or defer. “Mixed tissue”, “image quality”, “insufficient context” and “other” are reason codes for deferral/correction, not model classes. Optional free text has length limits and a reminder not to enter personal health information.

Default review mode does not expose the reference label in HTML/API payloads. A separate teaching/evaluation role may reveal it deliberately. Merely hiding a field with CSS does not prevent label leakage. Student suggestions remain identified as student reviews, not expert ground truth.

## Acceptance criteria

| ID | Requirement and observable acceptance |
|---|---|
| FR-01 | Gallery loads the approved manifest, paginates, and retains filters while opening/closing details. |
| FR-02 | Every model output uses the explicit three-class map; no alphabetical-directory inference is allowed. |
| FR-03 | A real model job can be requested for a curated image; the UI distinguishes pending, running, complete, failed and cached results. |
| FR-04 | All three model scores and the score/calibration type are shown; missing scores never appear as zeros. |
| FR-05 | Flagging and queue order match the versioned review policy; all images remain manually reviewable. |
| FR-06 | Attribution is tied to an explicit class/model/image hash, toggles off completely, and is described as attribution, not segmentation. |
| FR-07 | Accept/correct/defer persists after reload; the old source label and model prediction remain unchanged. |
| FR-08 | Every saved action records actor, reason, server timestamp, prediction ID and revision; retries do not create duplicate events. |
| FR-09 | Competing edits return a conflict and ask the reviewer to reload/resolve; neither reviewer silently overwrites the other. |
| FR-10 | CSV/JSON export contains the complete relevant history, source/model versions and educational disclaimer. |
| FR-11 | Model/dataset cards expose actual evidence and limitations; unmeasured fields read “Not measured”. |
| FR-12 | Source labels are absent from ordinary reviewer responses and available only in explicitly authorized teaching/evaluation views. |
| SAF-01 | Workbench and exports include the educational-only disclaimer. |
| SAF-02 | No patient diagnosis, treatment-response score, survival estimate or patient-level necrosis percentage is generated. |
| SAF-03 | Unknown/corrupt/out-of-scope inputs are rejected or explicitly deferred rather than assigned a guessed tissue class. |
| SAF-04 | A human correction never triggers automatic training or changes a locked benchmark label. |
| SAF-05 | No invented image-specific morphology narrative or stock heatmap appears as model evidence. |
| NFR-01 | All essential review actions are keyboard accessible; state is not communicated by color alone. |
| NFR-02 | Local review state survives application restart; cloud state survives Lambda instance recycling. |
| NFR-03 | A failed model/attribution request leaves the original image and review history usable, with explicit error status. |
| NFR-04 | Proposed performance targets: warm prediction p95 ≤3 s, cached detail load p95 ≤2 s, save acknowledgment p95 ≤2 s under an agreed small-team test. Measure, do not assert. |
| NFR-05 | Versioned API/model/data identifiers accompany saved results; training and serving preprocessing agree. |
| SEC-01 | Cloud write endpoints require verified authentication and authorization for the single approved project. |
| SEC-02 | No secrets, tokens or image payloads enter logs; no arbitrary URL fetch or arbitrary filesystem path is accepted. |
| OPS-01 | Deployment and deletion operate only on an approved named stack/resource inventory; workshop assets belonging to others are untouched. |
| OPS-02 | A tested portable export exists before teardown or account expiry. |

## Scope control

Essential release: curated gallery, real inference, scores, uncertainty ordering, original/attribution view, human review, history, export and model/data card. Add a public upload workflow, full WSI navigation, multi-tenant administration, Bedrock narratives, complex dashboards or continual learning only through a new requirement/approval. None is necessary to demonstrate the original pain point.
