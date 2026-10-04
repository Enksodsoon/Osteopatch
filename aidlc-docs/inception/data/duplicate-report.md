# Duplicate & exclusion report — U1 (CSV level)

**Status:** CSV/metadata level only. Image-content (hash + perceptual) deduplication is **PENDING** — no images downloaded in U1.

## Filename duplicates (CSV)
- Total rows: 1,144 · distinct `image.name`: **1,144** · duplicated filename rows: **0**.
- Join to PathDB `imageId`: **1,144 / 1,144** one-to-one (after separator normalization). No many-to-one filename collision observed between CSV and PathDB.

## Null / blank key columns (CSV)
| Column | Nulls | Blanks |
|---|---|---|
| `classification` | 0 | 0 |
| `image.name` | 0 | 0 |

## Label-based exclusions (fail-closed)
Rows whose raw label is not yet a resolved canonical class are flagged `included=FALSE`, `exclusion_reason=UNRESOLVED_LABEL:<raw>` in `manifest.csv` — **not** silently mapped:
| Raw label | Rows flagged |
|---|---|
| `Non-Viable-Tumor` | 263 |
| `viable: non-viable` | 53 |
| **Total pending owner ratification** | **316** |

## Pending at image stage (G2)
- Exact SHA-256 duplicate clusters across the 1,144 tiles.
- Perceptual near-duplicate groups (augmentation/crop siblings) — must share one split.
- Corrupt/unreadable image detection; color-mode / ICC / orientation consistency.
- Burned-in annotation overlay check.

None of the above can be completed without the image bytes, which U1 did not download (cap + cloud-first intent).
