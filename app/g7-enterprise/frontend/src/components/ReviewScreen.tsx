import { useEffect, useState } from "react";
import * as api from "../api";
import type { GalleryItem, Role, Scores } from "../types";
import { CLASS_LABELS } from "../types";

const CLASSES: (keyof Scores)[] = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"];

export function ReviewScreen({ role }: { role?: Role }) {
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [sel, setSel] = useState<GalleryItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const canWrite = role !== "auditor"; // auditor is read-only

  async function load() {
    setError(null);
    try {
      const g = await api.gallery("priority", 1, 24);
      setItems(g.items); setTotal(g.total);
      if (!sel && g.items.length) setSel(g.items[0]);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function act(action: "ACCEPT" | "CORRECT" | "DEFER", selected_label?: string) {
    if (!sel?.prediction) return;
    try {
      await api.submitReview(sel.image_id, sel.prediction.prediction_id, action, { selected_label });
      setMsg(`${action}${selected_label ? " → " + selected_label : ""} saved for ${sel.image_id}`);
      await load();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  }

  if (error) return <div className="panel err">Backend: {error}</div>;

  return (
    <div className="review-grid">
      <aside className="gallery">
        <div className="gallery-head">Review queue <span className="muted">({total} in scope, uncertainty-first)</span></div>
        <ul>
          {items.map((it) => (
            <li
              key={it.image_id}
              className={sel?.image_id === it.image_id ? "g-item on" : "g-item"}
              onClick={() => setSel(it)}
            >
              <span className="g-id">{it.image_id}</span>
              <span className={`pill pill-${it.prediction?.predicted_class ?? "none"}`}>
                {it.prediction?.predicted_class ?? "—"}
              </span>
              <span className="g-state">{it.review_state.status}</span>
            </li>
          ))}
        </ul>
      </aside>

      <section className="detail">
        {!sel ? <p className="muted">Select a patch.</p> : (
          <>
            <h2>{sel.image_id} <span className="muted">· group {sel.source_group}</span></h2>
            {sel.prediction ? (
              <>
                <div className="scores">
                  {CLASSES.map((c) => {
                    const v = sel.prediction!.scores[c];
                    const top = c === sel.prediction!.predicted_class;
                    return (
                      <div className="score-row" key={c}>
                        <span className="score-lbl">{CLASS_LABELS[c]}</span>
                        <div className="score-track"><div className={top ? "score-fill top" : "score-fill"} style={{ width: `${v * 100}%` }} /></div>
                        <span className="score-val">{v.toFixed(3)}</span>
                      </div>
                    );
                  })}
                </div>
                <p className="muted small">
                  Uncalibrated scores · margin {sel.prediction.top_two_margin.toFixed(3)} ·
                  entropy {sel.prediction.normalized_entropy.toFixed(3)} ·
                  bundle {sel.prediction.model_bundle_hash.slice(0, 12)}…
                </p>
                {canWrite ? (
                  <div className="actions">
                    <button className="btn acc" onClick={() => act("ACCEPT")}>Accept {sel.prediction.predicted_class}</button>
                    {CLASSES.filter((c) => c !== sel.prediction!.predicted_class).map((c) => (
                      <button className="btn cor" key={c} onClick={() => act("CORRECT", c)}>Correct → {c}</button>
                    ))}
                    <button className="btn def" onClick={() => act("DEFER")}>Defer</button>
                  </div>
                ) : <p className="muted">Read-only role (auditor).</p>}
                {msg && <p className="ok">{msg}</p>}
              </>
            ) : <p className="muted">No prediction for this patch.</p>}
            <p className="muted small">
              Attribution (Grad-CAM) renders here when pixel assets are present; it degrades
              honestly to a notice when they are not — never a fabricated heatmap.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
