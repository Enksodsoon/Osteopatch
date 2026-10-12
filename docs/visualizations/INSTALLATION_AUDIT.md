# Visualization Toolchain Installation Audit

**Audit date:** 11 October 2026 (Asia/Bangkok)  
**Repository:** `OsteoPatch_Kiro_Handoff`  
**Result:** Local visualization studio and export toolchain installed and smoke-checked. Reader-facing figures and reports use public descriptions for model variants, software roles, and evaluation terms.

## Plain-language terms

- **Reference model:** the stored model results used for comparison. Its original model file is unavailable.
- **Tuning candidate:** a later model experiment. Its stored evaluation found no demonstrated improvement, and no final model file was created.
- **Group-excluded evaluation:** images were grouped; each group was kept out of training once, scored separately, and then combined with results from the other groups.
- **Recall:** the share of images in a category that the model recognized correctly.
- **Class-average F1:** an average across categories of a score that balances precision (how often a category prediction is correct) and recall. Each category has equal weight.
- **Uncalibrated score:** a model score that is not a chance estimate. A score of 0.8 does not mean an 80% probability of disease.
- **Confusion matrix:** a table counting the true image category against the model's predicted category.
- **SVG / PNG:** a scalable drawing format / a fixed-pixel image format. **CPU-only** means the isolated tools do not use GPU acceleration.
- **Codex tool connection (MCP):** a connection that lets Codex call a local or external tool.

## Checkout and safeguards

- The working branch was `main`, at commit `ff45761471cc75e74d8c1ed719578e30b472cb62`, two commits ahead of its remote tracking branch at inspection.
- The checkout already had unrelated tracked and untracked changes before this work. Those changes and both application lockfiles were preserved.
- Visualization packages are isolated in `.tools/visualization/.venv` and `tools/visualization-studio/node_modules`. Both are ignored by Git. No application dependency or canonical Python environment was changed.
- No patient image was uploaded or copied into the deliverables. No model training, cloud provisioning, existing model-weight overwrite, or clinical evaluation was performed.
- Local input inspection found 1,144 TIFF images; the images remain in place and are not included in the studio or reports.

## Installed and available tools

| Tool | Version / location | Result |
|---|---|---|
| Graphviz | 16.1.0, installed with Windows Package Manager | Passed SVG smoke render |
| D2 diagram tool | 0.9.0, installed with Windows Package Manager | Passed local architecture diagram render |
| Mermaid command-line renderer | 11.4.2, already installed | Rendered all Mermaid sources to SVG; rendered the model pipeline to PNG |
| Netron model viewer | 9.3.1, already installed and present in the isolated Python environment | Import and availability smoke passed; no full model file was available to open |
| Python | 3.12.10; uv 0.12.23 | Isolated environment created and smoke-checked |
| Node.js / npm | 24.19.0 / 11.17.0 | Isolated studio dependencies installed from its lockfile |

The isolated Python environment uses CPU processing and pins Altair 6.3.0, diagrams 0.25.1, graphviz 0.20.3, Kaleido 1.5.0, Matplotlib 3.11.2, NetworkX 3.6.1, NumPy 2.5.2, pandas 3.0.6, Plotly 7.1.0, PyVis 0.3.2, scikit-learn 1.9.1, SciPy 1.18.1, seaborn 0.13.2, TensorBoard 2.21.0, PyTorch 2.12.1 CPU, torchinfo 1.8.0, torchview 0.2.7, and torchvision 0.27.1 CPU. Altair and PyVis imported successfully; the smoke run also generated synthetic examples for Graphviz, Python Diagrams, Plotly/Kaleido, Matplotlib, TorchView, and TensorBoard.

The React studio uses React and ReactDOM 19.3.0, React Flow 12.12.0, D3 7.9.0, ECharts 6.1.0, Lucide 1.55.0, TypeScript 7.0.2, and Vite 8.3.4. `npm audit` reported zero vulnerabilities at installation.

In that list, React builds the page, React Flow makes the system map interactive, D3 draws the model-structure view, ECharts draws the measurements, and Vite runs and builds the studio. Graphviz, Mermaid, and D2 render the editable architecture diagrams. The Python image tools create the static figures and synthetic smoke examples.

## Reproducible local commands

Run from the repository root in PowerShell:

```powershell
winget install --exact --id Graphviz.Graphviz
winget install --exact --id Terrastruct.D2
uv venv --python 3.12 .tools/visualization/.venv
uv pip install --python .tools/visualization/.venv/Scripts/python.exe -r tools/visualization-studio/requirements.txt
npm --prefix tools/visualization-studio ci
& .tools/visualization/.venv/Scripts/python.exe tools/visualization-studio/scripts/sync_model_data.py
& .tools/visualization/.venv/Scripts/python.exe tools/visualization-studio/scripts/generate_figures.py
.\tools\visualization-studio\scripts\render_diagrams.ps1
npm --prefix tools/visualization-studio run build
npm --prefix tools/visualization-studio run dev -- --host 127.0.0.1
```

The render script reads editable Mermaid (`.mmd`) and D2 (`.d2`) sources under `docs/visualizations/`; it does not change application model records. The studio serves only its own directory and the visualization output directory through its development file allow-list.

## Codex tool connections and skills

- The existing ECharts tool connection (`mcp-echarts` 0.7.1) was reused and returned a synthetic chart successfully.
- Playwright MCP 0.0.83 and Context7 4.3.0 were registered for browser inspection and documentation lookup; both passed a small smoke check.
- The Diagrams tool connection 0.3.0 was registered. Its Windows rendering check failed because Windows could not locate the Mermaid renderer executable; a generic diagram request also failed on Windows text encoding. The upstream server additionally assumes Linux-only isolation calls. Graphviz, Mermaid, D2, and Python Diagrams work directly, so no upstream workaround was added.
- Project skills added under `.agents/skills/` cover model visualization and system architecture. The installed visualization guidance was reused. No slide-design skill was available in the installed skill catalog; this audit covers local figures and architecture, not slide-deck production.

## Evidence and reader wording

The studio, static figures, diagram labels, custom guidance, and this report call the two comparisons the **reference model** and the **tuning candidate**. Grouped evaluation, recall, class-average F1, confusion matrices, and scores that are not chance estimates are explained in the reader-facing materials. Class labels are shown as non-tumor tissue, viable tumor, and necrotic tissue.

The stored evaluation records contain 1,028 image patches across three categories and four groups. Category counts are 484, 290, and 254. The reference-model recall is 90.3%, 11.0%, and 86.6%; the tuning-candidate recall is 87.6%, 4.5%, and 88.2%. Class-average F1 is 0.562 for the reference model and 0.523 for the candidate. The recorded candidate outcome is `NO BENEFIT`, meaning the stored evaluation did not demonstrate an improvement. The source JSON and CSV confusion-matrix counts agreed during figure generation.

The original reference-model file is unavailable. A separately recovered file contains only the three-category scoring part, not the image encoder; the matching encoder file is also absent. The diagrams therefore show documented model structure, not a model loaded and evaluated by this studio. It is unverified whether training and evaluation images came from separate patients; patches from one biological sample may be related. These are exploratory research results, not clinical validation.

## Deliverables

- [Interactive visualization studio source](../../tools/visualization-studio/src/App.tsx)
- Reference-model image-scoring flow (editable source, SVG, and PNG) is in this directory.
- Reference-model and candidate recall comparison (interactive HTML) is in this directory.
- [Interactive confusion matrix](confusion-matrix.html) and [SVG export](confusion-matrix.svg)
- [Local architecture diagram](software-architecture-local.d2) and [rendered architecture](software-architecture-local.svg)
- Other editable architecture diagrams and their SVG exports are in this directory.
- [Toolchain smoke results](toolchain-smoke-report.md)

## Build and presentation notes

`npm run build` passed after the wording changes. The generated JavaScript file is about 1.54 MB (504 KB compressed), above the build tool's 500 KB advisory size. It also warned that two third-party `use client` markers are not preserved in the standalone bundle; the build and local browser review succeeded. The Python smoke could not find the Linux Libertine font and substituted Sans; image generation succeeded.

This audit does not claim the cloud design is deployed, that the missing model files have been recovered, or that the figures validate clinical performance.
