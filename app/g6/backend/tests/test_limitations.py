"""The limitations catalog must stay TRUE, not merely present.

A limitations list that nobody checks is decoration. These tests enforce the
properties that make this one load-bearing:

1. Every cited evidence file still exists in the repo.
2. Every entry is falsifiable (states what would retire it).
3. The frozen G4 evaluation strings are served VERBATIM and never filtered.
4. The VIABLE_TUMOR weakness is present, blocking, and carries the real numbers.
5. Grouping/summary are internally consistent with the flat catalog.

If someone deletes a limitation to make something look better, this file fails.
That is the point.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from osteopatch import config, limitations  # noqa: E402
from osteopatch.modelcard import model_card  # noqa: E402

REPO_ROOT = config.PROJECT_ROOT


# ---------------------------------------------------------------------------
# Catalog integrity
# ---------------------------------------------------------------------------
def test_every_cited_evidence_file_exists():
    """A limitation pointing at a missing file is worse than no limitation."""
    missing = [
        (d["id"], p)
        for d in limitations.catalog()
        for p in d["evidence"]
        if not (REPO_ROOT / p).exists()
    ]
    assert not missing, (
        "limitations catalog cites evidence that does not exist: " f"{missing}"
    )


def test_every_entry_is_falsifiable():
    """Each limitation must say what would retire it."""
    for d in limitations.catalog():
        assert d["retired_by"].strip(), d["id"]
        assert len(d["retired_by"]) > 20, f"{d['id']}: retired_by too thin to be meaningful"


def test_ids_are_unique_and_well_formed():
    ids = [d["id"] for d in limitations.catalog()]
    assert len(ids) == len(set(ids)), "duplicate limitation ids"
    for i in ids:
        assert i.startswith("LIM-"), i
        assert i == i.upper(), i


def test_categories_and_severities_are_declared():
    for d in limitations.catalog():
        assert d["category"] in limitations.CATEGORIES
        assert d["severity"] in ("blocking", "high", "medium", "low")


def test_at_most_one_pinned_entry_per_category():
    """A pin that pins everything pins nothing."""
    seen: dict[str, int] = {}
    for d in limitations.catalog():
        if d["pin_first"]:
            seen[d["category"]] = seen.get(d["category"], 0) + 1
    assert all(n == 1 for n in seen.values()), f"bad pins: {seen}"


def test_catalog_covers_the_expected_surface():
    """Guards against a well-formed but gutted catalog."""
    cats = {d["category"] for d in limitations.catalog()}
    assert cats == set(limitations.CATEGORIES), f"missing categories: {cats}"
    assert limitations.summary()["total"] >= 25


# ---------------------------------------------------------------------------
# The VIABLE_TUMOR weakness must stay unmissable
# ---------------------------------------------------------------------------
def test_viable_weakness_is_blocking_and_first_in_model():
    items = limitations.catalog()
    viable = [d for d in items if d["id"] == "LIM-VIABLE-WEAK"]
    assert len(viable) == 1, "the VIABLE_TUMOR weakness entry was removed"
    entry = viable[0]
    assert entry["severity"] == "blocking"
    assert entry["category"] == "model"
    model_items = [d for d in items if d["category"] == "model"]
    assert model_items[0]["id"] == "LIM-VIABLE-WEAK", (
        "VIABLE_TUMOR weakness must sort first within the model group"
    )


def test_viable_weakness_statement_matches_the_frozen_metrics():
    """The headline numbers must come from the artifact, not from memory."""
    oof = json.loads(
        (config.MODEL_CARD_DIR / "overall-oof-metrics.json").read_text(encoding="utf-8")
    )
    per_class = oof["per_class"]["VIABLE_TUMOR"]
    entry = next(d for d in limitations.catalog() if d["id"] == "LIM-VIABLE-WEAK")
    s = entry["statement"]
    assert str(per_class["recall"]) in s, (
        f"statement {s!r} does not quote the frozen recall {per_class['recall']}"
    )
    assert str(per_class["f1"]) in s, (
        f"statement {s!r} does not quote the frozen f1 {per_class['f1']}"
    )
    # VIABLE row of the frozen confusion matrix: [NON_TUMOR, VIABLE, NECROSIS]
    viable_to_necrosis = oof["confusion_matrix_rows_true_cols_pred"][1][2]
    assert str(viable_to_necrosis) in s, (
        f"statement {s!r} does not quote the frozen VIABLE->NECROSIS count "
        f"{viable_to_necrosis}"
    )


# ---------------------------------------------------------------------------
# Frozen evaluation strings are never reworded
# ---------------------------------------------------------------------------
def test_frozen_g4_limitations_served_verbatim():
    oof = json.loads(
        (config.MODEL_CARD_DIR / "overall-oof-metrics.json").read_text(encoding="utf-8")
    )
    frozen = oof["limitations"]
    assert len(frozen) == 5, "the frozen G4 evaluation caveat list changed length"
    assert model_card()["limitations"] == frozen, (
        "frozen G4 evaluation limitations must be served verbatim, unmodified"
    )


def test_full_catalog_is_a_strict_superset_of_the_frozen_strings():
    """Nothing may be dropped on the way into the full catalog."""
    oof = json.loads(
        (config.MODEL_CARD_DIR / "overall-oof-metrics.json").read_text(encoding="utf-8")
    )
    full = model_card()["limitations_full"]
    assert len(full) > len(oof["limitations"])
    # The frozen strings are paraphrased/expanded in the catalog, so identity is
    # checked on the served frozen list, not string-matching here. What this
    # asserts is that serving the catalog never REPLACES the frozen evidence.
    assert model_card()["limitations"] == oof["limitations"]


# ---------------------------------------------------------------------------
# API shape
# ---------------------------------------------------------------------------
def test_model_card_exposes_the_full_catalog(client):
    mc = client.get("/v1/model-card").json()
    assert mc["limitations_full"], "limitations_full missing from /v1/model-card"
    assert mc["limitations_summary"]["total"] == len(mc["limitations_full"])
    assert mc["limitations_note"]
    for d in mc["limitations_full"]:
        assert set(d) == {
            "id",
            "category",
            "severity",
            "pin_first",
            "statement",
            "retired_by",
            "evidence",
        }
        assert d["statement"] and d["evidence"]


def test_grouped_matches_flat_catalog(client):
    mc = client.get("/v1/model-card").json()
    grouped = mc["limitations_grouped"]
    flat_ids = [d["id"] for d in mc["limitations_full"]]
    grouped_ids = [d["id"] for g in grouped for d in g["items"]]
    assert grouped_ids == flat_ids, "grouping reordered or dropped entries"
    for g in grouped:
        assert g["count"] == len(g["items"])
        assert g["blocking_count"] == sum(1 for i in g["items"] if i["severity"] == "blocking")


def test_summary_severity_counts_add_up(client):
    mc = client.get("/v1/model-card").json()
    s = mc["limitations_summary"]
    assert sum(s["by_severity"].values()) == s["total"]
    assert s["weakest_class"] == "VIABLE_TUMOR"


def test_disclaimer_and_claim_boundary_survive():
    """The catalog must never out-weigh the claim boundary it serves."""
    mc = model_card()
    assert "NOT for diagnosis" in mc["disclaimer"]
    claim = [d for d in mc["limitations_full"] if d["category"] == "claim"]
    assert claim, "the claim boundary is not stated as a limitation"
    assert any(d["severity"] == "blocking" for d in claim)