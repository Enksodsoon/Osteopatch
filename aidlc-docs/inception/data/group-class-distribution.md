# Group × class distribution — G2 (OsteoPatch Review)

**Status:** G2 offline/deterministic. Built from the existing `canonical_manifest.csv` under the **ratified** label policy. No pixels, no network, no AWS. Data file companion: `group_class_distribution.csv`.

**Grouping unit:** the 4 recovered **case/slide-group** tokens (`Case 3`, `Case 4`, `Case 48`, `P9`). These are case/slide ids (filename + PathDB subjectId + Training-Set/set folders, published count 4). No source proves true biological patient IDs — this is **case/slide-group independent**, NOT patient-independent. See `patient_mapping_evidence.md`.

## Canonical label counts (whole dataset, after ratified map)

| Canonical label | Trainable count |
|---|---|
| NON_TUMOR | 536 |
| VIABLE_TUMOR | 292 |
| NECROSIS | 263 |
| **Trainable total** | **1,091** |
| MIXED_VIABLE_NECROTIC (review-only, excluded from 3-class) | 53 |
| **Grand total (retained in manifest)** | **1,144** |

## Group × canonical label — counts

| Group | Size | Trainable | NON_TUMOR | VIABLE_TUMOR | NECROSIS | MIXED excluded | #learned classes present |
|---|---|---|---|---|---|---|---|
| Case 3 | 285 | 284 | 110 | 3 | 171 | 1 | 3 |
| Case 4 | 277 | 255 | 78 | 87 | 90 | 22 | 3 |
| Case 48 | 370 | 340 | 136 | 202 | 2 | 30 | 3 |
| P9 | 212 | 212 | 212 | 0 | 0 | 0 | 1 |
| **Total** | **1,144** | **1,091** | **536** | **292** | **263** | **53** | — |

## Group × canonical label — within-group %

| Group | NON_TUMOR % | VIABLE_TUMOR % | NECROSIS % |
|---|---|---|---|
| Case 3 | 38.6 | 1.1 | 60.0 |
| Case 4 | 28.2 | 31.4 | 32.5 |
| Case 48 | 36.8 | 54.6 | 0.5 |
| P9 | 100.0 | 0.0 | 0.0 |

(Percentages are of total group size including the MIXED rows, so each group's three class %s plus its MIXED share sum to 100.)

## Verifications

- **P9 is ~entirely NON_TUMOR — confirmed:** 212/212 patches NON_TUMOR, 0 VIABLE_TUMOR, 0 NECROSIS, 0 MIXED. Only **1** learned class present. A split placing P9 alone in validation/test would expose the model to a **single class**, making VIABLE_TUMOR and NECROSIS metrics not estimable on that fold.
- **Severe per-group class sparsity:** Case 3 has only **3** VIABLE_TUMOR (1.1%); Case 48 has only **2** NECROSIS (0.5%). Holding either group out starves the corresponding class in training or validation.
- **Every trainable row carries a group id** (recovered_group ∈ {Case-3, Case-4, Case-48, P9}); 0 trainable rows without a group.
- **No group is class-balanced**; no group contains a large, representative sample of all three classes.

These distributions directly drive the split and evaluation design in `split-proposal.md` and `g2-validation-report.md`.
