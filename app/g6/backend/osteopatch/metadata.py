"""Load source/QC metadata into the ``source_qc`` table.

Reads the FROZEN QC artifacts (read-only) and mirrors them into SQLite. Three
facts are kept distinct and never conflated:

  * ``original_label``    — the dataset-provided canonical label. May be an
                            EXCLUDED class (e.g. MIXED_VIABLE_NECROTIC). This is
                            source metadata, NOT a model output.
  * ``training_eligible`` — the frozen training gate (0/1). NOT a biological
                            class.
  * ``qc_review_flag``    — membership in the 63-row DATA-QC human-review-queue.
                            Kept SEPARATE from the model review-priority queue.

The model has exactly 3 outputs; nothing here becomes a 4th class.
"""
from __future__ import annotations

import csv
import sqlite3

from . import config


def _to_bool(val: str) -> int:
    return 1 if str(val).strip().lower() in {"true", "1", "yes"} else 0


def _load_qc_review_ids() -> dict[str, str]:
    """image_id -> human-readable reason, for the 63-row DATA-QC queue."""
    out: dict[str, str] = {}
    if not config.HUMAN_REVIEW_QUEUE.exists():
        return out
    with open(config.HUMAN_REVIEW_QUEUE, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            iid = (r.get("image_id") or "").strip()
            if not iid:
                continue
            bits = []
            if (r.get("content_flags") or "").strip():
                bits.append(r["content_flags"].strip())
            if (r.get("primary_qc_status") or "").strip():
                bits.append(r["primary_qc_status"].strip())
            out[iid] = "; ".join(bits) if bits else "DATA_QC_REVIEW"
    return out


def load_source_metadata(conn: sqlite3.Connection) -> dict[str, int]:
    """Populate ``source_qc`` from the frozen full-image QC results. Idempotent
    (INSERT OR REPLACE by image_id). Returns a small summary dict.

    Uses ``full-image-qc-results.csv`` because that is the artifact carrying
    ``primary_qc_status``, ``training_eligible`` and ``content_flags``; the
    ingestion manifest carries only provenance columns.
    """
    qc_review = _load_qc_review_ids()
    rows_in = 0
    source_csv = config.QC_RESULTS if config.QC_RESULTS.exists() else config.INGESTION_MANIFEST
    with open(source_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        payload = []
        for r in reader:
            iid = r["image_id"].strip()
            local = r.get("local_path", "") or ""
            fname = local.replace("\\", "/").rsplit("/", 1)[-1]
            flags = (r.get("content_flags") or "").strip()
            payload.append(
                (
                    iid,
                    r.get("group", "").strip(),
                    (r.get("canonical_label") or "").strip() or None,
                    r.get("primary_qc_status", "").strip() or "UNKNOWN",
                    _to_bool(r.get("training_eligible", "")),
                    1 if iid in qc_review else 0,
                    qc_review.get(iid) or (flags or None),
                    fname,
                )
            )
            rows_in += 1
    conn.executemany(
        """
        INSERT OR REPLACE INTO source_qc
          (image_id, source_group, original_label, primary_qc_status,
           training_eligible, qc_review_flag, qc_review_reason, tiff_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    conn.commit()
    return {
        "images_indexed": rows_in,
        "qc_review_flagged": len(qc_review),
        "training_eligible": conn.execute(
            "SELECT COUNT(*) FROM source_qc WHERE training_eligible = 1"
        ).fetchone()[0],
    }
