"""Temporary probe: is the ALREADY-RUNNING API on 8137 serving current code?

The distinctive marker of current code is `limitations_full` (the 34-entry
catalog). A server started before that work answers /v1/model-card without it.
"""

import json
import sys
import urllib.request

URL = "http://127.0.0.1:8137/v1/model-card"

try:
    with urllib.request.urlopen(URL, timeout=10) as r:
        d = json.load(r)
except Exception as exc:  # noqa: BLE001 - diagnostic probe
    print(f"FAIL: could not reach {URL}: {exc}")
    sys.exit(1)

frozen = d.get("limitations")
full = d.get("limitations_full")

print("top-level keys:", sorted(d.keys()))
print()
print("limitations (frozen five) count:", len(frozen) if isinstance(frozen, list) else "MISSING")
print("limitations_full present:", full is not None)
print("limitations_full entries:", len(full) if isinstance(full, list) else "n/a")
print("evaluation_evidence_available:", d.get("evaluation_evidence_available", "<key absent -> STALE CODE>"))
print()
if isinstance(full, list) and full:
    cats = sorted({str(x.get("category")) for x in full})
    print("categories:", len(cats), cats)
    v = [x for x in full if "VIABLE" in str(x.get("title", "")).upper()]
    print("VIABLE_TUMOR entry found:", bool(v))
    if v:
        print("  title:", v[0].get("title"))