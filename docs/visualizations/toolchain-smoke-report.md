# Visualization Toolchain Smoke Report

**Date:** 11 October 2026 (Asia/Bangkok)  
**Scope:** Installed visualization tools, generated figures and diagrams, interactive studio, and plain-language presentation.

## Plain-language terms

- **Reference model:** stored results used for comparison; its original model file is unavailable.
- **Tuning candidate:** a later model experiment recorded as showing no demonstrated improvement.
- **Group-excluded evaluation:** each image group was left out of training once, scored separately, and combined with the other groups.
- **Recall:** share of actual images in a category recognized correctly. **Precision:** share of images labeled as a category that are correct. **Class-average F1:** equal-weight average of category scores that balance precision and recall.
- **Uncalibrated score:** a model score, not a chance estimate or disease probability.
- **Confusion matrix:** counts of true image categories compared with predicted categories.
- **SVG / PNG:** a scalable drawing / fixed-pixel image. **Codex tool connection (MCP):** a connection that lets Codex call another tool.

## Results

| Check | Result | Evidence |
|---|---|---|
| Python visualization imports | Pass | All pinned imports succeeded in the isolated CPU environment |
| Python sample outputs | Pass | Synthetic graph, chart, heat map, and model-view outputs were written under the ignored tool workspace |
| Mermaid diagrams | Pass | All source diagrams rendered to SVG; the reference-model pipeline also rendered to PNG |
| D2 diagram | Pass | Local software architecture rendered to SVG |
| Evidence synchronization | Pass | Stored metrics matched the three-category order, row count, group totals, and candidate outcome assertions |
| Confusion-matrix consistency | Pass | The stored JSON matrix matched the stored CSV and class counts |
| Studio build | Pass | TypeScript build and Vite production build completed |
| npm dependency audit | Pass | Zero vulnerabilities were reported at installation |
| Browser layout and interaction | Pass | Desktop and 390-pixel mobile review; theme toggle, graph selection, zoom controls, and PNG export checked |
| Static HTML figures | Pass | Recall comparison and confusion matrix opened locally; labels, counts, and limitations were visible |
| Browser console and network | Pass | Final studio view had no console errors; app requests stayed on the local machine |
| ECharts Codex renderer | Pass | Synthetic chart returned a valid SVG |
| Playwright Codex connection | Pass | Local page inspection and screenshot succeeded |
| Context7 Codex connection | Pass | Documentation lookup for the graph library succeeded |
| Diagrams Codex connection | Partial | Registered, but its Windows-side renderer smoke failed; direct command-line and Python renderers passed |

## Reader-facing terminology

The app and generated figures use plain names for the review API, image review backend, reference model, and tuning candidate. The evaluation description says each image was scored by a model that did not train on its group. The UI defines recall and class-average F1, names the three tissue categories in plain language, and explains that model scores are not chance estimates.

The candidate is marked `NO BENEFIT` because that is the stored evaluation outcome; the report explains that no improvement was demonstrated. The original reference-model file is unavailable, and the recovered file is only the class-scoring part of a model. No new image predictions were produced for this smoke check.

## Figures and diagrams

- [Interactive studio](../../tools/visualization-studio/src/App.tsx)
- Reference-model image-scoring flow (PNG and SVG)
- Reference and candidate class-recall comparison (interactive HTML)
- [Confusion matrix](confusion-matrix.html)
- [Local software architecture](software-architecture-local.svg)
- [Review request flow](review-backend-delegation.svg)
- Additional API access, image import, attribution, data provenance, cloud design, and persistence diagrams are listed in this folder.

## Limits and remaining evidence

- Browser checks cover local research tooling only. They do not establish clinical validity. It is unverified whether training and evaluation images came from separate patients.
- The reference-model binary and the matching image-encoder checkpoint were unavailable. Architecture figures are based on stored configuration and code records.
- The recovered model file contains only the class-scoring part of the model. It was not used to reinterpret saved image results.
- The cloud diagram shows a proposed design in source code. No live cloud deployment or cloud resource was checked.
- The Diagrams tool connection has a Windows rendering limitation; the direct rendering commands used for the deliverables passed.
- The generated JavaScript file is about 1.54 MB, slightly above the build tool's advisory size. This did not prevent the build or local browser review.
