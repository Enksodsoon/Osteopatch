import { useEffect, useState } from "react";
import { getImage } from "../api";
import type { ImageDetail, Meta } from "../types";
import { t } from "../strings";
import { ImageViewer } from "./ImageViewer";
import { Analysis } from "./Analysis";

interface Props {
  imageId: string;
  meta: Meta;
  onBack: () => void;
}

export function AnalysisWithImage({ imageId, meta, onBack }: Props) {
  const [image, setImage] = useState<ImageDetail | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let current = true;
    setImage(null);
    setError(false);
    getImage(imageId)
      .then((next) => { if (current) setImage(next); })
      .catch(() => { if (current) setError(true); });
    return () => { current = false; };
  }, [imageId, retry]);

  if (error) {
    return (
      <div className="inline-error patch-load-error" role="alert">
        <span>{t("patch.loadError")}</span>
        <button type="button" className="btn-link" onClick={() => setRetry((n) => n + 1)} data-testid="retry-patch">
          {t("common.retry")}
        </button>
        <button type="button" className="btn-link" onClick={onBack}>{t("nav.backToWorkbench")}</button>
      </div>
    );
  }

  if (!image || image.image_id !== imageId) return <div className="page-loading" role="status">Loading patch…</div>;

  return (
    <section className="analysis-workspace" data-testid="analysis-workspace">
      <button className="btn-link back-link" onClick={onBack}>← {t("nav.backToWorkbench")}</button>
      <div className="analysis-toolbar">
        <span className="eyebrow">{t("analysis.title")}</span>
        <div className="pr-image-id">{image.image_id}</div>
      </div>
      <div className="analysis-main">
        <div className="analysis-image-col"><ImageViewer imageId={image.image_id} /></div>
        <div className="analysis-side-col">
          {image.prediction ? <Analysis image={image} meta={meta} /> : (
            <div className="empty-state"><strong>{t("patch.noPrediction")}</strong><span>{t("patch.noPredictionBody")}</span></div>
          )}
        </div>
      </div>
    </section>
  );
}
