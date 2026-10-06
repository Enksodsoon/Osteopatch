import { useState } from "react";
import * as api from "./api";
import type { Me, Role } from "./types";
import { DISCLAIMER_EN } from "./types";
import { Login } from "./components/Login";
import { ReviewScreen } from "./components/ReviewScreen";
import { RegistryScreen } from "./components/RegistryScreen";
import { LiveScreen } from "./components/live/LiveScreen";
import { ReportScreen } from "./components/reports/ReportScreen";

type Tab = "review" | "live" | "report" | "registry";

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("review");

  function onLoggedIn(m: Me) {
    setMe(m);
    const first = m.memberships[0];
    if (first) { setProjectId(first.project_id); api.setProject(first.project_id); }
  }

  function logout() {
    api.setToken(null); api.setProject(null);
    setMe(null); setProjectId(null);
  }

  if (!me) return <Login onLoggedIn={onLoggedIn} />;

  const role: Role | undefined = me.memberships.find((x) => x.project_id === projectId)?.role;
  const canRegistry = role === "ml_engineer" || role === "admin";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">OsteoPatch <span className="brand-ent">Enterprise</span></div>
        <div className="who">
          <label>
            Project:&nbsp;
            <select
              value={projectId ?? ""}
              onChange={(e) => { setProjectId(e.target.value); api.setProject(e.target.value); }}
            >
              {me.memberships.map((m) => (
                <option key={m.project_id} value={m.project_id}>{m.name} ({m.role})</option>
              ))}
            </select>
          </label>
          <span className="email">{me.email}</span>
          <button className="btn-ghost" onClick={logout}>Sign out</button>
        </div>
      </header>

      <div className="disclaimer-bar">⚠️ {DISCLAIMER_EN}</div>

      <nav className="tabs">
        <button className={tab === "review" ? "tab on" : "tab"} onClick={() => setTab("review")}>
          Review workbench
        </button>
        <button className={tab === "live" ? "tab on" : "tab"} onClick={() => setTab("live")}>
          Live inference
        </button>
        <button className={tab === "report" ? "tab on" : "tab"} onClick={() => setTab("report")}>
          Case report
        </button>
        {canRegistry && (
          <button className={tab === "registry" ? "tab on" : "tab"} onClick={() => setTab("registry")}>
            Model registry
          </button>
        )}
      </nav>

      <main className="main">
        {tab === "review" && projectId && <ReviewScreen key={projectId} role={role} />}
        {tab === "live" && projectId && <LiveScreen key={projectId} role={role} projectId={projectId} />}
        {tab === "report" && projectId && (
          <ReportScreen key={projectId} role={role} projectId={projectId} />
        )}
        {tab === "registry" && canRegistry && <RegistryScreen />}
      </main>
    </div>
  );
}
