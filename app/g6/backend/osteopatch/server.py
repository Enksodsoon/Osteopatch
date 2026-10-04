"""Run the OsteoPatch G6 API server, bound to 127.0.0.1 ONLY.

    python -m osteopatch.server

Never binds 0.0.0.0. The database must already be migrated + precomputed via
``python precompute.py`` (which the server also lazily migrates on first query).
"""
from __future__ import annotations

import uvicorn

from . import config


def main() -> None:
    uvicorn.run(
        "osteopatch.app:app",
        host=config.HOST,   # 127.0.0.1
        port=config.PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
