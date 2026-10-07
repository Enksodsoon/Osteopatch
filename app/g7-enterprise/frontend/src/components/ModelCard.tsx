import { useEffect, useState } from "react";
import { getModelCard } from "../api";
import type {
  Limitation,
  LimitationSeverity,
  ModelCard as ModelCardPayload,
} from "../types";
import { t, type StringKey } from "../strings";

function Severity({ level }: { level: LimitationSeverity }) {
  return (
    <span className={`sev sev-${level}`} data-testid={`sev-${level}`}>
      {t(`severity.${level}` as StringKey)}
    </span>
  );
}

function LimitationItem({ item }: { item: Limitation }) {
  return (
    <li
      className={`lim-item${item.severity === "blocking" ? " lim-blocking" : ""}`}
      data-testid={`limitation-${item.id}`}
      data-severity={item.severity}
      data-category={item.category}
    >
      <div className="lim-head">
        <Severity level={item.severity} />
        <span className="lim-id mono">{item.id}</span>
      </div>
      <p className="lim-statement">{item.statement}</p>
      <p className="lim-retired">
        <span className="lim-label">{t("limitations.note")}:</span> {item.retired_by}
      </p>
      <details className="lim-evidence">
        <summary>{t("limitations.evidence")}</summary>
        <ul className="mono">
          {item.evidence.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </details>
    </li>
  );
}

export function ModelCard() {
  const [card, setCard] = useState<ModelCardPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let current = true;
    setFailed(false); setCard(null);
    getModelCard()
      .then(next => { if (current) setCard(next); })
      .catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, [retry]);

  if (failed) {
    return (
      <div className="model-card" data-testid="model-card">
        <h2>{t("nav.modelCard")}</h2>
        <p className="muted small" data-testid="model-card-error">
          The model card could not be loaded. Its limitations are part of the
          evidence for this system, so nothing is shown in their place.
        </p>
        <button type="button" className="btn" onClick={() => setRetry(n => n + 1)}>Retry</button>
      </div>
    );
  }
  if (!card) return <div className="muted" role="status">Loading model evidence…</div>;

  const oof = (card.headline_oof ?? {}) as Record<string, unknown>;
  const summary = card.limitations_summary;
  const blocking = summary?.by_severity?.blocking ?? 0;
  const evidenceAvailable = card.evaluation_evidence_available !== false;
  const metric = (v: unknown) =>
    evidenceAvailable && v != null ? String(v) : t("metric.notMeasured");
  const architecture = evidenceAvailable && card.architecture
    ? String(card.architecture)
    : t("metric.notAvailable");

  return (
    <div className="model-card" data-testid="model-card">
      <h2>{t("nav.modelCard")}</h2>
      <table className="kv">
        <tbody>
          <tr><td>Model version</td><td>{card.model_version}</td></tr>
          <tr><td>Bundle SHA-256</td><td className="mono">{card.model_bundle_sha256}</td></tr>
          <tr><td>Calibration</td><td>{card.calibration_status}</td></tr>
          <tr><td>Classes</td><td>{(card.canonical_classes ?? []).join(", ")}</td></tr>
          <tr><td>Architecture</td><td>{architecture}</td></tr>
          <tr><td>OOF macro-F1 (LOGO)</td><td>{metric(oof.macro_f1)}</td></tr>
          <tr><td>OOF balanced acc</td><td>{metric(oof.balanced_accuracy)}</td></tr>
          <tr><td>n (OOF)</td><td>{metric(oof.n_rows)}</td></tr>
        </tbody>
      </table>
      <p className="muted small">{card.evidence_note}</p>

      <section className="limitations-full" data-testid="limitations-full">
        <h3>{t("limitations.heading")}</h3>
        <p className="muted small" data-testid="limitations-count">
          {t("limitations.count", { total: summary?.total ?? 0 })}
          {blocking > 0 ? ` · ${t("limitations.blockingCount", { n: blocking })}` : ""}
          {summary?.weakest_class
            ? ` · ${t("limitations.weakest", { cls: summary.weakest_class })}`
            : ""}
        </p>
        <p className="muted small">{card.limitations_note}</p>

        {(card.limitations_grouped ?? []).length === 0 ? (
          <p className="muted small">{t("limitations.empty")}</p>
        ) : (
          card.limitations_grouped.map((g) => (
            <section
              key={g.category}
              className="lim-group"
              data-testid={`lim-group-${g.category}`}
              data-count={g.count}
              data-blocking={g.blocking_count}
            >
              <h4>
                {t(`category.${g.category}` as StringKey)}
                <span className="lim-count">{g.count}</span>
              </h4>
              <ul className="lim-list">
                {g.items.map((item) => (
                  <LimitationItem key={item.id} item={item} />
                ))}
              </ul>
            </section>
          ))
        )}
      </section>

      <section className="limitations-frozen" data-testid="limitations-frozen">
        <h3>{t("limitations.frozenHeading")}</h3>
        {!evidenceAvailable ? (
          <p className="evidence-missing" data-testid="limitations-evidence-missing">
            <strong>{t("limitations.evidenceUnavailable")}.</strong>{" "}
            {card.evaluation_evidence_unavailable_reason}
          </p>
        ) : (
          <ul className="limitations">
            {(card.limitations ?? []).map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        )}
      </section>

      <p className="muted small">{card.disclaimer}</p>
    </div>
  );
}

export function Attribution() {
  return (
    <div className="attribution" data-testid="attribution">
      <h2>{t("attribution.title")}</h2>
      <p>{t("attribution.navBody")}</p>
      <p className="muted small" data-testid="attribution-nav-not-segmentation">
        {t("attribution.notSegmentation")}
      </p>
      <p className="attrib-disclosure small" data-testid="attribution-nav-recovery-disclosure">
        {t("attribution.recoveryDisclosure")}
      </p>
    </div>
  );
}

export function ModelEvidenceSummary({ runModelId }: { runModelId: string }) {
  const [card, setCard] = useState<ModelCardPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let current = true;
    setFailed(false); setCard(null);
    getModelCard().then(next => { if (current) setCard(next); })
      .catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, [retry]);

  const oof = (card?.headline_oof ?? {}) as Record<string, unknown>;
  const accuracy = percent(oof.accuracy_secondary);
  const summary = !card ? "Loading evaluation…"
    : card.evaluation_evidence_available && accuracy !== "Not available"
      ? `Frozen baseline accuracy ${accuracy}` : "Frozen evaluation unavailable";
  const perClass = (oof.per_class && typeof oof.per_class === "object" ? oof.per_class : {}) as
    Record<string, { precision?: unknown; recall?: unknown; f1?: unknown; support?: unknown }>;

  return <details className="slide-model-evidence" data-testid="slide-model-evidence">
    <summary>Model & data <span>{summary}</span></summary>
    {failed ? <div role="alert" className="inline-error">
      Evaluation evidence could not be loaded. <button type="button" onClick={() => setRetry(n => n + 1)}>Retry</button>
    </div> : !card ? <p className="muted small" role="status">Loading model evidence…</p> : <>
      <p className="model-run-note">This run uses <code>{runModelId}</code>; independent accuracy for this recovered model has not been measured.</p>
      {card.evaluation_evidence_available ? <>
        <h4>Frozen G4 baseline · separate model</h4>
        <div className="model-metric-row">
          <span><b>{accuracy}</b><small>Accuracy · secondary</small></span>
          <span><b>{percent(oof.balanced_accuracy)}</b><small>Balanced accuracy</small></span>
          <span><b>{percent(oof.macro_f1)}</b><small>Macro F1</small></span>
        </div>
        <p className="muted small">{String(oof.n_rows ?? "—")} eligible patches · pooled out-of-fold over four case/slide groups. The app’s 50-patch teaching set is a separate subset.</p>
        <div className="model-class-table" role="table" aria-label="Frozen baseline class metrics">
          <div className="model-class-row model-class-head" role="row"><span role="columnheader">Class</span><span role="columnheader">Support</span><span role="columnheader">Recall</span><span role="columnheader">F1</span></div>
          {card.canonical_classes.map(cls => {
            const values = perClass[cls] ?? {};
            return <div className="model-class-row" role="row" key={cls}>
              <span role="cell"><i className={`class-swatch cl-${cls}`} aria-hidden="true" />{cls}</span>
              <span role="cell">{String(values.support ?? "—")}</span>
              <span role="cell">{percent(values.recall)}</span>
              <span role="cell">{percent(values.f1)}</span>
            </div>;
          })}
        </div>
        {perClass.VIABLE_TUMOR?.recall != null && <p className="model-weakness">Viable-tumor recall: {percent(perClass.VIABLE_TUMOR.recall)} in that baseline evaluation.</p>}
      </> : <p className="muted small">Frozen evaluation metrics are not present in this runtime, so no accuracy estimate is shown.</p>}
      <details className="model-setup-details">
        <summary>Model setup</summary>
        <dl>
          <dt>Evaluated artifact</dt><dd>{card.model_version}</dd>
          <dt>Architecture</dt><dd>{card.architecture ?? "Not recorded"}</dd>
          <dt>Calibration</dt><dd>{card.calibration_status}</dd>
          <dt>Classes</dt><dd>{card.canonical_classes.join(" · ")}</dd>
          <dt>Bundle SHA-256</dt><dd className="mono">{card.model_bundle_sha256}</dd>
        </dl>
        {card.preprocessing != null && <pre>{JSON.stringify(card.preprocessing, null, 2)}</pre>}
      </details>
    </>}
  </details>;
}

function percent(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "Not available";
}
