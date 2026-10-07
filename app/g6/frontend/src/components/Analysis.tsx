import type { ImageDetail, Meta } from "../types";
import { t } from "../strings";
import { AttributionPanel } from "./AttributionPanel";
import { ScoreBars } from "./Shared";

export function Analysis({ image, meta }: { image: ImageDetail; meta: Meta }) {
  const prediction = image.prediction;

  return (
    <section className="analysis" data-testid="analysis">
      <h3>{t("analysis.title")}</h3>
      <div className="analysis-context" data-testid="analysis-context">
        <div className="analysis-row">
          <span className="muted small">{t("analysis.sourceGroup")}</span>
          <span>{image.source_group}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.qc")}</span>
          <span>{image.qc.primary_qc_status}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.datasetLabel")}</span>
          <span>{image.qc.original_label ?? "—"}</span>
        </div>
      </div>

      {prediction ? (
        <>
          <p className="muted small">{meta.score_label}</p>
          <ScoreBars pred={prediction} />
          <div className="analysis-margin" data-testid="analysis-margin">
            <div className="analysis-row">
              <span className="muted small">{t("analysis.topTwoMargin")}</span>
              <span>{prediction.top_two_margin.toFixed(4)}</span>
            </div>
            <div className="analysis-row">
              <span className="muted small">{t("analysis.uncertainty")}</span>
              <span>{prediction.normalized_entropy.toFixed(4)}</span>
            </div>
          </div>
          <p className="muted small">The score margin and uncertainty guide educational review only; scores are uncalibrated and not probabilities.</p>
          <AttributionPanel imageId={image.image_id} />
        </>
      ) : (
        <div className="empty-state" data-testid="analysis-no-prediction">
          <strong>{t("patch.noPrediction")}</strong>
          <span>{t("patch.noPredictionBody")}</span>
        </div>
      )}
    </section>
  );
}
