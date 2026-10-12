# Proposal

## Why

Developers and collaborators need a single clear view of how OsteoPatch is assembled, how its API and review flow work, and what the model evidence does and does not establish. The available diagramming tools also need a source-backed catalog that distinguishes installed local tools from hosted, unavailable, or limited options.

## What Changes

- Install OpenSpec, Answer me with HTML, Netron, TensorBoard, and a local Excalidraw MCP server in user-level or isolated environments.
- Add an offline HTML guide with editable source draft, architecture and API diagrams, development and AI terminology, actual model evidence, and a visualization-tool catalog.
- Keep the existing app, API, training records, static site, and presentation files unchanged.

## Capabilities

### New Capabilities

None. This is a documentation and developer-tooling change; it does not add runtime behavior.

### Modified Capabilities

None.

## Impact

- Adds the guide under `docs/software-ai-visual-guide/` and this OpenSpec change.
- Adds repo-local OpenSpec configuration and generated Codex workflow skills.
- Adds user-level Codex/Python tools and registers a local Excalidraw MCP server.
- Changes no application API, model artifact, dependency lock, or deployment configuration.
