"""Regression test: an aborted E2E run must not leak its temp workspace.

Every abort path in ``scripts/e2e_ui.py`` raises ``SystemExit``, and a
``SystemExit`` unwinds straight past any code that sits *after* the
``try``/``finally``.  The workspace cleanup used to live there, so each failed
run silently left behind a full copy of the review database plus the server
logs -- and the only visible symptom was a growing pile of temp directories.

Cleanup belongs inside the ``finally``.  These tests pin that down by driving
``main()`` down a forced-abort path and asserting the workspace is actually
gone afterwards.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
E2E_SCRIPT = REPO / "scripts" / "e2e_ui.py"


def _load_e2e():
    """Import scripts/e2e_ui.py by path.

    It lives outside the pytest ``pythonpath`` roots, and importing it by name
    would be ambiguous, so load it explicitly from the repo root.
    """
    spec = importlib.util.spec_from_file_location("e2e_ui_under_test", E2E_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare(monkeypatch, tmp_path, abort: bool = True, argv_extra: list[str] | None = None):
    """Wire e2e_ui.main() up so it runs anywhere, including a bare CI runner.

    main() guards itself before the run starts: it checks for the Playwright
    and Vite CLIs under node_modules, and (without --skip-prepare) it verifies
    the gitignored runtime artifacts.  All of that is absent on a clean CI
    checkout, so leaving it in place made this test pass only on a machine that
    happened to have run ``make runtime``.  Every one of those gates is stubbed
    here so the test exercises the cleanup and nothing else.
    """
    e2e = _load_e2e()

    fake_db = tmp_path / "canonical.sqlite3"
    fake_db.write_bytes(b"stand-in for the gitignored canonical review store")
    monkeypatch.setattr(e2e, "CANON_DB", fake_db)

    # Satisfy the node_modules existence checks with throwaway stand-ins.
    fake_cli = tmp_path / "cli.js"
    fake_cli.write_text("// stand-in for the real CLI\n", encoding="utf-8")
    monkeypatch.setattr(e2e, "PLAYWRIGHT_CLI", fake_cli)
    monkeypatch.setattr(e2e, "VITE_CLI", fake_cli)

    # Satisfy the project-venv lookup, which otherwise depends on the host OS
    # layout (.venv/Scripts on Windows, .venv/bin elsewhere).
    fake_repo = tmp_path / "repo"
    (fake_repo / ".venv" / "bin").mkdir(parents=True)
    (fake_repo / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    monkeypatch.setattr(e2e, "REPO", fake_repo)

    # Redirect mkdtemp so any leaked workspace is observable and cannot escape
    # into the real temp directory.
    root = tmp_path / "workspaces"
    root.mkdir()
    real_mkdtemp = tempfile.mkdtemp
    monkeypatch.setattr(
        e2e.tempfile,
        "mkdtemp",
        lambda prefix="", **kw: real_mkdtemp(prefix=prefix, dir=str(root)),
    )

    if abort:

        def _boom(*_a, **_kw):
            raise SystemExit("forced abort for the cleanup regression test")

        monkeypatch.setattr(e2e, "spawn", _boom)

    # --skip-prepare keeps the test off the runtime-artifact preflight, which
    # would otherwise shell out and fail on a checkout with no artifacts.
    monkeypatch.setattr(
        sys, "argv", ["e2e_ui.py", "--skip-prepare", *(argv_extra or [])]
    )
    return e2e, root


def test_aborted_run_leaves_no_workspace(monkeypatch, tmp_path):
    """The abort path must still delete the workspace holding the DB copy."""
    e2e, root = _prepare(monkeypatch, tmp_path)

    with pytest.raises(SystemExit, match="forced abort"):
        e2e.main()

    leaked = sorted(p.name for p in root.iterdir())
    assert leaked == [], (
        "an aborted e2e run leaked its temp workspace "
        f"({leaked}); it still holds a copy of the review database"
    )


def test_keep_workspace_flag_still_preserves_the_directory(monkeypatch, tmp_path):
    """--keep-workspace is an explicit opt-out, so it must keep working."""
    e2e, root = _prepare(monkeypatch, tmp_path, argv_extra=["--keep-workspace"])

    with pytest.raises(SystemExit, match="forced abort"):
        e2e.main()

    kept = sorted(p.name for p in root.iterdir())
    assert len(kept) == 1, f"expected exactly one kept workspace, found {kept}"
    assert kept[0].startswith("osteopatch-e2e-")
