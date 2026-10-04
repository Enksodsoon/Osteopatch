"""Hash-chained append-only audit log (E1 local WORM-sim).

Each entry carries the SHA-256 of the previous entry, so any tampering with an
earlier line breaks verification of every later line. E6 swaps the JSONL sink
for S3 Object-Lock; the chain logic is identical.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config

_LOCK = threading.Lock()
_GENESIS = "0" * 64


def _hash_entry(prev_hash: str, payload: dict) -> str:
    # canonical JSON (sorted keys) so the hash is reproducible
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + body).encode("utf-8")).hexdigest()


def _last_hash(path: Path) -> str:
    if not path.exists():
        return _GENESIS
    last = _GENESIS
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                last = json.loads(line)["hash"]
    return last


def record(actor: str, action: str, target: str, *, project_id: str | None = None,
           detail: dict | None = None, path: Path | None = None) -> dict:
    """Append one audit entry; returns it. Thread-safe within a process."""
    log_path = path or config.AUDIT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        prev = _last_hash(log_path)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": actor,
            "action": action,
            "target": target,
            "project_id": project_id,
            "detail": detail or {},
            "prev_hash": prev,
        }
        entry = {**payload, "hash": _hash_entry(prev, payload)}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    return entry


def verify_chain(path: Path | None = None) -> tuple[bool, int, str | None]:
    """Re-walk the chain. Returns (ok, entries_checked, first_bad_hash_or_None)."""
    log_path = path or config.AUDIT_LOG_PATH
    if not log_path.exists():
        return True, 0, None
    prev = _GENESIS
    n = 0
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            n += 1
            entry = json.loads(line)
            recomputed = _hash_entry(prev, {k: entry[k] for k in (
                "ts", "actor", "action", "target", "project_id", "detail", "prev_hash")})
            if entry.get("prev_hash") != prev or entry.get("hash") != recomputed:
                return False, n, entry.get("hash")
            prev = entry["hash"]
    return True, n, None


def read_entries(path: Path | None = None, limit: int = 200) -> list[dict]:
    log_path = path or config.AUDIT_LOG_PATH
    if not log_path.exists():
        return []
    out: list[dict] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out[-limit:]
