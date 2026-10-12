import { useEffect, useRef, useState } from "react";
import { exportUrl, getHealth, getMeta } from "./api";
import type { Health, Meta } from "./types";
import { t } from "./strings";
import { Disclaimer } from "./components/Shared";
import { ThemeControl } from "./components/ThemeControl";
import { Workbench } from "./components/Workbench";
import { PatchReview } from "./components/PatchReview";
import { Attribution, ModelCard } from "./components/ModelCard";
import {
  DEFAULT_CONTEXT,
  NAV_ITEMS,
  currentRoute,
  serializeRoute,
  subscribeToRouteChange,
  type QueueContext,
  type Route,
} from "./navigation";

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [startupError, setStartupError] = useState(false);
  // U001: the location is the source of truth, so a deep link survives a refresh.
  const [route, setRoute] = useState<Route>(currentRoute);
  const mainRef = useRef<HTMLElement | null>(null);

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
  }, []);

  // One listener for Back/Forward and for hand-edited hashes, removed on unmount.
  useEffect(() => subscribeToRouteChange(() => setRoute(currentRoute())), []);

  /** Navigate. `replace` keeps a history step out of the way for context-only edits. */
  const go = (next: Route, options?: { replace?: boolean }) => {
    const hash = serializeRoute(next);
    if (options?.replace) {
      window.history.replaceState(null, "", hash);
      setRoute(next);
      return;
    }
    if (window.location.hash === hash) {
      setRoute(next);
      return;
    }
    window.location.hash = hash; // fires hashchange; the listener applies the route
  };

  const reviewerView = route.name === "workbench" || route.name === "patch";
  const context: QueueContext =
    route.name === "workbench" || route.name === "patch" ? route.context : DEFAULT_CONTEXT;

  return (
    <div className="app">
      <button
        type="button"
        className="btn-link skip-link"
        onClick={() => mainRef.current?.focus()}
      >
        Skip to content
      </button>

      <header className="app-header">
        <button
          className="brand-home"
          type="button"
          onClick={() => go({ name: "workbench", context: DEFAULT_CONTEXT })}
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
          {NAV_ITEMS.map((item) => {
            const active = route.name === item.name ||
              (item.name === "workbench" && route.name === "patch");
            return (
              <button
                key={item.name}
                className={active ? "active" : ""}
                aria-current={active ? "page" : undefined}
                onClick={() =>
                  go(
                    item.name === "workbench"
                      ? { name: "workbench", context: DEFAULT_CONTEXT }
                      : { name: item.name },
                  )
                }
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="app-header-actions">
          <span
            className={health ? "system-status status-live" : "system-status status-offline"}
            role="status"
          >
            <span className="system-status-dot" aria-hidden="true" />
            {health ? t("app.apiLive") : t("app.apiOffline")}
          </span>
          <ThemeControl />
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

      <main className="app-main" id="main-content" tabIndex={-1} ref={mainRef}>
        {startupError && reviewerView && (
          <section className="startup-error" role="alert">
            <span className="startup-error-mark" aria-hidden="true">!</span>
            <div>
              <strong>{t("app.loadErrorTitle")}</strong>
              <p>{t("app.loadErrorBody")}</p>
            </div>
          </section>
        )}

        {!meta && !startupError && reviewerView && <div className="page-loading">Loading review workspace…</div>}

        {meta && route.name === "workbench" && (
          <Workbench
            context={context}
            onContextChange={(next) => go({ name: "workbench", context: next }, { replace: true })}
            onOpen={(imageId) => go({ name: "patch", imageId, context })}
          />
        )}
        {meta && route.name === "patch" && (
          <PatchReview
            imageId={route.imageId}
            meta={meta}
            onBack={() => go({ name: "workbench", context })}
            onNavigate={(imageId) => go({ name: "patch", imageId, context })}
          />
        )}
        {route.name === "model-card" && <ModelCard />}
        {route.name === "attribution" && <Attribution />}
        {route.name === "not-available" && (
          <section className="startup-error" role="status" data-testid="route-unavailable">
            <span className="startup-error-mark" aria-hidden="true">i</span>
            <div>
              <strong>Not available in this build</strong>
              <p>
                {route.declared
                  ? "This destination is part of the roadmap but is not implemented yet."
                  : "That address does not match any screen in this app."}{" "}
                Use the navigation above to continue.
              </p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
