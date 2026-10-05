#!/usr/bin/env python3
"""Build an explicitly allowlisted, dependency-free GitHub Pages website."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://enksodsoon.github.io/Osteopatch"
PAGES = {
    "index.html": "Overview",
    "getting-started.html": "Get started",
    "architecture.html": "Architecture",
    "evidence.html": "Model evidence",
    "operations.html": "Operations",
    "404.html": "Page not found",
}
SCREENSHOTS = (
    "osteopatch-workbench.png", "osteopatch-review.png", "osteopatch-attribution.png",
)
ALLOWED_OUTPUTS = frozenset(PAGES) | {
    "assets/styles.css", ".nojekyll", "build-info.json",
} | {f"assets/{name}" for name in SCREENSHOTS}
EVIDENCE = "aidlc-docs/inception/model/g4/overall-oof-metrics.json"


def source_path(root: Path, relative: str) -> Path:
    """Resolve a regular source file without allowing escapes or symlink reads."""
    root = root.resolve()
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts:
        raise ValueError(f"Unsafe source path: {relative}")
    candidate = root / part
    for node in (candidate, *candidate.parents):
        if node == root:
            break
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise ValueError(f"Symlink/junction source is not publishable: {relative}")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"Source must be a regular file within the repository: {relative}")
    return resolved


def output_path(output: Path, relative: str) -> Path:
    if relative not in ALLOWED_OUTPUTS:
        raise ValueError(f"Output is not allowlisted: {relative}")
    target = output / relative
    for node in (target, *target.parents):
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise ValueError(f"Symlink/junction output is not allowed: {node}")
        if node == output:
            break
    return target


def build(root: Path = ROOT, output: Path | None = None) -> list[Path]:
    root = root.resolve()
    output = Path(output) if output is not None else root / "_site"
    if output.name != "_site" or output.resolve() == root or output.resolve().is_relative_to(root / "site"):
        raise ValueError("The output must be a dedicated _site directory, never source content")
    for node in (output, *output.parents):
        if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
            raise ValueError(f"Symlink/junction output directory is not allowed: {node}")
    if output.exists():
        unexpected = [p.relative_to(output).as_posix() for p in output.rglob("*")
                      if p.is_file() and p.relative_to(output).as_posix() not in ALLOWED_OUTPUTS]
        if unexpected:
            raise ValueError(f"Refusing to publish unexpected existing output: {unexpected}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "assets").mkdir(exist_ok=True)
    layout = Template(source_path(root, "site/layout.html").read_text(encoding="utf-8"))
    evidence_bytes = source_path(root, EVIDENCE).read_bytes()
    evidence = json.loads(evidence_bytes)
    project = tomllib.loads(source_path(root, "pyproject.toml").read_text(encoding="utf-8"))["project"]
    expected_classes = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"]
    if evidence["class_order"] != expected_classes:
        raise ValueError("Frozen evidence class order changed; publication requires review")
    values = {
        "version": html.escape(project["version"]),
        "macro_f1": f"{evidence['macro_f1']:.6f}",
        "balanced_accuracy": f"{evidence['balanced_accuracy']:.6f}",
        "viable_recall": f"{evidence['per_class']['VIABLE_TUMOR']['recall']:.6f}",
        "evaluation_rows": str(int(evidence["n_rows"])),
    }
    for filename, label in PAGES.items():
        links = []
        for name, title in PAGES.items():
            if name == "404.html":
                continue
            current = ' aria-current="page"' if name == filename else ""
            links.append(f'<a href="{name}"{current}>{html.escape(title)}</a>')
        nav = "".join(links)
        body = Template(source_path(root, f"site/pages/{filename}").read_text(encoding="utf-8")).substitute(values)
        rendered = layout.substitute(
            **values, title=html.escape(f"{label} — OsteoPatch Review"),
            canonical=f"{SITE_URL}/{filename}", navigation=nav, body=body,
        )
        if re.search(r"\$\{?[A-Za-z_]", rendered):
            raise ValueError(f"Unresolved template variable in {filename}")
        output_path(output, filename).write_text(rendered, encoding="utf-8", newline="\n")
    shutil.copyfile(source_path(root, "site/styles.css"), output_path(output, "assets/styles.css"))
    for name in SCREENSHOTS:
        shutil.copyfile(source_path(root, f"docs/images/{name}"), output_path(output, f"assets/{name}"))
    output_path(output, ".nojekyll").write_text("", encoding="utf-8")
    files = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
             for name in sorted(ALLOWED_OUTPUTS - {"build-info.json"})}
    metadata = {"schema_version": 1, "project_version": project["version"],
                "evidence_file": EVIDENCE, "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
                "files": files}
    output_path(output, "build-info.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [output / name for name in sorted(ALLOWED_OUTPUTS)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        files = build()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Site build failed: {exc}", file=sys.stderr)
        return 1
    print(f"Built {len(files)} allowlisted files in {ROOT / '_site'}; no runtime data published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
