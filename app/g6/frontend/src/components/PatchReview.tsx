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

  const reload = useCallback(() => {
    getImage(imageId).then(setImage);
  }, [imageId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    // priority-ordered queue for prev/next
    listImages({ sort: "priority", filter: "all", page: 1, page_size: 60 }).then((d) =>
      setQueue(d.items),
    );
  }, []);

  if (!image) return <div className="muted">…</div>;
  const pred = image.prediction;

  const idx = queue.findIndex((q) => q.image_id === imageId);
  const prev = idx > 0 ? queue[idx - 1] : null;
  const next = idx >= 0 && idx < queue.length - 1 ? queue[idx + 1] : null;

  return (
    <div className="patch-review" data-testid="patch-review">
      {/* LEFT: queue + nav */}
      <aside className="pr-left">
        <button className="btn-link" onClick={onBack}>← {t("nav.backToWorkbench")}</button>
        <div className="pr-nav">
          <button disabled={!prev} onClick={() => prev && onNavigate(prev.image_id)} data-testid="prev-patch">
            {t("nav.prev")}
          </button>
          <button disabled={!next} onClick={() => next && onNavigate(next.image_id)} data-testid="next-patch">
            {t("nav.next")}
          </button>
        </div>
        <ul className="pr-queue">
          {queue.slice(0, 30).map((q) => (
            <li
              key={q.image_id}
              className={q.image_id === imageId ? "active" : ""}
              onClick={() => onNavigate(q.image_id)}
              data-testid={`queue-${q.image_id}`}
            >
              <span className="pr-queue-rank">#{q.review_priority_rank}</span>
              <span className="pr-queue-id">{q.image_id}</span>
              <span className={`dot status-${q.review_state.status}`} />
            </li>
          ))}
        </ul>
      </aside>

      {/* CENTER: image + attribution */}
      <section className="pr-center">
        <div className="pr-image-id">{image.image_id}</div>
        <ImageViewer imageId={image.image_id} />
        <AttributionPanel imageId={image.image_id} />
      </section>

      {/* RIGHT: prediction + review */}
      <aside className="pr-right">
        <Disclaimer />
        {pred && (
          <>
            <div className="pr-suggested" data-testid="suggested-class">
              <span className="pr-suggested-label">{t("patch.suggested")}</span>
              <ClassChip cls={pred.predicted_class} />
            </div>
            <ScoreBars pred={pred} />
            <div className="pr-priority" data-testid="priority-values">
              <div>
                {t("patch.margin")}: <strong>{pred.top_two_margin.toFixed(4)}</strong>
              </div>
              <div>
                {t("patch.entropy")}: <strong>{pred.normalized_entropy.toFixed(4)}</strong>{" "}
                <UncalibratedBadge />
              </div>
              <p className="muted small">{t("patch.priorityNote")}</p>
            </div>
            <div className="pr-meta">
              <h4>{t("patch.metadata")}</h4>
              <div>{t("patch.group")}: {image.source_group}</div>
              <div>{t("patch.qcStatus")}: {image.qc.primary_qc_status}</div>
              <div>{t("patch.originalLabel")}: {image.qc.original_label ?? "—"}</div>
              <QcBadges qc={image.qc} />
            </div>
            <ReviewPanel image={image} meta={meta} onReviewed={reload} />
            <ReviewHistory image={image} />
          </>
        )}
      </aside>
    </div>
  );
}
