import { useCallback, useEffect, useState } from "react";
import * as api from "../../api";
import type {
  LiveCapability, LivePatchResult, LiveRunDetail, LiveRunSummary,
  LiveSlideResult, LiveTile, Role,
} from "../../types";
import { DISCLAIMER_EN, SUPPORT_FLAG_LABELS } from "../../types";
import { ImportPanel } from "./ImportPanel";
import { VerdictCard } from "./VerdictCard";
import { TileGrid, TileInspector, UncertainRank } from "./TileGrid";
import { ProvenanceStrip } from "./ProvenanceStrip";

type Outcome =
  | { kind: "patch"; data: LivePatchResult }
  | { kind: "slide"; data: LiveSlideResult };

/**
 * The live inference tab.
 *
 * Owns four things and delegates the display: the capability probe (so the UI
 * can explain before anything is clicked), the import, the result, and the run
 * history. Reads are separated from writes throughout — history is loaded for
 * every role, because `live:read` is open to all six while `live:analyze` is
 * not.
 */
export function LiveScreen({ role, projectId, recordedOnly = false }: { role?: Role; projectId: string; recordedOnly?: boolean }) {
  const [capability, setCapability] = useState<LiveCapability | null>(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [runs, setRuns] = useState<LiveRunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [detail, setDetail] = useState<LiveRunDetail | null>(null);
  const [tile, setTile] = useState<LiveTile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [capabilityError, setCapabilityError] = useState<string | null>(null);
  const [openingRecord, setOpeningRecord] = useState(false);
  /** What the in-flight request is actually for — drives the sweep copy. */
  const [pendingKind, setPendingKind] = useState<"patch" | "slide" | null>(null);

  const loadRuns = useCallback(async () => {
    setRunsLoading(true);
    setRunsError(null);
    try { setRuns(await api.liveRuns(12)); }
    catch (e) {
      setRuns([]);
      setRunsError(String(e instanceof Error ? e.message : e));
    } finally { setRunsLoading(false); }
  }, []);

  useEffect(() => {
    let live = true;
    // `live:read` — every role may ask. It is torch-free, so it is cheap on load.
    if (!recordedOnly) api.liveCapability()
      .then((c) => { if (live) setCapability(c); })
      .catch((e: unknown) => {
        if (live) setCapabilityError(String(e instanceof Error ? e.message : e));
      });
    if (live) loadRuns();
    return () => { live = false; };
  }, [projectId, loadRuns, recordedOnly]);

  async function onImport(file: File, kind: "patch" | "slide") {
    setBusy(true); setPendingKind(kind);
    setError(null); setOutcome(null); setTile(null); setDetail(null);
    try {
      if (kind === "patch") {
        setOutcome({ kind, data: await api.importPatch(file) });
      } else {
        setOutcome({ kind, data: await api.importSlide(file) });
      }
      await loadRuns();
    } catch (e) {
      setError(describeUploadError(e, file));
    } finally {
      setBusy(false); setPendingKind(null);
    }
  }

  async function openRun(runId: string) {
    setBusy(true); setOpeningRecord(true); setError(null); setDetail(null); setOutcome(null); setTile(null);
    try {
      const d = await api.liveRun(runId);
      setDetail(d); setOutcome(null); setTile(null);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally { setBusy(false); setOpeningRecord(false); }
  }

  const run = outcome?.data.run ?? detail?.run ?? null;

  return (
    <div className={`live${recordedOnly ? " live-recorded" : ""}`}>
      {!recordedOnly && <>
      <section className="panel">
        <div className="live-intro">
          <h2>Live inference</h2>
          <p className="muted">
            Import your own patch or slide and run it through the recovered research head
            <b> right now</b>. Nothing here touches the frozen 1,144-image corpus.
          </p>
          {capability?.model_id && (
            <p className="mono subtle">{capability.model_id}</p>
          )}
          {capabilityError && (
            <p className="inline-error" role="alert">
              Inference capability could not be checked: {capabilityError}{" "}
              <button type="button" className="btn-link" onClick={() => {
                setCapabilityError(null);
                api.liveCapability().then(setCapability).catch((e: unknown) => setCapabilityError(String(e instanceof Error ? e.message : e)));
              }}>Retry</button>
            </p>
          )}
        </div>
        <ImportPanel
          role={role}
          capability={capability}
          busy={busy}
          onImport={onImport}
        />
      </section>

      {error && <p className="err panel" role="alert">{error}</p>}

      {busy && openingRecord && <p className="panel muted" role="status">Opening the recorded result. No inference is run.</p>}
      {busy && !openingRecord && !outcome && !detail && <ScanSweep sourceKind={pendingKind ?? "slide"} />}

      {outcome?.kind === "patch" && (
        <section className="panel">
          <VerdictCard run={outcome.data.run} prediction={outcome.data.prediction} />
          <ProvenanceStrip run={outcome.data.run} />
          {run?.notes && <p className="muted small">{run.notes}</p>}
        </section>
      )}

      {outcome?.kind === "slide" && (
        <section className="panel">
          <SlideResultView
            data={outcome.data}
            tile={tile}
            onInspect={setTile}
          />
        </section>
      )}
      </>}

      {recordedOnly && openingRecord && <p className="muted" role="status">Opening saved result…</p>}
      {recordedOnly && error && <p className="inline-error" role="alert">Saved result could not be opened: {error}</p>}
      {detail && (
        <section className="panel" data-testid="recorded-run-detail">
          <h3 className="run-title">
            {recordedOnly ? "Saved result" : "Recorded demo result"} <span className="mono subtle">{detail.run.run_id}</span>
          </h3>
          <p className="muted small">Recorded {formatRecordedAt(detail.run.created_at)} · model {detail.run.model_id}. Reopening stored scores does not run the model again.</p>
          <ProvenanceStrip run={detail.run} />
          {detail.n_tiles > 0 ? (
            <TileGrid
              tiles={detail.tiles}
              mosaic={{ cols: guessCols(detail.tiles), rows: guessRows(detail.tiles),
                        cell_px: 18, path_relative: "", class_colours: {},
                        undecoded_colour: [150, 150, 150] }}
              onInspect={setTile}
            />
          ) : (
            <p className="muted">This run holds no tiles.</p>
          )}
          <TileInspector tile={tile} />
          <UncertainRank tiles={detail.tiles} />
        </section>
      )}

      <section className="panel">
        <h3>{recordedOnly ? "Saved results" : "Recorded demo runs"}</h3>
        <p className="muted small">Opening a saved result shows what was recorded; it does not run the model again.</p>
        {runsLoading ? (
          <p className="muted" role="status">Loading recorded runs…</p>
        ) : runsError ? (
          <p className="inline-error" role="alert">
            Recorded runs could not be loaded: {runsError}{" "}
            <button type="button" className="btn-link" onClick={() => void loadRuns()}>Retry</button>
          </p>
        ) : runs.length === 0 ? (
          <p className="muted">No recorded runs are available for this project.</p>
        ) : (
          <ul className="runlist">
            {runs.map((r) => (
              <li key={r.run_id}>
                <button
                  type="button"
                  disabled={busy}
                  className={`runitem${detail?.run.run_id === r.run_id ? " on" : ""}`}
                  onClick={() => openRun(r.run_id)}
                >
                  <span className={`kindtag k-${r.source_kind}`}>recorded {r.source_kind}</span>
                  <span className="runname">{r.source_name}</span>
                  <span className="muted small">
                    {r.tile_count} tile{r.tile_count === 1 ? "" : "s"}
                    {r.truncated ? " · truncated" : ""}
                  </span>
                  <span className="muted small">{formatRecordedAt(r.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {!recordedOnly && <p className="muted small">
          {DISCLAIMER_EN} A live run is an experiment on a research head, not a reading of a
          patient.
        </p>}
      </section>
    </div>
  );
}

function SlideResultView({
  data, tile, onInspect,
}: {
  data: LiveSlideResult;
  tile: LiveTile | null;
  onInspect: (t: LiveTile) => void;
}) {
  const [full, setFull] = useState<LiveRunDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    api.liveRun(data.run.run_id)
      .then((d) => { if (live) setFull(d); })
      .catch(() => { /* the summary below still tells the story */ })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [data.run.run_id]);

  const flags = data.run.support_flags ?? [];

  return (
    <>
      <div className="slide-head">
        <div>
          <h3 className="run-title">{data.run.source_name}</h3>
          <p className="live-tag">live inference · not a corpus prediction</p>
        </div>
        <p className="muted small">
          {data.run.tile_count} of {data.run.tiles_available} tiles scored
          {data.run.truncated && (
            <> · <b>truncated</b>: the grid exceeded the tile cap and the remaining
              tiles were not scored</>
          )}
        </p>
      </div>

      {flags.length > 0 && (
        <div className="caveats" role="note">
          {flags.map((f) => (
            <p className="flag-line" key={f}>
              <span className="flag-tag">input caveat</span>
              {SUPPORT_FLAG_LABELS[f] ?? f}
            </p>
          ))}
        </div>
      )}

      {loading && !full ? (
        <p className="muted">Loading tiles…</p>
      ) : full ? (
        <TileGrid tiles={full.tiles} mosaic={data.mosaic} onInspect={onInspect} />
      ) : (
        <p className="muted">Tiles could not be re-read; the summary above is what the server returned.</p>
      )}
      <TileInspector tile={tile} />
      <ProvenanceStrip run={data.run} />
      {data.run.notes && <p className="muted small">{data.run.notes}</p>}
      {full && <UncertainRank tiles={full.tiles} />}
    </>
  );
}

/**
 * The scan sweep. Shown only while a request is genuinely in flight.
 *
 * This is the one piece of pure theatre in the app, and it is deliberately
 * labelled as progress rather than dressed up as a measurement: it reports that
 * the server is working, not how far along it is, because the API has no
 * progress to report and a fake percentage would be a lie.
 */
function ScanSweep({ sourceKind }: { sourceKind: "patch" | "slide" }) {
  const cells = sourceKind === "slide" ? 96 : 16;
  return (
    <section className="panel scanning" role="status" aria-live="polite">
      <div className="scan-grid" aria-hidden="true">
        {Array.from({ length: cells }, (_, i) => (
          <span key={i} style={{ animationDelay: `${i * 26}ms` }} />
        ))}
      </div>
      <p>
        {sourceKind === "slide"
          ? "Reading the slide and running a forward pass per tile…"
          : "Running a forward pass through the recovered head…"}
      </p>
      <p className="muted small">No progress percentage is shown because the server reports none.</p>
    </section>
  );
}

function describeUploadError(e: unknown, file: File): string {
  const raw = e instanceof Error ? e.message : String(e);
  if (raw.startsWith("415")) {
    return `${file.name} was refused (415). This API accepts ${file.name.slice(file.name.lastIndexOf(".")) ? "the formats it lists under /v1/live/capability" : "a supported image format"} — not PDF.`;
  }
  if (raw.startsWith("422")) {
    return `${file.name} could not be decoded as an image (422). Nothing was scored.`;
  }
  if (raw.startsWith("403")) {
    return "Your role is not permitted to import (403).";
  }
  return raw;
}

function formatRecordedAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

const guessCols = (tiles: LiveTile[]) => {
  const xs = [...new Set(tiles.map((t) => t.x))].sort((a, b) => a - b);
  return Math.max(xs.length, 1);
};
const guessRows = (tiles: LiveTile[]) => {
  const ys = [...new Set(tiles.map((t) => t.y))].sort((a, b) => a - b);
  return Math.max(ys.length, 1);
};
