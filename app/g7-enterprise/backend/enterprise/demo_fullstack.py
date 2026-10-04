"""Full-stack E1 demo over the REAL G6 data store.

Drives the whole enterprise journey end-to-end against the live 1,144-row G6
SQLite store (immutable predictions), through the auth / RBAC / tenancy gate:

  seed -> admin login -> grant real images into the project -> reviewer login
  -> real gallery (uncertainty-ranked) -> real prediction -> ACCEPT/CORRECT/DEFER
  -> export (model vs human) -> tenancy isolation -> audit chain verify.

Run (point OSTEOPATCH_DB at the real G6 store first):
  $env:OSTEOPATCH_DB="PATH_TO\osteopatch_g6.sqlite3"
  $env:PYTHONPATH="PATH_TO\app\g6\backend"
  python -m enterprise.demo_fullstack
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
    from enterprise import app as A, store, seed

    conn = store.connect()
    A.set_conn(conn)
    s = seed.seed(conn)
    pid = s["project_id"]
    c = TestClient(A.app)

    def login(email):
        return c.post("/auth/login", json={"email": email}).json()["access_token"]

    line = lambda: print("-" * 72)

    print("\n=== OsteoPatch Enterprise E1 — full-stack demo (REAL G6 data) ===")
    print("Educational prototype only. Not for diagnosis.\n")

    # 1. admin grants real images into the demo project (tenancy boundary)
    admin = login("admin@demo")
    g = c.post(f"/v1/projects/{pid}/scope", json={"limit": 50}, headers=_h(admin))
    assert g.status_code == 200, g.text
    print(f"[1] ADMIN granted {g.json()['granted']} real images into project {pid}")

    # 2. reviewer sees ONLY the granted gallery, uncertainty-ranked
    rev = login("reviewer@demo")
    gal = c.get("/api/v1/images", headers=_h(rev, pid), params={"sort": "priority", "page_size": 5})
    assert gal.status_code == 200, gal.text
    items = gal.json()["items"]
    total = gal.json().get("total")
    print(f"[2] REVIEWER gallery: total scoped={total}, top-5 by review-priority:")
    for it in items:
        pr = it["prediction"]
        print(f"      {it['image_id']:<28} pred={pr['predicted_class']:<13} "
              f"margin={pr['top_two_margin']:.3f} entropy={pr['normalized_entropy']:.3f}")
    line()

    # 3. open the single most-uncertain patch, read its immutable prediction
    target = items[0]
    img_id = target["image_id"]
    pred = target["prediction"]
    pred_id = pred["prediction_id"]
    sc = pred["scores"]
    print(f"[3] Most-uncertain patch: {img_id}")
    print(f"      scores  NON_TUMOR={sc['NON_TUMOR']:.3f}  VIABLE_TUMOR={sc['VIABLE_TUMOR']:.3f}  "
          f"NECROSIS={sc['NECROSIS']:.3f}   (uncalibrated)")
    print(f"      model suggests: {pred['predicted_class']}  bundle={pred['model_bundle_hash'][:12]}…")
    line()

    # 4. submit the three review actions against REAL predictions
    def review(image, prediction_id, action, **kw):
        body = {"prediction_id": prediction_id, "action": action,
                "idempotency_key": uuid.uuid4().hex, **kw}
        r = c.post(f"/api/v1/images/{image}/reviews", json=body, headers=_h(rev, pid))
        return r

    r1 = review(img_id, pred_id, "ACCEPT")
    print(f"[4a] ACCEPT  {img_id} -> {r1.status_code} rev={r1.json().get('revision_number')}")
    if len(items) > 1:
        img2 = items[1]["image_id"]; pid2 = items[1]["prediction"]["prediction_id"]
        r2 = review(img2, pid2, "CORRECT", selected_label="NECROSIS", reason="morphology")
        print(f"[4b] CORRECT {img2} -> NECROSIS  {r2.status_code} rev={r2.json().get('revision_number')}")
    if len(items) > 2:
        img3 = items[2]["image_id"]; pid3 = items[2]["prediction"]["prediction_id"]
        r3 = review(img3, pid3, "DEFER", reason="poor_image_quality")
        print(f"[4c] DEFER   {img3} -> {r3.status_code} rev={r3.json().get('revision_number')}")
    line()

    # 5. export preserves BOTH model prediction and human action
    exp = c.get("/api/v1/exports/reviews", headers=_h(rev, pid), params={"format": "json"})
    all_rows = exp.json()["rows"]
    reviewed = [r for r in all_rows if r.get("human_latest_action")]
    print(f"[5] EXPORT: {exp.json()['count']} rows in project scope; "
          f"{len(reviewed)} carry a human action (model prediction + action preserved)")
    for row in reviewed[:3]:
        print(f"      {row.get('image_id'):<28} model={row.get('model_predicted_class')!s:<13} "
              f"action={row.get('human_latest_action')!s:<8} human={row.get('human_corrected_class')!s}")
    line()

    # 6. tenancy isolation — a SECOND project gets DIFFERENT images
    p2 = c.post("/v1/projects", json={"name": "Project B"}, headers=_h(admin)).json()["project_id"]
    corpus = __import__("enterprise.review_proxy", fromlist=["all_corpus_image_ids"]).all_corpus_image_ids()
    other_ids = corpus[-10:]  # a disjoint tail
    gresp = c.post(f"/v1/projects/{p2}/scope", json={"image_ids": other_ids}, headers=_h(admin))
    assert gresp.status_code == 200, gresp.text
    # reviewer is NOT a member of Project B
    denied = c.get("/api/v1/images", headers=_h(rev, p2))
    print(f"[6] TENANCY: reviewer querying Project B (not a member) -> {denied.status_code} (expect 404)")
    # admin IS a member of both; confirm the two scopes are disjoint
    b_gal = c.get("/api/v1/images", headers=_h(admin, p2), params={"page_size": 100}).json()
    b_ids = {it["image_id"] for it in b_gal.get("items", [])}
    a_ids = {it["image_id"] for it in items}
    print(f"      Project A top ids ∩ Project B ids = {len(a_ids & b_ids)} (expect 0 — isolated)")
    print(f"      Project B scoped item count = {len(b_ids)} (granted {len(other_ids)})")
    line()

    # 7. audit chain
    aud = login("auditor@demo")
    av = c.get("/v1/audit", headers=_h(aud)).json()
    print(f"[7] AUDIT: chain_ok={av['chain_ok']}  entries_verified={av['entries_verified']}")
    print("    recent:", [f"{e['action']}" for e in av["entries"][-6:]])
    print("\n=== demo complete — every number above came from the real model/data ===")


if __name__ == "__main__":
    main()
