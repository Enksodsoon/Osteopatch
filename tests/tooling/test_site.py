"""Publication safety tests; no dataset, model download or cloud access required."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    if not path.is_file():
        raise AssertionError(f"Required implementation is missing: {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "_site"

    def build(self):
        return load_script("build_site").build(ROOT, self.output)

    def test_build_publishes_only_explicit_assets(self):
        self.build()
        actual = {p.relative_to(self.output).as_posix() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(actual, {
            "index.html", "getting-started.html", "architecture.html", "evidence.html",
            "operations.html", "404.html", "assets/styles.css", ".nojekyll",
            "assets/osteopatch-workbench.png", "assets/osteopatch-review.png",
            "assets/osteopatch-attribution.png", "build-info.json",
        })

    def test_build_is_deterministic(self):
        self.build()
        def snapshot():
            return {p.relative_to(self.output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.output.rglob("*") if p.is_file()}
        before = snapshot()
        self.build()
        self.assertEqual(before, snapshot())

    def test_metrics_are_read_from_frozen_evidence(self):
        self.build()
        evidence = json.loads((ROOT / "aidlc-docs/inception/model/g4/overall-oof-metrics.json").read_text())
        html = (self.output / "evidence.html").read_text(encoding="utf-8")
        self.assertIn(f"{evidence['macro_f1']:.6f}", html)
        self.assertIn(f"{evidence['per_class']['VIABLE_TUMOR']['recall']:.6f}", html)
        self.assertIn("patient-level independence", html)
        self.assertIn("g4-behavioral-recovery-r1", html)

    def test_valid_site_has_no_link_or_accessibility_errors(self):
        self.build()
        self.assertEqual(load_script("check_site").check(self.output), [])

    def test_missing_asset_is_reported(self):
        self.build()
        (self.output / "assets/osteopatch-workbench.png").unlink()
        errors = load_script("check_site").check(self.output)
        self.assertTrue(any("osteopatch-workbench.png" in error for error in errors), errors)

    def test_bad_fragment_is_reported(self):
        self.build()
        page = self.output / "index.html"
        page.write_text(page.read_text(encoding="utf-8") + '<a href="evidence.html#missing">Evidence</a>', encoding="utf-8")
        errors = load_script("check_site").check(self.output)
        self.assertTrue(any("missing" in error for error in errors), errors)

    def test_unsafe_source_path_is_rejected(self):
        with self.assertRaises(ValueError):
            load_script("build_site").source_path(ROOT, "../outside.txt")

    def test_source_symlink_is_rejected(self):
        link = Path(self.temp.name) / "link"
        target = Path(self.temp.name) / "secret.txt"
        target.write_text("not a publishable asset", encoding="utf-8")
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Creating symlinks is not permitted on this host")
        with self.assertRaises(ValueError):
            load_script("build_site").source_path(Path(self.temp.name), "link")

    def test_source_tree_cannot_be_an_output(self):
        with self.assertRaises(ValueError):
            load_script("build_site").build(ROOT, ROOT / "site")

    def test_unexpected_output_is_rejected(self):
        self.build()
        (self.output / "credentials.json").write_text("{}", encoding="utf-8")
        errors = load_script("check_site").check(self.output)
        self.assertTrue(any("Unexpected published file" in error for error in errors), errors)

    def test_missing_safety_disclosure_is_reported(self):
        self.build()
        page = self.output / "404.html"
        page.write_text(page.read_text(encoding="utf-8").replace("Not for diagnosis", "Removed"), encoding="utf-8")
        errors = load_script("check_site").check(self.output)
        self.assertTrue(any("disclosure" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
