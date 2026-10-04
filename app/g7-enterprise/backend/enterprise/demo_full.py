"""Full enterprise demo — E1 live + E2–E6 exercised end-to-end over real G6 data.

Extends demo_fullstack with the governance / registry / inference / drift surface.
Run exactly like demo_fullstack (point OSTEOPATCH_DB at a COPY of the G6 store).
"""
from __future__ import annotations

import uuid
from fastapi.testclient import TestClient


def _h(tok, pid=None):
    h = {"Authorization": f"Bearer {tok}"}
    if pid:
        h["X-Project-Id"] = pid
    return h


def main() -> None:
    from enterprise import app as A, store, seed, review_proxy, config as cfg

    conn = store.connect()
    A.set_conn(conn)
    s = seed.seed(conn)
    pid = s["project_id"]
    c = TestClient(A.app)
    login = lambda e: c.post("/auth/login", json={"email": e}).json()["access_token"]
    line = lambda: print("-" * 72)

    admin = login("admin@demo"); mle = login("mle@demo")
    path = login("path@demo"); rev = login("reviewer@demo"); aud = login("auditor@demo")

    print("\n=== OsteoPatch Enterprise — FULL demo (E1 live + E2–E6, real G6 data) ===")
    print("Educational prototype only. Not for diagnosis.\n")

    # --- E2 ingestion: register dataset + index a small valid manifest --------
    ds = c.post("/v1/datasets", json={"source": "TCIA-Osteosarcoma", "license": "TCIA",
                "split_declared": "slide-group-independent"}, headers=_h(admin)).json()
    man = c.post(f"/v1/datasets/{ds['dataset_id']}/manifest", json={"rows": [
        {"image_id": "demo-i1", "original_label": "NON_TUMOR", "source_group": "P1"},
        {"image_id": "demo-i2", "original_label": "NECROSIS", "source_group": "P1"},
    ]}, headers=_h(admin)).json()
    print(f"[E2] dataset {ds['dataset_id']} registered; manifest indexed {man['indexed']} patches "
          f"(fail-closed on unknown labels)")

    # --- E5 registry: register the frozen G4 bundle, walk to serving ----------
    g4 = cfg.__dict__  # not used; the real hash comes from G6 health below
    bundle = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"
    c.post("/v1/models", json={"bundle_sha256": bundle, "model_id": "baseline-frozen-g4",
           "eval_card_ref": "aidlc-docs/.../g4", "split_declared": "slide-group-independent"},
           headers=_h(mle))
    c.post("/v1/models/promote", json={"bundle_sha256": bundle, "to": "candidate"}, headers=_h(mle))
    c.post("/v1/models/promote", json={"bundle_sha256": bundle, "to": "shadow"}, headers=_h(mle))
    serv = c.post("/v1/models/promote", json={"bundle_sha256": bundle, "to": "serving",
                  "eval_passed": True}, headers=_h(mle)).json()
    print(f"[E5] model {serv['model_id']} promoted registered→candidate→shadow→serving "
          f"(state={serv['state']})")

    # --- E3 inference: enqueue (idempotent); GPU execution stays gated ---------
    enq = c.post("/v1/inference/enqueue", json={"image_ids": ["demo-i1", "demo-i2"],
                 "bundle_sha256": bundle}, headers=_h(mle)).json()
    print(f"[E3] enqueued {enq['newly_queued']} inference tasks (GPU execution gated — no spend)")
    line()

    # --- E1/live review flow to generate governance material ------------------
    c.post(f"/v1/projects/{pid}/scope", json={"limit": 30}, headers=_h(admin))
    gal = c.get("/api/v1/images", headers=_h(rev, pid), params={"sort": "priority", "page_size": 3}).json()
    items = gal["items"]
    for it in items:
        c.post(f"/api/v1/images/{it['image_id']}/reviews", json={
            "prediction_id": it["prediction"]["prediction_id"], "action": "DEFER",
            "reason": "uncertain_morphology", "idempotency_key": uuid.uuid4().hex,
        }, headers=_h(rev, pid))
    print(f"[E1] reviewer deferred {len(items)} most-uncertain patches to seed governance")

    # --- E4 governance: pathologist adjudicates, captures a correction, signs off
    tgt = items[0]["image_id"]
    adj = c.post(f"/v1/projects/{pid}/adjudications", json={"image_id": tgt,
                 "resolved_label": "NECROSIS", "rationale": "necrotic debris, no viable nuclei"},
                 headers=_h(path, pid)).json()
    corr = c.post(f"/v1/projects/{pid}/corrections", json={"image_id": tgt,
                  "from_label": items[0]["prediction"]["predicted_class"], "to_label": "NECROSIS"},
                  headers=_h(rev, pid)).json()
    so = c.post(f"/v1/projects/{pid}/signoffs", json={"image_ids": [it["image_id"] for it in items],
                "states": {it["image_id"]: "deferred" for it in items}}, headers=_h(path, pid)).json()
    print(f"[E4] pathologist adjudicated {tgt} -> {adj['resolved_label']}; "
          f"correction captured (capture-only={not corr['consumed_by_training']}); "
          f"batch signed off (sha={so['content_sha'][:12]}…, locked={so['locked']})")
    line()

    # --- E6 drift monitor over the real serving bundle ------------------------
    dr = c.get(f"/v1/projects/{pid}/drift", params={"bundle_sha256": bundle}, headers=_h(mle)).json()
    print(f"[E6] drift: {dr['n_reviewed']}/{dr['n_predictions']} reviewed  "
          f"defer_rate={dr['defer_rate']:.2f}  mean_margin={dr['mean_top_two_margin']:.3f}")
    print(f"      alerts: {dr['alerts'] or 'none'}")

    # --- rollback demo (E5) ---------------------------------------------------
    b2 = "f" * 64
    c.post("/v1/models", json={"bundle_sha256": b2, "model_id": "candidate-v2",
           "eval_card_ref": "x", "split_declared": "x"}, headers=_h(mle))
    c.post("/v1/models/promote", json={"bundle_sha256": b2, "to": "candidate"}, headers=_h(mle))
    c.post("/v1/models/promote", json={"bundle_sha256": b2, "to": "shadow"}, headers=_h(mle))
    c.post("/v1/models/promote", json={"bundle_sha256": b2, "to": "serving", "eval_passed": True}, headers=_h(mle))
    now = c.get("/v1/models/serving", headers=_h(mle)).json()
    rb = c.post("/v1/models/rollback", headers=_h(mle)).json()
    print(f"[E5] promoted candidate-v2 to serving ({now['model_id']}), then ROLLBACK -> "
          f"{rb['model_id']} ({rb['bundle_sha256'][:12]}…)")
    line()

    # --- audit chain ----------------------------------------------------------
    av = c.get("/v1/audit", headers=_h(aud)).json()
    print(f"[AUDIT] chain_ok={av['chain_ok']}  entries={av['entries_verified']}")
    print("        kinds:", sorted({e["action"] for e in av["entries"]}))
    print("\n=== full enterprise demo complete — real data, no AWS mutation, no spend ===")


if __name__ == "__main__":
    main()
