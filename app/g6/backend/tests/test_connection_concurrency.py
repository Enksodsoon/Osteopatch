"""Concurrency regression tests for the G6 SQLite connection strategy."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from osteopatch import app as app_module
from osteopatch import config


def test_production_connections_are_thread_local(tmp_path, monkeypatch):
    """Concurrent FastAPI worker threads must never share one SQLite handle.

    A single cross-thread connection produced intermittent sqlite3.InterfaceError
    under the real browser E2E journey. The production path now gives each worker
    thread its own handle while serialising first-use migrations.
    """
    monkeypatch.setattr(app_module, "_conn", None)
    monkeypatch.setattr(app_module, "_thread_conn", threading.local())
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "threaded.sqlite3")

    workers = 6
    barrier = threading.Barrier(workers)

    def open_and_query(_: int):
        barrier.wait(timeout=5)
        conn = app_module.get_conn()
        assert conn.execute("SELECT 1").fetchone()[0] == 1
        return conn

    with ThreadPoolExecutor(max_workers=workers) as pool:
        connections = list(pool.map(open_and_query, range(workers)))

    try:
        assert len({id(conn) for conn in connections}) == workers
    finally:
        for conn in connections:
            conn.close()
