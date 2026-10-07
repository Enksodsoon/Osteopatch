import { useEffect, useRef, useState } from "react";
import * as api from "../api";
import type { LiveCapability, LivePatchResult, LiveSlideResult, LiveRunDetail, Role } from "../types";
import { CLASS_LABELS, CLASS_NAMES, CLASSES, LIVE_ANALYZE_ROLES } from "../types";
import { AuthenticatedImage } from "./AuthenticatedImage";
import { DeepZoomViewer } from "./DeepZoomViewer";
import type { DeepZoomViewerHandle } from "./DeepZoomViewer";
import { Icon } from "./Icon";
import { ModelEvidenceSummary } from "./ModelCard";
import { VerdictCard } from "./live/VerdictCard";
import { ProvenanceStrip } from "./live/ProvenanceStrip";
import { TileGrid, TileInspector } from "./live/TileGrid";
import { LiveScreen } from "./live/LiveScreen";

type Annotation = api.SlideRegion & { id: string; label: string; note: string };
const labels = ["Observation", "NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"];

export function SlideWorkspace({ role, projectId, onReport }: {
  role?: Role; projectId: string; onReport: (runId: string) => void;
}) {
  const [items, setItems] = useState<api.SlideMeta[]>([]);
  const [slide, setSlide] = useState<api.SlideMeta | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [capability, setCapability] = useState<LiveCapability | null>(null);
  const [view, setView] = useState<api.SlideRegion>({ x: 0, y: 0, width: 1, height: 1 });
  const [mode, setMode] = useState<"pan" | "annotate">("pan");
  const [label, setLabel] = useState("Observation");
  const [note, setNote] = useState("");
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<LivePatchResult | LiveSlideResult | null>(null);
  const [detail, setDetail] = useState<LiveRunDetail | null>(null);
  const [analyzedRegion, setAnalyzedRegion] = useState<api.SlideRegion | null>(null);
  const [showAnalysisMap, setShowAnalysisMap] = useState(true);
  const viewer = useRef<DeepZoomViewerHandle>(null);
  const analysisRequest = useRef(0);
  const mayAnalyze = role !== undefined && LIVE_ANALYZE_ROLES.includes(role);
  const region = annotations.find(a => a.id === selected) ?? view;
  const zoom = slide ? Math.max(slide.width / Math.max(1, view.width), slide.height / Math.max(1, view.height)) : 1;

  function open(next: api.SlideMeta) {
    analysisRequest.current += 1;
    setBusy(false);
    setSlide(next); setView({ x: 0, y: 0, width: next.width, height: next.height });
    setSelected(null); setResult(null); setDetail(null); setAnalyzedRegion(null);
    setShowAnalysisMap(true); setError(null); setMode("pan");
    try {
      const saved: Annotation[] = JSON.parse(sessionStorage.getItem(`slide-notes:${projectId}:${next.slide_id}`) ?? "[]");
      setAnnotations(Array.isArray(saved) ? saved.filter(a => labels.includes(a.label) && [a.x, a.y, a.width, a.height].every(Number.isFinite) && a.width > 0 && a.height > 0) : []);
    } catch { setAnnotations([]); }
  }

  async function refresh() {
    setLoading(true); setError(null);
    try { const list = await api.slides(); setItems(list); if (!slide && list[0]) open(list[0]); }
    catch { setError("Could not load images. Check the local demo connection and try again."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); api.liveCapability().then(setCapability).catch(e => setError(String(e))); }, [projectId]);
  useEffect(() => {
    if (!slide) return;
    try { sessionStorage.setItem(`slide-notes:${projectId}:${slide.slide_id}`, JSON.stringify(annotations)); }
    catch { setError("Browser session storage is unavailable. Download annotations JSON to keep your work."); }
  }, [annotations, slide, projectId]);

  async function upload(file: File | undefined) {
    if (!file) return;
    if (!/\.(svs|ndpi|tiff?|png|jpe?g)$/i.test(file.name) || !file.size || file.size > 512 * 1024 * 1024) {
      setError("Choose a non-empty SVS, NDPI, TIFF, PNG or JPEG up to 512 MB."); return;
    }
    setBusy(true); setError(null);
    try { const next = await api.uploadSlide(file); setItems(current => [next, ...current]); open(next); }
    catch (e) { setError(uploadError(e)); }
    finally { setBusy(false); }
  }

  function addAnnotation(box: api.SlideRegion) {
    const id = crypto.randomUUID();
    setAnnotations(current => [...current, { ...box, id, label, note }]); setSelected(id);
  }
  async function analyze(whole: boolean) {
    if (!slide) return;
    const request = ++analysisRequest.current;
    setBusy(true); setError(null); setResult(null); setDetail(null);
    setAnalyzedRegion(whole ? null : region); setShowAnalysisMap(true);
    try {
      const next = await api.analyzeSlide(slide.slide_id, whole ? null : region);
      if (request !== analysisRequest.current) return;
      setResult(next);
      if (!("prediction" in next)) {
        const full = await api.liveRun(next.run.run_id);
        if (request === analysisRequest.current) setDetail(full);
      }
    } catch (e) { if (request === analysisRequest.current) setError(String(e)); }
    finally { if (request === analysisRequest.current) setBusy(false); }
  }
  async function download(action: () => Promise<void>) {
    setError(null); try { await action(); } catch (e) { setError(String(e)); }
  }

  return <div className={`slide-workspace${slide ? " has-slide" : ""}`}>
    <section className="panel slide-library-panel">
      <h2>Slide library</h2>
      <div className="slide-actions">
        {mayAnalyze ? <label className="btn-primary slide-upload">Add slide or image
          <input aria-label="Upload WSI or image" type="file" accept=".svs,.ndpi,.tif,.tiff,.png,.jpg,.jpeg" disabled={busy}
            onChange={e => { void upload(e.target.files?.[0]); e.target.value = ""; }} />
        </label> : <p className="muted">Shared slides are read-only for your role.</p>}
        <button aria-label="Refresh slide library" onClick={() => void refresh()} disabled={busy || loading}>Refresh</button>
        {busy && <span role="status">Working…</span>}
      </div>
      <p className="muted small">De-identified educational images only.</p>
      {items.length > 0 && <section className="slide-library" aria-label="Uploaded images">
        <h3>Available slides</h3>
        <div className="slide-list">
          {items.map(item => <button key={item.slide_id} type="button"
            className={`slide-card${slide?.slide_id === item.slide_id ? " active" : ""}`}
            aria-label={`Open ${item.filename}`} aria-pressed={slide?.slide_id === item.slide_id}
            disabled={busy} onClick={() => open(item)}>
            <AuthenticatedImage path={api.slideThumbnailPath(item.slide_id)}
              alt={`${item.filename} thumbnail`} testId={`slide-thumbnail-${item.slide_id}`} />
            <span className="slide-card-name" title={item.filename}>{item.filename}</span>
            <span className="muted small">{item.width.toLocaleString()} × {item.height.toLocaleString()}</span>
            <span className="muted small">Added <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}</time></span>
          </button>)}
        </div>
      </section>}
      {loading && <p role="status">Loading slides…</p>}
      {!loading && !items.length && <p className="muted">Add a slide to begin.</p>}
      {error && <p role="alert" className="inline-error">{error}</p>}
    </section>
    {slide && <>
      <section className="panel slide-viewer-panel">
        <div className="slide-viewer-heading">
          <h2>Slide viewer</h2>
          <span className="muted small">{slide.level_count > 1 ? `${slide.level_count} scan levels` : "Single-resolution image"}</span>
        </div>
        <details className="slide-details">
          <summary>Slide details</summary>
          <p className="muted small">{slide.filename} · {slide.width.toLocaleString()} × {slide.height.toLocaleString()} pixels · {slide.level_count} resolution levels · {slide.engine}
            {slide.mpp_x ? ` · ${slide.mpp_x} µm/pixel` : " · physical scale not supplied"}</p>
        </details>
        <div className="slide-actions viewer-toolbar" role="toolbar" aria-label="Slide viewer controls">
          <button aria-label="Zoom in slide" title="Zoom in" onClick={() => viewer.current?.zoom(1.5)}><Icon name="zoom-in" /></button>
          <button aria-label="Zoom out slide" title="Zoom out" onClick={() => viewer.current?.zoom(0.67)}><Icon name="zoom-out" /></button>
          <button aria-label="Fit slide" title="Fit slide" onClick={() => { viewer.current?.fit(); setSelected(null); }}><Icon name="fit" /></button>
          <button aria-label="Pan" title="Pan" aria-pressed={mode === "pan"} onClick={() => setMode("pan")}><Icon name="pan" /></button>
          <button aria-label="Draw annotation" title="Draw annotation" aria-pressed={mode === "annotate"} onClick={() => setMode("annotate")}><Icon name="annotate" /></button>
          {result && <button aria-label={`${showAnalysisMap ? "Hide" : "Show"} analysis overlay`} title={`${showAnalysisMap ? "Hide" : "Show"} analysis overlay`}
            aria-pressed={showAnalysisMap} onClick={() => setShowAnalysisMap(value => !value)}><Icon name={showAnalysisMap ? "eye" : "eye-off"} /></button>}
          <button aria-label="Full screen viewer" title="Full screen" onClick={() => viewer.current?.fullscreen()}><Icon name="fullscreen" /></button>
          <span className="mono small" aria-live="polite" data-testid="slide-zoom"
            data-zoom-value={zoom.toFixed(4)}>{zoom.toFixed(1)}×</span>
        </div>
        <DeepZoomViewer key={slide.slide_id} ref={viewer} slide={slide} mode={mode}
          annotations={annotations} selected={selected} analysisTiles={detail?.tiles ?? []}
          analysisRegion={analyzedRegion} prediction={result && "prediction" in result ? result.prediction : null}
          showAnalysisMap={showAnalysisMap} onViewChange={setView} onAddAnnotation={addAnnotation} />
        {slide.level_count <= 1 && <p className="viewer-source-note" role="note">This file has one image resolution. Zooming can enlarge it, but cannot reveal additional scan detail.</p>}
        {result && showAnalysisMap && <div className="analysis-map-legend" role="status">
          <span>{detail ? `${detail.tiles.length} analyzed regions` : "Analyzed view"}</span>
          {CLASSES.map(cls => <span key={cls}><i className={`class-swatch cl-${cls}`} />{CLASS_LABELS[cls]}</span>)}
          <span className="map-note">Class map · not an attention heatmap</span>
        </div>}
        <p className="muted small">Scroll or pinch to zoom · drag to pan · use the navigator to move across the slide.</p>
        <div className="slide-actions">
          <button onClick={() => void download(() => api.downloadSlide(slide.slide_id, slide.filename))}>Download original</button>
          <button onClick={() => void download(() => api.downloadRegion(slide.slide_id, region))}>Download region PNG</button>
          <button onClick={() => api.downloadJson({ educational_only: true, source: slide, annotations }, `${slide.slide_id}-annotations.json`)}>Download annotations JSON</button>
        </div>
      </section>
      <section className="panel slide-annotations-panel">
        <h3>Annotations</h3>
        <div className="slide-fields">
          <label>Annotation label<select value={label} onChange={e => setLabel(e.target.value)}>{labels.map(l => <option key={l}>{l}</option>)}</select></label>
          <label>Annotation note<input value={note} onChange={e => setNote(e.target.value)} placeholder="Describe what you observed" /></label>
          <button onClick={() => addAnnotation(view)}>Annotate current view</button>
        </div>
        {!annotations.length && <p className="muted small">Practice notes stay in this browser session.</p>}
        <ul className="annotation-list">{annotations.map(a => <li key={a.id}>
          <button aria-pressed={selected === a.id} onClick={() => { setSelected(a.id); viewer.current?.focus(a); }}>{a.label} · {a.width} × {a.height} · {a.note || "No note"}</button>
          <button aria-label={`Remove annotation ${a.label}`} onClick={() => { setAnnotations(current => current.filter(item => item.id !== a.id)); if (selected === a.id) setSelected(null); }}>Remove</button>
        </li>)}</ul>
      </section>
      <section className="panel slide-analysis-panel">
        <h3>Model analysis</h3>
        <div className="slide-actions">
          <button className="btn-primary" disabled={busy || !mayAnalyze || !capability?.available} onClick={() => void analyze(false)}>Analyze this view</button>
          <button disabled={busy || !mayAnalyze || !capability?.available} title="Checks up to 16 regions" onClick={() => void analyze(true)}>Scan slide</button>
          {busy && <span role="status">Analyzing…</span>}
        </div>
        {!capability?.available && <p className="muted" role="status">{capability?.reason ?? "Checking model availability…"} Viewing, annotations and downloads still work.</p>}
        <p className="muted small">Educational research demo · class scores are not probabilities.</p>
        <ClassAtlas />
        {result && <div data-testid="slide-analysis-result">
          {"prediction" in result ? <VerdictCard run={result.run} prediction={result.prediction} sourceLabel="Selected slide view" /> : <p>{result.run.tile_count} of {result.run.tiles_available} regions analyzed{result.run.truncated ? " · scan limit reached" : ""}.</p>}
          {detail && <><TileGrid tiles={detail.tiles} mosaic={(result as LiveSlideResult).mosaic} onInspect={tile => setSelected(`tile-${tile.tile_index}`)} />
            <TileInspector tile={detail.tiles.find(tile => selected === `tile-${tile.tile_index}`) ?? null} /></>}
          <ModelEvidenceSummary runModelId={result.run.model_id} />
          <details className="slide-run-details">
            <summary>Run provenance</summary>
            <ProvenanceStrip run={result.run} />
          </details>
          <div className="slide-actions">
            <button onClick={() => api.downloadJson(result, `${result.run.run_id}-analysis.json`)}>Download analysis JSON</button>
            <button className="btn-primary" onClick={() => onReport(result.run.run_id)}>Create case report</button>
          </div>
        </div>}
      </section>
    </>}
    <details className="panel recorded-results">
      <summary>Saved analyses</summary>
      <LiveScreen key={projectId} role={role} projectId={projectId} recordedOnly />
    </details>
  </div>;
}

function ClassAtlas() {
  return <figure className="class-atlas" data-testid="class-atlas">
    <div className="class-atlas-grid">
      {CLASSES.map((cls, index) => <div key={cls} className={`class-atlas-image cl-${cls}`} style={{ backgroundPosition: `${index * 50}% center` }} role="img" aria-label={`Synthetic educational illustration: ${CLASS_NAMES[cls]}`} />)}
    </div>
    <figcaption>{CLASSES.map(cls => <span key={cls}>{CLASS_NAMES[cls]}</span>)}</figcaption>
    <p>Synthetic teaching illustration · not slide evidence</p>
  </figure>;
}

function uploadError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.startsWith("401")) return "Your session ended. Sign in again to upload an image.";
  if (message.startsWith("403")) return "Your account cannot upload images to this project.";
  if (message.startsWith("413")) return "This file is over the 512 MB demo limit. Choose a smaller image.";
  if (message.startsWith("415")) return "Choose an SVS, NDPI, TIFF, PNG, or JPEG image.";
  if (message.startsWith("422")) return "This image could not be opened. Check that the file is complete and try again.";
  return "The image could not be opened. Check the local demo connection and try again.";
}
