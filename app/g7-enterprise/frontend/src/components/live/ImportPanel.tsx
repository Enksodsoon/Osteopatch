import { useRef, useState } from "react";
import type { LiveCapability, Role } from "../../types";
import {
  LIVE_ANALYZE_DENIED_REASON, LIVE_ANALYZE_ROLES,
} from "../../types";

/**
 * Drop a patch or a slide and send it for a live forward pass.
 *
 * Two honest constraints are designed into this component rather than hidden:
 *
 * 1. The upload is a RAW BODY with an `X-File-Name` header. The server has no
 *    `python-multipart` and does not need one. A `FormData` body here would
 *    4xx, so the bytes go straight through.
 * 2. Capabilities differ per persona. When the role cannot import, this shows
 *    WHY in plain words instead of rendering a button that would 403. Offering
 *    a control the user is not allowed to press is worse than not offering it.
 */
export function ImportPanel({
  role,
  capability,
  busy,
  onImport,
}: {
  role?: Role;
  capability: LiveCapability | null;
  busy: boolean;
  onImport: (file: File, kind: "patch" | "slide") => void;
}) {
  const [kind, setKind] = useState<"patch" | "slide">("patch");
  const [file, setFile] = useState<File | null>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const mayAnalyze = role !== undefined && LIVE_ANALYZE_ROLES.includes(role);
  const suffixes = capability?.allowed_suffixes ?? [];
  const maxBytes = capability?.max_upload_bytes ?? 0;

  function accept(f: File | undefined | null) {
    if (!f || busy) return;
    setError(null); setFile(null);
    if (!suffixes.some(s => f.name.toLowerCase().endsWith(s.toLowerCase()))) {
      setError(`Unsupported file. Choose ${suffixes.join(", ")}.`);
    } else if (f.size === 0 || (maxBytes > 0 && f.size > maxBytes)) {
      setError(`Choose a non-empty image smaller than ${Math.round(maxBytes / 1e6)} MB.`);
    } else setFile(f);
    if (inputRef.current) inputRef.current.value = "";
  }

  // ---- runtime missing: nothing here can work, so say exactly why ----------
  if (mayAnalyze && capability && !capability.available) {
    return (
      <div className="import-blocked" role="status">
        <h3>Live inference is not available on this machine</h3>
        <p>{capability.reason}</p>
        {capability.hint && (
          <pre className="hint">
            <code>{capability.hint}</code>
          </pre>
        )}
        <p className="muted small">
          The review surface above still works — this only affects live inference.
        </p>
      </div>
    );
  }

  if (!capability) return <p className="muted" role="status">Checking inference availability…</p>;

  // ---- role cannot import: explain, do not disable -----------------------
  if (!mayAnalyze) {
    return (
      <div className="import-blocked" role="status">
        <h3>Importing is not available to your role</h3>
        <p>
          You are signed in as <b>{role ?? "unknown"}</b>. Running a forward pass is a
          writer action, reserved for {LIVE_ANALYZE_ROLES.join(", ")}.
        </p>
        <p>{LIVE_ANALYZE_DENIED_REASON[role ?? ""] ?? "Your role is read-only here."}</p>
        <p className="muted small">
          Sign in as <b>reviewer@demo</b> to try the import yourself — every run below stays
          readable to you either way.
        </p>
      </div>
    );
  }

  return (
    <div className="import">
      <div className="kind-toggle" role="group" aria-label="What are you importing?">
        <button
          type="button"
          disabled={busy}
          className={kind === "patch" ? "kind on" : "kind"}
          aria-pressed={kind === "patch"}
          onClick={() => setKind("patch")}
        >
          Single patch
        </button>
        <button
          type="button"
          disabled={busy}
          className={kind === "slide" ? "kind on" : "kind"}
          aria-pressed={kind === "slide"}
          onClick={() => setKind("slide")}
        >
          Whole slide
        </button>
      </div>

      <div
        className={`drop${over ? " over" : ""}${file ? " has" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault(); setOver(false);
          accept(e.dataTransfer.files?.[0]);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          className="visually-hidden"
          aria-label="Choose a patch or slide to import"
          accept={suffixes.join(",")}
          onChange={(e) => accept(e.target.files?.[0])}
        />
        {file ? (
          <div className="picked">
            <span className="picked-name">{file.name}</span>
            <span className="muted">
              {(file.size / 1e6).toFixed(2)} MB
              {kind === "slide" && capability?.tile_px
                ? ` · will tile at ${capability.tile_px}px`
                : ""}
            </span>
            <button type="button" className="btn-ghost" disabled={busy} onClick={() => setFile(null)}>
              Choose another
            </button>
          </div>
        ) : (
          <button
            type="button"
            disabled={busy}
            className="drop-cta"
            onClick={() => inputRef.current?.click()}
          >
            Drop a {kind === "patch" ? "patch" : "whole-slide image"} here, or click to browse
            <span className="muted small">
              {suffixes.length ? suffixes.join("  ") : ""}
              {maxBytes ? ` · up to ${Math.round(maxBytes / 1e6)} MB` : ""}
            </span>
          </button>
        )}
      </div>
      {error && <p role="alert" className="err">{error}</p>}

      <button
        type="button"
        className="btn go"
        disabled={!file || busy}
        onClick={() => file && onImport(file, kind)}
      >
        {busy
          ? kind === "slide" ? "Scoring tiles…" : "Running forward pass…"
          : kind === "slide" ? "Import and score every tile" : "Import and score"}
      </button>

      <p className="muted small">
        Use educational images without patient information. Results are stored separately
        from the frozen corpus and never overwrite it.
      </p>
    </div>
  );
}
