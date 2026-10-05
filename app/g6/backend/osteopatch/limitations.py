"""The FULL, structured limitations catalog served by ``GET /v1/model-card``.

Why this exists
---------------
``overall-oof-metrics.json`` carries a five-string ``limitations`` array. That
array is the frozen G4 *evaluation* caveat list and it stays byte-identical in
the API response — it is durable evidence and must never be reworded in place.

But those five strings only describe the evaluation. They say nothing about the
attribution head, the platform, the deployment exposure, or the fact that the
original frozen bundle file is no longer on disk. Those limitations were real
and written down, just scattered across ~15 reports where no reviewer would ever
meet them.

So: ``limitations`` keeps the frozen strings verbatim, and ``limitations_full``
serves this catalog alongside it. Nothing is removed; the full set becomes
visible in one place.

Rules for this file
-------------------
1. **Every entry cites evidence that exists.** ``tests/test_limitations.py``
   walks ``evidence`` and fails if any path is missing from the repo tree.
2. **Every entry states what would retire it.** A limitation nobody can act on
   is a disclaimer; this way each one is falsifiable.
3. **The VIABLE_TUMOR weakness is structurally unmissable.** It is
   ``LIM-VIABLE-WEAK``, severity ``blocking``, and it is the first entry in the
   ``model`` group. No test may be relaxed to hide it.
4. **Nothing here is a clinical claim.** This is an educational prototype.

Severity means, for this catalog:
  blocking — the stated educational use is unsound if this is ignored
  high     — materially constrains what the numbers can support
  medium   — narrows scope or coverage
  low      — noted for completeness; not on the critical path
"""
from __future__ import annotations

from typing import Any

#: Stable machine-readable categories. The frontend groups on these, so treat
#: them as an API surface: add, do not rename.
CATEGORIES: tuple[str, ...] = (
    "claim",  # what this system may and may not be said to do
    "data",  # cohort, labels, splits
    "model",  # architecture, training, the learned scores
    "evaluation",  # what the reported metrics do and do not cover
    "attribution",  # the Grad-CAM disclosure chain
    "platform",  # this repository's engineering reality
    "deployment",  # the deployed demo
    "process",  # how this work was governed
)

_SEVERITIES: tuple[str, ...] = ("blocking", "high", "medium", "low")

#: Severity order used for sorting inside a category.
_SEVERITY_RANK = {s: i for i, s in enumerate(_SEVERITIES)}


def _lim(
    id: str,
    category: str,
    severity: str,
    statement: str,
    retired_by: str,
    evidence: list[str],
    pin_first: bool = False,
) -> dict[str, Any]:
    assert category in CATEGORIES, f"{id}: unknown category {category!r}"
    assert severity in _SEVERITIES, f"{id}: unknown severity {severity!r}"
    assert statement.strip(), f"{id}: empty statement"
    assert retired_by.strip(), f"{id}: not falsifiable — no retired_by"
    assert evidence, f"{id}: uncited limitation"
    return {
        "id": id,
        "category": category,
        "severity": severity,
        # Display pin. Exactly one entry per category may set it; that entry
        # sorts above its equally-severe siblings so the thing a reader must
        # not miss cannot be pushed down by alphabetical order.
        "pin_first": pin_first,
        "statement": statement,
        "retired_by": retired_by,
        "evidence": list(evidence),
    }


LIMITATIONS: list[dict[str, Any]] = [
    # ----------------------------------------------------------------- claim
    _lim(
        "LIM-CLAIM-EDUCATIONAL-ONLY",
        "claim",
        "blocking",
        "Educational / research prototype. It does not diagnose, does not "
        "prognose, does not predict treatment response, and its scores are not "
        "calibrated probabilities of anything. A reviewer's correction is a "
        "recorded human decision, not a clinical annotation.",
        "Retired only by a prospective, externally validated clinical study "
        "with a defined intended use — which this project does not claim to have run.",
        [
            "aidlc-docs/inception/model/claim-boundaries.md",
            "aidlc-docs/inception/risk-register.md",
            "PROJECT_BRIEF.md",
        ],
    ),
    _lim(
        "LIM-CLAIM-REVIEW-PRIORITY-NOT-ERROR-RATE",
        "claim",
        "high",
        "The 'review ambiguous patches first' ranking is a deterministic sort on "
        "raw score margin and entropy. It is a triage heuristic, not a "
        "calibrated probability of error and not a measure of diagnostic risk.",
        "Retired by a validated selective-prediction / triage study on held-out "
        "groups showing the ranking tracks actual error at a stated operating point.",
        [
            "aidlc-docs/inception/model/uncertainty-review-policy.md",
            "aidlc-docs/inception/model/g6/g6-summary.md",
        ],
    ),
    # ------------------------------------------------------------------ data
    _lim(
        "LIM-DATA-FOUR-GROUPS",
        "data",
        "high",
        "Evaluation rests on FOUR case/slide groups. Independence is verified at "
        "case/slide-group level only; token-to-patient identity was never "
        "confirmed, so this is NOT patient-level independence and no "
        "patient-level generalization claim is supportable.",
        "Retired by a larger cohort with verified patient identities and a "
        "pre-registered patient-level split.",
        [
            "aidlc-docs/inception/data/g2-validation-report.md",
            "aidlc-docs/inception/model/claim-boundaries.md",
            "aidlc-docs/inception/model/g4/overall-oof-metrics.json",
        ],
    ),
    _lim(
        "LIM-DATA-P9-SINGLE-CLASS",
        "data",
        "high",
        "The P9 group is 100% NON_TUMOR. On that fold VIABLE_TUMOR and NECROSIS "
        "have no test support, so their per-fold metrics are unavailable — "
        "reported as unavailable, never as zero.",
        "Retired by P9 (or any comparable group) containing both tumour classes "
        "in sufficient support.",
        [
            "aidlc-docs/inception/model/g4/per-fold-metrics.json",
            "aidlc-docs/inception/data/g2-validation-report.md",
        ],
    ),
    _lim(
        "LIM-DATA-SPARSE-FOLD-SUPPORT",
        "data",
        "medium",
        "Two held-out groups carry near-degenerate per-class support (Case-3 "
        "VIABLE_TUMOR test support = 3; Case-48 NECROSIS = 2). Those per-class "
        "reads are indicative only, with a confidence interval spanning "
        "essentially [0, 1].",
        "Retired by per-class support in the tens, so the interval is narrow "
        "enough to act on.",
        ["aidlc-docs/inception/model/g4/per-fold-metrics.json"],
    ),
    _lim(
        "LIM-DATA-ANNOTATION-PROVENANCE",
        "data",
        "high",
        "Labels are the published 'predominant class per patch' annotation — one "
        "annotator per image across two experts — not re-verified here, and not "
        "pixel-level ground truth. A patch labelled NON_TUMOR may still contain "
        "scattered viable tumour that a pathologist would call different.",
        "Retired by independent re-annotation of a random sample with reported "
        "inter-observer agreement.",
        ["aidlc-docs/inception/data/dataset-card.md"],
    ),
    _lim(
        "LIM-DATA-PATCHES-NOT-INDEPENDENT",
        "data",
        "high",
        "Patches are tiles cut from the same slides, not independent biological "
        "samples. No patch-as-patient bootstrap exists, so no confidence "
        "interval on any reported metric is claimable.",
        "Retired by a cluster bootstrap at the patient/slide level.",
        [
            "aidlc-docs/inception/model/g4/g4-summary.md",
            "aidlc-docs/inception/model/g4/overall-oof-metrics.json",
        ],
    ),
    _lim(
        "LIM-DATA-MIXED-EXCLUDED",
        "data",
        "medium",
        "53 patches whose source label reads 'viable: non-viable' are held out "
        "of the 3-class problem as MIXED_VIABLE_NECROTIC. This is source "
        "metadata, never a fourth model output — so genuinely mixed tissue is "
        "outside what the model was ever asked to classify.",
        "Retired by a ratified mixed-tissue label and a model that emits it.",
        ["aidlc-docs/inception/data/mixed-patch-policy.md"],
    ),
    _lim(
        "LIM-DATA-QC-ROWS-UNRESOLVED",
        "data",
        "medium",
        "63 rows (59 content-REVIEW + 4 perceptual near-duplicate candidates) "
        "remain intentionally unresolved and excluded from training_eligible "
        "pending human review. They are retained, not deleted.",
        "Retired by a human adjudicating every queued row and recording the "
        "decision.",
        [
            "aidlc-docs/inception/full-image-qc/full-image-qc-report.md",
            "aidlc-docs/inception/full-image-qc/training-eligibility-summary.csv",
        ],
    ),
    # ----------------------------------------------------------------- model
    _lim(
        "LIM-VIABLE-WEAK",
        "model",
        "blocking",
        "VIABLE_TUMOR is the model's weak class and the dominant limitation of "
        "this system. Pooled out-of-fold precision/recall/F1 are "
        "0.477612 / 0.110345 / 0.179272 (n=290): the model misses roughly 89% of "
        "viable tumour patches, and 153 of the 290 are predicted NECROSIS. Any "
        "workflow that treats a non-NECROSIS read as evidence of viable tumour "
        "will be wrong most of the time.",
        "Retired by widening independent VIABLE_TUMOR case/group coverage and "
        "re-measuring pooled out-of-fold recall on groups the model never saw.",
        [
            "aidlc-docs/inception/model/g4/overall-oof-metrics.json",
            "aidlc-docs/inception/model/g4/model-card-baseline.md",
            "aidlc-docs/inception/model/g5/g5-summary.md",
        ],
        pin_first=True,
    ),
    _lim(
        "LIM-MODEL-IMAGENET-ENCODER",
        "model",
        "high",
        "The encoder is a frozen ImageNet MobileNetV3-Small that was never "
        "trained on pathology. ImageNet accuracy is not pathology performance, "
        "and the frozen encoder is the most likely reason the viable/necrotic "
        "boundary is weak.",
        "Retired by a pathology-pretrained encoder evaluated under the same "
        "grouped protocol.",
        [
            "aidlc-docs/inception/model/g4/g4-summary.md",
            "aidlc-docs/inception/model/g4/run-configuration.json",
        ],
    ),
    _lim(
        "LIM-MODEL-UNCALIBRATED",
        "model",
        "blocking",
        "calibration_status is 'uncalibrated'. The three scores are raw softmax "
        "outputs of a class-ranking head. They are not disease probabilities and "
        "a score of 0.9 does not mean a 90% chance of anything.",
        "Retired by a leakage-safe calibration fitted on a held-out split with "
        "before/after log loss and Brier reported — which 4 groups may not permit.",
        [
            "aidlc-docs/inception/model/g4/final-bundle.json",
            "aidlc-docs/inception/model/g4/overall-oof-metrics.json",
        ],
    ),
    _lim(
        "LIM-MODEL-SINGLE-SEED",
        "model",
        "medium",
        "One seed (42). Multi-seed variance was never measured, so the headline "
        "numbers could be a favourable draw and no stability claim can be made.",
        "Retired by a 3-5 seed re-run reporting per-seed spread on the same folds.",
        ["aidlc-docs/inception/model/g4/run-configuration.json"],
    ),
    _lim(
        "LIM-MODEL-FINAL-FIT-NOT-EVALUATION",
        "model",
        "medium",
        "The shipped all-data model was trained on all 1,028 eligible patches. "
        "Its own training fit is not an evaluation metric; the honest "
        "performance statement for it is the frozen LOGO out-of-fold evaluation "
        "carried over as an estimate, with these limitations attached.",
        "Retired by evaluating the exact shipped weights on data they never saw.",
        ["aidlc-docs/inception/model/g4/model-card-baseline.md"],
    ),
    _lim(
        "LIM-MODEL-NO-IMPROVED-VARIANT",
        "model",
        "medium",
        "No better model exists. The one attempted alternative (G5, bounded "
        "last-stage fine-tuning) REGRESSED the baseline — VIABLE_TUMOR recall "
        "-0.0655, F1 -0.1041, pooled macro-F1 -0.0394 — with training loss "
        "falling at the same time, i.e. overfitting to 4 groups. baseline-frozen-g4 "
        "therefore remains the default because the alternative was measured, not "
        "because nothing was tried.",
        "Retired by a variant that improves pooled out-of-fold VIABLE_TUMOR "
        "recall on held-out groups without regressing the other classes.",
        ["aidlc-docs/inception/model/g5/g5-summary.md"],
    ),
    # ------------------------------------------------------------ evaluation
    _lim(
        "LIM-EVAL-NO-INDEPENDENT-SPLIT",
        "evaluation",
        "high",
        "No independent 3-way train/validation/test split exists or is possible "
        "here: 4 groups, one of them single-class. Evaluation is grouped "
        "leave-one-group-out and is exploratory by construction; hyperparameters "
        "were frozen a priori precisely because no honest validation split was available.",
        "Retired by a cohort large enough for a locked, independent test set.",
        [
            "aidlc-docs/inception/data/g2-validation-report.md",
            "aidlc-docs/inception/model/evaluation-protocol.md",
        ],
    ),
    _lim(
        "LIM-EVAL-POOLED-IS-EXPLORATORY",
        "evaluation",
        "high",
        "The headline metrics (macro-F1 0.562, balanced accuracy 0.626, log "
        "loss 1.195, Brier 0.496 over n=1,028) are pooled out-of-fold numbers "
        "from an exploratory grouped protocol on 4 groups. They are an estimate, "
        "not a performance guarantee, and not comparable to a clinically "
        "validated benchmark.",
        "Retired by a locked external test set reported once, with a stated "
        "confidence interval.",
        ["aidlc-docs/inception/model/g4/overall-oof-metrics.json"],
    ),
    _lim(
        "LIM-EVAL-NO-CLINICAL-VALIDITY",
        "evaluation",
        "blocking",
        "No clinical-validity study was run at any point: no reader study, no "
        "workflow study, no prospective comparison against a pathologist. "
        "Nothing here has been shown to improve any diagnostic outcome.",
        "Retired by a prospective clinical study with a pre-specified endpoint.",
        [
            "aidlc-docs/inception/data/g2-validation-report.md",
            "aidlc-docs/inception/model/claim-boundaries.md",
        ],
    ),
    # ----------------------------------------------------------- attribution
    _lim(
        "LIM-ATTRIB-RECONSTRUCTED-HEAD",
        "attribution",
        "high",
        "Attribution runs on a behaviorally reconstructed classifier "
        "(g4-behavioral-recovery-r1), not the original runtime head — those "
        "weights were not durably preserved. Its outputs were verified against "
        "the original stored scores, so it reproduces behaviour, not the "
        "original parameters.",
        "Retired by recovering the original head weights from a durable source.",
        [
            "app/g6/backend/osteopatch/config.py",
            "app/g6/backend/osteopatch/attribution.py",
        ],
    ),
    _lim(
        "LIM-ATTRIB-CONTRASTIVE-ONLY",
        "attribution",
        "high",
        "Grad-CAM here is CONTRASTIVE: the target is the raw logit difference "
        "A - B. It answers 'what pushed the model toward A rather than B', and "
        "an absolute single-class map is not recoverable this way.",
        "Retired by an absolute single-class attribution from a preserved head.",
        ["app/g6/backend/osteopatch/attribution.py"],
    ),
    _lim(
        "LIM-ATTRIB-NOT-SEGMENTATION",
        "attribution",
        "high",
        "An attribution overlay is not tissue segmentation, not a boundary, and "
        "not a diagnostic annotation. It is a gradient-weighted influence map "
        "and must never be read as a tumour outline.",
        "Not retirable by better attribution — this is a definitional boundary. "
        "It is retired only by a genuinely different, validated method.",
        [
            "app/g6/backend/osteopatch/app.py",
            "aidlc-docs/inception/model/evaluation-protocol.md",
        ],
    ),
    # -------------------------------------------------------------- platform
    _lim(
        "LIM-PLATFORM-FROZEN-BUNDLE-ABSENT",
        "platform",
        "high",
        "The original frozen bundle file (sha256 01727fb8…df63) is NOT present "
        "on disk. The 1,144 stored predictions remain keyed to that hash and are "
        "never rewritten, so the app serves the historical scores faithfully — "
        "but it cannot re-run that model to reproduce them from pixels.",
        "Retired by restoring a byte-identical copy of the bundle at the pinned "
        "hash; the loader refuses to start on mismatch.",
        [
            "app/g6/backend/osteopatch/config.py",
            "docs/current-state-audit.md",
        ],
    ),
    _lim(
        "LIM-PLATFORM-FROZEN-EVIDENCE-NOT-BAKED",
        "platform",
        "high",
        "The frozen G4 evaluation artifacts (aidlc-docs/inception/model/g4) are NOT "
        "copied into the deployed Lambda image, and the handler never sets "
        "OSTEOPATCH_MODEL_CARD_DIR. On that deployment the model card's OOF "
        "metrics are null and the frozen caveat list is empty — measured, not "
        "assumed. The API now says so explicitly rather than returning an empty "
        "list that reads as 'no caveats'. This catalog is unaffected: it ships "
        "inside the application package and is stdlib-only.",
        "Retired by baking the model-card directory into the image (or pointing "
        "OSTEOPATCH_MODEL_CARD_DIR at a fetched copy) and asserting its presence "
        "in verify_bake.py alongside the three existing artifacts.",
        [
            "app/g6/deploy/Dockerfile",
            "app/g6/deploy/lambda_handler.py",
            "app/g6/deploy/verify_bake.py",
        ],
    ),
    _lim(
        "LIM-PLATFORM-NO-SLIDE-INGESTION",
        "platform",
        "high",
        "There is no slide ingestion path. The whole-slide reader exists and is "
        "tested, but nothing ingests through it: there is no slide, tissue-mask "
        "or patch table, and no endpoint that accepts a whole-slide image. The "
        "1,144 patches were extracted by an earlier offline process that is not "
        "in this repository.",
        "Retired by a committed slide -> tissue mask -> patch pipeline with a "
        "level-0 coordinate manifest, plus an ingestion endpoint and tests.",
        [
            "app/g6/backend/osteopatch/pathology/reader.py",
            "app/g6/backend/osteopatch/migrations/0001_initial.sql",
            "docs/current-state-audit.md",
        ],
    ),
    _lim(
        "LIM-PLATFORM-PRECOMPUTED-SERVE",
        "platform",
        "medium",
        "The serving path is torch-free and precomputed: it reads stored scores "
        "out of SQLite and never runs inference. That is the point — it keeps a "
        "200 MB dependency out of the web app — but it means a patch added "
        "without an offline precompute pass has no score, and scoring latency "
        "figures are not inference latency figures.",
        "Retired by an explicit, tested offline scoring job that writes the same "
        "immutable prediction rows, with the staleness state surfaced in /health.",
        ["app/g6/backend/osteopatch/app.py", "app/g6/README.md"],
    ),
    _lim(
        "LIM-PLATFORM-CLEAN-CLONE-NO-PIXELS",
        "platform",
        "medium",
        "A clean clone cannot run the end-to-end smoke test. The 1,144 TIFFs "
        "(~287 MB) and the runtime database are gitignored by policy, so the "
        "preflight fails with an actionable message instead of silently passing.",
        "Retired by a committed, size-bounded synthetic fixture set that "
        "exercises the same paths.",
        ["docs/current-state-audit.md", ".gitignore"],
    ),
    _lim(
        "LIM-PLATFORM-TORCH-TESTS-SKIPPED-HERE",
        "platform",
        "low",
        "In the torch-free serve environment, 10 G6 backend tests skip (1 "
        "real-bundle, 9 attribution) because torch is intentionally absent. They "
        "are the seam that keeps the web path light and must not be suppressed "
        "to make that job look green; they run in the model environment instead.",
        "Retired by running the model-environment job and recording its result "
        "alongside this one.",
        ["docs/evidence/step02-baseline.md"],
    ),
    _lim(
        "LIM-PLATFORM-LEGACY-LINT",
        "platform",
        "low",
        "48 pre-existing ruff violations remain in untouched legacy files. CI "
        "blocks on new code and reports the legacy tree informationally, so the "
        "total is not zero.",
        "Retired by a deliberate cleanup pass that does not bury the real diff "
        "in churn.",
        ["docs/evidence/step04-static-baseline.md"],
    ),
    _lim(
        "LIM-PLATFORM-NO-AUTH-LOCAL",
        "platform",
        "high",
        "The G6 app has no authentication and no identity. It binds 127.0.0.1 "
        "only, and project scoping is a query filter — it separates data, it "
        "does not verify who is asking. Every review event is attributed to a "
        "caller-supplied reviewer string.",
        "Retired by real authentication with per-identity authorization on every "
        "project-scoped route.",
        [
            "app/g6/backend/osteopatch/config.py",
            "app/g6/backend/osteopatch/projects.py",
        ],
    ),
    # ------------------------------------------------------------ deployment
    _lim(
        "LIM-DEPLOY-OPEN-WRITE-ENDPOINT",
        "deployment",
        "high",
        "On the deployed demo API the review WRITE endpoint is open — no "
        "authentication — so anyone who can reach it can write review events. "
        "Bounded for a hackathon demo, and recorded here as live exposure, not "
        "as an accepted design.",
        "Retired by authentication in front of the write path, or by taking the "
        "write endpoint down.",
        ["aidlc-docs/g8-deployment-summary.md"],
    ),
    _lim(
        "LIM-DEPLOY-SUBSET-ONLY",
        "deployment",
        "medium",
        "The deployed demo serves a deterministic 50-image representative "
        "subset of the 1,144-image locally verified collection. Subset scoping is "
        "deployment configuration — it changes which rows are surfaced, never a "
        "score or a label, and the banner says so in the UI.",
        "Retired by deploying the full verified collection, or by keeping the "
        "subset and stating it everywhere the numbers appear.",
        [
            "aidlc-docs/g8-deployment-summary.md",
            "app/g6/backend/osteopatch/config.py",
        ],
    ),
    _lim(
        "LIM-DEPLOY-AWS-UNVERIFIED",
        "deployment",
        "high",
        "The AWS deployment state was NOT verified from this environment: no "
        "credentials were available and nothing was deployed, changed or "
        "re-checked. Treat every cloud figure as carried over from the original "
        "deployment record, not as a current observation.",
        "Retired by an authenticated read of the live stack, recorded with its "
        "timestamp.",
        ["aidlc-docs/g8-deployment-summary.md", "docs/aws-environment.md"],
    ),
    _lim(
        "LIM-DEPLOY-COLD-START",
        "deployment",
        "low",
        "First-attribution cold start on the CPU Lambda is reported at roughly "
        "10-30 seconds; warm and cached requests are fast. A reviewer who judges "
        "usability from the first click is measuring container start-up.",
        "Retired by a provisioned-concurrency or warmed-container setup.",
        ["aidlc-docs/g8-deployment-summary.md"],
    ),
    # --------------------------------------------------------------- process
    _lim(
        "LIM-PROCESS-NO-EXPERT-REVIEW",
        "process",
        "high",
        "No pathologist has vetted the teaching language, the failure examples, "
        "or the class definitions as this project presents them. The evaluation is "
        "internally consistent; it has not been externally reviewed by the "
        "audience it is written for.",
        "Retired by a documented expert review of the teaching material and a "
        "reviewed failure sample.",
        ["aidlc-docs/inception/requirements/requirement-verification-questions.md"],
    ),
]


def catalog() -> list[dict[str, Any]]:
    """Return every limitation, ordered by category then severity.

    Ordering is stable and deterministic so the UI, the API and the tests all
    agree on what "first" means — the blocking VIABLE_TUMOR weakness must never
    drift down the page.
    """
    cat_rank = {c: i for i, c in enumerate(CATEGORIES)}
    return sorted(
        LIMITATIONS,
        key=lambda d: (
            cat_rank[d["category"]],
            _SEVERITY_RANK[d["severity"]],
            0 if d["pin_first"] else 1,
            d["id"],
        ),
    )


def grouped() -> list[dict[str, Any]]:
    """Return the catalog grouped by category, preserving catalog()'s order."""
    out: list[dict[str, Any]] = []
    for cat in CATEGORIES:
        items = [d for d in catalog() if d["category"] == cat]
        if not items:
            continue
        out.append(
            {
                "category": cat,
                "count": len(items),
                "blocking_count": sum(1 for d in items if d["severity"] == "blocking"),
                "items": items,
            }
        )
    return out


def summary() -> dict[str, Any]:
    """Counts for the header. Cheap, and lets a client assert coverage."""
    items = catalog()
    by_sev = {s: sum(1 for d in items if d["severity"] == s) for s in _SEVERITIES}
    return {
        "total": len(items),
        "by_severity": by_sev,
        "categories": [g["category"] for g in grouped()],
        "weakest_class": "VIABLE_TUMOR",
    }