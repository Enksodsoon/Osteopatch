import type { CanonicalClass, Prediction, QcMeta } from "../types";
import { t } from "../strings";

export function Disclaimer() {
  // Always visible, no hidden panel.
  return (
    <div className="disclaimer" role="note" data-testid="disclaimer">
      {t("disclaimer.short")}
    </div>
  );
}

export function UncalibratedBadge() {
  return (
    <span className="badge badge-uncal" title={t("patch.scoreLabel")}>
      {t("patch.uncalibrated")}
    </span>
  );
}

const CLASS_ACCENT: Record<CanonicalClass, string> = {
  NON_TUMOR: "class-nt",
  VIABLE_TUMOR: "class-vt",
  NECROSIS: "class-nec",
};

// Accent is paired with a text label + a shape marker so it is never color-only.
export function ClassChip({ cls, selected }: { cls: CanonicalClass; selected?: boolean }) {
  return (
    <span className={`chip ${CLASS_ACCENT[cls]} ${selected ? "chip-selected" : ""}`}>
      <span className="chip-marker" aria-hidden="true" />
      {t(`class.${cls}` as const)}
    </span>
  );
}

export function ScoreBars({ pred }: { pred: Prediction }) {
  const order: CanonicalClass[] = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"];
  return (
    <div className="scorebars" data-testid="scorebars">
      <div className="scorebars-head">
        {t("patch.scores")} <UncalibratedBadge />
      </div>
      {order.map((c) => {
        const v = pred.scores[c];
        const isTop = c === pred.predicted_class;
        return (
          <div key={c} className={`scorebar ${isTop ? "scorebar-top" : ""}`} data-testid={`score-${c}`}>
            <div className="scorebar-label">
              <ClassChip cls={c} />
              <span className="scorebar-value">{v.toFixed(3)}</span>
            </div>
            <div className="scorebar-track">
              <div className={`scorebar-fill ${CLASS_ACCENT[c]}`} style={{ width: `${Math.round(v * 100)}%` }} />
            </div>
          </div>
        );
      })}
      <div className="scorebars-foot">{t("patch.scoreLabel")}</div>
    </div>
  );
}

export function QcBadges({ qc }: { qc: QcMeta }) {
  return (
    <div className="qc-badges">
      {qc.qc_review_flag && (
        <span className="badge badge-qc" title={qc.qc_review_reason ?? ""}>
          {t("patch.qcReview")}
        </span>
      )}
      <span className={`badge ${qc.training_eligible ? "badge-elig" : "badge-inelig"}`}>
        {t("patch.trainingEligible")}: {qc.training_eligible ? "yes" : "no"}
      </span>
    </div>
  );
}
