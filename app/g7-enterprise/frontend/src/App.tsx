import { useState, useEffect } from "react";
import * as api from "./api";
import type { Me, Role } from "./types";
import { t } from "./strings";
import { Login } from "./components/Login";
import { Icon } from "./components/Icon";
import { Workbench } from "./components/Workbench";
import { PatchReview } from "./components/PatchReview";
import { ModelCard } from "./components/ModelCard";
import { LearningGuide } from "./components/LearningGuide";
import { RegistryScreen } from "./components/RegistryScreen";
import { ReportScreen } from "./components/reports/ReportScreen";
import { SlideWorkspace } from "./components/SlideWorkspace";

type Tab = "review" | "patch" | "model-card" | "guide" | "report" | "registry" | "images";

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("review");
  const [reportRunId, setReportRunId] = useState<string | undefined>();
  const [imagesOpened, setImagesOpened] = useState(false);
  const [viewingImageId, setViewingImageId] = useState<string | null>(null);
  const [meta, setMeta] = useState<import("./types").Meta | null>(null);
  const [metaError, setMetaError] = useState(false);
  const [health, setHealth] = useState<import("./types").Health | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthRetry, setHealthRetry] = useState(0);
  const [exportError, setExportError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const role: Role | undefined = me?.memberships.find((x) => x.project_id === projectId)?.role;
  const canReadReview = !!role && role !== "ml_engineer";
  const canExport = !!role && ["reviewer", "pathologist", "admin", "auditor"].includes(role);

  function signOut(expired = false) {
    api.setToken(null); api.setProject(null);
    setMe(null); setProjectId(null); setMeta(null); setHealth(null);
    setViewingImageId(null); setTab("review"); setExportError(null); setMetaError(false);
    setSessionExpired(expired);
    setImagesOpened(false); setReportRunId(undefined);
  }

  useEffect(() => {
    const expired = () => signOut(true);
    window.addEventListener("osteopatch:session-expired", expired);
    return () => window.removeEventListener("osteopatch:session-expired", expired);
  }, []);
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

  useEffect(() => {
    if (!me) return;
    let current = true;
    setHealthLoading(true);
    const refresh = () => api.getHealth()
      .then((next) => { if (current) setHealth(next); })
      .catch(() => { if (current) setHealth(null); })
      .finally(() => { if (current) setHealthLoading(false); });
    refresh();
    const timer = window.setInterval(refresh, 30_000);
    return () => { current = false; window.clearInterval(timer); };
  }, [me, healthRetry]);

  useEffect(() => {
    if (!me || !projectId || !canReadReview) return;
    let current = true;
    setMeta(null);
    setMetaError(false);
    api.getMeta()
      .then((next) => { if (current) setMeta(next); })
      .catch(() => { if (current) setMetaError(true); });
    return () => { current = false; };
  }, [me, projectId, canReadReview]);

  function onLoggedIn(m: Me) {
    setSessionExpired(false);
    setMe(m);
    const first = m.memberships[0];
    if (first) { setProjectId(first.project_id); api.setProject(first.project_id); }
    if (first?.role === "ml_engineer") { setImagesOpened(true); setTab("images"); }
  }

  async function exportReviews(format: "csv" | "json") {
    setExportError(null);
    try { await api.downloadReviews(format); }
    catch (error) { setExportError(error instanceof Error ? error.message : String(error)); }
  }


  if (!me) return <Login onLoggedIn={onLoggedIn} sessionExpired={sessionExpired} />;

  const canRegistry = role === "ml_engineer" || role === "admin";

  return (
    <div className="app">
      <header className="app-header">
        <button
          className="brand-home"
          type="button"
          onClick={() => { setTab("review"); setViewingImageId(null); }}
            aria-label="Open review set"
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
            aria-label="Review set" title="Review set"
            onClick={() => { setTab("review"); setViewingImageId(null); }}
          >
            <Icon name="review" />
          </button>
          <button className={tab === "images" ? "active" : ""} aria-label="Images" title="Images" onClick={() => { setImagesOpened(true); setTab("images"); }}><Icon name="images" /></button>
          <button
            className={tab === "report" ? "active" : ""}
            aria-label="Reports" title="Reports"
            onClick={() => setTab("report")}
          >
            <Icon name="reports" />
          </button>
          <button
            className={tab === "guide" ? "active" : ""}
            aria-label="Learn" title="Learn"
            onClick={() => setTab("guide")}
          >
            <Icon name="learn" />
          </button>
          {canRegistry && (
            <details className="app-tools">
              <summary>Tools</summary>
              <button type="button" onClick={() => setTab("registry")}>Model registry</button>
            </details>
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
            className={`system-status ${health ? "status-live" : "status-offline"}`}
            role="status"
          >
            <span className="system-status-dot" aria-hidden="true" />
            {healthLoading ? "Checking API…" : health ? t("app.apiLive") : t("app.apiOffline")}
            {!health && !healthLoading && <button type="button" className="btn-link" onClick={() => setHealthRetry(n => n + 1)}>Retry API</button>}
          </span>
          {canExport && <div className="app-export" aria-label={t("export.title")}>
            <button className="btn-link" type="button" onClick={() => exportReviews("csv")} data-testid="export-csv">
              {t("export.csv")}
            </button>
            <button className="btn-link" type="button" onClick={() => exportReviews("json")} data-testid="export-json">
              {t("export.json")}
            </button>
          </div>}
          <button type="button" className="btn-link" onClick={() => signOut()}>Sign out</button>
        </div>
      </header>

      {meta?.attribution_enabled && (
        <div className="subset-banner" role="note" data-testid="subset-banner">
          <span className="subset-label">{t("app.eyebrow")}</span>
          {t("subset.banner")}
        </div>
      )}

      {metaError && (
        <div className="inline-error app-status-error" role="alert">
          <span>Review data could not be reached. Check the local API, then retry.</span>
          <button type="button" className="btn-link" onClick={() => { setMetaError(false); setMeta(null); api.getMeta().then(setMeta).catch(() => setMetaError(true)); }}>
            {t("common.retry")}
          </button>
        </div>
      )}
      {exportError && <p className="inline-error" role="alert">Export failed: {exportError}</p>}

      <main className="app-main">
        {imagesOpened && projectId && <div hidden={tab !== "images"}><SlideWorkspace role={role} projectId={projectId} onReport={runId => { setReportRunId(runId); setTab("report"); }} /></div>}
        {!canReadReview && ["review", "model-card"].includes(tab) && <div className="empty-state" role="status"><strong>The review set is not available for your role</strong><span>Open Images to view slides and saved results, or visit Learn for the guide.</span><button className="btn-primary" onClick={() => { setImagesOpened(true); setTab("images"); }}>Open images</button></div>}
        {projectId && canReadReview && <div hidden={tab !== "review"}><Workbench active={tab === "review"} onOpen={(id) => { setViewingImageId(id); setTab("patch"); }} /></div>}
        {tab === "patch" && viewingImageId && projectId && meta && (
          <PatchReview
            key={viewingImageId}
            imageId={viewingImageId}
            meta={meta}
            canReview={role !== "auditor"}
            onBack={() => { setViewingImageId(null); setTab("review"); }}
            onNavigate={(id) => setViewingImageId(id)}
          />
        )}
        {tab === "model-card" && canReadReview && <ModelCard />}
        {tab === "guide" && <LearningGuide onOpenModel={() => setTab("model-card")} />}
        {tab === "report" && projectId && (
          <ReportScreen key={projectId} role={role} projectId={projectId} userEmail={me.email} initialRunId={reportRunId} />
        )}
        {tab === "patch" && viewingImageId && !meta && !metaError && <div role="status" className="page-loading">Loading review configuration…</div>}
        {tab === "registry" && canRegistry && <RegistryScreen />}
      </main>
    </div>
  );
}

