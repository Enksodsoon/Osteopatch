import { useState, useEffect } from "react";
import * as api from "./api";
import type { Me, Role } from "./types";
import { DISCLAIMER_EN } from "./types";
import { t } from "./strings";
import { Login } from "./components/Login";
import { Workbench } from "./components/Workbench";
import { PatchReview } from "./components/PatchReview";
import { ModelCard } from "./components/ModelCard";
import { RegistryScreen } from "./components/RegistryScreen";
import { LiveScreen } from "./components/live/LiveScreen";
import { ReportScreen } from "./components/reports/ReportScreen";

type Tab = "review" | "patch" | "analysis" | "library" | "model-card" | "live" | "report" | "registry";

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("review");
  const [viewingImageId, setViewingImageId] = useState<string | null>(null);
  const [meta, setMeta] = useState<import("./types").Meta | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const stored = localStorage.getItem("osteopatch.theme");
      if (stored === "light" || stored === "dark") return stored;
    } catch { /* ignore */ }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("osteopatch.theme", theme); } catch { /* ignore */ }
  }, [theme]);

  function onLoggedIn(m: Me) {
    setMe(m);
    const first = m.memberships[0];
    if (first) { setProjectId(first.project_id); api.setProject(first.project_id); }
    // load review meta once logged in
    api.getMeta().then(setMeta).catch(() => {});
  }


  if (!me) return <Login onLoggedIn={onLoggedIn} />;

  const role: Role | undefined = me.memberships.find((x) => x.project_id === projectId)?.role;
  const canRegistry = role === "ml_engineer" || role === "admin";

  return (
    <div className="app">
      <header className="app-header">
        <button
          className="brand-home"
          type="button"
          onClick={() => { setTab("review"); setViewingImageId(null); }}
          aria-label="Open review workbench"
        >
          <span className="brand-mark" aria-hidden="true">OP</span>
          <span className="app-brand">
            <span className="app-kicker">{t("app.eyebrow")}</span>
            <strong>{t("app.title")}</strong>
            <span className="app-sub">{t("app.subtitle")}</span>
          </span>
        </button>

        <nav className="app-nav" aria-label="Primary">
          <button
            className={tab === "review" ? "active" : ""}
            onClick={() => { setTab("review"); setViewingImageId(null); }}
          >
            {t("nav.workbench")}
          </button>
          <button
            className={tab === "model-card" ? "active" : ""}
            onClick={() => setTab("model-card")}
          >
            {t("nav.modelCard")}
          </button>
          <button
            className={tab === "live" ? "active" : ""}
            onClick={() => setTab("live")}
          >
            Live inference
          </button>
          <button
            className={tab === "report" ? "active" : ""}
            onClick={() => setTab("report")}
          >
            Case report
          </button>
          {canRegistry && (
            <button
              className={tab === "registry" ? "active" : ""}
              onClick={() => setTab("registry")}
            >
              Model registry
            </button>
          )}
        </nav>

        <div className="app-header-actions">
          <button
            type="button"
            className="theme-toggle"
            onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
            aria-pressed={theme === "dark"}
            aria-label={t("theme.toggleAria")}
            data-testid="theme-toggle"
          >
            <span className="theme-toggle-icon" aria-hidden="true" />
            {theme === "light" ? t("theme.light") : t("theme.dark")}
          </button>
          <span
            className={me ? "system-status status-live" : "system-status status-offline"}
            role="status"
          >
            <span className="system-status-dot" aria-hidden="true" />
            {me ? t("app.apiLive") : t("app.apiOffline")}
          </span>
          <div className="app-export" aria-label={t("export.title")}>
            <a className="btn-link" href={api.exportUrl("csv")} data-testid="export-csv">
              {t("export.csv")}
            </a>
            <a className="btn-link" href={api.exportUrl("json")} data-testid="export-json">
              {t("export.json")}
            </a>
          </div>
        </div>
      </header>

      <div className="disclaimer">⚠️ {DISCLAIMER_EN}</div>

      {meta?.attribution_enabled && (
        <div className="subset-banner" role="note" data-testid="subset-banner">
          <span className="subset-label">{t("app.eyebrow")}</span>
          {t("subset.banner")}
        </div>
      )}

      <main className="app-main">
        {tab === "review" && projectId && <Workbench onOpen={(id) => { setViewingImageId(id); setTab("patch"); }} />}
        {tab === "patch" && viewingImageId && projectId && meta && (
          <PatchReview
            imageId={viewingImageId}
            meta={meta}
            onBack={() => { setViewingImageId(null); setTab("review"); }}
            onNavigate={(id) => setViewingImageId(id)}
          />
        )}
        {tab === "model-card" && <ModelCard />}
        {tab === "live" && projectId && <LiveScreen key={projectId} role={role} projectId={projectId} />}
        {tab === "report" && projectId && (
          <ReportScreen key={projectId} role={role} projectId={projectId} />
        )}
        {tab === "registry" && canRegistry && <RegistryScreen />}
      </main>
    </div>
  );
}

