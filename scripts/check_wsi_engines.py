#!/usr/bin/env python
"""Report which whole-slide image reader engines are actually usable.

The WSI stack is capability-detected, never assumed. This script prints the
same report the API exposes on /health so a CI log records which engine a
machine actually has.

OpenSlide is OPTIONAL. When absent, the Pillow fallback reader is used and
reports only metadata the file genuinely contains — null otherwise, never
invented.

    python scripts/check_wsi_engines.py

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "g6" / "backend"))

from osteopatch.pathology import reader  # noqa: E402


def main() -> int:
    report = reader.engine_report()
    print(json.dumps(report, indent=2, sort_keys=True))

    # Exit 0 regardless of which engines exist: a machine without OpenSlide is
    # a valid configuration, not a failure. This job records capability; it
    # does not gate on it.
    return 0


if __name__ == "__main__":
    sys.exit(main())