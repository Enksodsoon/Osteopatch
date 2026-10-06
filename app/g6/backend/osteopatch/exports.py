"""Export serialisation — one implementation, two callers.

The G6 route and the enterprise unified app both export review rows. Before
this module each formatted its own CSV, which meant the two downloads could
drift (a new column, a different header) while both still called themselves
"the review export". The shape lives here so the bytes are identical.

Nothing here interprets a row. The rows arrive from ``queries.export_rows``,
which already preserves BOTH the immutable model prediction and the human
correction, plus the disclaimer.
"""
from __future__ import annotations

import csv
import io

from . import config


def rows_to_csv(rows: list[dict]) -> str:
    """CSV text with the first row's keys as the header.

    Column order is therefore the row dict's insertion order, which is stable
    for a given read model. An empty review set yields an empty file rather than
    a header-only file, matching the original behaviour.
    """
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return buf.getvalue()


def json_envelope(rows: list[dict]) -> dict:
    """JSON envelope carrying provenance alongside the rows.

    ``model_version`` / ``model_bundle_sha256`` travel with the data so a
    downloaded file can never be read as though it came from a different model.
    """
    return {
        "disclaimer": config.DISCLAIMER,
        "model_version": config.MODEL_VERSION,
        "model_bundle_sha256": config.EXPECTED_BUNDLE_SHA256,
        "count": len(rows),
        "rows": rows,
    }


CSV_FILENAME = "osteopatch_reviews.csv"
