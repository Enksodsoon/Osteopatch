#!/usr/bin/env python
"""Verify the vendored prompt pack against its own SHA256_MANIFEST.json.

The prompt pack originally lived only on the owner's Desktop, outside version
control. It is vendored at aidlc-docs/prompt-pack/ so the 129-task roadmap
cannot be lost to a reset. This checker proves the vendored copy is byte
identical to the authored pack, and is safe to re-run in CI or by hand.

Exit codes: 0 every listed file matches, 1 at least one mismatch or the
manifest itself is unusable.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent / "aidlc-docs" / "prompt-pack"
MANIFEST_NAME = "SHA256_MANIFEST.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    manifest_path = PACK_ROOT / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"FAIL: manifest not found at {manifest_path}")
        return 1
    try:
        expected: dict[str, str] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: manifest is not valid JSON: {exc}")
        return 1
    if not expected:
        print("FAIL: manifest contains no entries")
        return 1

    # The manifest cannot hash itself; ignore it if it lists itself.
    checked = 0
    missing: list[str] = []
    mismatched: list[tuple[str, str, str]] = []
    for rel, want in sorted(expected.items()):
        if rel == MANIFEST_NAME:
            continue
        target = PACK_ROOT / rel
        if not target.is_file():
            missing.append(rel)
            continue
        got = sha256_file(target)
        checked += 1
        if got != want:
            mismatched.append((rel, want, got))

    for rel in missing:
        print(f"MISSING: {rel}")
    for rel, want, got in mismatched:
        print(f"MISMATCH: {rel}\n  expected {want}\n  actual   {got}")

    total = len([k for k in expected if k != MANIFEST_NAME])
    if missing or mismatched:
        print(f"FAIL: {checked}/{total} matched, {len(missing)} missing, {len(mismatched)} mismatched")
        return 1
    print(f"OK: {checked}/{total} prompt-pack files match SHA256_MANIFEST.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
