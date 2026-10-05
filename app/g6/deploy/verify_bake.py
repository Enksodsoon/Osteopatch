#!/usr/bin/env python
"""Verify baked runtime artifacts by HASH inside the built image.

Runs as a Docker build step. The Dockerfile COPYs three runtime artifacts into
the image; this confirms each is byte-identical to the committed expectation.

Filename identity is not sufficient: a rebuilt or substituted database with the
right name would otherwise sail through and produce an image that is not the one
that was certified.

    python verify_bake.py <bake_dir> <expected.json>

Exit 0 = all match. Exit 1 = drift; the Docker build fails.

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify_bake.py <bake_dir> <expected.json>", file=sys.stderr)
        return 64

    bake_dir = Path(sys.argv[1])
    expected = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["artifacts"]

    layout = {
        "database": "db/osteopatch_g6.sqlite3",
        "recovered_model": "models/g4-behavioral-recovery-r1.pt",
        "g8_subset": "g8-subset-image-ids.json",
    }

    failed = False
    for key, rel in layout.items():
        path = bake_dir / rel
        want = expected[key]["sha256"]
        if not path.exists():
            print(f"::error::baked artifact missing: {key} at {rel}", file=sys.stderr)
            failed = True
            continue
        got = sha256_file(path)
        if got != want:
            print(
                f"::error::baked artifact drift for {key}\n"
                f"  expected {want}\n"
                f"  actual   {got}\n"
                f"  path     {rel}\n"
                "Refusing to build an image from a drifted build context.",
                file=sys.stderr,
            )
            failed = True
            continue
        print(f"[ok] {key:<16} {rel}  {got[:16]}…")

    if not failed:
        print("baked runtime artifacts verified against committed expectations")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())