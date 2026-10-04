#!/usr/bin/env python
"""Fail CI when a declared dependency has no row in docs/dependencies.md.

The handoff brief requires every third-party dependency to carry: name,
version, source, license, why it is needed, what depends on it, runtime
footprint, fallback behaviour, and security considerations.

This check keeps that record honest: a dependency added to pyproject.toml
without a register row fails the build.

    python scripts/check_deps.py          # check
    python scripts/check_deps.py --list   # show what it matched

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
REGISTER = REPO / "docs" / "dependencies.md"

# Distro name -> the aliases that may appear in the register. Case-insensitive.
# `uvicorn[standard]` normalises to `uvicorn`.
def canonical(name: str) -> str:
    return re.split(r"[\[<>=!; ]", name.strip(), maxsplit=1)[0].strip().lower()


def declared(cfg: dict) -> list[str]:
    names: list[str] = []
    names += [canonical(d) for d in cfg["project"].get("dependencies", [])]
    for extra_deps in cfg["project"].get("optional-dependencies", {}).values():
        names += [canonical(d) for d in extra_deps]
    return sorted(set(names))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list matched/unmatched")
    args = ap.parse_args()

    if not REGISTER.exists():
        print(f"::error::{REGISTER} is missing — dependency governance is mandatory")
        return 1

    with PYPROJECT.open("rb") as fh:
        cfg = tomllib.load(fh)

    text = REGISTER.read_text(encoding="utf-8").lower()
    wanted = declared(cfg)

    # `ruff`/`mypy` are grouped in one markdown table row each; a plain
    # substring search over the register is intentionally permissive here —
    # the governance requirement is that a record EXISTS, and the register's
    # own governance rule states licenses must be read from upstream.
    missing = [name for name in wanted if name not in text]

    if args.list:
        print("declared:", ", ".join(wanted))
        print("missing :", ", ".join(missing) if missing else "(none)")

    if missing:
        print(
            "::error::dependencies declared in pyproject.toml but absent from "
            "docs/dependencies.md: " + ", ".join(missing)
        )
        print("Add a row for each, in the SAME commit that introduces it.")
        return 1

    print(f"all {len(wanted)} declared dependencies have a register row")
    return 0


if __name__ == "__main__":
    sys.exit(main())