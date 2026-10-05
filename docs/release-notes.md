## OsteoPatch Review — research preview

An educational, human-in-the-loop osteosarcoma patch-review workbench with source/QC context, immutable three-class predictions, revision-aware human decisions, qualified attribution and inspectable model limitations.

This repository also provides reproducible software checks, current developer/architecture guides, a static project website, contribution/security policies, pinned automation and opt-in MCP profiles.

### Important boundaries
- Not for diagnosis, treatment decisions, treatment-response prediction, prognosis or clinical reporting.
- Model scores are uncalibrated. Frozen viable-tumor recall is 0.110345; the exploratory evaluation is not patient-independent clinical validation.
- The original G4 binary is absent. The recovered attribution head has a separate identity.
- Source archives exclude runtime pixels, model binaries and review databases. Restoring an approved runtime bundle is a separate prerequisite.
- The historical AWS demo may run a different source revision and requires an approved deployment/access/cost configuration.
- The repository retains its proprietary license declaration; third-party materials have separate terms.

This is a draft prerelease for maintainer review. Confirm the exact revision, CI results, runtime distribution rights, security boundaries and deployment state before publishing. A release is not clinical certification.
