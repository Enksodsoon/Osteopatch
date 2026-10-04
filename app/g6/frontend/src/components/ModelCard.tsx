import { useEffect, useState } from "react";
import { t } from "../strings";

export function ModelCard() {
  const [card, setCard] = useState<any>(null);
  useEffect(() => {
    fetch("/v1/model-card").then((r) => r.json()).then(setCard);
  }, []);
  if (!card) return <div className="muted">…</div>;
  const oof = card.headline_oof ?? {};
  return (
    <div className="model-card" data-testid="model-card">
      <h2>{t("nav.modelCard")}</h2>
      <table className="kv">
        <tbody>
          <tr><td>Model version</td><td>{card.model_version}</td></tr>
          <tr><td>Bundle SHA-256</td><td className="mono">{card.model_bundle_sha256}</td></tr>
          <tr><td>Calibration</td><td>{card.calibration_status}</td></tr>
          <tr><td>Classes</td><td>{(card.canonical_classes ?? []).join(", ")}</td></tr>
          <tr><td>Architecture</td><td>{card.architecture}</td></tr>
          <tr><td>OOF macro-F1 (LOGO)</td><td>{oof.macro_f1}</td></tr>
          <tr><td>OOF balanced acc</td><td>{oof.balanced_accuracy}</td></tr>
          <tr><td>n (OOF)</td><td>{oof.n_rows}</td></tr>
        </tbody>
      </table>
      <p className="muted small">{card.evidence_note}</p>
      <ul className="limitations">
        {(card.limitations ?? []).map((l: string, i: number) => <li key={i}>{l}</li>)}
      </ul>
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
