import { useCallback, useEffect, useState } from "react";
import { getImage, listImages } from "../api";
import type { CanonicalClass, ImageDetail, ImageSummary, Meta } from "../types";
import { t } from "../strings";
import { ImageViewer } from "./ImageViewer";
import { AttributionPanel } from "./AttributionPanel";
import { ReviewHistory, ReviewPanel } from "./ReviewPanel";
import { ClassChip, Disclaimer, QcBadges, ScoreBars, UncalibratedBadge } from "./Shared";

type SelfCheck = { imageId: string | null; active: boolean; guess: CanonicalClass | null; revealed: boolean };

export function PatchReview({
  imageId,
  meta,
  onBack,
  onNavigate,
  canReview = true,
}: {
  imageId: string;
  meta: Meta;
  canReview?: boolean;
  onBack: () => void;
        onNavigate: (id: string) => void;
}) {
  const [image, setImage] = useState<ImageDetail | null>(null);
  const [queue, setQueue] = useState<ImageSummary[]>([]);
  const [failed, setFailed] = useState(false);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [selfCheck, setSelfCheck] = useState<SelfCheck>({ imageId: null, active: false, guess: null, revealed: false });

  useEffect(() => {
    setSelfCheck({ imageId, active: false, guess: null, revealed: false });
  }, [imageId]);

  useEffect(() => {
    let current = true;
    setImage((loaded) => loaded?.image_id === imageId ? loaded : null);
    setFailed(false);
    getImage(imageId)
      .then((next) => { if (current) setImage(next); })
      .catch(() => { if (current) { setImage(null); setFailed(true); } });
    return () => { current = false; };
  }, [imageId, reloadVersion]);

  const reload = useCallback(() => setReloadVersion((version) => version + 1), []);

  useEffect(() => {
    let current = true;
    listImages({ sort: "priority", filter: "all", page: 1, page_size: 60 })
      .then((d) => { if (current) setQueue(d.items); })
      .catch(() => { if (current) setQueue([]); });
    return () => { current = false; };
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

  if (!image || image.image_id !== imageId) return <div className="page-loading" role="status">Loading patch…</div>;
  const pred = image.prediction;
  const activeCheck = selfCheck.imageId === imageId && selfCheck.active;
  const revealedCheck = activeCheck && selfCheck.revealed;

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
          {pred && (!activeCheck || revealedCheck) && (
            <div className="patch-toolbar-class" data-testid="patch-toolbar-class">
              <span>{t("patch.suggested")}</span>
              <ClassChip cls={pred.predicted_class} />
            </div>
          )}
        </div>
        <ImageViewer imageId={image.image_id} />
        {!activeCheck || revealedCheck ? <AttributionPanel imageId={image.image_id} /> : null}
      </section>

      <aside className="pr-right">
        <div className="panel-heading prediction-heading">
          <span className="eyebrow">{t("patch.reviewEyebrow")}</span>
          <h2>{t("patch.reviewTitle")}</h2>
        </div>
        <Disclaimer />
        {pred ? (
          <>
            <section className="self-check" data-testid="self-check">
              <div className="self-check-heading">
                <div><h3>Self-check</h3><p className="muted small">Choose before revealing the model suggestion. Your practice choice is not saved.</p></div>
                <button type="button" className="btn-link" aria-pressed={activeCheck}
                  onClick={() => setSelfCheck({ imageId, active: !activeCheck, guess: null, revealed: false })}>
                  {activeCheck ? "Exit self-check" : "Try a self-check"}
                </button>
              </div>
              {activeCheck && (
                <>
                  <div className="self-check-choices" role="group" aria-label="Choose a tissue class">
                    {meta.canonical_classes.map((cls) => (
                <button key={cls} type="button" data-testid={`self-check-choice-${cls}`} className={`self-check-choice${selfCheck.guess === cls ? " active" : ""}`}
                        aria-pressed={selfCheck.guess === cls}
                        onClick={() => setSelfCheck({ imageId, active: true, guess: cls, revealed: false })}>
                        <ClassChip cls={cls} />
                      </button>
                    ))}
                  </div>
                  {selfCheck.guess && !revealedCheck && (
                    <button type="button" className="btn-primary" onClick={() => setSelfCheck({ ...selfCheck, revealed: true })}>
                      Reveal comparison
                    </button>
                  )}
                  {revealedCheck && (
                    <div className="self-check-result" role="status">
                      <p>Your selection: <ClassChip cls={selfCheck.guess!} /></p>
                      <p>Model suggestion: <ClassChip cls={pred.predicted_class} /></p>
                      <ScoreBars pred={pred} />
                      <p className="muted small">Agreement is a comparison with this model output, not a measure of correctness.</p>
                    </div>
                  )}
                </>
              )}
            </section>
            {!activeCheck && <div className="pr-suggested" data-testid="suggested-class">
              <span className="pr-suggested-label">{t("patch.suggested")}</span><ClassChip cls={pred.predicted_class} />
            </div>}
            {!activeCheck && <ScoreBars pred={pred} />}
            {(!activeCheck || revealedCheck) && <div className="pr-priority" data-testid="priority-values">
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
            </div>}
            <div className="pr-meta">
              <h4>{t("patch.metadata")}</h4>
              <dl>
                <div><dt>{t("patch.group")}</dt><dd>{image.source_group}</dd></div>
                <div><dt>{t("patch.qcStatus")}</dt><dd>{image.qc.primary_qc_status}</dd></div>
                {(!activeCheck || revealedCheck) && <div><dt>{t("patch.originalLabel")}</dt><dd>{image.qc.original_label ?? "—"}</dd></div>}
              </dl>
              <QcBadges qc={image.qc} />
            </div>
            {(!activeCheck || revealedCheck) && (canReview ? <ReviewPanel image={image} meta={meta} onReviewed={reload} /> : <p role="status" className="muted">Your role can inspect review history but cannot save reviews.</p>)}
            {(!activeCheck || revealedCheck) && <ReviewHistory image={image} />}
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
