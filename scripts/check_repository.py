#!/usr/bin/env python3
"""Artifact-free repository policy checks; complements, not replaces, security scanning."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    "LICENSE", ".editorconfig", ".gitattributes", ".env.example", ".python-version",
    ".node-version", ".github/CODEOWNERS", ".github/pull_request_template.md",
    ".github/dependabot.yml", ".github/workflows/ci.yml", ".github/workflows/pages.yml",
    ".github/workflows/capabilities.yml", ".github/workflows/deploy-frontend.yml",
    ".github/workflows/release.yml", ".kiro/settings/mcp.json",
    "config/mcp/vscode.example.json", "docs/README.md", "docs/getting-started.md",
    "docs/architecture.md", "docs/model-evidence.md", "docs/deployment.md",
    "docs/agent-tooling.md", "docs/repository-guide.md", "docs/project-status.md",
    "site/README.md", "site/layout.html", "scripts/build_site.py", "scripts/check_site.py",
)
CURRENT_DOCS = tuple(p for p in REQUIRED if p.endswith(".md")) + (
    "app/g6/README.md", "aidlc-docs/README.md", "prompts/README.md", "templates/README.md",
    "docs/evidence/README.md",
)


def check_workflow(text: str, filename: str) -> list[str]:
    errors = []
    if re.search(r"\bpull_request_target\b", text):
        errors.append(f"{filename}: pull_request_target is not permitted")
    if "permissions:" not in text or re.search(r"permissions:\s*write-all", text):
        errors.append(f"{filename}: explicit least-privilege permissions are required")
    for action in re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", text, re.MULTILINE):
        action = action.strip("\"'")
        if not action.startswith("./") and not re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", action):
            errors.append(f"{filename}: third-party Action must use a full commit SHA: {action}")
    if text.count("runs-on:") > text.count("timeout-minutes:"):
        errors.append(f"{filename}: every runner job needs a timeout")
    return errors


def check_mcp(config: dict) -> list[str]:
    errors = []
    for name, server in config.get("mcpServers", {}).items():
        if server.get("disabled") is not True:
            errors.append(f"MCP {name}: shared profile must be disabled by default")
        if server.get("autoApprove") != []:
            errors.append(f"MCP {name}: automatic tool approval is not allowed")
        auth = server.get("headers", {}).get("Authorization", "")
        if auth and auth != "Bearer ${GITHUB_MCP_TOKEN}":
            errors.append(f"MCP {name}: credentials must be an environment reference")
        if name == "github-readonly" and server.get("headers", {}).get("X-MCP-Readonly") != "true":
            errors.append("MCP GitHub: read-only enforcement is missing")
    return errors


def check_tracked(files: list[str]) -> list[str]:
    errors = []
    for name in files:
        path = PurePosixPath(name)
        private_env = path.name == ".env" or (path.name.startswith(".env.") and not path.name.endswith(".example"))
        private_binary = path.suffix.lower() in {".pt", ".pth", ".onnx", ".safetensors", ".sqlite3", ".sqlite", ".db", ".pem", ".key"}
        private_dir = any(p in {"runtime-artifacts", "node_modules", ".venv", "_site"} for p in path.parts)
        if private_env or private_binary or private_dir:
            errors.append(f"Private/generated artifact is tracked: {name}")
    return errors


EVIDENCE_DIR = "docs/task-evidence"
# A citation is a repo-relative path to a data artifact a reviewer must be able to open.
# What a receipt names in order to *run* or merely *locate* something is not evidence:
# programs, databases, globs, bare directories and generated/vendor trees.
_CITATION = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._*+-]+)+/?")
_NOT_ARTIFACT = frozenset({
    ".py", ".sh", ".bash", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".exe", ".cmd", ".ps1",
    ".sqlite", ".sqlite3", ".db",
})
_GENERATED = frozenset({".venv", "node_modules", "_site", "runtime-artifacts", "__pycache__"})
# A `command` records what ran, faithfully and as it ran. Its paths are arguments to a
# process, not pointers a reviewer can follow, so they are never citations.
_INVOCATION_FIELDS = frozenset({"command", "argv", "cwd"})


def _is_citation(token: str, roots: set[str] | None = None) -> bool:
    if not token or "*" in token or ".." in token or token.startswith(("/", ".")):
        return False
    parts = token.rstrip("/").split("/")
    if not re.search(r"\.[A-Za-z0-9]+$", parts[-1]):
        return False  # a directory, or prose that merely ends in a full stop
    if roots is not None and parts[0] not in roots:
        return False  # a URL, a git ref or an expression - not a path in this repository
    return not (_GENERATED & set(parts)
                or PurePosixPath(token).suffix.lower() in _NOT_ARTIFACT)


def artifact_citations(node: object, roots: set[str] | None = None) -> set[str]:
    """Every artifact path named anywhere in a receipt, in prose or in a field."""
    found: set[str] = set()
    if isinstance(node, str):
        found.update(t for t in _CITATION.findall(node) if _is_citation(t, roots))
    elif isinstance(node, dict):
        for key, value in node.items():
            if key not in _INVOCATION_FIELDS:
                found |= artifact_citations(value, roots)
    elif isinstance(node, list):
        for value in node:
            found |= artifact_citations(value, roots)
    return found


def cited_records(node: object) -> set[str]:
    """Gate records a receipt points at, by field name - the one unambiguous pointer."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "gate_record" and isinstance(value, str):
                found.add(value)
            found |= cited_records(value)
    elif isinstance(node, list):
        for value in node:
            found |= cited_records(value)
    return found


def _load(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def evidence_verdict(root: Path, rel: str, ignored: set[str], tracked: set[str]) -> str:
    """Classify one citation.

    `untracked` is accepted on purpose: tracked-ness is a commit-time property, and the
    failure this check prevents is a reviewer being unable to *read* the evidence, not its
    being uncommitted. A git-ignored path is rejected either way - it vanishes on the next
    clean checkout even though it exists in this working tree.
    """
    if rel in ignored:
        return "git-ignored"
    if not (root / rel).is_file():
        return "missing"
    return "tracked" if rel in tracked else "untracked"


def git_ignored(root: Path, paths: set[str]) -> set[str]:
    """Which of `paths` git would ignore, asked only about the paths at hand.

    Fails closed: if git cannot answer, every citation is reported rather than trusted.
    """
    if not paths:
        return set()
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-z", "--stdin"],
        input=("\0".join(sorted(paths)) + "\0").encode(), check=False, capture_output=True)
    if result.returncode not in (0, 1):
        return set(paths)
    return {p for p in result.stdout.decode("utf-8").split("\0") if p}


def top_level(root: Path) -> set[str]:
    """Top-level names; a repo-relative citation always starts with one of these."""
    return {p.name for p in root.iterdir()}


def receipt_citations(root: Path) -> set[str]:
    """Every artifact the receipts cite, following each cited record one level down."""
    found: set[str] = set()
    roots = top_level(root)
    for receipt in sorted((root / EVIDENCE_DIR).glob("*.json")):
        data = _load(receipt)
        if data is None:
            continue
        found |= artifact_citations(data, roots)
        for record in cited_records(data):
            nested = _load(root / record)
            if nested is not None:
                found |= artifact_citations(nested, roots)
    return found


def check_receipt_evidence(root: Path, ignored: set[str] | None = None,
                           tracked: set[str] | None = None) -> list[str]:
    """Every artifact a receipt cites must survive a clean checkout.

    Unreadable evidence is the failure mode: a receipt that points a reviewer at a
    git-ignored or absent file passes review while proving nothing. `ignored` and
    `tracked` are injectable so the classification can be tested without a git repo.
    """
    if ignored is None:
        ignored = git_ignored(root, receipt_citations(root))
    tracked = tracked or set()
    roots = top_level(root)
    errors: list[str] = []
    for receipt in sorted((root / EVIDENCE_DIR).glob("*.json")):
        rel = receipt.relative_to(root).as_posix()
        data = _load(receipt)
        if data is None:
            errors.append(f"{rel}: receipt is not readable JSON; durability is UNVERIFIED")
            continue
        citations = artifact_citations(data, roots)
        for record in cited_records(data):
            if evidence_verdict(root, record, ignored, tracked) in {"missing", "git-ignored"}:
                continue  # already reported as a citation in its own right
            nested = _load(root / record)
            if nested is None:
                errors.append(f"{rel}: cited gate record is not readable JSON: {record}")
            else:
                citations |= artifact_citations(nested, roots)
        for citation in sorted(citations):
            verdict = evidence_verdict(root, citation, ignored, tracked)
            if verdict in {"missing", "git-ignored"}:
                errors.append(
                    f"{rel}: cited evidence is unreadable to a reviewer ({verdict}): {citation}")
    return errors


def check(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors = [f"Required file is missing: {p}" for p in REQUIRED if not (root / p).is_file()]
    for path in sorted((root / ".github/workflows").glob("*.yml")):
        errors.extend(check_workflow(path.read_text(encoding="utf-8"), path.name))
    mcp = root / ".kiro/settings/mcp.json"
    if mcp.is_file():
        try:
            errors.extend(check_mcp(json.loads(mcp.read_text(encoding="utf-8"))))
        except (ValueError, TypeError) as exc:
            errors.append(f"MCP JSON is invalid: {exc}")
    for relative in CURRENT_DOCS:
        path = root / relative
        if not path.is_file():
            continue
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        for link in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", text):
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f"{relative}: missing or escaping document link: {link}")
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=False, capture_output=True)
    tracked: set[str] = set()
    if result.returncode:
        errors.append("git ls-files failed; cannot verify tracked-artifact policy")
    else:
        tracked = {p for p in result.stdout.decode("utf-8").split("\0") if p}
        errors.extend(check_tracked(sorted(tracked)))
    errors.extend(check_receipt_evidence(root, tracked=tracked))
    makefile = root / "Makefile"
    if makefile.exists() and ".venv/Scripts/python.exe" in makefile.read_text(encoding="utf-8"):
        errors.append("Makefile: use portable locked uv commands, not a Windows-only Python path")
    return errors


def main() -> int:
    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Repository checks: {len(errors)} error(s).")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
