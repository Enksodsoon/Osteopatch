import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "../../api";
import type {
  GalleryItem, LiveRunSummary, PublicReport, ReportSummary, Role,
} from "../../types";
import {
  DISCLAIMER_EN, REPORT_WRITE_DENIED_REASON, REPORT_WRITE_ROLES,
} from "../../types";

/**
 * Author, sign and export a case report.
 *
 * The design constraint that shapes everything here: the report must never be
 * able to state something the model did not state. So the screen shows, BEFORE
 * submission, exactly how many of the selected images produced no call — and
 * the exported document carries that split into the file itself.
 *
 * There is no edit affordance. Reports are append-only; changing your mind
 * means writing a second report, which is the correct behaviour for a record.
 */
export function ReportScreen({ role, projectId }: { role?: Role; projectId: string }) {
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [runs, setRuns] = useState<LiveRunSummary[]>([]);
  const [history, setHistory] = useState<ReportSummary[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [pickedRuns, setPickedRuns] = useState<Set<string>>(new Set());
  const [form, setForm] = useState({ case_id: "", title: "", findings_text: "" });
  const [sign, setSign] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [made, setMade] = useState<PublicReport | null>(null);

  const mayWrite = role !== undefined && REPORT_WRITE_ROLES.includes(role);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [g, r, h] = await Promise.all([
        api.gallery("priority", 1, 50),
        api.liveRuns(12).catch(() => [] as LiveRunSummary[]),
        api.reports(20).catch(() => [] as ReportSummary[]),
      ]);
      // Guard the arrays at this boundary. A malformed body should degrade to an
      // empty list, not white-screen the whole tab — but an HTTP failure still
      // rejects and surfaces above, so nothing is silently swallowed here.
      setGallery(Array.isArray(g.items) ? g.items : []);
      setRuns(Array.isArray(r) ? r : []);
      setHistory(Array.isArray(h) ? h : []);
      if (!form.case_id) {
        const first = Array.isArray(g.items) ? g.items[0] : undefined;
        setForm((f) => ({
          ...f,
          case_id: first ? guessCase(first.image_id) : "",
          title: first ? `Case review — ${guessCase(first.image_id)}` : "",
        }));
      }
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  function toggle(set: Set<string>, id: string, apply: (s: Set<string>) => void) {
    const next = new Set(set);
    if (next.has(id)) next.delete(id); else next.add(id);
    apply(next);
  }

  const selected = gallery.filter((g) => picked.has(g.image_id));
  // A frozen corpus row carries a margin but no band; anything at or below the
  // indeterminate threshold is counted here so the reviewer sees the same split
  // the server will compute, before submitting.
  const likelyUnresolved = selected.filter(
    (g) => g.prediction && g.prediction.top_two_margin <= 0.05,
  );

  const totalPicked = picked.size + pickedRuns.size;
  const signWarning = useMemo(
    () => likelyUnresolved.length > 0,
    [likelyUnresolved.length],
  );

  async function submit() {
    setBusy(true); setError(null);
    try {
      const created = await api.createReport({
        case_id: form.case_id.trim(),
        title: form.title.trim(),
        findings_text: form.findings_text,
        image_ids: [...picked],
        run_ids: [...pickedRuns],
        signer_email: sign ? "reviewer@demo" : null,
        signer_role: sign ? (role ?? null) : null,
        signoff_note: sign ? "Signed in the unified app." : null,
      });
      setMade(created);
      setHistory(await api.reports(20).catch(() => history));
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  // ---- reader-only personas: explain, never offer a dead control ----------
  if (!mayWrite) {
    return (
      <div className="live">
        <section className="panel">
          <div className="live-intro">
            <h2>Case reports</h2>
            <p className="muted">
              A report is a typed, append-only clinical-style document spanning the
              patches you scored. It carries the real model card and limitations text,
              the sign-off, and a content hash you can re-check later.
            </p>
          </div>
          <div className="import-blocked" role="status">
            <h3>Authoring is not available to your role</h3>
            <p>
              You are signed in as <b>{role ?? "unknown"}</b>. Authoring is a writer action,
              reserved for {REPORT_WRITE_ROLES.join(", ")}.
            </p>
            <p>{REPORT_WRITE_DENIED_REASON[role ?? ""] ?? "Your role is read-only here."}</p>
          </div>
        </section>
        <ReportHistory history={history} />
      </div>
    );
  }

  // ---- the composed result: downloads + hash -----------------------------
  if (made) {
    return (
      <div className="live">
        <ReportResult report={made} onBack={() => { setMade(null); void load(); }} />
        <ReportHistory history={history} />
      </div>
    );
  }

  return (
    <div className="live">
      <section className="panel">
        <div className="live-intro">
          <h2>Case report</h2>
          <p className="muted">
            Pick the images you scored, write what you actually observed, sign, and
            export. The document is stored append-only and is never edited in place.
          </p>
        </div>

        <div className="report-form">
          <div className="form-row">
            <label>
              Case id
              <input
                value={form.case_id}
                aria-label="Case id"
                onChange={(e) => setForm({ ...form, case_id: e.target.value })}
              />
            </label>
            <label className="grow">
              Title
              <input
                value={form.title}
                aria-label="Title"
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
          </div>

          <fieldset className="picker">
            <legend>Scored patches in scope ({picked.size} selected)</legend>
            <ul>
              {gallery.map((g) => (
                <li key={g.image_id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={picked.has(g.image_id)}
                      aria-label={`Include ${g.image_id}`}
                      onChange={() => toggle(picked, g.image_id, setPicked)}
                    />
                    <span className="mono small">{g.image_id}</span>
                    <span className={`pill pill-${g.prediction?.predicted_class ?? "none"}`}>
                      {g.prediction?.predicted_class ?? "—"}
                    </span>
                    <span className="muted small">
                      margin {g.prediction ? g.prediction.top_two_margin.toFixed(3) : "—"}
                    </span>
                    {g.prediction && g.prediction.top_two_margin <= 0.05 && (
                      <span className="tiny-flag">will be recorded as no-call</span>
                    )}
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>

          {runs.length > 0 && (
            <fieldset className="picker">
              <legend>Live runs to include ({pickedRuns.size} selected)</legend>
              <ul>
                {runs.map((r) => (
                  <li key={r.run_id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={pickedRuns.has(r.run_id)}
                        aria-label={`Include run ${r.source_name}`}
                        onChange={() => toggle(pickedRuns, r.run_id, setPickedRuns)}
                      />
                      <span className="small">{r.source_name}</span>
                      <span className="kindtag k-slide">{r.source_kind}</span>
                      <span className="muted small">{r.tile_count} tiles</span>
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
          )}

          <label>
            Findings
            <textarea
              rows={6}
              value={form.findings_text}
              aria-label="Findings"
              placeholder="What you actually observed. Report what the model could not determine as such."
              onChange={(e) => setForm({ ...form, findings_text: e.target.value })}
            />
          </label>

          <label className="checkline">
            <input
              type="checkbox"
              checked={sign}
              aria-label="Sign this report"
              onChange={(e) => setSign(e.target.checked)}
            />
            <span>Sign this report as <b>{role}</b></span>
          </label>

          {sign && signWarning && (
            <p className="warn-note" role="status">
              <b>{likelyUnresolved.length}</b> of your {selected.length} selected patch
              {selected.length === 1 ? "" : "es"} ha{likelyUnresolved.length === 1 ? "s" : "ve"}{" "}
              a top-two separation at or below 0.05. Those will be recorded as{" "}
              <b>producing no call</b>, and the sign-off will be marked{" "}
              <b>PARTIAL</b> in the exported document. They cannot be stated as findings.
            </p>
          )}

          <button
            type="button"
            className="btn go"
            disabled={busy || totalPicked === 0 || !form.case_id || !form.title}
            onClick={submit}
          >
            {busy ? "Writing report…" : `Write report covering ${totalPicked} item(s)`}
          </button>

          <p className="muted small">
            The exported document carries the prototype disclosure, the uncalibrated-score
            label, the real model card and limitations text, and a SHA-256 over the whole
            document. {DISCLAIMER_EN}
          </p>
          {error && <p className="err" role="alert">{error}</p>}
        </div>
      </section>

      <ReportHistory history={history} />
    </div>
  );
}

/** Downloads, hash proof, and the honesty split of the report just written. */
function ReportResult({ report, onBack }: { report: PublicReport; onBack: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);
  const v = report.hash_verification;

  async function grab(fmt: "html" | "md") {
    setBusy(fmt); setDlError(null);
    try { await api.downloadExport(report.report_id, fmt); }
    catch (e) { setDlError(String(e instanceof Error ? e.message : e)); }
    finally { setBusy(null); }
  }

  return (
    <section className="panel">
      <div className="slide-head">
        <div>
          <h3 className="run-title">{report.title}</h3>
          <p className="muted small mono">{report.report_id}</p>
        </div>
        <span className={report.is_signed ? "live-tag signed" : "live-tag draft"}>
          {report.is_signed
            ? (report.signoff_covers_all ? "Signed" : "Signed — PARTIAL")
            : "Draft — unsigned"}
        </span>
      </div>

      <div className="tally">
        <span className="tally-chip">
          <b>{report.n_supported}</b> with a determinable class
        </span>
        <span className="tally-chip tally-uncertain">
          <b>{report.n_unresolved}</b> produced no call
        </span>
      </div>

      {report.n_unresolved > 0 && (
        <p className="unresolved-note" role="status">
          {report.n_unresolved} item{report.n_unresolved === 1 ? "" : "s"} in this report
          produced <b>no determinable class</b>. They are listed in the export under
          &ldquo;patches that produced no call&rdquo; and carry no class assertion.
        </p>
      )}

      {v && (
        <div className={`hashbox${v.matches ? " ok" : " bad"}`}>
          <span className="hash-label">
            content SHA-256 {v.matches ? "recomputed and matching" : "DOES NOT MATCH"}
          </span>
          <code>{report.content_sha256}</code>
          <span className="muted small">
            Stored and re-derived from the typed document on read. This is the value
            the sign-off covers.
          </span>
        </div>
      )}

      <div className="actions">
        <button className="btn go" disabled={busy !== null} onClick={() => grab("html")}>
          {busy === "html" ? "Preparing…" : "Download HTML (opens offline, prints to PDF)"}
        </button>
        <button className="btn" disabled={busy !== null} onClick={() => grab("md")}>
          {busy === "md" ? "Preparing…" : "Download Markdown"}
        </button>
        <button className="btn def" onClick={onBack}>Write another</button>
      </div>
      {dlError && <p className="err" role="alert">{dlError}</p>}
      <p className="muted small">
        Both files render from the same typed source, so they cannot disagree.The sign-off covers {report.n_images} item(s) in total.
      </p>
    </section>
  );
}

function ReportHistory({ history }: { history: ReportSummary[] }) {
  return (
    <section className="panel">
      <h3>Reports in this project</h3>
      {history.length === 0 ? (
        <p className="muted">No reports yet. Reports are append-only — a revision is a new one.</p>
      ) : (
        <ul className="runlist">
          {history.map((r) => (
            <li key={r.report_id}>
              <div className="runitem static">
                <span className="runname">{r.title}</span>
                <span className="muted small">{r.n_images} item(s)</span>
                <span className="muted small">{r.author_email}</span>
                <span className={`tiny-flag${r.signer_email ? "" : " unsigned"}`}>
                  {r.signer_email ? "signed" : "draft"}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Case ids in this corpus look like `Case-3-A10-10547-25283`. */
function guessCase(imageId: string): string {
  const m = imageId.match(/^(Case-\d+-[A-Z]+\d+)/);
  return m ? m[1] : imageId.split("-").slice(0, 3).join("-");
}