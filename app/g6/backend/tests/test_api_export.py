"""HTTP API + export tests via FastAPI TestClient."""
from __future__ import annotations

import csv
import io

from osteopatch import repo

HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"


def _pid(image_id):
    return repo.prediction_id_for(image_id, HASH)


def test_health_and_meta(client):
    h = client.get("/v1/health").json()
    assert h["status"] == "ok" and h["images_indexed"] == 4
    m = client.get("/v1/meta").json()
    assert m["canonical_classes"] == ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"]
    assert m["score_label"] == "Model score — uncalibrated"
    # G7: the "coming in G7" placeholder is retired; attribution is now wired.
    assert m["g7_placeholder"] == ""
    assert m["attribution_enabled"] is True
    assert len(m["attribution"]["pairs"]) == 6
    assert "behaviorally reconstructed" in m["attribution"]["disclosure"]


def test_gallery_sort_by_priority(client):
    data = client.get("/v1/images?sort=priority").json()
    ids = [it["image_id"] for it in data["items"]]
    # ambiguous (margin 0.01) must come first; clear-nt (margin 0.85) last
    assert ids[0] == "img-ambiguous"
    assert ids[-1] == "img-clear-nt"
    # every item carries a review-priority rank + uncalibrated label
    assert data["items"][0]["review_priority_rank"] == 1
    assert data["items"][0]["prediction"]["score_label"] == "Model score — uncalibrated"


def test_gallery_filter_predicted_class(client):
    data = client.get("/v1/images?filter=pred_NON_TUMOR").json()
    assert all(it["prediction"]["predicted_class"] == "NON_TUMOR" for it in data["items"])


def test_gallery_filter_unreviewed_then_reviewed(client):
    # initially everything unreviewed
    un = client.get("/v1/images?filter=unreviewed").json()
    assert un["total"] == 4
    # accept one
    client.post("/v1/images/img-clear-nt/reviews", json={
        "prediction_id": _pid("img-clear-nt"), "action": "ACCEPT",
        "expected_revision": 0, "idempotency_key": "ui1",
    })
    rev = client.get("/v1/images?filter=reviewed").json()
    assert [it["image_id"] for it in rev["items"]] == ["img-clear-nt"]


def test_review_post_201_then_409_then_idempotent(client):
    r1 = client.post("/v1/images/img-ambiguous/reviews", json={
        "prediction_id": _pid("img-ambiguous"), "action": "CORRECT",
        "selected_label": "NECROSIS", "expected_revision": 0, "idempotency_key": "p1",
    })
    assert r1.status_code == 201 and r1.json()["created"] is True
    # stale expected_revision -> 409
    r2 = client.post("/v1/images/img-ambiguous/reviews", json={
        "prediction_id": _pid("img-ambiguous"), "action": "ACCEPT",
        "expected_revision": 0, "idempotency_key": "p2",
    })
    assert r2.status_code == 409
    # idempotent replay of p1 -> 200, same event
    r3 = client.post("/v1/images/img-ambiguous/reviews", json={
        "prediction_id": _pid("img-ambiguous"), "action": "CORRECT",
        "selected_label": "NECROSIS", "expected_revision": 0, "idempotency_key": "p1",
    })
    assert r3.status_code == 200 and r3.json()["created"] is False
    assert r3.json()["review_event_id"] == r1.json()["review_event_id"]


def test_review_422_and_404(client):
    # CORRECT without valid class -> 422
    bad = client.post("/v1/images/img-ambiguous/reviews", json={
        "prediction_id": _pid("img-ambiguous"), "action": "CORRECT",
        "selected_label": "BONE", "expected_revision": 0, "idempotency_key": "b1",
    })
    assert bad.status_code == 422
    # unknown image -> 404
    nf = client.post("/v1/images/ghost/reviews", json={
        "prediction_id": _pid("img-ambiguous"), "action": "ACCEPT",
        "expected_revision": 0, "idempotency_key": "b2",
    })
    assert nf.status_code == 404


def test_review_history_shows_original_prediction_unchanged(client):
    client.post("/v1/images/img-ambiguous/reviews", json={
        "prediction_id": _pid("img-ambiguous"), "action": "CORRECT",
        "selected_label": "NON_TUMOR", "expected_revision": 0, "idempotency_key": "h1",
    })
    detail = client.get("/v1/images/img-ambiguous").json()
    # the model prediction is still the original argmax (VIABLE_TUMOR)
    assert detail["prediction"]["predicted_class"] == "VIABLE_TUMOR"
    # the human correction is recorded in history
    assert detail["history"][-1]["selected_class"] == "NON_TUMOR"
    assert detail["review_state"]["status"] == "reviewed"


def test_export_preserves_prediction_and_correction(client):
    client.post("/v1/images/img-ambiguous/reviews", json={
        "prediction_id": _pid("img-ambiguous"), "action": "CORRECT",
        "selected_label": "NON_TUMOR", "expected_revision": 0, "idempotency_key": "e1",
    })
    # JSON export
    j = client.get("/v1/exports/reviews?format=json").json()
    assert j["disclaimer"] and j["model_bundle_sha256"] == HASH
    row = next(r for r in j["rows"] if r["image_id"] == "img-ambiguous")
    assert row["model_predicted_class"] == "VIABLE_TUMOR"   # original model
    assert row["human_corrected_class"] == "NON_TUMOR"       # human correction
    assert row["model_score_label"] == "Model score — uncalibrated"
    # CSV export has both columns too
    csv_text = client.get("/v1/exports/reviews?format=csv").text
    reader = list(csv.DictReader(io.StringIO(csv_text)))
    crow = next(r for r in reader if r["image_id"] == "img-ambiguous")
    assert crow["model_predicted_class"] == "VIABLE_TUMOR"
    assert crow["human_corrected_class"] == "NON_TUMOR"
    assert "disclaimer" in crow and crow["disclaimer"]


def test_model_card_served(client):
    mc = client.get("/v1/model-card").json()
    assert mc["model_bundle_sha256"] == HASH
    assert mc["calibration_status"] == "uncalibrated"
    assert mc["canonical_classes"] == ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"]
