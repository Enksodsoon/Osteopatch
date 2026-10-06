"""The web serve path must stay torch-free.

`docs/dependencies.md` C1 promises that opening a patch in the browser never
waits on PyTorch, because every prediction is precomputed. Once the optional
`model` extra is installed on a demo machine that promise becomes easy to break
silently: torch is importable, so an accidental top-level import is invisible
until someone measures request latency.

These tests measure it instead of reading the source. The probes run in a FRESH
subprocess whose ``sys.meta_path`` refuses to resolve torch/torchvision/
pytorch_grad_cam, so a module-level OR a lazy in-request import fails loudly
rather than quietly costing seconds.

Skipped (not failed) when torch is absent -- a torch-free venv is the stronger
case, and there the invariant holds trivially.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENTERPRISE_DIR = Path(__file__).resolve().parents[3] / "g7-enterprise" / "backend"

FROZEN_HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"

#: Blocked inside the child interpreter. Blocking the ROOT package is enough:
#: torch, torchvision and pytorch_grad_cam are all imported by those names.
BLOCKED = ("torch", "torchvision", "pytorch_grad_cam")


def _have_torch() -> bool:
    try:
        import torch  # noqa: F401
    except Exception:
        return False
    return True


# --------------------------------------------------------------------------
# Child-interpreter sources. Module-level and flush-left so they read as real
# Python instead of an indented template string.
# --------------------------------------------------------------------------
_TRIPWIRE = '''
import importlib.machinery


class _BlockingLoader:
    """Wraps a real loader and refuses to EXECUTE it.

    Blocking in ``exec_module`` rather than in ``find_spec`` is the precise
    distinction: ``import torch`` dies, while ``importlib.util.find_spec`` --
    which the live capability endpoint legitimately uses to answer "is torch
    installed?" without loading a ~1 GB runtime -- still works. Blocking
    discovery instead would have failed a route that never imports anything.
    """

    def __init__(self, inner, name):
        self._inner = inner
        self._name = name

    def create_module(self, spec):
        return self._inner.create_module(spec)

    def exec_module(self, module):
        raise AssertionError("serve path imported " + self._name)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _TorchTripwire:
    """Refuses to EXECUTE the optional model stack on the serve path."""

    BLOCKED = BLOCKED_HERE

    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root not in self.BLOCKED:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        spec.loader = _BlockingLoader(spec.loader, fullname)
        return spec


sys.meta_path.insert(0, _TorchTripwire())
'''

_SERVE_PROBE = """
import sys

sys.path.insert(0, BACKEND_DIR_HERE)
from fastapi.testclient import TestClient

from osteopatch import app as app_module, db, repo

TRIPWIRE_HERE

conn = db.connect(DB_PATH_HERE)
db.run_migrations(conn)
conn.execute(
    "INSERT INTO source_qc(image_id, source_group, original_label, "
    "primary_qc_status, training_eligible, qc_review_flag, qc_review_reason, "
    "tiff_filename) VALUES ('img-mid-nec','Case-48','NECROSIS','PASS',1,0,NULL,'x.tiff')"
)
repo.upsert_prediction(conn, "img-mid-nec", FROZEN_HASH_HERE, "baseline-frozen-g4",
                       [0.20, 0.25, 0.55])
conn.commit()
app_module.set_conn(conn)

client = TestClient(app_module.app)
for path in SERVE_PATHS_HERE:
    response = client.get(path)
    assert response.status_code == 200, "%s -> %s: %s" % (
        path, response.status_code, response.text[:200])

leaked = [m for m in sys.modules if m.split(".")[0] in _TorchTripwire.BLOCKED]
assert not leaked, "model stack resident after the serve path: %s" % sorted(leaked)
print("SERVE_PATH_TORCH_FREE_OK")
"""

_TRIPWIRE_SELFTEST = """
import importlib.util
import sys

sys.path.insert(0, BACKEND_DIR_HERE)

TRIPWIRE_HERE

# A real import must die.
try:
    import torch  # noqa: F401
except AssertionError as exc:
    assert "imported torch" in str(exc), exc
else:
    raise SystemExit("tripwire did not fire on import: the guard would be worthless")

# A capability PROBE must still work: it does not execute the module, which is
# exactly why the live endpoint may use it. If this ever fails, the guard has
# become stricter than "may not import" and is rejecting a legitimate question.
assert importlib.util.find_spec("torch") is not None
assert "torch" not in sys.modules

print("TRIPWIRE_FIRES_OK")
"""

_ATTRIBUTION_PROBE = """
import sys

sys.path.insert(0, BACKEND_DIR_HERE)

import torch  # noqa: F401  -- this endpoint is ALLOWED to load it
import torchvision  # noqa: F401

from osteopatch import attribution

assert attribution.get_state()["target_layer_name"] == "model.features[-1]"
print("ATTRIBUTION_LOADS_TORCH_OK")
"""

#: The live-inference READ routes live on the enterprise app, not the G6 one, so
#: they get their own probe. Only the two inference POSTs may load torch;
#: reading a capability, listing runs or reading one back must stay cheap.
#: (path, expected status) -- an unknown run is a 404, which is the point.
LIVE_READ_PATHS = (
    ("/v1/health", 200),
    ("/v1/live/capability", 200),
    ("/v1/live/runs", 200),
    ("/v1/live/runs/live-doesnotexist", 404),
)

_LIVE_READ_PROBE = """
import os
import sys

sys.path.insert(0, BACKEND_DIR_HERE)
sys.path.insert(0, ENTERPRISE_DIR_HERE)

TRIPWIRE_HERE

from fastapi.testclient import TestClient

from enterprise import app as ent_app, seed, store

conn = store.connect(ENT_DB_HERE)
ent_app.set_conn(conn)
seeded = seed.seed(conn)  # scope_size defaults to None -> grants nothing in G6

client = TestClient(ent_app.app)
token = client.post("/auth/login", json={"email": "reviewer@demo"}).json()["access_token"]
headers = {"Authorization": "Bearer " + token,
           "X-Project-Id": seeded["project_id"]}

for path, expected in LIVE_READ_PATHS_HERE:
    response = client.get(path, headers=headers)
    assert response.status_code == expected, "%s -> %s (expected %s): %s" % (
        path, response.status_code, expected, response.text[:200])

# The capability probe must be answerable WITHOUT a model loaded.
assert client.get("/v1/live/capability", headers=headers).json()["available"] is True

leaked = [m for m in sys.modules if m.split(".")[0] in _TorchTripwire.BLOCKED]
assert not leaked, "model stack resident after the live read path: %s" % sorted(leaked)
print("LIVE_READ_PATH_TORCH_FREE_OK")
"""

#: The request paths a reviewer actually exercises. Attribution is deliberately
#: ABSENT -- it is the one endpoint allowed to load torch.
SERVE_PATHS = (
    "/v1/health",
    "/v1/meta",
    "/v1/model-card",
    "/v1/images",
    "/v1/images/img-mid-nec",
    "/v1/images/img-mid-nec/review",
    "/v1/images/img-mid-nec/attribution/meta",
    "/v1/exports/reviews",
)


def _substitute(source: str, **values: object) -> str:
    """Inline values as Python literals and splice in the tripwire.

    A ``Path`` is stringified first: ``repr(Path(...))`` would emit
    ``WindowsPath('...')``, which the child interpreter cannot resolve.
    """
    tripwire = _TRIPWIRE.replace("BLOCKED_HERE", repr(BLOCKED))
    source = source.replace("TRIPWIRE_HERE", tripwire)
    for key, value in values.items():
        literal = repr(str(value)) if isinstance(value, Path) else repr(value)
        source = source.replace(f"{key.upper()}_HERE", literal)
    assert "_HERE" not in source, "unsubstituted placeholder left in the probe source"
    return source


def _run(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


@pytest.mark.skipif(not _have_torch(), reason="torch absent; the invariant is trivially true")
def test_review_serve_paths_never_import_torch(tmp_path):
    source = _substitute(
        _SERVE_PROBE,
        backend_dir=BACKEND_DIR,
        db_path=(tmp_path / "serve.sqlite3").as_posix(),
        frozen_hash=FROZEN_HASH,
        serve_paths=SERVE_PATHS,
    )
    proc = _run(source)
    assert proc.returncode == 0, (
        "serve path touched torch or an endpoint failed:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "SERVE_PATH_TORCH_FREE_OK" in proc.stdout


@pytest.mark.skipif(not _have_torch(), reason="torch absent; nothing to warm")
def test_tripwire_itself_rejects_a_torch_import():
    """The guard is only worth anything if it actually fires.

    Without this, a green run above could mean the probe was inert rather than
    that the serve path stayed clean.
    """
    proc = _run(_substitute(_TRIPWIRE_SELFTEST, backend_dir=BACKEND_DIR))
    assert proc.returncode == 0, proc.stderr
    assert "TRIPWIRE_FIRES_OK" in proc.stdout


@pytest.mark.skipif(not _have_torch(), reason="torch absent")
def test_attribution_is_the_one_path_that_does_load_torch():
    """The complement of the serve-path test.

    'we never import torch' must not be satisfiable by attribution being
    silently broken, so the same subprocess that blocks torch everywhere else
    must still build the recovered model when attribution is asked for it.
    """
    proc = _run(_substitute(_ATTRIBUTION_PROBE, backend_dir=BACKEND_DIR))
    assert proc.returncode == 0, proc.stderr
    assert "ATTRIBUTION_LOADS_TORCH_OK" in proc.stdout


@pytest.mark.skipif(not _have_torch(), reason="torch absent; the invariant is trivially true")
def test_live_read_paths_never_import_torch(tmp_path, monkeypatch):
    """Reading the live surface must not load the model.

    Only the two inference POSTs may. If `/v1/live/capability` or a run
    read-back pulled torch in, a page load would cost ~1 GB before the user had
    asked for a single prediction — and the capability endpoint exists
    specifically so the UI can decide that cheaply.
    """
    work = tmp_path / "live"
    work.mkdir()
    monkeypatch.setenv("OSTEOPATCH_ENT_DB", str(work / "ent.sqlite3"))
    monkeypatch.setenv("OSTEOPATCH_AUDIT_LOG", str(work / "audit.jsonl"))
    monkeypatch.setenv("OSTEOPATCH_PROJECT_SCOPES", str(work / "scopes"))
    monkeypatch.setenv("OSTEOPATCH_DB", str(work / "g6-empty.sqlite3"))

    source = _substitute(
        _LIVE_READ_PROBE,
        backend_dir=BACKEND_DIR,
        enterprise_dir=ENTERPRISE_DIR,
        ent_db=(work / "ent.sqlite3").as_posix(),
        live_read_paths=LIVE_READ_PATHS,
    )
    proc = _run(source)
    assert proc.returncode == 0, (
        "the live read path touched torch or a route failed:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "LIVE_READ_PATH_TORCH_FREE_OK" in proc.stdout
