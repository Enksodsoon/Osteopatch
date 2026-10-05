"""Regression tests for repository configuration checks."""
from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
