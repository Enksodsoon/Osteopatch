#!/usr/bin/env python
"""Regenerate the per-app requirements.txt compatibility shims from pyproject.toml.

The canonical dependency definition is the root pyproject.toml + uv.lock.
app/g6/backend/requirements.txt and app/g7-enterprise/backend/requirements.txt
are kept ONLY because Docker build contexts and existing documentation reference
them. They are generated, never hand-edited.

Run after changing dependencies:
    python scripts/sync_requirements.py          # writes the shims
    python scripts/sync_requirements.py --check  # exits 1 if they are stale

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"

TARGETS = {
    REPO / "app" / "g6" / "backend" / "requirements.txt": "G6",
    REPO / "app" / "g7-enterprise" / "backend" / "requirements.txt": "Enterprise (E1)",
}

HEADER = """\
# GENERATED FILE — DO NOT EDIT BY HAND.
# Source of truth: pyproject.toml (dependency versions) + uv.lock (exact pins).
# Regenerate with:  python scripts/sync_requirements.py
# Verify with:      python scripts/sync_requirements.py --check
#
# This file exists only so Docker build contexts and documentation that
# reference it keep working. Two hand-maintained dependency lists is exactly
# how these diverged before; there is now one source of truth.
#
# Educational research prototype. Not for diagnosis, treatment decisions,
# or predicting treatment response.
"""

ENTERPRISE_ONLY: set[str] = set()


def load() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def render(app: str, cfg: dict) -> str:
    lines = [HEADER]
    deps: list[str] = list(cfg["project"]["dependencies"])
    # Both apps install from the ONE project definition; the shims differ only
    # in which extras they pull. Dedup while preserving first-seen order.
    deps = list(dict.fromkeys(deps))
    dev = cfg["project"]["optional-dependencies"]["dev"]
    lines.append(f"\n# --- {app}: runtime ---")
    for d in sorted(deps):
        lines.append(d)
    lines.append(f"\n# --- {app}: dev / test ---")
    for d in sorted(dev):
        lines.append(d)
    lines.append("")
    return "\n".join(lines)


def _name(spec: str) -> str:
    return spec.split("=")[0].split(">")[0].split("<")[0].split("[")[0].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify shims are current")
    args = ap.parse_args()

    cfg = load()
    stale: list[Path] = []
    for path, app in TARGETS.items():
        want = render(app, cfg)
        if not path.exists() or path.read_text(encoding="utf-8") != want:
            stale.append(path)
            if not args.check:
                path.write_text(want, encoding="utf-8")
                print(f"wrote   {path.relative_to(REPO)}")
            else:
                print(f"STALE   {path.relative_to(REPO)}")
    if args.check:
        if stale:
            print(
                f"\n{len(stale)} requirements shim(s) out of date. "
                "Run: python scripts/sync_requirements.py"
            )
            return 1
        print("requirements shims are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())