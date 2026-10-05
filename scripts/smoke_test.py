#!/usr/bin/env python
"""One command that proves the whole local product works end to end.

Runs, in order:

  1. ``scripts/prepare_runtime.py``  — locate and hash-verify the runtime
     artifacts, so a missing prerequisite produces an actionable message
     instead of a confusing failure deep inside a server boot.
  2. ``app/local-tester.py``          — boot BOTH apps on 127.0.0.1 and drive
     them over real HTTP against real data: gallery, patch detail, scores,
     review submission, persistence across reload, export, attribution
     metadata, tenancy, governance, registry, drift and audit.

This is a Python entry point rather than a Makefile target because ``make`` is
not present on every developer machine (it is absent on Windows by default).
The Makefile exposes the same commands for environments that have it.

Requires no AWS account and spends nothing. Exits non-zero if any check fails.

    python scripts/smoke_test.py
    python scripts/smoke_test.py --only g6
    python scripts/smoke_test.py --keep-workspace

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTER = REPO / "app" / "local-tester.py"
PREPARE = REPO / "scripts" / "prepare_runtime.py"
DEFAULT_OUT = REPO / "docs" / "evidence" / "smoke-result.json"


def run(cmd: list[str], label: str) -> int:
    print(f"\n{'=' * 70}\n== {label}\n{'=' * 70}")
    proc = subprocess.run(cmd, cwd=str(REPO))
    print(f"\n-- {label}: exit {proc.returncode}")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["g6", "enterprise", "all"], default="all")
    ap.add_argument("--keep-workspace", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--skip-prepare",
        action="store_true",
        help="skip the artifact precondition check (not recommended)",
    )
    args = ap.parse_args()

    if not args.skip_prepare:
        rc = run([sys.executable, str(PREPARE)], "preflight: runtime artifacts")
        if rc != 0:
            print(
                "\nSMOKE ABORTED: runtime artifacts are missing or do not match "
                "their committed hashes.\nSee app/g6/deploy/runtime-artifacts.expected.json.\n"
                "The artifacts are large binaries and are deliberately not committed.",
                file=sys.stderr,
            )
            return rc

    cmd = [sys.executable, str(TESTER), "--only", args.only]
    if args.keep_workspace:
        cmd.append("--keep-workspace")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["--out", str(args.out)]

    rc = run(cmd, "end-to-end local smoke (real HTTP, real data)")

    print(f"\n{'=' * 70}")
    if rc == 0:
        print(f"SMOKE PASSED — evidence written to {args.out.relative_to(REPO)}")
    else:
        print(f"SMOKE FAILED (exit {rc}) — evidence written to {args.out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())