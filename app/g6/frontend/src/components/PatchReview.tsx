import { useCallback, useEffect, useState } from "react";
import { getImage, listImages } from "../api";
import type { ImageDetail, ImageSummary, Meta } from "../types";
import { t } from "../strings";
import { ImageViewer } from "./ImageViewer";
import { AttributionPanel } from "./AttributionPanel";
import { ReviewHistory, ReviewPanel } from "./ReviewPanel";
import { ClassChip, Disclaimer, QcBadges, ScoreBars, UncalibratedBadge } from "./Shared";

export function PatchReview({
  imageId,
  meta,
  onBack,
  onNavigate,
}: {
  imageId: string;
  meta: Meta;
  onBack: () => void;
  onNavigate: (id: string) => void;
}) {
  const [image, setImage] = useState<ImageDetail | null>(null);
  const [queue, setQueue] = useState<ImageSummary[]>([]);
  const [failed, setFailed] = useState(false);

  const reload = useCallback(() => {
    setFailed(false);
    getImage(imageId)
      .then(setImage)
      .catch(() => {
        setImage(null);
        setFailed(true);
      });
  }, [imageId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    listImages({ sort: "priority", filter: "all", page: 1, page_size: 60 })
      .then((d) => setQueue(d.items))
      .catch(() => setQueue([]));
  }, []);

  if (failed) {
    return (
      <div className="inline-error patch-load-error" role="alert">
        <span>{t("patch.loadError")}</span>
        <button type="button" className="btn-link" onClick={reload}>{t("common.retry")}</button>
        <button type="button" className="btn-link" onClick={onBack}>{t("nav.backToWorkbench")}</button>
      </div>
    );
  }

  if (!image) return <div className="page-loading">Loading patch…</div>;
  const pred = image.prediction;

  const idx = queue.findIndex((q) => q.image_id === imageId);
  const prev = idx > 0 ? queue[idx - 1] : null;
  const next = idx >= 0 && idx < queue.length - 1 ? queue[idx + 1] : null;

  return (
    <div className="patch-review" data-testid="patch-review">
      <aside className="pr-left">
        <button className="btn-link back-link" onClick={onBack}>← {t("nav.backToWorkbench")}</button>

        <div className="panel-heading">
          <span className="eyebrow">{t("patch.queueEyebrow")}</span>
          <h2>{t("patch.queueTitle")}</h2>
          <p>{t("patch.queueBody")}</p>
        </div>

        <div className="pr-nav">
          <button disabled={!prev} onClick={() => prev && onNavigate(prev.image_id)} data-testid="prev-patch">
            ← {t("nav.prev")}
          </button>
          <button disabled={!next} onClick={() => next && onNavigate(next.image_id)} data-testid="next-patch">
            {t("nav.next")} →
          </button>
        </div>

        <ul className="pr-queue">
          {queue.slice(0, 30).map((q) => (
            <li key={q.image_id}>
              <button
                type="button"
                className={q.image_id === imageId ? "active" : ""}
                onClick={() => onNavigate(q.image_id)}
                data-testid={`queue-${q.image_id}`}
                aria-current={q.image_id === imageId ? "true" : undefined}
              >
                <span className="pr-queue-rank">#{q.review_priority_rank}</span>
                <span className="pr-queue-id">{q.image_id}</span>
                <span className={`dot status-${q.review_state.status}`} aria-label={q.review_state.status} />
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="pr-center">
        <div className="patch-toolbar">
          <div>
            <span className="eyebrow">{t("patch.viewerEyebrow")}</span>
            <div className="pr-image-id">{image.image_id}</div>
          </div>
          {pred && (
            <div className="patch-toolbar-class">
              <span>{t("patch.suggested")}</span>
              <ClassChip cls={pred.predicted_class} />
            </div>
          )}
        </div>
        <ImageViewer imageId={image.image_id} />
        <AttributionPanel imageId={image.image_id} />
      </section>

      <aside className="pr-right">
        <div className="panel-heading prediction-heading">
          <span className="eyebrow">{t("patch.reviewEyebrow")}</span>
          <h2>{t("patch.reviewTitle")}</h2>
        </div>
        <Disclaimer />
        {pred ? (
          <>
            <div className="pr-suggested" data-testid="suggested-class">
              <span className="pr-suggested-label">{t("patch.suggested")}</span>
              <ClassChip cls={pred.predicted_class} />
            </div>
            <ScoreBars pred={pred} />
            <div className="pr-priority" data-testid="priority-values">
              <div className="metric-row">
                <span>{t("patch.margin")}</span>
                <strong>{pred.top_two_margin.toFixed(4)}</strong>
              </div>
              <div className="metric-row">
                <span>{t("patch.entropy")}</span>
                <strong>{pred.normalized_entropy.toFixed(4)}</strong>
                <UncalibratedBadge />
              </div>
              <p className="muted small">{t("patch.priorityNote")}</p>
            </div>
            <div className="pr-meta">
              <h4>{t("patch.metadata")}</h4>
              <dl>
                <div><dt>{t("patch.group")}</dt><dd>{image.source_group}</dd></div>
                <div><dt>{t("patch.qcStatus")}</dt><dd>{image.qc.primary_qc_status}</dd></div>
                <div><dt>{t("patch.originalLabel")}</dt><dd>{image.qc.original_label ?? "—"}</dd></div>
              </dl>
              <QcBadges qc={image.qc} />
            </div>
            <ReviewPanel image={image} meta={meta} onReviewed={reload} />
            <ReviewHistory image={image} />
          </>
        ) : (
          <div className="empty-state">
            <strong>{t("patch.noPrediction")}</strong>
            <span>{t("patch.noPredictionBody")}</span>
          </div>
        )}
      </aside>
    </div>
  );
}
