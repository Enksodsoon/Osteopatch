import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../../api";
import type { SlideMeta } from "../../api";
import type {
  GalleryItem, LiveRunSummary, PublicReport, ReportSummary, Role,
} from "../../types";
import {
  REPORT_WRITE_DENIED_REASON, REPORT_WRITE_ROLES,
} from "../../types";
import { AuthenticatedImage } from "../AuthenticatedImage";

type ReportLibraryItem = {
  key: string;
  label: string;
  caseId: string;
  name: string;
  slideId?: string;
  runId?: string;
};

function reportLibraryItems(gallery: GalleryItem[], runs: LiveRunSummary[], slides: SlideMeta[]): ReportLibraryItem[] {
  const slideItems = slides.map((slide) => ({
    key: `slide:${slide.slide_id}`, label: `${slide.filename} · uploaded slide`,
    caseId: slide.filename.replace(/\.[^.]+$/, ""), name: slide.filename, slideId: slide.slide_id,
  }));
  const runItems = runs.map((run) => ({
    key: `run:${run.run_id}`, label: `${run.source_name} · analyzed image`,
    caseId: run.source_name.replace(/\.[^.]+$/, ""), name: run.source_name, runId: run.run_id,
  }));
  const cases = [...new Set(gallery.map((image) => image.source_group).filter(Boolean))].map((caseId) => ({
    key: `case:${caseId}`, label: `${caseId} · teaching set`, caseId, name: caseId,
  }));
  return [...slideItems, ...runItems, ...cases];
}

/** Author, revise, and export a project report. Revisions are new records. */
export function ReportScreen({ role, projectId, userEmail, initialRunId }: { role?: Role; projectId: string; userEmail: string; initialRunId?: string }) {
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [runs, setRuns] = useState<LiveRunSummary[]>([]);
  const [slides, setSlides] = useState<SlideMeta[]>([]);
  const [history, setHistory] = useState<ReportSummary[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [pickedRuns, setPickedRuns] = useState<Set<string>>(new Set(initialRunId ? [initialRunId] : []));
  const [pickedSlides, setPickedSlides] = useState<Set<string>>(new Set());
  const [librarySelection, setLibrarySelection] = useState("");
  const [libraryQuery, setLibraryQuery] = useState("");
  const [revisionOf, setRevisionOf] = useState<string | null>(null);
  const [form, setForm] = useState({ case_id: "", title: "", findings_text: "", findings_html: "" });
  const [sign, setSign] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const [made, setMade] = useState<PublicReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const mayWrite = role !== undefined && REPORT_WRITE_ROLES.includes(role);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [g, r, h, s] = await Promise.all([
        mayWrite ? api.gallery("priority", 1, 50) : Promise.resolve({ items: [] }),
        api.liveRuns(50),
        api.reports(20),
        mayWrite ? api.slides() : Promise.resolve([]),
      ]);
      const items = Array.isArray(g.items) ? g.items : [];
      setGallery(items);
      setRuns(Array.isArray(r) ? r : []);
      setHistory(Array.isArray(h) ? h : []);
      setSlides(Array.isArray(s) ? s : []);
      const library = reportLibraryItems(items, Array.isArray(r) ? r : [], Array.isArray(s) ? s : []);
      const first = library.find((item) => item.key.startsWith("case:")) ?? library[0];
      setLibrarySelection((current) => current || first?.key || "");
      setLibraryQuery((current) => current || first?.label || "");
      setForm((current) => current.case_id || !first ? current : ({
        ...current, case_id: first.caseId, title: `Case review — ${first.name}`,
      }));
    } catch (e) {
      setLoadError(String(e instanceof Error ? e.message : e));
    } finally { setLoading(false); }
  }, [projectId, mayWrite]);

  useEffect(() => { void load(); }, [load]);

  async function openReport(id: string) {
    setBusy(true); setError(null); setVerificationError(null);
    try { setMade(await api.report(id)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  function editAsRevision(report: PublicReport) {
    const library = reportLibraryItems(gallery, runs, slides);
    const selectedItem = library.find((item) => item.caseId === report.case_id);
    setLibrarySelection(selectedItem?.key ?? "");
    setLibraryQuery(selectedItem?.label ?? report.case_id);
    setForm({
      case_id: report.case_id,
      title: report.title,
      findings_text: report.findings_text,
      findings_html: report.findings_html || plainTextAsHtml(report.findings_text),
    });
    setPicked(new Set(report.images.filter((image) => image.source_kind === "corpus").map((image) => image.image_id)));
    setPickedRuns(new Set(report.images.filter((image) => image.source_kind === "live" && image.run_id).map((image) => image.run_id!)));
    setPickedSlides(new Set(report.images.filter((image) => image.source_kind === "slide").map((image) => image.image_id.replace(/^slide:/, ""))));
    setRevisionOf(report.report_id);
    setMade(null);
    setError(null);
  }

  if (made) {
    return <div className="live">
      <ReportResult report={made} mayWrite={mayWrite} verificationError={verificationError}
        onEdit={() => editAsRevision(made)}
        onBack={() => { setMade(null); setVerificationError(null); void load(); }} />
      {error && <p className="err" role="alert">{error}</p>}
      <ReportHistory history={history} busy={busy} onOpen={openReport} />
    </div>;
  }

  if (loading) return <p role="status">Loading reports…</p>;
  if (loadError) return <section className="panel"><p className="err" role="alert">{loadError}</p><button className="btn" onClick={() => void load()}>Retry</button></section>;

  function toggle(set: Set<string>, id: string, apply: (next: Set<string>) => void) {
    const next = new Set(set);
    if (next.has(id)) next.delete(id); else next.add(id);
    apply(next);
  }

  const selected = gallery.filter((g) => picked.has(g.image_id));
  const likelyUnresolved = selected.filter((g) => g.prediction && g.prediction.top_two_margin <= 0.05);
  const analyzedSlideIds = new Set(slides.filter((slide) => runs.some((run) =>
    run.source_name === slide.filename || run.source_name.startsWith(`${slide.slide_id}-`),
  )).map((slide) => slide.slide_id));
  const unanalyzedSlides = slides.filter((slide) => !analyzedSlideIds.has(slide.slide_id));
  const totalPicked = picked.size + pickedRuns.size + pickedSlides.size;
  const library = reportLibraryItems(gallery, runs, slides);

  function chooseLibraryItem(item: ReportLibraryItem) {
    setLibrarySelection(item.key);
    setLibraryQuery(item.label);
    setForm((current) => ({ ...current, case_id: item.caseId, title: `Case review — ${item.name}` }));
    if (item.runId) setPickedRuns((current) => new Set([...current, item.runId!]));
    if (item.slideId) {
      const slide = slides.find((candidate) => candidate.slide_id === item.slideId);
      const matchingRuns = slide ? runs.filter((run) =>
        run.source_name === slide.filename || run.source_name.startsWith(`${slide.slide_id}-`),
      ) : [];
      if (matchingRuns.length) {
        setPickedSlides((current) => { const next = new Set(current); next.delete(item.slideId!); return next; });
        setPickedRuns((current) => new Set([...current, ...matchingRuns.map((run) => run.run_id)]));
      } else setPickedSlides((current) => new Set([...current, item.slideId!]));
    }
  }

  function searchLibrary(value: string) {
    setLibraryQuery(value);
    const match = library.find((item) => item.label === value);
    setLibrarySelection(match?.key ?? "");
    if (match) chooseLibraryItem(match);
    else setForm((current) => ({ ...current, case_id: "" }));
  }

  async function submit() {
    setBusy(true); setError(null); setVerificationError(null);
    try {
      const created = await api.createReport({
        case_id: form.case_id.trim(),
        title: form.title.trim(),
        findings_text: form.findings_text,
        findings_html: form.findings_html,
        image_ids: [...picked],
        run_ids: [...pickedRuns],
        slide_ids: [...pickedSlides],
        revision_of: revisionOf,
        signer_email: sign ? userEmail : null,
        signer_role: sign ? (role ?? null) : null,
        signoff_note: sign ? "Signed in the unified app." : null,
      });
      setMade(created);
      try { setMade(await api.report(created.report_id)); }
      catch (e) {
        setVerificationError(`The report was saved, but its hash check could not be loaded: ${String(e instanceof Error ? e.message : e)}`);
      }
      try { setHistory(await api.reports(20)); }
      catch (e) {
        setVerificationError((message) => [message, `Report history could not be refreshed: ${String(e instanceof Error ? e.message : e)}`].filter(Boolean).join(" "));
      }
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally { setBusy(false); }
  }

  if (!mayWrite) {
    return <div className="live">
      <section className="panel">
        <div className="live-intro">
          <h2>Case reports</h2>
          <p className="muted">Open a saved report to review its observations and results.</p>
        </div>
        <div className="import-blocked" role="status">
          <h3>Writing reports is not available to your role</h3>
          <p>You are signed in as <b>{role ?? "unknown"}</b>. Writing is available to {REPORT_WRITE_ROLES.join(", ")}.</p>
          <p>{REPORT_WRITE_DENIED_REASON[role ?? ""] ?? "Your role is read-only here."}</p>
        </div>
      </section>
      {error && <p className="err" role="alert">{error}</p>}
      <ReportHistory history={history} busy={busy} onOpen={openReport} />
    </div>;
  }

  return <div className="live">
    <section className="panel">
      <div className="live-intro">
        <h2>{revisionOf ? "Revise case report" : "Case report"}</h2>
        <p className="muted">Choose images, record your observations, then save. Revisions create a new saved report.</p>
      </div>

      <div className="report-form">
        {revisionOf && <p className="revision-note" role="status">New revision of <span className="mono">{revisionOf}</span></p>}
        <div className="form-row">
          <label className="grow">Slide or case from library
            <input type="search" list="report-slide-library" value={libraryQuery} aria-label="Search slide library"
              placeholder="Search slide names or teaching cases" onChange={(e) => searchLibrary(e.target.value)} />
            <datalist id="report-slide-library">{library.map((item) => <option key={item.key} value={item.label} />)}</datalist>
          </label>
          <label className="grow">Report name<input value={form.title} aria-label="Report name"
            onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        </div>
        <p className="report-case-id muted small">Case ID · <span className="mono">{form.case_id || "Choose a slide or teaching case"}</span></p>

        <fieldset className="picker report-item-picker">
          <legend>Images in this report ({totalPicked} selected)</legend>
          <div className="report-item-group">
            <h3>AI analyzed · teaching set</h3>
            {gallery.length ? <ul>{gallery.map((g) => <li key={g.image_id}>
              <label className="report-item">
                <input type="checkbox" checked={picked.has(g.image_id)} aria-label={`Include ${g.image_id}`}
                  onChange={() => toggle(picked, g.image_id, setPicked)} />
                <AuthenticatedImage path={api.thumbnailPath(g.image_id)} alt="" className="report-item-thumb" />
                <span className="report-item-detail">
                  <span className="mono small">{g.image_id}</span>
                  <span className={`pill pill-${g.prediction?.predicted_class ?? "none"}`}>{g.prediction?.predicted_class ?? "No result"}</span>
                  <span className="muted small">margin {g.prediction ? g.prediction.top_two_margin.toFixed(3) : "—"}</span>
                  {g.prediction && g.prediction.top_two_margin <= 0.05 && <span className="tiny-flag">No call</span>}
                </span>
              </label>
            </li>)}</ul> : <p className="muted small">No teaching images are available.</p>}
          </div>

          <div className="report-item-group">
            <h3>AI analyzed · uploaded images</h3>
            {runs.length ? <ul>{runs.map((run) => <li key={run.run_id}>
              <label className="report-item">
                <input type="checkbox" checked={pickedRuns.has(run.run_id)} aria-label={`Include run ${run.source_name}`}
                  onChange={() => toggle(pickedRuns, run.run_id, setPickedRuns)} />
                <AuthenticatedImage path={api.liveThumbnailPath(run.run_id)} alt="" className="report-item-thumb" label={`${run.source_name} preview`} />
                <span className="report-item-detail">
                  <span className="small">{run.source_name}</span>
                  <span className="kindtag k-slide">{run.source_kind}</span>
                  <span className="muted small">{run.tile_count} tiles · {new Date(run.created_at).toLocaleString()}</span>
                </span>
              </label>
            </li>)}</ul> : <p className="muted small">No uploaded images have an AI result yet.</p>}
          </div>

          <div className="report-item-group">
            <h3>Not yet analyzed · uploaded slides</h3>
            {unanalyzedSlides.length ? <ul>{unanalyzedSlides.map((slide) => <li key={slide.slide_id}>
              <label className="report-item">
                <input type="checkbox" checked={pickedSlides.has(slide.slide_id)} aria-label={`Include ${slide.filename}`}
                  onChange={() => toggle(pickedSlides, slide.slide_id, setPickedSlides)} />
                <AuthenticatedImage path={api.slideThumbnailPath(slide.slide_id)}
                  alt="" className="report-item-thumb" label={`${slide.filename} preview`} testId={`slide-thumbnail-${slide.slide_id}`} />
                <span className="report-item-detail">
                  <span className="small">{slide.filename}</span>
                  <span className="muted small">{slide.width.toLocaleString()} × {slide.height.toLocaleString()} pixels · no AI result</span>
                </span>
              </label>
            </li>)}</ul> : <p className="muted small">All uploaded slides with a saved run appear above.</p>}
          </div>
        </fieldset>

        <RichTextEditor key={revisionOf ?? "new"} initialHtml={form.findings_html}
          onChange={(findings_html, findings_text) => setForm((current) => ({ ...current, findings_html, findings_text }))} />

        <label className="checkline">
          <input type="checkbox" checked={sign} aria-label="Sign this report" onChange={(e) => setSign(e.target.checked)} />
          <span>Sign this report as <b>{role}</b></span>
        </label>

        {sign && likelyUnresolved.length > 0 && (
          <p className="warn-note" role="status"><b>{likelyUnresolved.length}</b> selected teaching image(s) have closely separated scores. The report will record them as no-call and mark sign-off partial; they are not findings.</p>
        )}

        <div className="report-form-actions">
          <button type="button" className="btn go" disabled={busy || totalPicked === 0 || (!librarySelection && !revisionOf) || !form.case_id.trim() || !form.title.trim()}
            onClick={submit}>
            {busy ? "Saving report…" : revisionOf ? `Save revision · ${totalPicked} item(s)` : `Save report · ${totalPicked} item(s)`}
          </button>
          {revisionOf && <button type="button" className="btn" disabled={busy} onClick={() => {
            const first = library.find((item) => item.key.startsWith("case:")) ?? library[0];
            setRevisionOf(null); setLibrarySelection(first?.key ?? ""); setLibraryQuery(first?.label ?? "");
            setForm(first ? { case_id: first.caseId, title: `Case review — ${first.name}`, findings_text: "", findings_html: "" } : { case_id: "", title: "", findings_text: "", findings_html: "" });
            setPicked(new Set()); setPickedRuns(new Set()); setPickedSlides(new Set());
          }}>
            Discard revision
          </button>}
        </div>
        {error && <p className="err" role="alert">{error}</p>}
      </div>
    </section>
    <ReportHistory history={history} busy={busy} onOpen={openReport} />
  </div>;
}

function RichTextEditor({ initialHtml, onChange }: { initialHtml: string; onChange: (html: string, text: string) => void }) {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const selectionRef = useRef<Range | null>(null);
  const commands = [
    { label: "Bold", command: "bold", icon: "bold" },
    { label: "Italic", command: "italic", icon: "italic" },
    { label: "Underline", command: "underline", icon: "underline" },
    { label: "Bulleted list", command: "insertUnorderedList", icon: "bullets" },
    { label: "Numbered list", command: "insertOrderedList", icon: "numbers" },
    { label: "Heading", command: "formatBlock", value: "h3", icon: "heading" },
    { label: "Undo", command: "undo", icon: "undo" },
    { label: "Redo", command: "redo", icon: "redo" },
  ] as const;
  function update(target: HTMLDivElement) {
    onChange(sanitizeEditorHtml(target.innerHTML), (target.innerText ?? target.textContent ?? "").replace(/\u00a0/g, " ").trim());
  }
  function rememberSelection() {
    const editor = editorRef.current;
    const selection = window.getSelection();
    if (editor && selection?.rangeCount && editor.contains(selection.anchorNode)) {
      selectionRef.current = selection.getRangeAt(0).cloneRange();
    }
  }

  return <div className="report-rich-field">
    <span className="report-field-label">Findings</span>
    <div className="rich-toolbar" role="toolbar" aria-label="Text formatting tools">
      {commands.map((item) => <button key={item.label} type="button" aria-label={item.label} title={item.label}
        onMouseDown={(event) => { rememberSelection(); event.preventDefault(); }}
        onClick={() => {
          const editor = editorRef.current;
          const selection = window.getSelection();
          if (editor && selection && selectionRef.current) {
            editor.focus();
            selection.removeAllRanges();
            selection.addRange(selectionRef.current);
          }
          document.execCommand(item.command, false, "value" in item ? item.value : undefined);
          if (editor) { update(editor); rememberSelection(); }
        }}><ReportToolbarIcon name={item.icon} /></button>)}
    </div>
    <div data-testid="findings-editor" role="textbox" aria-label="Findings" aria-multiline="true"
      contentEditable suppressContentEditableWarning className="report-rich-editor" data-placeholder="Describe what you observed in the images."
      onInput={(event) => update(event.currentTarget)}
      onMouseUp={rememberSelection}
      onKeyUp={rememberSelection}
      ref={(element) => { editorRef.current = element; if (element && element.dataset.ready !== "true") { element.innerHTML = sanitizeEditorHtml(initialHtml); element.dataset.ready = "true"; } }} />
  </div>;
}

function ReportToolbarIcon({ name }: { name: string }) {
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === "bold" && <path d="M7 5h6a3.5 3.5 0 0 1 0 7H7zm0 7h7a3.5 3.5 0 0 1 0 7H7z" />}
    {name === "italic" && <path d="M14 4h6M4 20h6M15 4 9 20" />}
    {name === "underline" && <path d="M7 4v7a5 5 0 0 0 10 0V4M5 20h14" />}
    {name === "bullets" && <><circle cx="5" cy="6" r="1" /><circle cx="5" cy="12" r="1" /><circle cx="5" cy="18" r="1" /><path d="M10 6h9M10 12h9M10 18h9" /></>}
    {name === "numbers" && <><text x="2.5" y="8" fill="currentColor" stroke="none" fontSize="7">1</text><text x="2.5" y="20" fill="currentColor" stroke="none" fontSize="7">2</text><path d="M10 6h9M10 18h9" /></>}
    {name === "heading" && <><path d="M5 5v14M19 5v14M5 12h14" /><text x="8" y="9" fill="currentColor" stroke="none" fontSize="6">H</text></>}
    {name === "undo" && <><path d="M9 14 4 9l5-5" /><path d="M4 9h9a7 7 0 0 1 0 14" transform="translate(0 -3)" /></>}
    {name === "redo" && <><path d="m15 14 5-5-5-5" /><path d="M20 9h-9a7 7 0 0 0 0 14" transform="translate(0 -3)" /></>}
  </svg>;
}

function sanitizeEditorHtml(value: string): string {
  const parsed = new DOMParser().parseFromString(value, "text/html");
  const allowed = new Set(["P", "DIV", "BR", "STRONG", "B", "EM", "I", "U", "H2", "H3", "UL", "OL", "LI", "BLOCKQUOTE"]);
  const blocked = new Set(["SCRIPT", "STYLE", "IFRAME", "OBJECT", "SVG", "MATH"]);
  const escape = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const serialize = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return escape(node.textContent ?? "");
    if (!(node instanceof Element)) return "";
    if (blocked.has(node.tagName)) return "";
    const children = Array.from(node.childNodes, serialize).join("");
    if (!allowed.has(node.tagName)) return children;
    const tag = node.tagName.toLowerCase();
    return tag === "br" ? "<br>" : `<${tag}>${children}</${tag}>`;
  };
  return Array.from(parsed.body.childNodes, serialize).join("");
}

function plainTextAsHtml(value: string): string {
  return value.split(/\r?\n/).map((line) => `<p>${line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") || "<br>"}</p>`).join("");
}

/** Downloads and hash proof for a saved report. */
function ReportResult({ report, mayWrite, verificationError, onEdit, onBack }: {
  report: PublicReport; mayWrite: boolean; verificationError: string | null; onEdit: () => void; onBack: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);
  const v = report.hash_verification;
  const attachedPreviews = report.images.filter((image) => image.preview_attached).length;
  const sourceCount = new Set(report.images.map((image) =>
    image.source_kind === "live" ? `run:${image.run_id}` : `${image.source_kind}:${image.image_id}`,
  )).size;

  async function grab(fmt: "html" | "md") {
    setBusy(fmt); setDlError(null);
    try { await api.downloadExport(report.report_id, fmt); }
    catch (e) { setDlError(String(e instanceof Error ? e.message : e)); }
    finally { setBusy(null); }
  }

  return <section className="panel">
    <div className="slide-head"><div><h3 className="run-title">{report.title}</h3><p className="muted small mono">{report.report_id}</p></div>
      <span className={report.is_signed ? "live-tag signed" : "live-tag draft"}>{report.is_signed ? (report.signoff_covers_all ? "Signed" : "Signed — partial") : "Draft — unsigned"}</span>
    </div>
    {report.revision_of && <p className="revision-note">Revision of <span className="mono">{report.revision_of}</span></p>}
    <div className="tally">
      <span className="tally-chip"><b>{report.n_supported}</b> with a model result</span>
      <span className="tally-chip tally-uncertain"><b>{report.n_unresolved}</b> no-call</span>
      {(report.n_not_analyzed ?? 0) > 0 && <span className="tally-chip"><b>{report.n_not_analyzed}</b> not analyzed</span>}
    </div>
    {report.n_unresolved > 0 && <p className="unresolved-note" role="status">{report.n_unresolved} item(s) produced no determinable class. The export keeps them separate from findings.</p>}
    {v && <div className={`hashbox${v.matches ? " ok" : " bad"}`}>
      <span className="hash-label" data-testid="report-hash-status">Content check · {v.matches ? "verified" : "does not match"}</span>
      <code>{report.content_sha256}</code>
    </div>}
    {verificationError && <p className="inline-error" role="alert">{verificationError}</p>}
    <p className="report-attachment-status muted small" role="status">
      {attachedPreviews} image preview{attachedPreviews === 1 ? "" : "s"} attached for {sourceCount} selected image{sourceCount === 1 ? "" : "s"} and included in the content hash.
      {attachedPreviews < sourceCount ? ` ${sourceCount - attachedPreviews} selected image(s) had no preview available.` : ""}
    </p>
    <div className="actions">
      <button className="btn go" disabled={busy !== null} onClick={() => grab("html")}>{busy === "html" ? "Preparing…" : "Download HTML with images"}</button>
      <button className="btn" disabled={busy !== null} onClick={() => grab("md")}>{busy === "md" ? "Preparing…" : "Download Markdown with images"}</button>
      {mayWrite && <button className="btn" onClick={onEdit}>Edit as new revision</button>}
      <button className="btn def" onClick={onBack}>Back to reports</button>
    </div>
    {dlError && <p className="err" role="alert">{dlError}</p>}
  </section>;
}

function ReportHistory({ history, busy, onOpen }: { history: ReportSummary[]; busy: boolean; onOpen: (id: string) => void }) {
  return <section className="panel">
    <h3>Saved reports</h3>
    {history.length === 0 ? <p className="muted">Reports you save will appear here.</p> : <ul className="runlist">
      {history.map((report) => <li key={report.report_id}>
        <button type="button" className="runitem" disabled={busy} onClick={() => onOpen(report.report_id)}>
          <span className="runname">{report.title}</span>
          <span className="muted small">{report.n_images} item(s)</span>
          <span className="muted small">{report.author_email}</span>
          {report.revision_of && <span className="kindtag">revision</span>}
          <span className={`tiny-flag${report.signer_email ? "" : " unsigned"}`}>{report.signer_email ? "signed" : "draft"}</span>
        </button>
      </li>)}
    </ul>}
  </section>;
}
