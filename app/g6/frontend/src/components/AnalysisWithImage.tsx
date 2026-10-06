import { useCallback, useEffect, useState } from "react";
import { getImage } from "../api";
import type { ImageDetail, Meta } from "../types";
import { t } from "../strings";
import { ImageViewer } from "./ImageViewer";
import { Analysis } from "./Analysis";interface Props {
  imageId: string;
  meta: Meta;
  onBack: () => void;
  onOpenAnalysis: () => void;
}
export function AnalysisWithImage({ imageId, meta, onBack, onOpenAnalysis }: Props) {
  const [image, setImage] = useState<ImageDetail | null>(null);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(() => {
    setFailed(false);
    getImage(imageId).then(setImage).catch(() => {
      setImage(null);
      setFailed(true);
    });
  }, [imageId]);

  useEffect(() => { reload(); });
  const [_, setTick] = useState(0);
  // Kept explicit so this shell can refresh from parent if needed later.
  const refresh = useCallback(() => setTick((v) => v + 1), []);
  void refresh;

  const active = image && image.prediction;

  if (failed) {
    return (
      <div className="inline-error patch-load-error" role="alert">
        <span>{t("patch.loadError")}</span>
        <button type="button" className="btn-link" onClick={reload} data-testid="retry-patch">
          {t("common.retry")}
        </button>
        <button type="button" className="btn-link" onClick={onBack}>
          {t("nav.backToWorkbench")}
        </button>
      </div>
    );
  }

  if (!image) return <div className="page-loading">Loading patch…</div>;

  return (
    <div className="analysis-workspace" data-testid="analysis-workspace">
      <button className="btn-link back-link" onClick={onBack}>
        ← {t("nav.backToWorkbench")}
      </button>

      <div className="analysis-toolbar">
        <span className="eyebrow">{t("analysis.title")}</span>
        <div className="pr-image-id">{image.image_id}</div>
        <button type="button" className="btn-link" onClick={onOpenAnalysis} data-testid="open-analysis">
          {t("analysis.title")} →
        </button>
      </div>

      <div className="analysis-main">
        <div className="analysis-image-col">
          <ImageViewer imageId={image.image_id} />
        </div>
        <div className="analysis-side-col">
          {active ? (
            <>
              <Analysis image={image} meta={meta} />
              <div className="analysis-note-hint" data-testid="analysis-note-hint">
                <span className="muted small">{t("editor.expandHint")}</span>
              </div>
            </>
          ) : (
            <div className="empty-state">
              <strong>{t("patch.noPrediction")}</strong>
              <span>{t("patch.noPredictionBody")}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
