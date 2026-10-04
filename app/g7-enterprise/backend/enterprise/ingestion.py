"""E2 — Dataset & ingestion (local bookkeeping REAL; pixel pipeline gated).

What runs locally now:
- register a dataset (source, license, declared split) in the enterprise store
- validate + index a curated patch manifest (image_id + original_label + group),
  fail-closed on unknown labels, into a staging table ready for scope grants

What stays gated (needs the pixel pipeline / scanning / compute):
- arbitrary upload + virus/format scan (admin-capability + security review)
- WSI tiling into patches (also explicitly NOT a detector/segmenter — non-goal)
"""
from __future__ import annotations

import csv
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .scaffolds import GateNotApproved

GATE = "G-ING (ingestion approval)"
PHASE = "E2 ingestion"

CANONICAL = ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset (
    dataset_id   TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    license      TEXT,
    split_declared TEXT,
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS staged_patch (
    dataset_id   TEXT NOT NULL,
    image_id     TEXT NOT NULL,
    original_label TEXT NOT NULL,
    source_group TEXT,
    PRIMARY KEY (dataset_id, image_id)
);
"""


class IngestionError(Exception):
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def register_dataset(conn, *, source: str, license: str, split_declared: str,
                     created_by: str) -> dict:
    ensure_schema(conn)
    did = f"ds_{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO dataset(dataset_id, source, license, split_declared, created_by, "
        "created_at) VALUES (?,?,?,?,?,?)",
        (did, source, license, split_declared, created_by, _now()),
    )
    conn.commit()
    return {"dataset_id": did, "source": source}


def index_manifest(conn, *, dataset_id: str, rows: list[dict]) -> dict:
    """Index a curated manifest. Each row needs image_id + original_label; label
    must be canonical (fail-closed — an unknown label aborts the whole index)."""
    ensure_schema(conn)
    if conn.execute("SELECT 1 FROM dataset WHERE dataset_id=?", (dataset_id,)).fetchone() is None:
        raise IngestionError("unknown dataset_id", 404)
    unknown = sorted({r["original_label"] for r in rows if r["original_label"] not in CANONICAL})
    if unknown:
        raise IngestionError(f"fail-closed: unknown labels {unknown} (never guessed)")
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO staged_patch(dataset_id, image_id, original_label, "
            "source_group) VALUES (?,?,?,?)",
            (dataset_id, r["image_id"], r["original_label"], r.get("source_group")),
        )
    conn.commit()
    return {"dataset_id": dataset_id, "indexed": len(rows)}


def index_manifest_csv(conn, *, dataset_id: str, csv_path: str | Path) -> dict:
    p = Path(csv_path)
    if not p.exists():
        raise IngestionError(f"manifest not found: {p}", 404)
    with p.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return index_manifest(conn, dataset_id=dataset_id, rows=rows)


def staged_image_ids(conn, dataset_id: str) -> list[str]:
    ensure_schema(conn)
    return [r["image_id"] for r in conn.execute(
        "SELECT image_id FROM staged_patch WHERE dataset_id=? ORDER BY image_id",
        (dataset_id,))]


# --- gated pixel pipeline -------------------------------------------------
def scan_and_upload(path: str):
    raise GateNotApproved(PHASE, GATE, "Virus/format scan + arbitrary upload gated.")


def tile_wsi(path: str, patch_px: int = 256):
    raise GateNotApproved(PHASE, GATE,
                          "WSI tiler gated (and OsteoPatch is NOT a detector/segmenter).")
