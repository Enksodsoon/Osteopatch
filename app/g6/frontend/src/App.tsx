import { useEffect, useState } from "react";
import { exportUrl, getHealth, getMeta } from "./api";
import type { Health, Meta } from "./types";
import { t } from "./strings";
import { Disclaimer } from "./components/Shared";
import { Workbench } from "./components/Workbench";
import { PatchReview } from "./components/PatchReview";
import { AnalysisWithImage } from "./components/AnalysisWithImage";
import { Library } from "./components/Library";
import { Attribution, ModelCard } from "./components/ModelCard";
type View =
  | { name: "workbench" }
  | { name: "patch"; imageId: string }
  | { name: "analysis"; imageId: string }
  | { name: "library" }
  | { name: "model-card" }
  | { name: "attribution" };
export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [startupError, setStartupError] = useState(false);
  const [retryVersion, setRetryVersion] = useState(0);
  const [view, setView] = useState<View>({ name: "workbench" });
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const stored = localStorage.getItem("osteopatch.theme");
      if (stored === "light" || stored === "dark") return stored;
    } catch {
      /* ignore */
    }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("osteopatch.theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  useEffect(() => {
    let active = true;
    getMeta()
      .then((m) => {
        if (active) setMeta(m);
      })
      .catch(() => {
        if (active) setStartupError(true);
      });
    getHealth()
      .then((h) => {
        if (active) setHealth(h);
      })
      .catch(() => {
        if (active) setHealth(null);
      });
    return () => {
      active = false;
    };
  }, [retryVersion]);

  const reviewerView = view.name === "workbench" || view.name === "patch";

  return (
    <div className="app">
      <header className="app-header">
        <button
          className="brand-home"
          type="button"
          onClick={() => setView({ name: "workbench" })}
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
            className={reviewerView ? "active" : ""}
            onClick={() => setView({ name: "workbench" })}
          >
            {t("nav.workbench")}
          </button>
          <button
            className={view.name === "model-card" ? "active" : ""}
            onClick={() => setView({ name: "model-card" })}
          >
            {t("nav.modelCard")}
          </button>
          <button
            className={view.name === "attribution" ? "active" : ""}
            onClick={() => setView({ name: "attribution" })}
          >
            {t("nav.attribution")}
          </button>
          <button
            className={view.name === "library" ? "active" : ""}
            onClick={() => setView({ name: "library" })}
          >
            {t("nav.library")}
          </button>
          <button
            className={view.name === "analysis" ? "active" : ""}
            onClick={() => {
              if (view.name === "patch") {
                setView({ name: "analysis", imageId: view.imageId });
              }
            }}
            disabled={view.name !== "patch"}
            title={t("analysis.title")}
          >
            {t("analysis.title")}
          </button>
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
            className={health ? "system-status status-live" : "system-status status-offline"}
            role="status"
          >
            <span className="system-status-dot" aria-hidden="true" />
            {health ? t("app.apiLive") : t("app.apiOffline")}
          </span>
          <div className="app-export" aria-label={t("export.title")}>
            <a className="btn-link" href={exportUrl("csv")} data-testid="export-csv">
              {t("export.csv")}
            </a>
            <a className="btn-link" href={exportUrl("json")} data-testid="export-json">
              {t("export.json")}
            </a>
          </div>
        </div>
      </header>

      <Disclaimer />

      {health?.image_subset_scoped && (
        <div className="subset-banner" role="note" data-testid="subset-banner">
          <span className="subset-label">DEMO DATASET</span>
          {t("subset.banner")}
        </div>
      )}

      <main className="app-main">
        {startupError && reviewerView && (
          <section className="startup-error" role="alert">
            <span className="startup-error-mark" aria-hidden="true">!</span>
            <div>
              <strong>{t("app.loadErrorTitle")}</strong>
              <p>{t("app.loadErrorBody")}</p>
              <button type="button" className="btn-link" onClick={() => { setStartupError(false); setMeta(null); setRetryVersion((n) => n + 1); }}>
                {t("common.retry")}
              </button>
            </div>
          </section>
        )}

        {!meta && !startupError && reviewerView && <div className="page-loading">Loading review workspace…</div>}

        {meta && view.name === "workbench" && (
          <Workbench onOpen={(imageId) => setView({ name: "patch", imageId })} />
        )}
        {meta && view.name === "patch" && (
          <PatchReview
            imageId={view.imageId}
            meta={meta}
            onBack={() => setView({ name: "workbench" })}
            onNavigate={(imageId) => setView({ name: "patch", imageId })}
            onOpenAnalysis={(imageId) => setView({ name: "analysis", imageId })}
          />
        )}
        {meta && view.name === "analysis" && (
          <AnalysisWithImage
            imageId={view.imageId}
            meta={meta}
            onBack={() => setView({ name: "patch", imageId: view.imageId })}
          />
        )}
        {view.name === "library" && <Library onOpen={(id) => setView({ name: "patch", imageId: id })} />}
        {view.name === "model-card" && <ModelCard />}
        {view.name === "attribution" && <Attribution />}
      </main>
    </div>
  );
}
