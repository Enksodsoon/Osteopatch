import { useEffect, useState } from "react";
import { exportUrl, getHealth, getMeta } from "./api";
import type { Health, Meta } from "./types";
import { t } from "./strings";
import { Disclaimer } from "./components/Shared";
import { Workbench } from "./components/Workbench";
import { PatchReview } from "./components/PatchReview";
import { Attribution, ModelCard } from "./components/ModelCard";

type View =
  | { name: "workbench" }
  | { name: "patch"; imageId: string }
  | { name: "model-card" }
  | { name: "attribution" };

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [view, setView] = useState<View>({ name: "workbench" });

  useEffect(() => {
    getMeta().then(setMeta);
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <strong>{t("app.title")}</strong>
          <span className="app-sub">{t("app.subtitle")}</span>
        </div>
        <nav className="app-nav">
          <button
            className={view.name === "workbench" || view.name === "patch" ? "active" : ""}
            onClick={() => setView({ name: "workbench" })}
          >
            {t("nav.workbench")}
          </button>
          <button className={view.name === "model-card" ? "active" : ""} onClick={() => setView({ name: "model-card" })}>
            {t("nav.modelCard")}
          </button>
          <button className={view.name === "attribution" ? "active" : ""} onClick={() => setView({ name: "attribution" })}>
            {t("nav.attribution")}
          </button>
        </nav>
        <div className="app-export">
          <a className="btn-link" href={exportUrl("csv")} data-testid="export-csv">{t("export.csv")}</a>
          <a className="btn-link" href={exportUrl("json")} data-testid="export-json">{t("export.json")}</a>
        </div>
      </header>

      <Disclaimer />

      {health?.image_subset_scoped && (
        <div className="subset-banner" role="note" data-testid="subset-banner">
          {t("subset.banner")}
        </div>
      )}

      <main className="app-main">
        {!meta && <div className="muted">…</div>}
        {meta && view.name === "workbench" && (
          <Workbench onOpen={(imageId) => setView({ name: "patch", imageId })} />
        )}
        {meta && view.name === "patch" && (
          <PatchReview
            imageId={view.imageId}
            meta={meta}
            onBack={() => setView({ name: "workbench" })}
            onNavigate={(imageId) => setView({ name: "patch", imageId })}
          />
        )}
        {meta && view.name === "model-card" && <ModelCard />}
        {meta && view.name === "attribution" && <Attribution />}
      </main>
    </div>
  );
}
