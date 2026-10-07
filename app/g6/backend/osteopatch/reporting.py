"""Typed case reports: one source document, two renderings, one hash.

Why a report is its own concept
-------------------------------
A report is not a review event and not a prediction. It reads both. It is
stored append-only in ``case_report`` / ``case_report_image``, so producing a
document can never change what was reviewed, by whom, or when — and a report
that is later revised is a NEW row that names what it supersedes, never an
in-place edit.

One typed source, two exports
-----------------------------
:class:`ReportDocument` is the single source of truth. :meth:`to_markdown` and
:meth:`to_html` both render from it and from nothing else, so the two files
cannot drift; ``tests/test_reporting.py`` extracts the shared facts out of both
and asserts they agree.

Provenance you can re-check
---------------------------
``content_sha256`` is a digest over a canonical JSON serialization of the
document. Anyone holding the document later can recompute it and learn whether
they are looking at the thing that was signed.

Honesty is structural, not stylistic
------------------------------------
The most important rule here: a patch whose top two classes are not separable
is NEVER presented as a finding. It is moved into an "not determinable" section
with its raw scores, so the document cannot quietly upgrade a non-result into a
conclusion. Sign-off that does not cover every image is recorded as partial.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import hashlib
import html
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from . import limitations, modelcard

#: The three outputs. A report may never introduce a fourth.
CANONICAL_CLASSES = ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")

#: Below this top-two separation the model is not making a call, so neither is
#: the report. Mirrors LIVE_MARGIN_INDETERMINATE in config.
INDETERMINATE_MARGIN = 0.05

#: The text that must appear in every exported document, without exception.
DISCLAIMER = (
    "Educational research prototype. Not for diagnosis, treatment decisions, "
    "treatment-response prediction, or prognosis."
)

#: Every score in a report is uncalibrated. This label travels with each one.
SCORE_LABEL = "Model score — uncalibrated (recovered research head), not a probability"


class ReportError(Exception):
    """Base for report failures. Never raised for a merely uncertain result."""


class ReportScopeError(ReportError):
    """An image or case outside the caller's project."""


class SignoffError(ReportError):
    """A sign-off that the document cannot honestly accept."""


# ---------------------------------------------------------------------------
# Typed source
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportImage:
    """One patch as it appears in the document, copied at write time."""

    ordinal: int
    image_id: str
    source_kind: str                      # 'corpus' | 'live'
    run_id: str | None = None
    predicted_class: str | None = None
    confidence: str | None = None
    top_two_margin: float | None = None
    scores: dict[str, float] | None = None
    caveat: str | None = None
    #: Set when a human review_event corroborates this patch's prediction.
    #: Copied, not recomputed, so the document does not claim corroboration it
    #: cannot show.
    corroborated: bool = False
    #: Whether the model made a call at all. Drives the supported/unresolved
    #: split; computed once here so both renderings agree.
    determinate: bool = True
    analysis_status: str | None = None
    #: Small PNG preview captured when the report is written. This is inside
    #: document_json, so the report hash also protects the exported image.
    preview_png_base64: str | None = None

    @property
    def class_label(self) -> str:
        if not self.predicted_class:
            return "no class asserted"
        return {
            "NON_TUMOR": "Non-tumor",
            "VIABLE_TUMOR": "Viable tumor",
            "NECROSIS": "Necrosis",
        }[self.predicted_class]


@dataclass(frozen=True)
class ReportDocument:
    """The frozen typed source. Both exports render from exactly this."""

    report_id: str
    project_id: str
    case_id: str
    title: str
    findings_text: str
    author_email: str
    created_at: str
    images: list[ReportImage] = field(default_factory=list)
    signer_email: str | None = None
    signer_role: str | None = None
    signed_at: str | None = None
    signoff_note: str | None = None
    model_card: dict[str, Any] = field(default_factory=dict)
    limitations_summary: dict[str, Any] = field(default_factory=dict)
    limitations_text: list[dict[str, Any]] = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    findings_html: str | None = None
    revision_of: str | None = None

    # -- provenance ---------------------------------------------------------

    def canonical_json(self) -> str:
        """Deterministic serialization. This is what the hash covers.

        ``sort_keys`` and fixed separators mean two processes hashing the same
        document get the same digest; ``ensure_ascii=False`` keeps the real
        characters rather than escapes, so the hash is over the text a reader
        would see.
        """
        payload = asdict(self)
        # Omit absent additions so reports written before rich findings and
        # report revisions continue to reproduce their original content hash.
        if self.findings_html is None:
            payload.pop("findings_html")
        if self.revision_of is None:
            payload.pop("revision_of")
        for image in payload["images"]:
            if image["analysis_status"] is None:
                image.pop("analysis_status")
            if image["preview_png_base64"] is None:
                image.pop("preview_png_base64")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @property
    def is_signed(self) -> bool:
        return bool(self.signer_email and self.signed_at)

    # -- the honesty split --------------------------------------------------

    @property
    def supported(self) -> list[ReportImage]:
        """Images the document is willing to state a class for."""
        return [i for i in self.images if i.determinate and i.analysis_status != "not_analyzed"]

    @property
    def unresolved(self) -> list[ReportImage]:
        """Images that produced NO call. Never presented as findings."""
        return [i for i in self.images if not i.determinate and i.analysis_status != "not_analyzed"]

    @property
    def not_analyzed(self) -> list[ReportImage]:
        return [i for i in self.images if i.analysis_status == "not_analyzed"]

    @property
    def signoff_covers_all(self) -> bool:
        """True when the signer saw the whole document, unresolved included."""
        return self.is_signed and not self.unresolved

    # -- renderings ---------------------------------------------------------

    def to_markdown(self) -> str:
        return render_markdown(self)

    def to_html(self) -> str:
        return render_html(self)


# ---------------------------------------------------------------------------
# Building the document
# ---------------------------------------------------------------------------


def _classify(scores: dict[str, float] | None, margin: float | None,
              confidence: str | None) -> bool:
    """Whether the model actually made a call on this image.

    Explicit confidence from the store wins; otherwise fall back to the margin.
    Both paths are conservative: anything that is not clearly decided is
    treated as NOT decided.
    """
    if confidence == "indeterminate":
        return False
    if confidence in ("clear", "low"):
        return True
    if margin is None or scores is None:
        return False
    return margin > INDETERMINATE_MARGIN


class _FindingsHTML(HTMLParser):
    """Keep a small formatting allowlist and derive the signed plain text."""

    allowed = {"p", "div", "br", "strong", "b", "em", "i", "u", "h2", "h3", "ul", "ol", "li", "blockquote"}
    blocked = {"script", "style", "iframe", "object", "svg", "math"}
    block = {"p", "div", "h2", "h3", "li", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.text: list[str] = []
        self.stack: list[str] = []
        self.skip: list[str] = []

    def _break(self) -> None:
        if self.text and not self.text[-1].endswith("\n"):
            self.text.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.skip:
            if tag in self.blocked:
                self.skip.append(tag)
            return
        if tag in self.blocked:
            self.skip.append(tag)
            return
        if tag not in self.allowed:
            return
        if tag in self.block:
            self._break()
        if tag == "br":
            self.output.append("<br>")
            self.text.append("\n")
        else:
            self.output.append(f"<{tag}>")
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            if tag in self.skip:
                self.skip = self.skip[:len(self.skip) - 1 - self.skip[::-1].index(tag)]
            return
        if tag not in self.stack:
            return
        while self.stack:
            current = self.stack.pop()
            self.output.append(f"</{current}>")
            if current == tag:
                break
        if tag in self.block:
            self._break()

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        self.output.append(html.escape(data, quote=False))
        self.text.append(data)

    def finish(self) -> tuple[str, str]:
        while self.stack:
            self.output.append(f"</{self.stack.pop()}>")
        return "".join(self.output).strip(), "".join(self.text).strip()


def sanitize_findings_html(value: str) -> tuple[str, str]:
    parser = _FindingsHTML()
    parser.feed(value)
    parser.close()
    return parser.finish()


def model_card_excerpt() -> dict[str, Any]:
    """The real model card, excerpted. Never invented, never paraphrased.

    Absent evaluation artifacts are reported as absent — the card already
    carries that language, and a report must not imply there were no caveats.
    """
    card = modelcard.model_card()
    return {
        "model_version": card["model_version"],
        "calibration_status": card["calibration_status"],
        "canonical_classes": list(CANONICAL_CLASSES),
        "intended_use": card.get("intended_use"),
        "performance_statement": card.get("performance_statement"),
        "macro_f1": card["headline_oof"].get("macro_f1"),
        "n_rows": card["headline_oof"].get("n_rows"),
        "evaluation_evidence_available": card["evaluation_evidence_available"],
        "evaluation_evidence_unavailable_reason": card[
            "evaluation_evidence_unavailable_reason"
        ],
        "frozen_limitations": list(card.get("limitations") or []),
    }


def limitations_excerpt(limit: int = 6) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Real limitations text, most severe first.

    Returns ``(summary, items)``. The summary is the catalog's own counts; the
    items are verbatim statements, never rewritten.
    """
    items = sorted(
        limitations.catalog(),
        key=lambda d: (
            {"blocking": 0, "high": 1, "medium": 2, "low": 3}.get(d["severity"], 4),
            d["id"],
        ),
    )
    return limitations.summary(), [
        {
            "id": d["id"],
            "severity": d["severity"],
            "category": d["category"],
            "statement": d["statement"],
        }
        for d in items[:limit]
    ]


def draft_document(
    *,
    project_id: str,
    case_id: str,
    title: str,
    findings_text: str,
    findings_html: str | None = None,
    revision_of: str | None = None,
    author_email: str,
    images: list[dict[str, Any]],
    signer_email: str | None = None,
    signer_role: str | None = None,
    signoff_note: str | None = None,
    report_id: str | None = None,
    created_at: str | None = None,
) -> ReportDocument:
    """Assemble a typed document from real rows. Does not write anything."""
    report_id = report_id or f"rep-{uuid.uuid4().hex[:16]}"
    created_at = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    safe_html, rich_text = sanitize_findings_html(findings_html) if findings_html is not None else (None, None)

    built: list[ReportImage] = []
    for n, raw in enumerate(images, start=1):
        scores = raw.get("scores")
        margin = raw.get("top_two_margin")
        confidence = raw.get("confidence")
        built.append(
            ReportImage(
                ordinal=n,
                image_id=str(raw["image_id"]),
                source_kind=str(raw.get("source_kind") or "corpus"),
                run_id=raw.get("run_id"),
                predicted_class=raw.get("predicted_class"),
                confidence=confidence,
                top_two_margin=float(margin) if margin is not None else None,
                scores={k: float(v) for k, v in scores.items()} if scores else None,
                caveat=raw.get("caveat"),
                corroborated=bool(raw.get("corroborated")),
                determinate=_classify(scores, margin, confidence),
                analysis_status=raw.get("analysis_status"),
                preview_png_base64=raw.get("preview_png_base64"),
            )
        )

    summary, lim_items = limitations_excerpt()
    return ReportDocument(
        report_id=report_id,
        project_id=project_id,
        case_id=case_id,
        title=title.strip() or f"Case {case_id}",
        findings_text=rich_text if rich_text is not None else findings_text.strip(),
        author_email=author_email,
        created_at=created_at,
        images=built,
        signer_email=signer_email,
        signer_role=signer_role,
        signed_at=created_at if signer_email else None,
        signoff_note=signoff_note,
        model_card=model_card_excerpt(),
        limitations_summary=summary,
        limitations_text=lim_items,
        findings_html=safe_html,
        revision_of=revision_of,
    )


# ---------------------------------------------------------------------------
# Persistence — INSERT only
# ---------------------------------------------------------------------------


def store_document(conn: sqlite3.Connection, doc: ReportDocument) -> dict[str, Any]:
    """Append a document. There is no update function, by design."""
    conn.execute(
        """INSERT INTO case_report (
             report_id, project_id, case_id, title, findings_text, author_email,
             signer_email, signer_role, signed_at, signoff_note, created_at,
             revision, supersedes_report_id, document_json, content_sha256
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
        (
            doc.report_id, doc.project_id, doc.case_id, doc.title, doc.findings_text,
            doc.author_email, doc.signer_email, doc.signer_role, doc.signed_at,
            doc.signoff_note, doc.created_at, doc.revision_of, doc.canonical_json(), doc.content_sha256,
        ),
    )
    for img in doc.images:
        # Uploaded WSI references live in document_json. The normalized image
        # table predates slide sources and intentionally remains schema-stable.
        if img.source_kind == "slide":
            continue
        conn.execute(
            """INSERT INTO case_report_image (
                 report_id, ordinal, image_id, source_kind, run_id,
                 predicted_class, confidence, top_two_margin, scores_json, caveat_text
               ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                doc.report_id, img.ordinal, img.image_id, img.source_kind, img.run_id,
                img.predicted_class, img.confidence, img.top_two_margin,
                json.dumps(img.scores, sort_keys=True) if img.scores else None,
                img.caveat,
            ),
        )
    conn.commit()
    return public_report(doc)


def public_report(doc: ReportDocument) -> dict[str, Any]:
    return {
        "report_id": doc.report_id,
        "project_id": doc.project_id,
        "case_id": doc.case_id,
        "title": doc.title,
        "findings_text": doc.findings_text,
        "findings_html": doc.findings_html,
        "revision_of": doc.revision_of,
        "author_email": doc.author_email,
        "created_at": doc.created_at,
        "is_signed": doc.is_signed,
        "signer_email": doc.signer_email,
        "signer_role": doc.signer_role,
        "signed_at": doc.signed_at,
        "signoff_note": doc.signoff_note,
        "signoff_covers_all": doc.signoff_covers_all,
        "content_sha256": doc.content_sha256,
        "disclaimer": doc.disclaimer,
        "n_images": len(doc.images),
        "n_supported": len(doc.supported),
        "n_unresolved": len(doc.unresolved),
        "n_not_analyzed": len(doc.not_analyzed),
        "images": [
            {**{k: v for k, v in asdict(i).items() if k != "preview_png_base64"},
             "preview_attached": bool(i.preview_png_base64)}
            for i in doc.images
        ],
        "model_card": doc.model_card,
        "limitations_summary": doc.limitations_summary,
        "limitations_text": doc.limitations_text,
        "score_label": SCORE_LABEL,
        "export_endpoints": {
            "html": f"/v1/reports/{doc.report_id}/export.html",
            "markdown": f"/v1/reports/{doc.report_id}/export.md",
        },
    }


def load_document(conn: sqlite3.Connection, report_id: str) -> ReportDocument:
    row = conn.execute(
        "SELECT document_json, content_sha256 FROM case_report WHERE report_id = ?",
        (report_id,),
    ).fetchone()
    if row is None:
        raise ReportError(f"no such report: {report_id}")
    raw = json.loads(row["document_json"])
    return _from_json(raw)


def _from_json(raw: dict[str, Any]) -> ReportDocument:
    return ReportDocument(
        report_id=raw["report_id"],
        project_id=raw["project_id"],
        case_id=raw["case_id"],
        title=raw["title"],
        findings_text=raw["findings_text"],
        author_email=raw["author_email"],
        created_at=raw["created_at"],
        images=[ReportImage(**i) for i in raw.get("images", [])],
        signer_email=raw.get("signer_email"),
        signer_role=raw.get("signer_role"),
        signed_at=raw.get("signed_at"),
        signoff_note=raw.get("signoff_note"),
        model_card=raw.get("model_card", {}),
        limitations_summary=raw.get("limitations_summary", {}),
        limitations_text=raw.get("limitations_text", []),
        disclaimer=raw.get("disclaimer", DISCLAIMER),
        findings_html=raw.get("findings_html"),
        revision_of=raw.get("revision_of"),
    )


def verify_hash(conn: sqlite3.Connection, report_id: str) -> dict[str, Any]:
    """Re-derive the digest from the stored document and compare it.

    This is the whole point of storing a hash. The recomputation reads
    ``document_json`` from the database and hashes it again from scratch; the
    comparison is against the ``content_sha256`` column that was written with
    the document. They are read from two different columns on purpose — a
    function that hashed the object it was handed would agree with itself
    forever and prove nothing.
    """
    row = conn.execute(
        "SELECT content_sha256, document_json FROM case_report WHERE report_id = ?",
        (report_id,),
    ).fetchone()
    if row is None:
        raise ReportError(f"no such report: {report_id}")

    stored = row["content_sha256"]
    recomputed = hashlib.sha256(row["document_json"].encode("utf-8")).hexdigest()
    # The document as loaded back must also agree with its own declared hash,
    # which is what `canonical_json` reproduces byte-for-byte.
    doc = _from_json(json.loads(row["document_json"]))
    return {
        "report_id": report_id,
        "stored_sha256": stored,
        "recomputed_from_document_json": recomputed,
        "hash_of_typed_document": doc.content_sha256,
        "matches": stored == recomputed == doc.content_sha256,
        "document_json_is_canonical": row["document_json"] == doc.canonical_json(),
    }


def list_reports(conn: sqlite3.Connection, project_id: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT report_id, case_id, title, author_email, created_at, signer_email,
                  content_sha256, supersedes_report_id AS revision_of, document_json
             FROM case_report r
            WHERE project_id = ?
            ORDER BY created_at DESC, report_id DESC
            LIMIT ?""",
        (project_id, limit),
    ).fetchall()
    reports = []
    for row in rows:
        item = dict(row)
        document = json.loads(item.pop("document_json"))
        item["n_images"] = len(document.get("images", []))
        reports.append(item)
    return reports


# ---------------------------------------------------------------------------
# Rendering — both read only from the typed document
# ---------------------------------------------------------------------------


def _score_lines(img: ReportImage) -> list[str]:
    if not img.scores:
        return ["- scores: not recorded"]
    return [f"- {k}: {img.scores[k]:.4f}" for k in CANONICAL_CLASSES if k in img.scores]


def _markdown_preview(img: ReportImage) -> list[str]:
    if not img.preview_png_base64:
        return []
    return [
        f"![Attached image preview for report item {img.ordinal}]"
        f"(data:image/png;base64,{img.preview_png_base64})",
        "",
    ]


def _html_preview(img: ReportImage) -> str:
    if not img.preview_png_base64:
        return ""
    return (
        '<figure class="report-preview">'
        f'<img alt="Attached image preview for report item {img.ordinal}" '
        f'src="data:image/png;base64,{html.escape(img.preview_png_base64, quote=True)}">'
        "<figcaption>Attached image preview · included in the content SHA-256.</figcaption>"
        "</figure>"
    )


def render_markdown(doc: ReportDocument) -> str:
    """Markdown. Every number here also appears in render_html."""
    L: list[str] = []
    status = "SIGNED" if doc.is_signed else "DRAFT — UNSIGNED"
    L.append(f"# {doc.title}")
    L.append("")
    L.append(f"> **{status}** — {doc.disclaimer}")
    L.append("")
    L.append(f"- Report id: `{doc.report_id}`")
    L.append(f"- Case: `{doc.case_id}`")
    L.append(f"- Project: `{doc.project_id}`")
    L.append(f"- Author: {doc.author_email}")
    L.append(f"- Created: {doc.created_at}")
    if doc.revision_of:
        L.append(f"- Revision of: `{doc.revision_of}`")
    L.append(f"- Content SHA-256: `{doc.content_sha256}`")
    if doc.is_signed:
        L.append(f"- Signed by: {doc.signer_email} ({doc.signer_role}) at {doc.signed_at}")
        if not doc.signoff_covers_all:
            L.append(
                f"- **Sign-off is PARTIAL**: {len(doc.unresolved)} image(s) in this "
                "report produced no determinable class and are listed below."
            )
    else:
        L.append("- Sign-off: **none recorded**")
    L.append("")

    L.append("## Reviewer findings")
    L.append("")
    L.append(doc.findings_html or doc.findings_text or "_No findings text was supplied._")
    L.append("")

    L.append("## Patches with a determinable class")
    L.append("")
    if doc.supported:
        for img in doc.supported:
            L.append(
                f"### {img.ordinal}. `{img.image_id}` — {img.predicted_class} "
                f"({img.class_label})"
            )
            L.append("")
            L.append(f"- Source: {img.source_kind}"
                     + (f" (run `{img.run_id}`)" if img.run_id else ""))
            L.append(f"- Top-two separation: "
                     f"{img.top_two_margin:.4f}" if img.top_two_margin is not None
                     else "- Top-two separation: not recorded")
            L.append(f"- Corroborated by a recorded review: {'yes' if img.corroborated else 'no'}")
            L.extend(_score_lines(img))
            if img.caveat:
                L.append(f"- Caveat: {img.caveat}")
            L.extend(_markdown_preview(img))
            L.append("")
    else:
        L.append("_None. No patch in this report produced a determinable class._")
        L.append("")

    L.append("## Patches that produced no call")
    L.append("")
    if doc.unresolved:
        L.append(
            "The top two classes for these patches were not separable. **No class is "
            "asserted for them and none of their scores may be read as a finding.**"
        )
        L.append("")
        for img in doc.unresolved:
            L.append(
                f"### {img.ordinal}. `{img.image_id}` — INDETERMINATE"
            )
            L.append("")
            L.append(f"- Top-two separation: "
                     f"{img.top_two_margin:.4f}" if img.top_two_margin is not None
                     else "- Top-two separation: not recorded")
            L.extend(_score_lines(img))
            if img.caveat:
                L.append(f"- Caveat: {img.caveat}")
            L.extend(_markdown_preview(img))
            L.append("")
    else:
        L.append("_None._")
        L.append("")

    L.append("## Uploaded images without an AI run")
    L.append("")
    if doc.not_analyzed:
        for img in doc.not_analyzed:
            L.append(f"### {img.ordinal}. `{img.image_id}` — not analyzed")
            L.append("")
            L.append(f"- Source: {img.source_kind}")
            L.append(f"- Note: {img.caveat or 'No model run was attached to this image.'}")
            L.extend(_markdown_preview(img))
            L.append("")
    else:
        L.append("_None._")
        L.append("")

    L.append("## Model card excerpt")
    L.append("")
    mc = doc.model_card
    L.append(f"- Model version: `{mc.get('model_version')}`")
    L.append(f"- Calibration: {mc.get('calibration_status')}")
    L.append(f"- Classes: {', '.join(mc.get('canonical_classes') or [])}")
    L.append(f"- Pooled out-of-fold macro-F1: {mc.get('macro_f1')}"
             + (f" (n={mc['n_rows']})" if mc.get("n_rows") else ""))
    L.append(f"- Intended use: {mc.get('intended_use')}")
    L.append(f"- Performance statement: {mc.get('performance_statement')}")
    if not mc.get("evaluation_evidence_available"):
        L.append(f"- Evaluation evidence: **absent** — "
                 f"{mc.get('evaluation_evidence_unavailable_reason')}")
    L.append("")
    L.append(f"> {SCORE_LABEL}")
    L.append("")
    L.append("### Frozen G4 evaluation limitations (verbatim)")
    L.append("")
    for lim in mc.get("frozen_limitations") or []:
        L.append(f"- {lim}")
    L.append("")

    L.append("## Limitations catalog (verbatim, most severe first)")
    L.append("")
    summary = doc.limitations_summary
    L.append(
        f"Catalog total: {summary.get('total')} — "
        + ", ".join(f"{k}: {v}" for k, v in (summary.get("by_severity") or {}).items())
    )
    L.append("")
    for lim in doc.limitations_text:
        L.append(f"- **[{lim['severity'].upper()}]** ({lim['id']}) {lim['statement']}")
    L.append("")
    L.append("---")
    L.append("")
    L.append(f"*{doc.disclaimer}*")
    return "\n".join(L) + "\n"


def render_html(doc: ReportDocument) -> str:
    """Self-contained HTML: no external CSS, no fonts, no network.

    Opens offline and prints to PDF from the browser. Deliberately plain —
    a report that needs a CDN to be readable is not a record of anything.
    """
    e = html.escape
    status = "SIGNED" if doc.is_signed else "DRAFT — UNSIGNED"
    status_cls = "signed" if doc.is_signed else "draft"

    def head(k: str, v: str) -> str:
        return f"<dt>{e(k)}</dt><dd>{e(v)}</dd>"

    parts: list[str] = []
    parts.append(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{e(doc.title)}</title>\n<style>\n{_HTML_CSS}\n</style>\n</head>\n<body>\n"
    )
    parts.append(
        f'<div class="banner {status_cls}"><strong>{e(status)}</strong> — {e(doc.disclaimer)}</div>'
    )
    parts.append(f"<h1>{e(doc.title)}</h1>")

    parts.append('<dl class="meta">')
    parts.append(head("Report id", doc.report_id or ""))
    parts.append(head("Case", doc.case_id or ""))
    parts.append(head("Project", doc.project_id or ""))
    parts.append(head("Author", doc.author_email or ""))
    parts.append(head("Created", doc.created_at or ""))
    if doc.revision_of:
        parts.append(head("Revision of", doc.revision_of))
    parts.append(head("Content SHA-256", doc.content_sha256 or ""))
    if doc.is_signed:
        parts.append(head("Signed by", f"{doc.signer_email or ''} ({doc.signer_role or ''}) at {doc.signed_at or ''}"))
        if not doc.signoff_covers_all:
            parts.append(
                "<dt class=\"warn\">Sign-off</dt>"
                f"<dd class=\"warn\"><strong>PARTIAL</strong> — {len(doc.unresolved)} "
                "image(s) produced no determinable class and are listed below.</dd>"
            )
    else:
        parts.append("<dt>Sign-off</dt><dd><strong>none recorded</strong></dd>")
    parts.append("</dl>")

    parts.append("<h2>Reviewer findings</h2>")
    findings = doc.findings_html or (e(doc.findings_text).replace("\n", "<br>") if doc.findings_text else "<em>No findings text was supplied.</em>")
    parts.append(f'<div class="prose">{findings}</div>')

    parts.append("<h2>Patches with a determinable class</h2>")
    if doc.supported:
        for img in doc.supported:
            parts.append(
                f'<article class="img supported cl-{e(img.predicted_class or "")}">'
                f"<h3>{img.ordinal}. {e(img.image_id)} — "
                f"<span class=\"cls\">{e(img.predicted_class or '')}</span> "
                f"<span class=\"muted\">({e(img.class_label)})</span></h3>"
                "<ul>"
                + f"<li>Source: {e(img.source_kind)}"
                + (f" (run {e(img.run_id or '')}" if img.run_id else "")
                + "</li>"
                + (f"<li>Top-two separation: {img.top_two_margin:.4f}</li>"
                   if img.top_two_margin is not None
                   else "<li>Top-two separation: not recorded</li>")
                + f"<li>Corroborated by a recorded review: "
                  f"{'yes' if img.corroborated else 'no'}</li>"
                + "".join(f"<li class=\"mono\">{e(s)}</li>" for s in _score_lines(img))
                + (f"<li class=\"caveat\">Caveat: {e(img.caveat or '')}</li>" if img.caveat else "")
                + "</ul>"
                + _html_preview(img)
                + "</article>"
            )
    else:
        parts.append(
            "<p class=\"empty\"><em>None. No patch in this report produced a "
            "determinable class.</em></p>"
        )

    parts.append("<h2>Patches that produced no call</h2>")
    if doc.unresolved:
        parts.append(
            "<p class=\"unresolved-note\">The top two classes for these patches were "
            "not separable. <strong>No class is asserted for them and none of their "
            "scores may be read as a finding.</strong></p>"
        )
        for img in doc.unresolved:
            parts.append(
                '<article class="img indeterminate">'
                f"<h3>{img.ordinal}. {e(img.image_id)} — INDETERMINATE</h3><ul>"
                + (f"<li>Top-two separation: {img.top_two_margin:.4f}</li>"
                   if img.top_two_margin is not None
                   else "<li>Top-two separation: not recorded</li>")
                + "".join(f"<li class=\"mono\">{e(s)}</li>" for s in _score_lines(img))
                + (f"<li class=\"caveat\">Caveat: {e(img.caveat or '')}</li>" if img.caveat else "")
                + "</ul>"
                + _html_preview(img)
                + "</article>"
            )
    else:
        parts.append("<p class=\"empty\"><em>None.</em></p>")

    parts.append("<h2>Uploaded images without an AI run</h2>")
    if doc.not_analyzed:
        for img in doc.not_analyzed:
            parts.append(
                '<article class="img not-analyzed">'
                f"<h3>{img.ordinal}. {e(img.image_id)} — not analyzed</h3>"
                f"<p>{e(img.caveat or 'No model run was attached to this image.')}</p>"
                f"{_html_preview(img)}</article>"
            )
    else:
        parts.append("<p class=\"empty\"><em>None.</em></p>")

    parts.append("<h2>Model card excerpt</h2>")
    mc = doc.model_card
    parts.append("<dl class=\"meta\">")
    parts.append(head("Model version", str(mc.get("model_version") or "")))
    parts.append(head("Calibration", str(mc.get("calibration_status") or "")))
    parts.append(head("Classes", ", ".join(mc.get("canonical_classes") or [])))
    parts.append(
        head("Pooled OOF macro-F1",
             f"{mc.get('macro_f1')}" + (f" (n={mc['n_rows']})" if mc.get("n_rows") else ""))
    )
    parts.append(head("Intended use", str(mc.get("intended_use") or "")))
    parts.append(head("Performance statement", str(mc.get("performance_statement") or "")))
    if not mc.get("evaluation_evidence_available"):
        parts.append(
            f"<dt class=\"warn\">Evaluation evidence</dt>"
            f"<dd class=\"warn\"><strong>absent</strong> — "
            f"{e(str(mc.get('evaluation_evidence_unavailable_reason') or ''))}</dd>"
        )
    parts.append("</dl>")
    parts.append(f'<p class="score-label">{e(SCORE_LABEL)}</p>')

    parts.append("<h3>Frozen G4 evaluation limitations (verbatim)</h3><ul>")
    for lim in mc.get("frozen_limitations") or []:
        parts.append(f"<li>{e(str(lim))}</li>")
    parts.append("</ul>")

    parts.append("<h2>Limitations catalog (verbatim, most severe first)</h2>")
    summary = doc.limitations_summary
    parts.append(
        "<p>Catalog total: "
        f"{e(str(summary.get('total') or ''))} — "
        + e(", ".join(f"{k}: {v}" for k, v in (summary.get("by_severity") or {}).items()))
        + "</p><ul>"
    )
    for lim in doc.limitations_text:
        parts.append(
            f"<li><span class=\"sev sev-{e(lim['severity'])}\">{e(lim['severity'].upper())}"
            f"</span> <span class=\"muted\">({e(lim['id'])})</span> "
            f"{e(lim['statement'])}</li>"
        )
    parts.append("</ul>")

    parts.append(f'<footer><em>{e(doc.disclaimer)}</em></footer>')
    parts.append("</body>\n</html>\n")
    return "".join(parts)


_HTML_CSS = """
:root { --ink:#15181d; --muted:#5b6472; --line:#d7dce3; --warn:#8a4b00; --warnbg:#fff6e6; }
* { box-sizing: border-box; }
body { margin:0; padding:0 0 48px; background:#fff; color:var(--ink);
  font:16px/1.6 Georgia, 'Times New Roman', serif; }
main, body > * { max-width: 820px; margin-left:auto; margin-right:auto; }
body > * { padding-left:24px; padding-right:24px; }
h1 { font-size:28px; line-height:1.2; margin:24px 0 8px; letter-spacing:-0.01em; }
h2 { font-size:19px; margin:32px 0 8px; padding-bottom:6px;
  border-bottom:2px solid var(--line); }
h3 { font-size:16px; margin:18px 0 6px; }
.banner { background:#3a2a00; color:#ffd480; font:600 14px/1.5 system-ui, sans-serif;
  padding:12px 24px; }
.banner.draft { background:#8a4b00; color:#fff; }
dl.meta { display:grid; grid-template-columns:max-content 1fr; gap:4px 16px;
  font:14px/1.5 ui-monospace, Menlo, Consolas, monospace; margin:12px 0 0; }
dl.meta dt { color:var(--muted); }
dl.meta dd { margin:0; overflow-wrap:anywhere; }
dl.meta dt.warn, dl.meta dd.warn { color:var(--warn); }
.mono { font-family:ui-monospace, Menlo, Consolas, monospace; font-size:13px; }
.report-preview { margin:12px 0; }
.report-preview img { display:block; max-width:100%; max-height:360px; object-fit:contain; border:1px solid var(--line); }
.report-preview figcaption { color:var(--muted); font:12px/1.4 system-ui, sans-serif; margin-top:4px; }
ul { margin:6px 0 12px; padding-left:20px; }
li { margin:3px 0; }
.prose { white-space:normal; }
p.empty { color:var(--muted); }
article.img { border:1px solid var(--line); border-left-width:4px; border-radius:6px;
  padding:12px 16px; margin:12px 0; }
article.supported { border-left-color:#2e6f4e; }
article.indeterminate { border-left-color:#c07a00; background:var(--warnbg); }
article.indeterminate h3 { color:var(--warn); }
.cls { font-family:ui-monospace, Menlo, Consolas, monospace; }
.unresolved-note { background:var(--warnbg); border-left:4px solid #c07a00;
  padding:10px 14px; border-radius:4px; font-size:15px; }
.score-label { display:inline-block; background:var(--warnbg); color:var(--warn);
  border:1px solid #c07a00; border-radius:4px; padding:3px 9px; font:600 13px/1.5 system-ui, sans-serif; }
.caveat { color:var(--warn); font-size:14px; }
.muted { color:var(--muted); font-size:14px; }
.sev { font:700 11px/1 system-ui, sans-serif; letter-spacing:.06em;
  border-radius:3px; padding:2px 6px; }
.sev-blocking { background:#7f1d1d; color:#fff; }
.sev-high { background:#b45309; color:#fff; }
.sev-medium { background:#d6b25e; color:#3a2a00; }
.sev-low { background:#e3e7ec; color:#3a4552; }
footer { margin-top:36px; padding-top:12px; border-top:1px solid var(--line);
  color:var(--muted); font-size:14px; }
@media print {
  body { font-size:11pt; }
  h2 { page-break-after:avoid; }
  article.img { page-break-inside:avoid; }
  .banner { background:#3a2a00 !important; -webkit-print-color-adjust:exact;
    print-color-adjust:exact; }
  a[href]:after { content:''; }
}
"""
