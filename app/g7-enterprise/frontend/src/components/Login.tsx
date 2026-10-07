import { useState } from "react";
import * as api from "../api";
import type { Me } from "../types";
import { DISCLAIMER_EN } from "../types";

const DEMO_USERS = [
  "admin@demo", "path@demo", "reviewer@demo", "student@demo", "mle@demo", "auditor@demo",
];

export function Login({ onLoggedIn, sessionExpired = false }: { onLoggedIn: (m: Me) => void; sessionExpired?: boolean }) {
  const [email, setEmail] = useState("reviewer@demo");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function doLogin(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await api.login(email.trim());
      onLoggedIn(await api.me());
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={doLogin}>
        <h1>OsteoPatch <span className="brand-ent">Enterprise</span></h1>
        <p className="muted">Sign in to the local educational demo.</p>
        {sessionExpired && <p role="alert" className="err">Your session expired. Sign in again to continue.</p>}
        <input
          aria-label="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@org"
        />
        <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        {error && <p className="err" role="alert">{error === "Failed to fetch" ? "The local demo server is unavailable. Start it with the documented demo command, then retry sign-in." : error}</p>}
        <div className="demo-users">
          <span className="muted">Demo users:</span>
          {DEMO_USERS.map((u) => (
            <button type="button" key={u} className="chip" onClick={() => setEmail(u)}>{u}</button>
          ))}
        </div>
        <p className="disclaimer-sm">⚠️ {DISCLAIMER_EN}</p>
      </form>
    </div>
  );
}
