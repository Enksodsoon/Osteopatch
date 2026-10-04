# Claim boundaries — G3 (OsteoPatch Review)

**Status:** G3 **design only**. Defines exactly what this prototype may and may not claim. Keeps every claim **proportional to 4 recovered case/slide groups** of patch-level data. Grounded in doc 02 (§Split and leakage policy, §Selection/calibration/reporting), doc 03 (SAF-01/02), G2 `g2-validation-report.md` §5 limitations.

**Independence wording:** always **case/slide-group independent** (4 groups). **Never** "patient-independent", "patient-level", or "clinically independent".

---

## Allowed claims (with current/forthcoming evidence)

- **Exploratory** patch-level tissue classification into NON_TUMOR / VIABLE_TUMOR / NECROSIS.
- An **educational / research prototype** that demonstrates a testable suggestion + visible uncertainty + accountable human review.
- Evaluated with **case/slide-group separation** via Leave-One-Group-Out CV over **4 recovered source groups**.
- Results carry **limited external validity**: 4 groups, one of them (P9) single-class.
- A **model class score** per class for the supplied patch under the evaluated task.
- Reports that are honest about not-estimable classes, sparse-class folds, and the pooled-vs-per-fold spread.

## NOT allowed without new evidence (a new dataset version + a fresh evaluation gate)

- ❌ **Patient-level validated** / patient-independent performance.
- ❌ **Clinically validated** or diagnostic-grade performance.
- ❌ **Generalizes to osteosarcoma patients** / to the general population.
- ❌ **Diagnostic performance** claims (sensitivity/specificity presented as clinical).
- ❌ **Treatment-response** assessment.
- ❌ **Prognosis** / survival estimation.
- ❌ **Clinical necrosis-percentage estimation** for a patient (doc 03 SAF-02).
- ❌ Any claim that an **unflagged** image is "safe".
- ❌ A softmax score reported as a **disease probability** / certainty.

## The independence caveat (must accompany every headline)

> Patch counts are **not** independent biological samples. The 1,091 trainable patches come from only **4 case/slide groups** (Case 3 / Case 4 / Case 48 / P9); patches within a group share stain, scanner and biology. Case/slide-group→biological-patient identity is **unverified** (`../data/patient_mapping_evidence.md`). P9 is 100% NON_TUMOR, so VIABLE_TUMOR and NECROSIS are not estimable on its fold. **A 4-group cohort cannot support a generalization or clinical-validity claim.**

## Mandatory disclaimers

- Workbench and every export carry the **educational-only** disclaimer (doc 03 SAF-01).
- No patient diagnosis, treatment-response, survival, or patient-level necrosis-% is generated (doc 03 SAF-02).
- Model/dataset cards state intended use, the case/slide-group (not patient) independence limitation, the split method, which metrics are not estimable, and calibration limitations; unmeasured fields read **"Not measured"** (doc 03 FR-11).
