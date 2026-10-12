import { useEffect, useRef, useState } from "react";
import * as api from "../api";
import { CLASS_LABELS, CLASS_NAMES, CLASSES } from "../types";
import type { CanonicalClass, Scores } from "../types";

function defaultClass(scores: Scores | null): CanonicalClass {
  return scores ? [...CLASSES].sort((a, b) => scores[b] - scores[a])[0] : "NON_TUMOR";
}

function strongestAlternative(scores: Scores | null, focus: CanonicalClass): CanonicalClass {
  return CLASSES.filter(cls => cls !== focus)
    .sort((a, b) => (scores?.[b] ?? 0) - (scores?.[a] ?? 0))[0];
}

export function LiveAttributionPanel({ runId, tileIndex, sourceLabel, scores, available }: {
  runId: string; tileIndex: number; sourceLabel: string; scores: Scores | null; available: boolean;
}) {
  const [focus, setFocus] = useState(() => defaultClass(scores));
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const request = useRef(0);

  useEffect(() => () => { request.current += 1; }, []);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  function chooseClass(value: CanonicalClass) {
    request.current += 1;
    setFocus(value);
    setImageUrl(null);
    setStatus("idle");
  }

  async function generate() {
    const targetA = focus;
    const targetB = strongestAlternative(scores, focus);
    const current = ++request.current;
    setImageUrl(null);
    setStatus("loading");
    try {
      const url = await api.blobUrl(api.tileAttributionPath(runId, tileIndex, targetA, targetB));
      if (current !== request.current) { URL.revokeObjectURL(url); return; }
      setImageUrl(url);
      setStatus("idle");
    } catch {
      if (current === request.current) setStatus("error");
    }
  }

  return (
    <section className="attrib-panel live-attribution" data-testid="live-attribution-panel">
      <h4>Grad-CAM · {sourceLabel}</h4>
      <p className="muted small">Choose a class to highlight its model evidence. The recovered model compares it with the highest-scoring alternative; scores are uncalibrated.</p>
      <div className="attrib-controls">
        <label className="attrib-focus">
          Focus class
          <select aria-label="Grad-CAM focus class" data-testid="live-attribution-class"
            value={focus} onChange={event => chooseClass(event.target.value as CanonicalClass)}>
            {CLASSES.map(cls => <option key={cls} value={cls}>{CLASS_LABELS[cls]}</option>)}
          </select>
        </label>
        <button type="button" className="btn" disabled={!available || status === "loading"} onClick={() => void generate()}>
          {status === "loading" ? "Generating Grad-CAM…" : imageUrl ? "Regenerate Grad-CAM" : "Generate Grad-CAM"}
        </button>
      </div>
      {!available && <p className="muted" role="status">Grad-CAM is unavailable for this undecoded region.</p>}
      {status === "loading" && <p className="muted" role="status">Computing Grad-CAM for the selected tile…</p>}
      {status === "error" && <p className="attrib-error" role="alert">Grad-CAM could not be loaded. The prediction remains available; retry or choose another decoded region.</p>}
      {imageUrl && <figure className="live-attribution-result">
        <img src={imageUrl} alt={`Grad-CAM overlay highlighting ${CLASS_NAMES[focus]} evidence for ${sourceLabel}`}
          data-testid="live-attribution-overlay" />
        <figcaption>{CLASS_NAMES[focus]} focus · {sourceLabel}</figcaption>
      </figure>}
      <p className="attrib-disclosure small" data-testid="live-attribution-disclosure">
        Attribution is model explanation, not segmentation or diagnosis. It explains this analyzed tile only, not the whole WSI.
      </p>
    </section>
  );
}
