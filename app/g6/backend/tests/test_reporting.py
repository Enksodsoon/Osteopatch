"""Case reports — append-only storage, hash provenance, and export agreement.

The tests defend four product claims, in order of how badly it would hurt to
get them wrong:

1. **An indeterminate patch is never stated as a finding.** A report that
   reports a non-result as a conclusion is worse than no report, so this is
   asserted on the typed document, in BOTH renderings, and in the public
   summary the UI reads.
2. **HTML and Markdown cannot disagree.** Both are rendered from one typed
   source, so every fact asserted about one is asserted about the other.
3. **The hash is checkable.** It is recomputed from the stored document and
   compared to the stored column — two different columns, read separately.
4. **Writing a report changes nothing else.** The frozen corpus is compared by
   row content before and after.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import json
import re
import sqlite3

import pytest
from osteopatch import db, integrity, reporting
from osteopatch.reporting import ReportError, draft_document


@pytest.fixture()
def rep_db(tmp_path):
    conn = db.connect(tmp_path / "reports.sqlite3")
    db.run_migrations(conn)
    return conn


CLEAR = {
    "image_id": "Case-3-A10-10547-25283",
    "source_kind": "corpus",
    "predicted_class": "NECROSIS",
    "confidence": "clear",
    "top_two_margin": 0.61,
    "scores": {"NON_TUMOR": 0.12, "VIABLE_TUMOR": 0.01, "NECROSIS": 0.87},
    "corroborated": True,
}
TIED = {
    "image_id": "Case-3-A17-15765-20926",
    "source_kind": "live",
    "run_id": "live-abc123",
    "predicted_class": "NON_TUMOR",
    "confidence": "indeterminate",
    "top_two_margin": 0.0,
    "scores": {"NON_TUMOR": 0.5, "VIABLE_TUMOR": 0.001, "NECROSIS": 0.499},
    "caveat": "The top two classes are effectively tied.",
}


def a_doc(**over):
    kw = dict(
        project_id="prj_1",
        case_id="Case-3-A10",
        title="Osteosarcoma — Case-3-A10 review",
        findings_text="Dense viable areas are present but the necrosis dominates.",
        author_email="reviewer@demo",
        images=[dict(CLEAR), dict(TIED)],
        signer_email="path@demo",
        signer_role="pathologist",
        signoff_note="Reviewed against the frozen prediction.",
        report_id="rep-test-0001",
        created_at="2026-10-06T12:00:00+00:00",
    )
    kw.update(over)
    return draft_document(**kw)


# ---------------------------------------------------------------------------
# 1. The honesty split
# ---------------------------------------------------------------------------


def test_an_indeterminate_patch_is_never_a_finding():
    doc = a_doc()
    assert [i.image_id for i in doc.supported] == [CLEAR["image_id"]]
    assert [i.image_id for i in doc.unresolved] == [TIED["image_id"]]


def test_rich_findings_are_sanitized_and_bound_to_the_report_hash(rep_db):
    doc = a_doc(findings_html='<p><strong>Observed</strong> matrix.</p><script>alert(1)</script><img src=x onerror=alert(2)>')
    assert doc.findings_text == "Observed matrix."
    assert doc.findings_html == "<p><strong>Observed</strong> matrix.</p>"
    assert "<script" not in doc.to_html() and "onerror" not in doc.to_html()
    stored = reporting.store_document(rep_db, doc)
    assert stored["findings_html"] == doc.findings_html
    assert reporting.verify_hash(rep_db, doc.report_id)["matches"] is True


def test_exported_image_preview_is_offline_and_bound_to_the_report_hash(rep_db):
    preview = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+tOQ8AAAAASUVORK5CYII="
    doc = a_doc(images=[dict(CLEAR, preview_png_base64=preview)])
    public = reporting.store_document(rep_db, doc)

    assert public["images"][0]["preview_attached"] is True
    assert "preview_png_base64" not in public["images"][0]
    assert f"data:image/png;base64,{preview}" in doc.to_html()
    assert f"data:image/png;base64,{preview}" in doc.to_markdown()
    assert doc.content_sha256 in doc.to_html() and doc.content_sha256 in doc.to_markdown()
    assert reporting.verify_hash(rep_db, doc.report_id)["matches"] is True


def test_unanalyzed_slide_is_not_a_no_call_and_survives_without_schema_changes(rep_db):
    slide = {"image_id": "slide:" + "a" * 32, "source_kind": "slide",
             "analysis_status": "not_analyzed", "caveat": "No model run is attached."}
    doc = a_doc(images=[slide])
    assert doc.supported == [] and doc.unresolved == []
    assert [image.image_id for image in doc.not_analyzed] == [slide["image_id"]]
    public = reporting.store_document(rep_db, doc)
    assert public["n_not_analyzed"] == 1 and public["n_unresolved"] == 0
    assert "Uploaded images without an AI run" in doc.to_markdown()
    assert "not analyzed" in doc.to_html()
    assert reporting.list_reports(rep_db, "prj_1")[0]["n_images"] == 1
    assert rep_db.execute("SELECT COUNT(*) FROM case_report_image WHERE report_id=?", (doc.report_id,)).fetchone()[0] == 0


def test_report_revision_is_linked_in_the_existing_append_only_column(rep_db):
    original = a_doc()
    reporting.store_document(rep_db, original)
    revision = a_doc(report_id="rep-test-0002", revision_of=original.report_id,
                     findings_text="Updated observation.")
    reporting.store_document(rep_db, revision)
    assert reporting.list_reports(rep_db, "prj_1")[0]["revision_of"] == original.report_id
    assert reporting.load_document(rep_db, original.report_id).findings_text != revision.findings_text


def test_a_tied_score_with_no_confidence_field_is_still_refused():
    """Defence in depth: if the store gave no confidence, the margin decides."""
    doc = a_doc(images=[{**CLEAR, "confidence": None, "top_two_margin": 0.01}])
    assert doc.supported == []
    assert len(doc.unresolved) == 1


def test_neither_export_names_a_class_for_an_indeterminate_image():
    doc = a_doc()
    md, ht = doc.to_markdown(), doc.to_html()

    supported_block_md = md.split("## Patches that produced no call")[0]
    supported_block_ht = ht.split("Patches that produced no call")[0]
    for block in (supported_block_md, supported_block_ht):
        assert CLEAR["image_id"] in block
        # The tied image must NOT appear in the part that claims a class...
        assert TIED["image_id"] not in block

    # ...and both renderings must name it in the unresolved section instead.
    for doc_text in (md, ht):
        assert TIED["image_id"] in doc_text
        assert "INDETERMINATE" in doc_text.upper()


def test_the_public_summary_separates_supported_from_unresolved():
    pub = reporting.public_report(a_doc())
    assert pub["n_images"] == 2
    assert pub["n_supported"] == 1
    assert pub["n_unresolved"] == 1


def test_signoff_is_marked_partial_when_any_image_is_unresolved():
    doc = a_doc()
    assert doc.is_signed
    assert doc.signoff_covers_all is False
    for text in (doc.to_markdown(), doc.to_html()):
        assert "PARTIAL" in text


def test_signoff_covers_all_when_every_image_is_determinate():
    doc = a_doc(images=[dict(CLEAR)])
    assert doc.signoff_covers_all is True
    assert "PARTIAL" not in doc.to_markdown()
    assert "PARTIAL" not in doc.to_html()


def test_an_unsigned_document_says_draft_in_both_renderings():
    doc = a_doc(signer_email=None, signer_role=None)
    assert doc.is_signed is False
    assert "DRAFT" in doc.to_markdown()
    assert "DRAFT" in doc.to_html()
    assert "none recorded" in doc.to_markdown()


# ---------------------------------------------------------------------------
# 2. HTML and Markdown agree
# ---------------------------------------------------------------------------

#: Facts that MUST appear in both renderings. This is the agreement contract:
#: if a number or an identifier is in one export it is in the other.
SHARED_FACTS = [
    "rep-test-0001",
    "Case-3-A10",
    "prj_1",
    "reviewer@demo",
    "path@demo",
    "2026-10-06T12:00:00+00:00",
    CLEAR["image_id"],
    TIED["image_id"],
    "NECROSIS",
    "NON_TUMOR",
    "VIABLE_TUMOR",
    "INDETERMINATE",
]


@pytest.mark.parametrize("fact", SHARED_FACTS)
def test_both_exports_contain_every_shared_fact(fact):
    doc = a_doc()
    assert fact in doc.to_markdown(), f"markdown is missing {fact!r}"
    assert fact in doc.to_html(), f"html is missing {fact!r}"


def test_both_exports_agree_on_every_score_to_four_decimals():
    doc = a_doc()
    md, ht = doc.to_markdown(), doc.to_html()
    for img in doc.images:
        for name, value in (img.scores or {}).items():
            rendered = f"{value:.4f}"
            assert rendered in md, f"{name}={rendered} missing from markdown"
            assert rendered in ht, f"{name}={rendered} missing from html"


def test_both_exports_carry_the_same_content_hash():
    doc = a_doc()
    assert doc.content_sha256 in doc.to_markdown()
    assert doc.content_sha256 in doc.to_html()


def test_both_exports_carry_the_disclaimer_and_the_uncalibrated_label():
    doc = a_doc()
    for text in (doc.to_markdown(), doc.to_html()):
        assert "Not for diagnosis" in text
        assert "not a probability" in text


def test_html_is_self_contained_and_offline_readable():
    """No CDN, no webfont, no remote reference of any kind."""
    html_text = a_doc().to_html()
    assert html_text.startswith("<!doctype html>")
    assert "<style>" in html_text          # styles are inline
    assert not re.search(r'src\s*=\s*"https?://', html_text)
    assert not re.search(r'@import\s+url\(\s*["\']?https?://', html_text)
    assert "fonts.googleapis.com" not in html_text
    assert "@media print" in html_text      # prints to PDF from the browser


# ---------------------------------------------------------------------------
# 3. Hash provenance
# ---------------------------------------------------------------------------


def test_stored_hash_is_recomputable_from_the_stored_document(rep_db):
    doc = a_doc()
    reporting.store_document(rep_db, doc)
    result = reporting.verify_hash(rep_db, doc.report_id)
    assert result["matches"] is True
    assert result["stored_sha256"] == doc.content_sha256
    assert result["recomputed_from_document_json"] == doc.content_sha256
    assert result["document_json_is_canonical"] is True


def test_a_tampered_document_fails_the_hash(rep_db):
    """The check must be able to fail, or it proves nothing.

    The append-only trigger blocks an in-place edit, so this bypasses it the way
    direct database or file corruption would — drop the guard, rewrite the
    bytes, leave the stored hash alone. That is precisely the case ``verify_hash``
    exists to catch and the trigger cannot.
    """
    doc = a_doc()
    reporting.store_document(rep_db, doc)
    assert reporting.verify_hash(rep_db, doc.report_id)["matches"] is True

    rep_db.execute("DROP TRIGGER case_report_no_update")
    tampered = json.loads(rep_db.execute(
        "SELECT document_json FROM case_report WHERE report_id=?", (doc.report_id,)
    ).fetchone()[0])
    tampered["findings_text"] = "TAMPERED - every class is viable tumor."
    rep_db.execute("UPDATE case_report SET document_json=? WHERE report_id=?",
                   (json.dumps(tampered, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False), doc.report_id))
    rep_db.commit()

    result = reporting.verify_hash(rep_db, doc.report_id)
    assert result["matches"] is False
    assert result["stored_sha256"] != result["recomputed_from_document_json"]


def test_the_same_document_always_hashes_the_same_way():
    assert a_doc().content_sha256 == a_doc().content_sha256
    assert len(a_doc().content_sha256) == 64


def test_two_different_documents_hash_differently():
    assert a_doc().content_sha256 != a_doc(findings_text="something else").content_sha256


# ---------------------------------------------------------------------------
# 4. Append-only
# ---------------------------------------------------------------------------


def test_a_stored_report_cannot_be_updated(rep_db):
    doc = a_doc()
    reporting.store_document(rep_db, doc)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        rep_db.execute("UPDATE case_report SET title='rewritten' WHERE report_id=?",
                       (doc.report_id,))
    rep_db.commit()


def test_a_revision_is_a_new_row_not_an_edit(rep_db):
    first = a_doc()
    reporting.store_document(rep_db, first)
    second = a_doc(report_id="rep-test-0002", findings_text="Revised findings.")
    reporting.store_document(rep_db, second)

    rows = rep_db.execute(
        "SELECT report_id, findings_text FROM case_report ORDER BY report_id"
    ).fetchall()
    assert len(rows) == 2
    assert [r["report_id"] for r in rows] == ["rep-test-0001", "rep-test-0002"]
    # the original text is still intact — nothing was overwritten
    assert rows[0]["findings_text"] == first.findings_text


def test_a_signed_report_without_a_signer_is_rejected(rep_db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        rep_db.execute(
            """INSERT INTO case_report
               (report_id, project_id, case_id, title, findings_text, author_email,
                signed_at, created_at, revision, document_json, content_sha256)
               VALUES ('r','p','c','t','f','a@x','2026-01-01T00:00:00Z',
                       '2026-01-01T00:00:00Z',1,'{}','%s')""" % ("a" * 64)
        )


def test_a_report_cannot_supersede_itself(rep_db):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        rep_db.execute(
            """INSERT INTO case_report
               (report_id, project_id, case_id, title, findings_text, author_email,
                created_at, revision, supersedes_report_id, document_json, content_sha256)
               VALUES ('r','p','c','t','f','a@x','2026-01-01T00:00:00Z',1,'r','{}',?)""",
            ("a" * 64,),
        )


def test_a_report_image_cannot_claim_a_fourth_class(rep_db):
    doc = a_doc()
    reporting.store_document(rep_db, doc)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        rep_db.execute(
            "INSERT INTO case_report_image VALUES (?,?,?,?,?,?,?,?,?,?)",
            (doc.report_id, 99, "x", "corpus", None, "MIXED", "clear", 0.5, None, None),
        )


# ---------------------------------------------------------------------------
# 5. Real content, and the corpus is untouched
# ---------------------------------------------------------------------------


def test_the_report_pulls_the_real_model_card_not_a_stub():
    doc = a_doc()
    mc = doc.model_card
    assert mc["model_version"] == "baseline-frozen-g4"
    assert mc["calibration_status"] == "uncalibrated"
    assert mc["macro_f1"] == 0.562311
    assert "NOT diagnosis" in mc["intended_use"]
    assert mc["frozen_limitations"], "frozen G4 caveats must be carried, not dropped"
    for text in (doc.to_markdown(), doc.to_html()):
        assert "baseline-frozen-g4" in text
        assert "0.562311" in text


def test_the_report_pulls_the_real_limitations_catalog():
    doc = a_doc()
    assert doc.limitations_summary["total"] > 0
    assert doc.limitations_text
    first = doc.limitations_text[0]
    assert first["severity"] in {"blocking", "high", "medium", "low"}
    assert first["statement"]
    # verbatim catalog text in both exports
    for text in (doc.to_markdown(), doc.to_html()):
        assert first["id"] in text
        assert first["statement"][:40] in text


def test_a_report_may_span_several_patches_from_one_case(rep_db):
    imgs = [dict(CLEAR, image_id=f"Case-3-A10-{i}") for i in range(4)]
    doc = a_doc(case_id="Case-3-A10", images=imgs)
    reporting.store_document(rep_db, doc)
    stored = reporting.load_document(rep_db, doc.report_id)
    assert len(stored.images) == 4
    assert {i.ordinal for i in stored.images} == {1, 2, 3, 4}
    assert all(i.image_id.startswith("Case-3-A10-") for i in stored.images)


def test_a_loaded_report_round_trips_to_the_same_hash(rep_db):
    doc = a_doc()
    reporting.store_document(rep_db, doc)
    assert reporting.load_document(rep_db, doc.report_id).content_sha256 == doc.content_sha256


def test_writing_a_report_leaves_the_frozen_corpus_byte_identical(rep_db):
    """The whole reason reports are a separate store."""
    before = integrity.corpus_row_digest(rep_db)
    reporting.store_document(rep_db, a_doc())
    reporting.store_document(rep_db, a_doc(report_id="rep-test-0002"))
    integrity.assert_corpus_unchanged(before, integrity.corpus_row_digest(rep_db))


def test_writing_a_report_writes_no_review_event(rep_db):
    rep_db.execute(
        "INSERT INTO source_qc (image_id, source_group, primary_qc_status, "
        "training_eligible, tiff_filename) VALUES ('i','g','PASS',1,'f.tiff')"
    )
    rep_db.commit()
    before = rep_db.execute("SELECT COUNT(*) FROM review_event").fetchone()[0]
    reporting.store_document(rep_db, a_doc(images=[dict(CLEAR, image_id="i")]))
    after = rep_db.execute("SELECT COUNT(*) FROM review_event").fetchone()[0]
    assert before == after == 0


def test_reports_are_scoped_to_a_project(rep_db):
    reporting.store_document(rep_db, a_doc())
    assert len(reporting.list_reports(rep_db, "prj_1")) == 1
    assert reporting.list_reports(rep_db, "prj_other") == []


def test_loading_an_unknown_report_raises(rep_db):
    with pytest.raises(ReportError, match="no such report"):
        reporting.load_document(rep_db, "rep-nope")
