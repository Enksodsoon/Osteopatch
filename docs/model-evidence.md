# Model evidence and claim boundaries

## Intended use
Educational/research patch review only. Not for diagnosis, ruling out tumor, treatment decisions, treatment-response prediction, prognosis or clinical reporting. Software verification and model validation are different activities.

## Population and frozen evaluation
The full local source collection contains **1,144 patches**. The frozen G4 pooled out-of-fold evaluation uses **1,028 eligible patches** across four case/slide groups. The historical public demo is a **50-image subset**. These are different denominators.

Authoritative values: [overall-oof-metrics.json](../aidlc-docs/inception/model/g4/overall-oof-metrics.json).

| Metric | Frozen value |
|---|---:|
| Macro-F1 | 0.562311 |
| Balanced accuracy | 0.626460 |
| Secondary accuracy | 0.670233 |
| VIABLE_TUMOR recall | **0.110345** |

The viable-tumor weakness is a major limitation, not a footnote. These values must not be rounded into a claim of diagnostic reliability. They are not prospective, external or patient-independent validation. Patient-level independence is unverified; one fold is single-class, some per-group class supports are very small, and patches are not independent patients. Scores are uncalibrated class scores, not disease probabilities.

## Artifact identity
| Artifact | Identity and status |
|---|---|
| Original G4 bundle | `baseline-frozen-g4`; binary absent; frozen evaluation and immutable predictions retained |
| Recovered head | `g4-behavioral-recovery-r1`; separate behavioral reconstruction for qualified attribution, not the original classifier |

Original SHA-256:
```text
01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63
```
Recovered-head SHA-256:
```text
ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73
```

[Runtime constants](../app/g6/backend/osteopatch/config.py) enforce separate identities. Agreement with surviving predictions does not establish that the recovered head has the original model's weights, new-image behavior, generalization or evaluation validity. Never assign the old hash to a different file.

## Review and explanation
Canonical model outputs remain `NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`. Mixed, uncertain, deferred and poor-quality are review/QC states. Human corrections are append-only, separate from predictions and do not silently retrain anything.

Contrastive Grad-CAM describes model behavior. It is not tissue segmentation, a causal explanation or a diagnosis. Missing pixels, invalid identities or unavailable model dependencies must be disclosed; do not fabricate a substitute heatmap.

## Supporting records
[Dataset card](../aidlc-docs/inception/data/dataset-card.md) · [G4 model card](../aidlc-docs/inception/model/g4/model-card-baseline.md) · [Limitations catalog](../app/g6/backend/osteopatch/limitations.py) · [Original evaluation plan](02_model_and_evaluation_plan.md).

New experiments require a new dated record and appropriate authorization. Do not overwrite frozen evaluations while improving repository presentation.
