#!/usr/bin/env python
"""Rebuild the GitHub-free Docker build context at app/g6/deploy/_bake/.

The Dockerfile COPYs three files from ``deploy/_bake/``. That directory is
gitignored and, before this script existed, was produced by no committed
process — so a clean clone could not build the image at all.

This reconstructs it by COPYING verified artifacts. It never creates, mutates,
or fabricates a database, a model, or a subset list: each source is hashed and
checked against ``app/g6/deploy/runtime-artifacts.expected.json`` first, and a
mismatch aborts before anything is written.

Nothing here is committed. The binaries stay out of git; only this script and
the expected-hash file do.

    python scripts/prepare_bake.py           # build _bake/
    python scripts/prepare_bake.py --verify  # verify an existing _bake/
    python scripts/prepare_bake.py --clean   # remove _bake/

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXPECTED_FILE = REPO / "app" / "g6" / "deploy" / "runtime-artifacts.expected.json"
BAKE_DIR = REPO / "app" / "g6" / "deploy" / "_bake"

#: source relative path (under runtime-artifacts) -> destination (under _bake)
LAYOUT = {
    "database": "_bake/db/osteopatch_g6.sqlite3",
    "recovered_model": "_bake/models/g4-behavioral-recovery-r1.pt",
    "g8_subset": "_bake/g8-subset-image-ids.json",
}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def resolve_root() -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from prepare_runtime import candidate_roots  # single source of truth

    db_rel = json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))["artifacts"]["database"][
        "relative_path"
    ]
    for root in candidate_roots():
        if (root / db_rel).exists():
            return root
    raise SystemExit(
        "runtime artifacts not found; run scripts/prepare_runtime.py for details"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="verify only, do not copy")
    ap.add_argument("--clean", action="store_true", help="remove the _bake directory")
    args = ap.parse_args()

    if args.clean:
        if BAKE_DIR.exists():
            shutil.rmtree(BAKE_DIR)
            print(f"removed {BAKE_DIR.relative_to(REPO)}")
        else:
            print("nothing to clean")
        return 0

    spec = json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))["artifacts"]
    root = resolve_root()

    if args.verify:
        mode = "verify"
    else:
        mode = "build"

    # Verify EVERY source before writing ANY destination, so a partial bake can
    # never be produced.
    plan: list[tuple[str, Path, Path, str]] = []
    for key, dest_rel in LAYOUT.items():
        s = spec[key]
        src = root / s["relative_path"]
        if not src.exists():
            print(f"  [MISSING   ] {key}: {src}", file=sys.stderr)
            return 2
        actual = sha256_file(src)
        if actual != s["sha256"]:
            print(
                f"  [MISMATCH  ] {key}\n"
                f"      expected {s['sha256']}\n"
                f"      actual   {actual}\n"
                f"      source   {src}",
                file=sys.stderr,
            )
            return 1
        plan.append((key, src, REPO / "app" / "g6" / "deploy" / dest_rel, actual))
        print(f"  [{'OK':>11}] {key:<16} {s['relative_path']}")

    if args.verify:
        bad = 0
        for _key, _src, dest, expected_sha in plan:
            if not dest.exists():
                print(f"  [MISSING   ] {dest.relative_to(REPO)}", file=sys.stderr)
                bad += 1
            elif sha256_file(dest) != expected_sha:
                print(f"  [MISMATCH  ] {dest.relative_to(REPO)}", file=sys.stderr)
                bad += 1
            else:
                print(f"  [{'OK':>11}] {dest.relative_to(REPO)}")
        return 1 if bad else 0

    for _key, src, dest, _sha in plan:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    # Record what was baked, so the build context is self-describing.
    (BAKE_DIR / "MANIFEST.json").write_text(
        json.dumps(
            {
                "built_from": str(root),
                "expected_hashes": EXPECTED_FILE.name,
                "note": "Generated. Do not commit; regenerable via scripts/prepare_bake.py.",
                "artifacts": {
                    key: {"sha256": sha, "dest": LAYOUT[key]}
                    for key, _src, _dest, sha in plan
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n{mode} complete: {BAKE_DIR.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())