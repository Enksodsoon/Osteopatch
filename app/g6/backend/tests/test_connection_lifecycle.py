"""F007 acceptance tests — bounded database connection lifetime.

Task: F007 (verify and bound database connection lifetime and concurrent writes).
Task-owned test file for this increment. Each test is tagged with the F007
acceptance ID it exercises so a reviewer can trace assertion -> executable
evidence.

Disposable databases only: ``tmp_path``. Nothing here may touch the canonical
review store, so every test that opens a connection points ``config.DB_PATH``
at its own temporary file first.

The seeded rows are SYNTHETIC (source_group/original_label say FIXTURE) and
carry the active bundle identity so export/gallery assertions have something to
check against — the same convention the existing ``conftest`` fixture uses. No
inference ran here and nothing here is evidence about a real model.
"""
from __future__ import annotations

import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from osteopatch import app as app_module  # noqa: E402
from osteopatch import config, db, queries, repo  # noqa: E402

BUNDLE_HASH = config.EXPECTED_BUNDLE_SHA256

# Deterministic synthetic fixture rows: (image_id, source_group, scores).
SEED = [
    ("img-ambiguous", "Case-3", [0.33, 0.34, 0.33]),
    ("img-clear-nt", "Case-4", [0.90, 0.05, 0.05]),
    ("img-mid-nec", "Case-48", [0.20, 0.25, 0.55]),
]


def _pid(image_id: str) -> str:
    return repo.prediction_id_for(image_id, BUNDLE_HASH)


def _is_open(conn: sqlite3.Connection) -> bool:
    """A closed sqlite3 handle raises ProgrammingError on any operation."""
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False
    return True


def _seed(path: Path) -> sqlite3.Connection:
    conn = db.connect(path)
    db.run_migrations(conn)
    for image_id, group, scores in SEED:
        conn.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label, "
            "primary_qc_status, training_eligible, qc_review_flag, "
            "qc_review_reason, tiff_filename) VALUES (?,?,'FIXTURE_LABEL','PASS',1,0,"
            "NULL,?)",
            (image_id, group, f"{image_id}.tiff"),
        )
        repo.upsert_prediction(conn, image_id, BUNDLE_HASH, "baseline-frozen-g4", scores)
    conn.commit()
    return conn


def _other_handle(path: Path, busy_timeout_ms: int = 250) -> sqlite3.Connection:
    """An independent connection, used to observe whether a write lock is held."""
    other = db.connect(path)
    other.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
    return other


@pytest.fixture()
def db_path(tmp_path) -> Path:
    path = tmp_path / "lifecycle.sqlite3"
    keeper = _seed(path)
    keeper.close()
    return path


@pytest.fixture(autouse=True)
def _isolated_lifecycle(monkeypatch, db_path):
    """Give every test a private connection lifecycle.

    ``raising=False`` because this task introduces the registry/lock names; the
    fixture must also work against the pre-change module so a failure is the
    missing behavior, not a broken fixture.
    """
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(app_module, "_conn", None, raising=False)
    monkeypatch.setattr(app_module, "_thread_conn", threading.local(), raising=False)
    monkeypatch.setattr(app_module, "_open_conns", {}, raising=False)
    monkeypatch.setattr(app_module, "_open_conns_lock", threading.Lock(), raising=False)
    monkeypatch.setattr(db, "_MIGRATED", set(), raising=False)
    monkeypatch.setattr(db, "_MIGRATION_LOCK", threading.Lock(), raising=False)
    yield
    # Teardown calls the release API this task introduces. getattr keeps a
    # pre-change failure attributable to the test that caused it instead of
    # raising a fixture error over the top of the real assertion.
    close_all = getattr(app_module, "close_all_connections", None)
    if close_all is not None:
        close_all()


# ---------------------------------------------------------------------------
# F007-AT01 — concurrent reads do not produce sqlite InterfaceError
# ---------------------------------------------------------------------------
def test_at01_concurrent_reads_produce_no_interface_error(db_path):
    """8 threads x 25 gallery+detail reads, released simultaneously.

    Baseline behaviour (verified, reused): each worker thread owns its own
    handle, so no shared-cursor ``InterfaceError``.
    """
    workers, iterations = 8, 25
    barrier = threading.Barrier(workers)
    handles: dict[int, sqlite3.Connection] = {}
    failures: list[str] = []

    def read_traffic(index: int) -> None:
        try:
            barrier.wait(timeout=15)
            for step in range(iterations):
                conn = app_module.get_conn()
                handles[id(conn)] = conn
                queries.list_images(conn, sort="priority")
                assert queries.get_image(conn, SEED[step % len(SEED)][0]) is not None
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            failures.append(f"{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(read_traffic, range(workers)))

    assert failures == []
    # one handle per worker thread, never one shared handle
    assert len(handles) == workers
    assert queries.list_images(app_module.get_conn(), sort="priority")["total"] >= len(SEED)


# ---------------------------------------------------------------------------
# F007-AT02 — two distinct writes at revision 0 cannot both create revision 1
# ---------------------------------------------------------------------------
def test_at02_distinct_writes_at_revision_zero_create_exactly_one_event(db_path):
    """8 writers, 8 distinct idempotency keys, ALL claiming expected_revision=0."""
    writers = 8
    barrier = threading.Barrier(writers)
    created: list[int] = []
    conflicts: list[str] = []
    unexpected: list[str] = []
    lock = threading.Lock()

    def write(index: int) -> None:
        conn = app_module.get_conn()
        barrier.wait(timeout=15)
        try:
            repo.submit_review(
                conn, "img-clear-nt", _pid("img-clear-nt"), "ACCEPT",
                expected_revision=0, idempotency_key=f"f007-race-{index}",
            )
        except repo.ConflictError as exc:
            with lock:
                conflicts.append(exc.message)
        except Exception as exc:  # noqa: BLE001
            with lock:
                unexpected.append(f"{type(exc).__name__}: {exc}")
        else:
            with lock:
                created.append(index)

    with ThreadPoolExecutor(max_workers=writers) as pool:
        list(pool.map(write, range(writers)))

    assert unexpected == []
    assert len(created) == 1
    assert len(conflicts) == writers - 1

    conn = db.connect(db_path)
    rows = conn.execute(
        "SELECT revision_number, COUNT(*) AS n FROM review_event "
        "WHERE image_id = 'img-clear-nt' GROUP BY revision_number"
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM review_event WHERE image_id = 'img-clear-nt'"
    ).fetchone()[0]
    conn.close()
    assert total == 1
    assert [r["n"] for r in rows] == [1]
    assert rows[0]["revision_number"] == 1


def test_at02_same_idempotency_key_replays_instead_of_double_writing(db_path):
    """The other half of step 06: same key from 8 threads -> one event, 7 replays."""
    writers = 8
    barrier = threading.Barrier(writers)
    results: list[tuple[bool, int]] = []
    lock = threading.Lock()

    def db_module_conn() -> sqlite3.Connection:
        return db.connect(db_path)

    def replay(index: int) -> None:
        conn = db_module_conn()
        barrier.wait(timeout=15)
        event, was_created = repo.submit_review(
            conn, "img-mid-nec", _pid("img-mid-nec"), "DEFER",
            expected_revision=0, idempotency_key="f007-same-key", reason="mixed_tissue",
        )
        with lock:
            results.append((was_created, event["revision_number"]))

    with ThreadPoolExecutor(max_workers=writers) as pool:
        list(pool.map(replay, range(writers)))

    conn = db_module_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM review_event WHERE image_id = 'img-mid-nec'"
    ).fetchone()[0]
    conn.close()
    assert sum(1 for created, _ in results if created) == 1
    assert {rev for _, rev in results} == {1}
    assert total == 1


# ---------------------------------------------------------------------------
# F007-AT03 — connections and transactions are released after handler
#             exceptions and at application shutdown
# ---------------------------------------------------------------------------
def _begin_uncommitted_write(conn: sqlite3.Connection, image_id: str) -> None:
    """Start a write transaction and leave it open (no commit)."""
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "INSERT INTO review_event(review_event_id, image_id, prediction_id, action, "
        "selected_class, reason, note, reviewer, created_at, revision_number, "
        "idempotency_key) VALUES (?,?,?,'ACCEPT',NULL,NULL,NULL,'f007','2026-01-01',"
        "9001,'f007-uncommitted')",
        ("f007-event-9001", image_id, _pid(image_id)),
    )


def test_at03_release_rolls_back_and_closes_this_threads_connection(db_path):
    """release_conn() must end the transaction AND close the handle."""
    conn = app_module.get_conn()
    assert conn.in_transaction is False
    _begin_uncommitted_write(conn, "img-clear-nt")
    assert conn.in_transaction is True

    released = app_module.release_conn()

    assert released is True
    assert _is_open(conn) is False
    assert app_module.get_conn() is not conn  # next request gets a fresh handle

    # the rolled-back write is gone
    fresh = app_module.get_conn()
    assert fresh.execute(
        "SELECT COUNT(*) FROM review_event WHERE review_event_id = 'f007-event-9001'"
    ).fetchone()[0] == 0

    # and this thread no longer holds the database write lock
    other = _other_handle(db_path)
    try:
        other.execute("BEGIN IMMEDIATE")
        other.rollback()
    finally:
        other.close()


def test_nested_request_scopes_release_once_at_the_outermost_exit(db_path):
    """An inner scope must not close the handle its caller is still using."""
    with app_module.request_connection() as outer:
        with app_module.request_connection() as inner:
            assert inner is outer
        # the inner scope left the handle open for the outer one
        assert app_module.open_connection_count() == 1
        assert outer.execute("SELECT COUNT(*) FROM source_qc").fetchone()[0] == len(SEED)
    assert app_module.open_connection_count() == 0


def test_at03_release_is_idempotent_and_safe_when_nothing_is_open(db_path):
    assert app_module.release_conn() is False  # nothing cached yet
    app_module.get_conn()
    assert app_module.release_conn() is True
    assert app_module.release_conn() is False


def test_at03_shutdown_closes_every_open_connection(db_path):
    """Application shutdown must release all worker-thread connections."""
    workers = 4
    barrier = threading.Barrier(workers)
    handles: list[sqlite3.Connection] = []
    lock = threading.Lock()

    def hold(index: int) -> None:
        conn = app_module.get_conn()
        barrier.wait(timeout=15)
        with lock:
            handles.append(conn)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(hold, range(workers)))

    assert len(handles) == workers
    assert all(_is_open(c) for c in handles)
    assert app_module.open_connection_count() == workers

    closed = app_module.close_all_connections()

    assert closed == workers
    assert app_module.open_connection_count() == 0
    assert not any(_is_open(c) for c in handles)


def test_at03_handler_exception_leaves_no_transaction_for_the_next_request(db_path):
    """A request that dies mid-write must not hand its transaction on."""
    conn = app_module.get_conn()

    with pytest.raises(RuntimeError, match="simulated handler failure"):
        with app_module.request_connection() as scoped:
            assert scoped is conn
            _begin_uncommitted_write(scoped, "img-mid-nec")
            raise RuntimeError("simulated handler failure")

    assert _is_open(conn) is False
    assert app_module.open_connection_count() == 0

    # the next request on this thread is clean and can write
    with app_module.request_connection() as next_conn:
        assert next_conn.in_transaction is False
        repo.submit_review(
            next_conn, "img-mid-nec", _pid("img-mid-nec"), "ACCEPT",
            expected_revision=0, idempotency_key="f007-after-failure",
        )
    assert app_module.open_connection_count() == 0


def test_at03_app_lifespan_shutdown_releases_connections(db_path):
    """The real shutdown wiring, not just the helper it calls."""
    from fastapi.testclient import TestClient

    app_module.get_conn()
    assert app_module.open_connection_count() >= 1

    with TestClient(app_module.app) as client:
        assert client.get("/v1/health").status_code == 200

    assert app_module.open_connection_count() == 0


# ---------------------------------------------------------------------------
# F007-AT04 — existing set_conn fixtures still run, and never reach canonical data
# ---------------------------------------------------------------------------
def test_at04_injected_connection_survives_the_request_lifecycle(db_path, monkeypatch):
    """Fixture injection keeps working: the injected handle is never closed."""
    from fastapi.testclient import TestClient

    injected = _seed(db_path.parent / "injected.sqlite3")

    opened: list[object] = []
    real_connect = db.connect

    def spy(*args, **kwargs):  # pragma: no cover - must never run
        opened.append((args, kwargs))
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(db, "connect", spy)
    app_module.set_conn(injected)
    try:
        with app_module.request_connection() as conn:
            assert conn is injected
        assert _is_open(injected) is True
        assert app_module.open_connection_count() == 0
        assert injected.execute("SELECT COUNT(*) FROM source_qc").fetchone()[0] == len(SEED)

        with TestClient(app_module.app) as client:
            assert client.get("/v1/images").status_code == 200
            assert client.get("/v1/health").json()["status"] == "ok"
        assert _is_open(injected) is True
    finally:
        app_module.set_conn(None)
        injected.close()

    assert opened == [], "an injected fixture must not open a second connection"


def test_at04_uninjected_requests_only_open_the_disposable_store(db_path, monkeypatch):
    """With no injection, every opened path must be the disposable temp DB."""
    from fastapi.testclient import TestClient

    opened_paths: list[str] = []
    real_connect = db.connect

    def spy(path=None):
        opened_paths.append(str(path if path is not None else config.DB_PATH))
        return real_connect() if path is None else real_connect(path)

    monkeypatch.setattr(db, "connect", spy)
    with TestClient(app_module.app) as client:
        assert client.get("/v1/images").status_code == 200
        assert client.get(f"/v1/images/{SEED[0][0]}").status_code == 200
        assert client.get("/v1/images/nope").status_code == 404

    assert opened_paths, "expected the app to open its configured database"
    assert set(opened_paths) == {str(db_path)}


# ---------------------------------------------------------------------------
# F007-AT05 — no broad catch hides a failed write as a successful review
# ---------------------------------------------------------------------------
def test_at05_failed_write_inside_a_request_propagates_and_commits_nothing(db_path):
    """A rejected write must raise out of the lifecycle, not look like success."""
    with app_module.request_connection() as conn:
        repo.submit_review(
            conn, "img-ambiguous", _pid("img-ambiguous"), "ACCEPT",
            expected_revision=0, idempotency_key="f007-good",
        )

    with pytest.raises(sqlite3.IntegrityError):
        with app_module.request_connection() as conn:
            # revision 1 already exists -> the unique index rejects this
            conn.execute(
                "INSERT INTO review_event(review_event_id, image_id, prediction_id, "
                "action, selected_class, reason, note, reviewer, created_at, "
                "revision_number, idempotency_key) VALUES (?,?,?,'ACCEPT',NULL,NULL,"
                "NULL,'f007','2026-01-01',1,'f007-duplicate')",
                ("f007-duplicate-event", "img-ambiguous", _pid("img-ambiguous")),
            )

    check = db.connect(db_path)
    rows = check.execute(
        "SELECT review_event_id, idempotency_key FROM review_event "
        "WHERE image_id = 'img-ambiguous' ORDER BY revision_number"
    ).fetchall()
    check.close()
    assert [r["idempotency_key"] for r in rows] == ["f007-good"]
    assert app_module.open_connection_count() == 0


def test_at05_review_conflicts_surface_as_failures_over_http(db_path):
    """A failed review must read as a failure in the API, not as a saved review."""
    from fastapi.testclient import TestClient

    payload = {
        "prediction_id": _pid("img-clear-nt"),
        "action": "ACCEPT",
        "expected_revision": 0,
        "idempotency_key": "f007-http-1",
    }
    with TestClient(app_module.app) as client:
        assert client.post("/v1/images/img-clear-nt/reviews", json=payload).status_code == 201
        # replay of the same key is a 200 no-op, not a second event
        replay = client.post("/v1/images/img-clear-nt/reviews", json=payload)
        assert replay.status_code == 200
        assert replay.json()["created"] is False

        stale = dict(payload, idempotency_key="f007-http-2", expected_revision=0)
        conflict = client.post("/v1/images/img-clear-nt/reviews", json=stale)
        assert conflict.status_code == 409
        # the conflict names the revision the caller must re-read
        assert conflict.json()["detail"] == {"expected_revision": 0, "current_revision": 1}

        unknown = client.post("/v1/images/nope/reviews", json=payload)
        assert unknown.status_code == 404

        state = client.get("/v1/images/img-clear-nt/review").json()
        assert state["revision"] == 1
        assert state["status"] == "reviewed"
        assert len(state["history"]) == 1
    assert app_module.open_connection_count() == 0


# ---------------------------------------------------------------------------
# Step 05 — migrations run once per database; failed init is not cached
# ---------------------------------------------------------------------------
def test_migrations_run_once_per_database_across_threads(db_path, monkeypatch):
    calls: list[int] = []
    real_migrate = db.run_migrations

    def counting(conn):
        calls.append(1)
        return real_migrate(conn)

    monkeypatch.setattr(db, "run_migrations", counting)
    workers = 6
    barrier = threading.Barrier(workers)

    def open_it(_i: int) -> None:
        barrier.wait(timeout=15)
        app_module.get_conn().execute("SELECT 1").fetchone()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(open_it, range(workers)))

    assert len(calls) == 1


def test_failed_initialization_is_not_cached_and_is_retried(db_path, monkeypatch):
    real_migrate = db.run_migrations
    boom = RuntimeError("migration 9999 is broken")

    def exploding(conn):
        raise boom

    monkeypatch.setattr(db, "run_migrations", exploding)
    with pytest.raises(RuntimeError, match="migration 9999 is broken"):
        app_module.get_conn()

    # nothing cached, and no half-initialised handle left registered
    assert app_module.open_connection_count() == 0
    with pytest.raises(RuntimeError, match="migration 9999 is broken"):
        app_module.get_conn()

    monkeypatch.setattr(db, "run_migrations", real_migrate)
    conn = app_module.get_conn()
    assert conn.execute("SELECT COUNT(*) FROM source_qc").fetchone()[0] == len(SEED)
    assert app_module.open_connection_count() == 1


# ---------------------------------------------------------------------------
# Step 07 — export rows are materialized before the connection is released
# ---------------------------------------------------------------------------
def test_export_rows_outlive_the_connection_that_produced_them(db_path):
    with app_module.request_connection() as conn:
        rows = queries.export_rows(conn)
        assert app_module.open_connection_count() == 1

    # the handle is gone; the data must not be a lazy cursor
    assert isinstance(rows, list)
    assert len(rows) == len(SEED)
    assert {r["image_id"] for r in rows} == {i[0] for i in SEED}
    assert all(r["model_bundle_hash"] == BUNDLE_HASH for r in rows)
    assert all("human_review_status" in r for r in rows)
    assert app_module.open_connection_count() == 0


def test_http_export_body_is_complete_after_the_connection_is_released(db_path):
    """The CSV is built before release, so streaming the body cannot truncate it."""
    import csv
    import io

    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as client:
        response = client.get("/v1/exports/reviews?format=csv")
        assert response.status_code == 200
        text = response.text

    parsed = list(csv.DictReader(io.StringIO(text)))
    assert {r["image_id"] for r in parsed} == {i[0] for i in SEED}
    assert all(r["model_bundle_hash"] == BUNDLE_HASH for r in parsed)
    assert app_module.open_connection_count() == 0
