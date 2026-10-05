#!/usr/bin/env python3
"""Check the generated site for unsafe publication, broken links and basic semantics."""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build_site import ALLOWED_OUTPUTS, PAGES, ROOT


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.errors: list[str] = []
        self.h1 = 0
        self.viewport = False
        self.lang = False
        self.main = False
        self.title = False

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if "id" in data:
            if data["id"] in self.ids:
                self.errors.append(f"duplicate id: {data['id']}")
            self.ids.add(data["id"])
        self.h1 += tag == "h1"
        self.viewport |= tag == "meta" and data.get("name") == "viewport"
        self.lang |= tag == "html" and data.get("lang") == "en"
        self.main |= tag == "main"
        self.title |= tag == "title"
        if tag == "img" and not data.get("alt", "").strip():
            self.errors.append("image is missing descriptive alt text")
        if tag in {"script", "iframe", "form"}:
            self.errors.append(f"unsupported active content: {tag}")
        if any(name.startswith("on") for name in data):
            self.errors.append("inline event handler is not allowed")
        for name in ("href", "src"):
            if data.get(name):
                self.links.append(data[name])


def check(output: Path = ROOT / "_site") -> list[str]:
    output = output.resolve()
    errors: list[str] = []
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    errors.extend(f"Unexpected published file: {name}" for name in sorted(actual - ALLOWED_OUTPUTS))
    errors.extend(f"Missing published file: {name}" for name in sorted(ALLOWED_OUTPUTS - actual))
    pages: dict[str, Page] = {}
    for name in PAGES:
        path = output / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        page = Page()
        page.feed(text)
        pages[name] = page
        errors.extend(f"{name}: {error}" for error in page.errors)
        if not all((page.h1 == 1, page.viewport, page.lang, page.main, page.title)):
            errors.append(f"{name}: missing document semantics (one h1, lang, viewport, main, title)")
        if "Not for diagnosis" not in text or "educational" not in text.lower():
            errors.append(f"{name}: missing educational safety disclosure")
    for name, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if url.scheme:
                if url.scheme not in {"https", "http", "mailto"}:
                    errors.append(f"{name}: unsafe URL scheme: {link}")
                continue
            if url.netloc or url.path.startswith("/"):
                errors.append(f"{name}: root/protocol-relative URL breaks project Pages: {link}")
                continue
            target = (output / (unquote(url.path) or name)).resolve()
            if target.is_dir():
                target /= "index.html"
            if not target.is_relative_to(output) or not target.is_file():
                errors.append(f"{name}: missing or escaping local target: {link}")
                continue
            target_name = target.relative_to(output).as_posix()
            if url.fragment and target_name in pages and unquote(url.fragment) not in pages[target_name].ids:
                errors.append(f"{name}: missing fragment: {link}")
    return errors


def main() -> int:
    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    print(f"Site checks: {len(errors)} error(s).")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
