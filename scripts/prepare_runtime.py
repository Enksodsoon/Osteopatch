#!/usr/bin/env python
"""Locate, verify and describe OsteoPatch's runtime artifacts.

This replaces the hardcoded, machine-specific paths that previously lived in
``osteopatch/config.py`` (a dead ``C:\\Users\\enkso\\.kiro\\crew\\scratch\\...``
directory). Resolution is now, in order:

    1. the ``OSTEOPATCH_RUNTIME_ARTIFACTS`` environment variable
    2. ``<repo-root>/runtime-artifacts``
    3. ``<app-root>/runtime-artifacts``

If none of those hold the artifacts, this exits non-zero with an actionable
message naming what is missing — never a stack trace, and never a silent
fallback to an empty set.

Every artifact is hashed and checked against
``app/g6/deploy/runtime-artifacts.expected.json``, which IS committed. The
artifacts themselves never are.

    python scripts/prepare_runtime.py            # report + verify
    python scripts/prepare_runtime.py --json     # machine-readable
    python scripts/prepare_runtime.py --strict   # fail if optional bulk is absent

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXPECTED_FILE = REPO / "app" / "g6" / "deploy" / "runtime-artifacts.expected.json"

#: The original frozen G4 bundle. Recorded for identity only: this file is
#: absent from disk and is NEVER reassigned to the recovered head.
ORIGINAL_G4_BUNDLE_SHA256 = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"
RECOVERED_MODEL_ID = "g4-behavioral-recovery-r1"


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("OSTEOPATCH_RUNTIME_ARTIFACTS", "").strip()
    if env:
        roots.append(Path(env))
    roots.append(REPO / "runtime-artifacts")
    roots.append(REPO / "app" / "g6" / "runtime-artifacts")
    seen, out = set(), []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def locate(database_spec: dict) -> tuple[Path | None, list[str]]:
    """Return the first candidate root holding the database, plus a search log."""
    tried = []
    for root in candidate_roots():
        db = root / database_spec["relative_path"]
        if db.exists():
            return root, tried
        tried.append(str(root))
    return None, tried


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="also require bulk pixel artifacts")
    args = ap.parse_args()

    expected = json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))["artifacts"]
    root, tried = locate(expected["database"])

    if root is None:
        msg = (
            "runtime artifacts not found.\n"
            f"  looked in: {', '.join(tried)}\n"
            "  set OSTEOPATCH_RUNTIME_ARTIFACTS, or restore the artifacts under\n"
            "  <repo>/runtime-artifacts/.\n"
            "  These are large binaries (1,144 TIFFs, ~287 MB) and are deliberately\n"
            "  NOT committed. See app/g6/deploy/runtime-artifacts.expected.json for the\n"
            "  hashes they must match."
        )
        print(msg, file=sys.stderr)
        return 2

    report: dict = {
        "runtime_artifacts_root": str(root),
        "original_g4_bundle_sha256": ORIGINAL_G4_BUNDLE_SHA256,
        "original_g4_bundle_present": (root / "models" / "osteopatch_g4_baseline_bundle.pt").exists(),
        "recovered_model_id": RECOVERED_MODEL_ID,
        "artifacts": {},
        "bulk": {},
        "ok": True,
    }

    failures: list[str] = []
    for name, spec in expected.items():
        path = root / spec["relative_path"]
        entry: dict = {"relative_path": spec["relative_path"], "path": str(path)}
        if not path.exists():
            entry.update(status="MISSING", expected_sha256=spec["sha256"])
            failures.append(f"{name}: MISSING ({spec['relative_path']})")
            report["artifacts"][name] = entry
            continue
        actual = sha256_file(path)
        size = path.stat().st_size
        entry.update(
            status="OK" if actual == spec["sha256"] else "HASH_MISMATCH",
            actual_sha256=actual,
            expected_sha256=spec["sha256"],
            bytes=size,
            expected_bytes=spec.get("bytes"),
        )
        if entry["status"] != "OK":
            failures.append(
                f"{name}: HASH MISMATCH\n"
                f"    expected {spec['sha256']}\n"
                f"    actual   {actual}\n"
                f"    path     {path}"
            )
        report["artifacts"][name] = entry

    # Bulk pixels/thumbnails: reported, and required only under --strict.
    for sub in ("images", "thumbnails"):
        d = root / sub
        count = len(list(d.iterdir())) if d.is_dir() else 0
        report["bulk"][sub] = {"path": str(d), "count": count, "present": d.is_dir()}
    if args.strict:
        for sub, info in report["bulk"].items():
            if info["count"] == 0:
                failures.append(f"{sub}: required under --strict but empty/missing ({info['path']})")

    report["ok"] = not failures
    report["failures"] = failures

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"runtime artifacts root: {root}")
        print(f"original frozen G4 bundle present: {report['original_g4_bundle_present']}")
        for name, entry in report["artifacts"].items():
            print(f"  [{entry['status']:>13}] {name:<16} {entry['relative_path']}")
        for sub, info in report["bulk"].items():
            print(f"  [{'OK' if info['count'] else 'EMPTY':>13}] {sub:<16} {info['count']} files")
        if failures:
            print("\nFAILED:", file=sys.stderr)
            for f in failures:
                print(f"  - {f}", file=sys.stderr)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())