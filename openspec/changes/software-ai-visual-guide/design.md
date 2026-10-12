# Design

## Context

The repository already documents the architecture, API contracts, and model limitations. The G4 evaluation metrics and fold histories are tracked, but model weight files and TensorBoard event logs are absent. The task is documentation and user-level tooling only.

## Goals / Non-Goals

**Goals:**

- Produce one offline HTML guide grounded in current source docs and frozen evaluation files.
- Install the requested local tools without changing OsteoPatch's app dependencies.
- Preserve existing uncommitted files and make source provenance visible in the guide.

**Non-Goals:**

- Change or expose runtime API behavior, run training or inference, publish to a cloud service, or include source images, sample rows, credentials, or patient identifiers.
- Claim clinical validity or inspect a model binary that is not present.

## Decisions

- Use the Answer me with HTML skill to render a Markdown source draft into a single-file page in `docs/software-ai-visual-guide/`. Keep diagrams as text or embed the local fold-history chart in the page.
- Use OpenSpec with `skip_specs: true` because the work changes docs and developer tooling, not observable product behavior.
- Install the npm CLI and HTML skill globally for the current user. Install Netron and TensorBoard as isolated `uv` tools. Build Excalidraw from the existing MIT-licensed checkout and register it as a local stdio MCP server after the successful handshake.
- Reuse existing Draw.io, Mermaid, PlantUML, ECharts, AntV, slide, and design tools. Catalog available app connectors without sending the guide or repo data to them.
- Source project claims from `docs/architecture.md`, `docs/08_data_and_api_contracts.md`, `docs/model-evidence.md`, `app/g6/backend/osteopatch/app.py`, and the frozen G4 evaluation records. Mark the training-loss series as training loss, not validation performance.

## Risks / Trade-offs

- No compatible model weights or TensorBoard event files exist → document Netron and TensorBoard as installed tools for future use and keep the guide's current project evidence sourced from tracked JSON/CSV.
- Excalidraw export can send a diagram to an external site when explicitly used → register only the local MCP server and note that export limitation in the catalog.
- The source repository is already dirty → add new files only and preserve all existing paths.
