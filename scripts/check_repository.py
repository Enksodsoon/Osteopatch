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
    if result.returncode:
        errors.append("git ls-files failed; cannot verify tracked-artifact policy")
    else:
        errors.extend(check_tracked([p for p in result.stdout.decode("utf-8").split("\0") if p]))
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
