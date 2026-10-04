import { useEffect, useState } from "react";
import * as api from "../api";
import type { ServingModel } from "../types";

const STATES = ["registered", "candidate", "shadow", "serving", "retired"];

export function RegistryScreen() {
  const [serving, setServing] = useState<ServingModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({
    bundle_sha256: "", model_id: "", eval_card_ref: "", split_declared: "slide-group-independent",
  });

  async function refresh() {
    setError(null);
    try {
      const s = await api.servingModel();
      setServing("bundle_sha256" in s ? (s as ServingModel) : null);
    } catch (e) { setError(String(e instanceof Error ? e.message : e)); }
  }
  useEffect(() => { refresh(); }, []);

  async function wrap(fn: () => Promise<unknown>, label: string) {
    setError(null); setMsg(null);
    try { await fn(); setMsg(label); await refresh(); }
    catch (e) { setError(String(e instanceof Error ? e.message : e)); }
  }

  return (
    <div className="registry">
      <section className="panel">
        <h3>Serving model</h3>
        {serving ? (
          <div className="serving-card">
            <div className="serving-id">{serving.model_id}</div>
            <code>{serving.bundle_sha256.slice(0, 24)}…</code>
            <div className="statechips">
              {STATES.map((s) => (
                <span key={s} className={s === serving.state ? "schip on" : "schip"}>{s}</span>
              ))}
            </div>
            <button className="btn def" onClick={() => wrap(api.rollbackModel, "Rolled back to previous serving bundle")}>
              Roll back
            </button>
          </div>
        ) : <p className="muted">No model is serving yet.</p>}
      </section>

      <section className="panel">
        <h3>Register a bundle</h3>
        <div className="reg-form">
          {(["bundle_sha256", "model_id", "eval_card_ref", "split_declared"] as const).map((k) => (
            <label key={k}>
              {k}
              <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            </label>
          ))}
          <button className="btn" onClick={() => wrap(() => api.registerModel(form), `Registered ${form.model_id}`)}>
            Register
          </button>
        </div>
        <h4>Promote</h4>
        <div className="promote-row">
          {STATES.filter((s) => s !== "registered").map((s) => (
            <button
              key={s}
              className="btn"
              onClick={() => wrap(
                () => api.promoteModel(form.bundle_sha256, s, s === "serving" ? true : undefined),
                `Promoted ${form.bundle_sha256.slice(0, 8)}… → ${s}`,
              )}
            >
              → {s}
            </button>
          ))}
        </div>
        <p className="muted small">
          Promotion to <b>serving</b> requires a passing eval gate; promoting a new serving bundle
          auto-retires the current one (single-serving invariant). Rollback restores the last retired.
        </p>
      </section>

      {msg && <p className="ok">{msg}</p>}
      {error && <p className="err">{error}</p>}
    </div>
  );
}
