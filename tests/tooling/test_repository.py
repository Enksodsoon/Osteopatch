"""Regression tests for repository configuration checks."""
from __future__ import annotations

import contextlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_site import ROOT, load_script


class RepositoryTests(unittest.TestCase):
    def test_current_repository_contract(self):
        self.assertEqual(load_script("check_repository").check(ROOT), [])

    def test_mutable_action_reference_is_rejected(self):
        errors = load_script("check_repository").check_workflow("name: unsafe\npermissions: read-all\nsteps:\n  - uses: actions/checkout@main\n", "example.yml")
        self.assertTrue(any("SHA" in e for e in errors), errors)

    def test_pull_request_target_is_rejected(self):
        errors = load_script("check_repository").check_workflow("permissions: read-all\non: pull_request_target\n", "example.yml")
        self.assertTrue(any("pull_request_target" in e for e in errors), errors)

    def test_autoapproved_mcp_is_rejected(self):
        cfg = {"mcpServers": {"unsafe": {"disabled": False, "autoApprove": ["*"]}}}
        errors = load_script("check_repository").check_mcp(cfg)
        self.assertGreaterEqual(len(errors), 2)

    def test_tracked_private_artifacts_are_rejected(self):
        files = [".env", "runtime-artifacts/models/model.pt", "safe/.env.example"]
        errors = load_script("check_repository").check_tracked(files)
        self.assertEqual(len(errors), 2)

    def test_profiles_are_parseable_and_safe(self):
        kiro = json.loads((ROOT / ".kiro/settings/mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(load_script("check_repository").check_mcp(kiro), [])
        vscode = json.loads((ROOT / "config/mcp/vscode.example.json").read_text(encoding="utf-8"))
        self.assertEqual(vscode["inputs"][0]["password"], True)
        self.assertTrue(all(Path(p).name != ".env" for p in [".env.example"]))


def _repo(tmp: Path, receipt: dict, files: tuple[str, ...] = ()) -> Path:
    """A throwaway tree holding one receipt plus whatever `files` should exist."""
    for rel in files:
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp / rel).write_text("{}", encoding="utf-8")
    receipts = tmp / "docs/task-evidence"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return tmp


@contextlib.contextmanager
def _tmp():
    with tempfile.TemporaryDirectory() as name:
        yield Path(name)


class ReceiptEvidenceTests(unittest.TestCase):
    """A receipt must only cite artifacts a fresh checkout can actually open.

    `untracked` is deliberately accepted: tracked-ness is a commit-time property and
    the failure being prevented is *unreadable* evidence, not uncommitted evidence.
    """

    def setUp(self):
        self.script = load_script("check_repository")

    def _errors(self, tmp: Path, receipt: dict, ignored=(), tracked=(), files=()) -> list[str]:
        """`ignored`/`tracked` are git's answers; `files` is what exists on disk."""
        root = _repo(tmp, receipt, files=tuple(ignored) + tuple(tracked) + tuple(files))
        return self.script.check_receipt_evidence(root, set(ignored), set(tracked))

    def _all_citations(self) -> set[str]:
        """Every artifact a receipt points at, following the records it cites."""
        found: set[str] = set()
        for receipt in sorted((ROOT / "docs/task-evidence").glob("*.json")):
            data = json.loads(receipt.read_text(encoding="utf-8"))
            found |= self.script.artifact_citations(data)
            for record in self.script.cited_records(data):
                if (ROOT / record).is_file():
                    found |= self.script.artifact_citations(
                        json.loads((ROOT / record).read_text(encoding="utf-8")))
        return found

    def test_current_receipts_cite_only_readable_artifacts(self):
        self.assertEqual(self.script.check_receipt_evidence(ROOT), [])

    def test_ignored_citation_is_rejected(self):
        with _tmp() as tmp:
            errors = self._errors(tmp, {"tests": [{"gate_record": "scratch/task/gate.json"}]},
                                  ignored=("scratch/task/gate.json",))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("git-ignored", errors[0])

    def test_missing_citation_is_rejected(self):
        with _tmp() as tmp:
            errors = self._errors(tmp, {"tests": [{"gate_record": "docs/evidence/gates/gone.json"}]})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("missing", errors[0])

    def test_untracked_but_readable_citation_is_accepted(self):
        with _tmp() as tmp:
            errors = self._errors(tmp, {"tests": [{"gate_record": "docs/evidence/gates/g.json"}]},
                                  files=("docs/evidence/gates/g.json",))
        self.assertEqual(errors, [])

    def test_verdicts_cover_every_citation_state(self):
        with _tmp() as tmp:
            root = _repo(tmp, {}, files=("docs/evidence/gates/t.json",
                                          "docs/evidence/gates/u.json"))
            tracked = {"docs/evidence/gates/t.json"}
            cases = {
                "docs/evidence/gates/t.json": "tracked",
                "docs/evidence/gates/u.json": "untracked",
                "docs/evidence/gates/nope.json": "missing",
            }
            got = {rel: self.script.evidence_verdict(root, rel, set(), set(tracked))
                   for rel in cases}
        self.assertEqual(got, cases)

    def test_record_pointer_that_leads_to_an_ignored_log_is_rejected(self):
        """A record that points at an ignored transcript is as unreadable as a bad cite."""
        with _tmp() as tmp:
            root = _repo(tmp, {"tests": [{"gate_record": "docs/evidence/gates/r.json"}]},
                         files=("docs/evidence/gates/r.log",))
            (root / "docs/evidence/gates/r.json").write_text(
                json.dumps({"output_log": "docs/evidence/gates/r.log"}), encoding="utf-8")
            errors = self.script.check_receipt_evidence(
                root, {"docs/evidence/gates/r.log"}, set())
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("r.log", errors[0])

    def test_invocations_and_locations_are_not_artifact_citations(self):
        """Scripts, databases, generated dirs, globs and bare directories are not evidence."""
        receipt = {"tests": [{"command": "'.venv/Scripts/python.exe' scratch/task/sweep.py"}],
                   "notes": ["records lived in scratch/gates/",
                             "see docs/evidence/gates/f003-*.json",
                             "db at scratch/throwaway-db/throwaway.sqlite3",
                             "deps in app/g6/frontend/node_modules/.bin/vitest",
                             "artefact docs/evidence/gates/f007-smoke.log"]}
        with _tmp() as tmp:
            root = _repo(tmp, receipt, files=("docs/evidence/gates/f007-smoke.log",))
            found = sorted(self.script.artifact_citations(receipt))
            errors = self.script.check_receipt_evidence(root, set(), set())
        self.assertEqual(found, ["docs/evidence/gates/f007-smoke.log"])
        self.assertEqual(errors, [])

    def test_malformed_receipt_is_reported_not_skipped(self):
        with _tmp() as tmp:
            root = _repo(tmp, {})
            (root / "docs/task-evidence/broken.json").write_text("{not json", encoding="utf-8")
            errors = self.script.check_receipt_evidence(root, set(), set())
        self.assertTrue(any("broken.json" in e for e in errors), errors)

    def test_repository_check_fails_the_build_on_an_unreadable_citation(self):
        """`check()` is what CI runs, so the error must surface from there, in a real repo."""
        with _tmp() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            (tmp / ".gitignore").write_text("scratch/" + chr(10), encoding="utf-8")
            _repo(tmp, {"tests": [{"gate_record": "scratch/task/gate.json"}]},
                  files=("scratch/task/gate.json",))
            errors = self.script.check(tmp)
        self.assertTrue(any("git-ignored" in e and "scratch/task/gate.json" in e
                            for e in errors), errors)

    def test_no_receipt_cites_an_unreadable_path(self):
        """Independent oracle: ask git directly, so the guarantee is not self-fulfilling."""
        cited = self._all_citations()
        out = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-z", "--stdin"],
                             input=("\0".join(sorted(cited)) + "\0").encode(),
                             capture_output=True)
        self.assertEqual([p for p in out.stdout.decode().split("\0") if p], [],
                         "receipts cite git-ignored artifacts")
        self.assertTrue(cited, "no citations found; the probe itself is broken")


if __name__ == "__main__":
    unittest.main()
