# Patient-mapping evidence — U1 (critical question)

**Status:** evidence gathered from the official CSV + PathDB metadata. **No image bytes downloaded.** This document records what IS supported, what is INFERENCE, and the explicit limits. It does not assert patient-independent performance.

## 1. What the CSV contains
- The CSV has **no dedicated** `patient` / `case` / `subject` / `slide` / `group` **column**. Only `image.name` encodes grouping.
- `image.name` grammar (observed): `<GROUP> <SLIDE>-<Xcoord>-<Ycoord>`, e.g. `Case 3 A10-10547-25283`, `P9 B11-10159-22267`, `Case 48 - P5 C13-24121-14200`.
- **4 distinct GROUP tokens** partition all 1,144 rows:

| Group token | CSV rows | Distinct slide codes |
|---|---|---|
| `Case 3` | 285 | 10 (A7,A8,A10,A12–A18) |
| `Case 4` | 277 | 10 (C21,C22,C24,C27–C29,C31,C34,C48,C52) |
| `Case 48` (carries sub-token `P5`) | 370 | 13 (C13–C25) |
| `P9` | 212 | 8 (B6,B7,B11,B12,B27,B28,B34,B35) |
| **Total** | **1,144** | — |

## 2. What PathDB adds (documented, not inferred)
- PathDB collection `Osteosarcoma-Tumor-Assessment` (collectionId 18) returns **1,144** image records.
- `subjectId` values are the **per-patch identifiers** (e.g. `Case-3-A10-10547-25283`), with **1,144 distinct subjectIds = 1,144 distinct imageIds**. ⇒ **PathDB `subjectId` is NOT a biological patient id.** Do not equate the two.
- `imageUrl` paths encode the release folder layout, e.g.
  `…/converted/Osteosarcoma-UT/Training-Set-2/set1/Case-3-A10-10547-25283.tiff`.
  This is a **documented** source-side folder grouping (`Training-Set-{1,2}/set{1..12}`), stronger evidence than filename inference alone.
- **CSV ↔ PathDB join: 1,144 / 1,144 one-to-one** after normalizing separators (strip spaces around `-`, whitespace→`-`, collapse repeats). Every CSV row maps to exactly one PathDB image.

## 3. Group tokens vs the published "4 patients"
- The published collection describes **4 selected patients**. The data yields **exactly 4 group tokens** (`Case 3`, `Case 4`, `Case 48`, `P9`), each a disjoint set of slides and patches.
- **Confidence that the 4 group tokens correspond to the 4 published patients: MODERATE–HIGH**, because (a) the count matches exactly, (b) each token owns a disjoint slide-code set, (c) the token appears in both the CSV filename and the independent PathDB subjectId/imageUrl.
- **Limit / unresolved:** TCIA public metadata examined here does **not** contain an explicit table stating "Case 3 = patient A, Case 4 = patient B…". The `Case 48` token additionally embeds a `P5` code and `P9` uses a `P`-prefix, so the naming scheme is not uniform; a token is a reasonable **slide/case grouping unit** but the one-token-per-biological-patient claim rests on the count coincidence + disjoint slides, not on a documented patient manifest. **Do not** report patient-independent metrics on this basis without TCIA documentation confirming the token→patient identity.

## 4. Grouping recommendation (for G2, not decided here)
- Treat the **4 group tokens as the grouping unit** for any split so that all patches/slides of one token stay in one split (prevents the most obvious leakage). Label this grouping **"case/slide-group independent"**, NOT "patient-independent", until the token→patient identity is documented.
- With only 4 groups, a single train/val/test split cannot cover all classes patient-independently; **grouped cross-validation** or an explicitly-labelled exploratory/demo evaluation is the honest option. Decide at G2 after the patient × class table is built from resolved labels.

## 5. Class × group support (resolved + unresolved labels shown separately)
Raw-label distribution per group (from CSV `classification`):

| Group | Non-Tumor | Viable | Non-Viable-Tumor* | viable: non-viable* |
|---|---|---|---|---|
| Case 3 | 110 | 3 | 171 | 1 |
| Case 4 | 78 | 87 | 90 | 22 |
| Case 48 | 136 | 202 | 2 | 30 |
| P9 | 212 | 0 | 0 | 0 |

\* fail-closed (unresolved) labels — see `label_aliases.json`. Note `P9` is **entirely Non-Tumor**, so a split placing P9 in test would leave test with a single class — a concrete reason group-aware splitting matters here.

## 6. Explicit limits
- No biological patient identifiers, demographics, or clinical outcomes are present or inferred.
- No image content inspected (dimensions taken from PathDB metadata, not re-measured).
- Any "patient-independent" claim is **unsupported** at U1; the strongest defensible statement is **"grouped by the 4 case/slide tokens, cross-checked against PathDB subjectId and imageUrl folders."**
