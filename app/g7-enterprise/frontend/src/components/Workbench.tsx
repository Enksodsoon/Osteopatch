import { useEffect, useState } from "react";
import { listImages, thumbnailUrl } from "../api";
import type { ImageList, ImageSummary } from "../types";
import { t } from "../strings";
import { ClassChip, QcBadges } from "./Shared";

const FILTERS = [
  "all",
  "unreviewed",
  "reviewed",
  "deferred",
  "pred_NON_TUMOR",
  "pred_VIABLE_TUMOR",
  "pred_NECROSIS",
] as const;

const SORTS = ["priority", "predicted_class", "image_id"] as const;

export function Workbench({ onOpen }: { onOpen: (imageId: string) => void }) {
  const [sort, setSort] = useState<string>("priority");
  const [filter, setFilter] = useState<string>("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ImageList | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFailed(false);
    listImages({ sort, filter, q, page, page_size: 60 })
      .then((d) => {
        if (active) {
          setData(d);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setData(null);
          setFailed(true);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [sort, filter, q, page, reloadKey]);

  return (
    <div className="workbench" data-testid="workbench">
      <section className="workbench-hero">
        <div>
          <div className="eyebrow">{t("workbench.eyebrow")}</div>
          <h1 className="workbench-cta" data-testid="workbench-cta">
            {t("workbench.cta")}
          </h1>
          <p>{t("workbench.intro")}</p>
        </div>
        <div className="hero-callout" aria-label="Review workflow">
          <span className="hero-callout-index">01</span>
          <strong>{t("workbench.calloutTitle")}</strong>
          <span>{t("workbench.calloutBody")}</span>
        </div>
      </section>

      <section className="workbench-toolbar" aria-label="Patch controls">
        <div className="workbench-controls">
          <label>
            <span>{t("workbench.sort")}</span>
            <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }} data-testid="sort-select">
              {SORTS.map((s) => (
                <option key={s} value={s}>{t(`workbench.sort.${s}` as const)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("workbench.filter")}</span>
            <select value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); }} data-testid="filter-select">
              {FILTERS.map((f) => (
                <option key={f} value={f}>{t(`workbench.filter.${f}` as const)}</option>
              ))}
            </select>
          </label>
          <label className="search-field">
            <span>{t("workbench.searchLabel")}</span>
            <input
              type="search"
              placeholder={t("workbench.search")}
              value={q}
              onChange={(e) => { setQ(e.target.value); setPage(1); }}
              data-testid="search-input"
            />
          </label>
        </div>

        {data && (
          <div className="workbench-meta">
            <span className="result-dot" aria-hidden="true" />
            {t("workbench.pageOf", { page: data.page, total: data.total })}
          </div>
        )}
      </section>

      {loading && <div className="gallery-skeleton" aria-label="Loading patches" />}

      {failed && !loading && (
        <div className="inline-error" role="alert">
          <span>{t("workbench.loadError")}</span>
          <button className="btn-link" type="button" onClick={() => setReloadKey((v) => v + 1)}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {data && data.items.length === 0 && !loading && (
        <div className="empty-state" data-testid="workbench-empty">
          <strong>{t("workbench.empty")}</strong>
          <span>{t("workbench.emptyHint")}</span>
        </div>
      )}

      <div className="gallery" data-testid="gallery">
        {data?.items.map((im) => (
          <GalleryCard key={im.image_id} im={im} onOpen={onOpen} />
        ))}
      </div>

      {data && data.total > data.page_size && (
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">←</button>
          <span>{page}</span>
          <button
            disabled={page * data.page_size >= data.total}
            onClick={() => setPage((p) => p + 1)}
            aria-label="Next page"
          >→</button>
        </div>
      )}
    </div>
  );
}

function GalleryCard({ im, onOpen }: { im: ImageSummary; onOpen: (id: string) => void }) {
  const pred = im.prediction;
  return (
    <button
      className="card"
      onClick={() => onOpen(im.image_id)}
      data-testid={`card-${im.image_id}`}
      data-predicted-class={pred?.predicted_class ?? ""}
    >
      <div className="card-thumb">
        <img src={thumbnailUrl(im.image_id)} alt={`Histology patch ${im.image_id}`} loading="lazy" />
        {im.review_priority_rank != null && (
          <span className="card-rank" title={t("workbench.rank")}>
            <span>PRIORITY</span> #{im.review_priority_rank}
          </span>
        )}
        <span className={`card-status status-${im.review_state.status}`}>
          <span className="dot" aria-hidden="true" />
          {t(`status.${im.review_state.status}` as const)}
        </span>
      </div>
      <div className="card-body">
        <div className="card-id">{im.image_id}</div>
        {pred && (
          <div className="card-prediction">
            <ClassChip cls={pred.predicted_class} />
            <div className="card-margin">
              <span>{t("patch.margin")}</span>
              <strong>{pred.top_two_margin.toFixed(3)}</strong>
            </div>
          </div>
        )}
        <QcBadges qc={im.qc} />
      </div>
    </button>
  );
}
