"""E2–E6 tests — governance, registry, ingestion, inference, drift.

Unit-level against the module APIs with isolated SQLite dbs. No G6 data / torch
needed except the drift test, which builds a tiny in-memory prediction+review
store mimicking the G6 schema so the drift math is exercised on real rows.
"""
import sqlite3

import pytest


@pytest.fixture()
def ent_conn(tmp_path):
    from enterprise import store
    return store.connect(tmp_path / "ent.sqlite3")


# ---------------------------------------------------------------------------
# E4 governance
# ---------------------------------------------------------------------------
def test_adjudication_rejects_unknown_label(ent_conn):
    from enterprise import governance
    with pytest.raises(governance.GovernanceError):
        governance.adjudicate(ent_conn, project_id="p", image_id="i",
                              resolver="path@demo", resolved_label="MIXED")


def test_adjudication_records(ent_conn):
    from enterprise import governance
    r = governance.adjudicate(ent_conn, project_id="p", image_id="i",
                             resolver="path@demo", resolved_label="NECROSIS",
                             rationale="necrotic debris")
    assert r["resolved_label"] == "NECROSIS"
    hist = governance.adjudication_history(ent_conn, "p", "i")
    assert len(hist) == 1 and hist[0]["resolver"] == "path@demo"


def test_signoff_is_hash_stable_and_order_independent(ent_conn):
    from enterprise import governance
    a = governance.sign_off_batch(ent_conn, project_id="p", signed_by="x",
                                 image_ids=["b", "a", "c"], states={"a": "reviewed", "b": "deferred", "c": "reviewed"})
    b = governance.sign_off_batch(ent_conn, project_id="p", signed_by="x",
                                 image_ids=["c", "a", "b"], states={"a": "reviewed", "b": "deferred", "c": "reviewed"})
    assert a["content_sha"] == b["content_sha"]  # order-independent
    assert a["image_count"] == 3
    stored = governance.get_batch(ent_conn, a["batch_id"])
    assert stored["locked"] is True and stored["image_ids"] == ["a", "b", "c"]


def test_signoff_empty_rejected(ent_conn):
    from enterprise import governance
    with pytest.raises(governance.GovernanceError):
        governance.sign_off_batch(ent_conn, project_id="p", signed_by="x", image_ids=[], states={})


def test_correction_capture_is_capture_only(ent_conn):
    from enterprise import governance
    r = governance.capture_correction(ent_conn, project_id="p", image_id="i",
                                      from_label="VIABLE_TUMOR", to_label="NECROSIS",
                                      captured_by="rev@demo")
    assert r["consumed_by_training"] is False
    store = governance.correction_store(ent_conn, "p")
    assert len(store) == 1 and store[0]["consumed_by_training"] == 0


# ---------------------------------------------------------------------------
# E5 registry — state machine, single-serving, rollback
# ---------------------------------------------------------------------------
def _register(conn, sha="a" * 64, mid="m1"):
    from enterprise import registry
    return registry.register(conn, bundle_sha256=sha, model_id=mid,
                            eval_card_ref="card", split_declared="group-independent",
                            registered_by="mle@demo")


def test_register_idempotent(ent_conn):
    from enterprise import registry
    r1 = _register(ent_conn)
    r2 = _register(ent_conn)
    assert r1["bundle_sha256"] == r2["bundle_sha256"]
    assert registry.get(ent_conn, "a" * 64)["state"] == "registered"


def test_illegal_transition_rejected(ent_conn):
    from enterprise import registry
    _register(ent_conn)
    with pytest.raises(registry.RegistryError):
        registry.promote(ent_conn, bundle_sha256="a" * 64,
                        to=registry.ModelState.SERVING, actor="mle@demo")  # skips candidate/shadow


def test_promote_to_serving_requires_eval_gate(ent_conn):
    from enterprise import registry
    _register(ent_conn)
    registry.promote(ent_conn, bundle_sha256="a" * 64, to=registry.ModelState.CANDIDATE, actor="x")
    registry.promote(ent_conn, bundle_sha256="a" * 64, to=registry.ModelState.SHADOW, actor="x")
    with pytest.raises(registry.RegistryError):  # eval not passed
        registry.promote(ent_conn, bundle_sha256="a" * 64, to=registry.ModelState.SERVING, actor="x")
    registry.set_eval_passed(ent_conn, "a" * 64, True, "x")
    r = registry.promote(ent_conn, bundle_sha256="a" * 64, to=registry.ModelState.SERVING, actor="x")
    assert r["state"] == "serving"


def test_single_serving_invariant_and_rollback(ent_conn):
    from enterprise import registry
    MS = registry.ModelState
    sha1, sha2 = "a" * 64, "b" * 64
    for sha in (sha1, sha2):
        _register(ent_conn, sha=sha, mid=sha[:4])
        registry.promote(ent_conn, bundle_sha256=sha, to=MS.CANDIDATE, actor="x")
        registry.promote(ent_conn, bundle_sha256=sha, to=MS.SHADOW, actor="x")
        registry.set_eval_passed(ent_conn, sha, True, "x")
    registry.promote(ent_conn, bundle_sha256=sha1, to=MS.SERVING, actor="x")
    assert registry.serving(ent_conn)["bundle_sha256"] == sha1
    # promoting sha2 to serving must auto-retire sha1 (single-serving invariant)
    registry.promote(ent_conn, bundle_sha256=sha2, to=MS.SERVING, actor="x")
    assert registry.serving(ent_conn)["bundle_sha256"] == sha2
    assert registry.get(ent_conn, sha1)["state"] == "retired"
    # rollback returns the most-recently-retired (sha1) to serving
    rb = registry.rollback(ent_conn, "x")
    assert rb["bundle_sha256"] == sha1
    assert registry.serving(ent_conn)["bundle_sha256"] == sha1
    assert registry.get(ent_conn, sha2)["state"] == "retired"


# ---------------------------------------------------------------------------
# E2 ingestion — fail-closed on unknown labels
# ---------------------------------------------------------------------------
def test_manifest_fails_closed_on_unknown_label(ent_conn):
    from enterprise import ingestion
    ds = ingestion.register_dataset(ent_conn, source="TCIA", license="CC",
                                    split_declared="group", created_by="admin@demo")
    with pytest.raises(ingestion.IngestionError):
        ingestion.index_manifest(ent_conn, dataset_id=ds["dataset_id"],
                                rows=[{"image_id": "i1", "original_label": "MYSTERY"}])


def test_manifest_indexes_valid_rows(ent_conn):
    from enterprise import ingestion
    ds = ingestion.register_dataset(ent_conn, source="TCIA", license="CC",
                                    split_declared="group", created_by="admin@demo")
    r = ingestion.index_manifest(ent_conn, dataset_id=ds["dataset_id"], rows=[
        {"image_id": "i1", "original_label": "NON_TUMOR", "source_group": "P1"},
        {"image_id": "i2", "original_label": "NECROSIS", "source_group": "P1"},
    ])
    assert r["indexed"] == 2
    assert ingestion.staged_image_ids(ent_conn, ds["dataset_id"]) == ["i1", "i2"]


# ---------------------------------------------------------------------------
# E3 inference — idempotent enqueue
# ---------------------------------------------------------------------------
def test_enqueue_is_idempotent(ent_conn):
    from enterprise import inference
    r1 = inference.enqueue(ent_conn, image_ids=["i1", "i2"], bundle_sha256="h")
    assert r1["newly_queued"] == 2
    r2 = inference.enqueue(ent_conn, image_ids=["i1", "i2", "i3"], bundle_sha256="h")
    assert r2["newly_queued"] == 1  # only i3 is new
    assert inference.queue_depth(ent_conn) == 3
    # shadow run of the same images is a separate lane
    r3 = inference.enqueue(ent_conn, image_ids=["i1"], bundle_sha256="h", shadow=True)
    assert r3["newly_queued"] == 1


# ---------------------------------------------------------------------------
# E6 drift — real math over a tiny G6-shaped store
# ---------------------------------------------------------------------------
def _g6like(tmp_path):
    conn = sqlite3.connect(tmp_path / "g6.sqlite3")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
      CREATE TABLE prediction(image_id TEXT, model_bundle_hash TEXT, predicted_class TEXT,
        non_tumor_score REAL, viable_tumor_score REAL, necrosis_score REAL,
        top_two_margin REAL, normalized_entropy REAL);
      CREATE TABLE review_event(image_id TEXT, action TEXT, selected_class TEXT, revision_number INT);
    """)
    return conn


def test_drift_report_computes_rates(tmp_path):
    from enterprise import observability
    conn = _g6like(tmp_path)
    # 4 predictions on bundle H; 3 reviewed: 1 ACCEPT, 1 DEFER, 1 CORRECT(disagree)
    preds = [
        ("i1", "NECROSIS", 0.1, 0.2, 0.7, 0.5, 0.6),
        ("i2", "NON_TUMOR", 0.6, 0.2, 0.2, 0.4, 0.7),
        ("i3", "VIABLE_TUMOR", 0.2, 0.5, 0.3, 0.2, 0.9),
        ("i4", "NECROSIS", 0.3, 0.1, 0.6, 0.3, 0.8),
    ]
    for p in preds:
        conn.execute("INSERT INTO prediction VALUES (?,?,?,?,?,?,?,?)",
                     (p[0], "H", p[1], p[2], p[3], p[4], p[5], p[6]))
    conn.execute("INSERT INTO review_event VALUES ('i1','ACCEPT',NULL,1)")
    conn.execute("INSERT INTO review_event VALUES ('i2','DEFER',NULL,1)")
    conn.execute("INSERT INTO review_event VALUES ('i3','CORRECT','NECROSIS',1)")  # != VIABLE_TUMOR
    conn.commit()
    rep = observability.drift_report(conn, bundle_sha256="H")
    assert rep.n_predictions == 4 and rep.n_reviewed == 3
    assert abs(rep.defer_rate - 1/3) < 1e-9
    assert abs(rep.correction_rate - 1/3) < 1e-9
    assert abs(rep.disagreement_rate - 1/3) < 1e-9
    assert "defer_rate" in " ".join(rep.alerts)  # 0.33 > 0.25 threshold
