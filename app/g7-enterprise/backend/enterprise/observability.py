"""E6 — Observability: drift monitor (REAL, local) + the gated AWS seam.

The hash-chained audit log already runs locally (enterprise.audit). This module
adds the model-drift monitor, computed from the real review + prediction data,
and names the ONE seam that genuinely needs AWS: shipping the audit chain to S3
Object-Lock (WORM) and exporting OTel traces. Those two raise GateNotApproved;
everything else is live.

Drift signals (per serving bundle, over a project's scoped images):
- score distribution: mean of each class score + mean top-two margin + mean entropy
- defer_rate: share of reviewed images whose latest action is DEFER
- correction_rate: share of reviewed images whose latest action is CORRECT
- disagreement_rate: correction_rate restricted to where human != model

Threshold crossing is advisory: the caller decides. No auto-retrain (non-goal).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .scaffolds import GateNotApproved

GATE = "G-OBS (WORM retention + OTel export)"
PHASE = "E6 observability"


@dataclass
class DriftReport:
    bundle_sha256: str
    n_predictions: int
    n_reviewed: int
    mean_scores: dict = field(default_factory=dict)
    mean_top_two_margin: float = 0.0
    mean_entropy: float = 0.0
    defer_rate: float = 0.0
    correction_rate: float = 0.0
    disagreement_rate: float = 0.0
    alerts: list = field(default_factory=list)


# default advisory thresholds (tunable per deployment)
THRESHOLDS = {
    "defer_rate": 0.25,
    "correction_rate": 0.30,
    "disagreement_rate": 0.20,
    "mean_top_two_margin_low": 0.10,   # thin margins on average = low confidence
}


def drift_report(conn, *, bundle_sha256: str, image_ids: list[str] | None = None,
                 thresholds: dict | None = None) -> DriftReport:
    """Compute drift signals from the G6 review store `conn`.

    `image_ids` scopes to a project's granted set (None = all). Reads only; the
    immutable prediction/review model is never mutated.
    """
    th = {**THRESHOLDS, **(thresholds or {})}
    where = "WHERE p.model_bundle_hash = ?"
    params: list = [bundle_sha256]
    if image_ids:
        where += " AND p.image_id IN (%s)" % ",".join("?" for _ in image_ids)
        params += list(image_ids)

    rows = conn.execute(
        f"""SELECT p.image_id, p.non_tumor_score, p.viable_tumor_score,
                   p.necrosis_score, p.top_two_margin, p.normalized_entropy,
                   p.predicted_class
            FROM prediction p {where}""",
        params,
    ).fetchall()
    n = len(rows)
    rep = DriftReport(bundle_sha256=bundle_sha256, n_predictions=n, n_reviewed=0)
    if n == 0:
        return rep

    rep.mean_scores = {
        "NON_TUMOR": statistics.fmean(r["non_tumor_score"] for r in rows),
        "VIABLE_TUMOR": statistics.fmean(r["viable_tumor_score"] for r in rows),
        "NECROSIS": statistics.fmean(r["necrosis_score"] for r in rows),
    }
    rep.mean_top_two_margin = statistics.fmean(r["top_two_margin"] for r in rows)
    rep.mean_entropy = statistics.fmean(r["normalized_entropy"] for r in rows)

    # latest review state per image (append-only review_event; max revision wins)
    deferred = corrected = disagree = reviewed = 0
    for r in rows:
        latest = conn.execute(
            "SELECT action, selected_class FROM review_event WHERE image_id=? "
            "ORDER BY revision_number DESC LIMIT 1", (r["image_id"],),
        ).fetchone()
        if latest is None:
            continue
        reviewed += 1
        if latest["action"] == "DEFER":
            deferred += 1
        elif latest["action"] == "CORRECT":
            corrected += 1
            if latest["selected_class"] and latest["selected_class"] != r["predicted_class"]:
                disagree += 1
    rep.n_reviewed = reviewed
    if reviewed:
        rep.defer_rate = deferred / reviewed
        rep.correction_rate = corrected / reviewed
        rep.disagreement_rate = disagree / reviewed

    # advisory alerts
    if rep.defer_rate > th["defer_rate"]:
        rep.alerts.append(f"defer_rate {rep.defer_rate:.2f} > {th['defer_rate']}")
    if rep.correction_rate > th["correction_rate"]:
        rep.alerts.append(f"correction_rate {rep.correction_rate:.2f} > {th['correction_rate']}")
    if rep.disagreement_rate > th["disagreement_rate"]:
        rep.alerts.append(f"disagreement_rate {rep.disagreement_rate:.2f} > {th['disagreement_rate']}")
    if rep.mean_top_two_margin < th["mean_top_two_margin_low"]:
        rep.alerts.append(f"mean_top_two_margin {rep.mean_top_two_margin:.3f} < {th['mean_top_two_margin_low']}")
    return rep


# ---------------------------------------------------------------------------
# The ONE gated AWS seam. Everything above runs locally; these need AWS + spend.
# ---------------------------------------------------------------------------
def ship_audit_to_worm(bucket: str):
    raise GateNotApproved(PHASE, GATE,
                          "S3 Object-Lock (WORM) sink needs AWS + spend approval. "
                          "The local hash-chained audit (enterprise.audit) is live now.")


def export_otel_traces(endpoint: str):
    raise GateNotApproved(PHASE, GATE, "OTel collector export needs an approved endpoint.")
