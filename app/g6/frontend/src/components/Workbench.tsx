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

  useEffect(() => {
    let active = true;
    setLoading(true);
    listImages({ sort, filter, q, page, page_size: 60 }).then((d) => {
      if (active) {
        setData(d);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [sort, filter, q, page]);

  return (
    <div className="workbench" data-testid="workbench">
      <div className="workbench-cta" data-testid="workbench-cta">
        {t("workbench.cta")}
      </div>

      <div className="workbench-controls">
        <label>
          {t("workbench.sort")}
          <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }} data-testid="sort-select">
            {SORTS.map((s) => (
              <option key={s} value={s}>{t(`workbench.sort.${s}` as const)}</option>
            ))}
          </select>
        </label>
        <label>
          {t("workbench.filter")}
          <select value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); }} data-testid="filter-select">
            {FILTERS.map((f) => (
              <option key={f} value={f}>{t(`workbench.filter.${f}` as const)}</option>
            ))}
          </select>
        </label>
        <input
          type="search"
          placeholder={t("workbench.search")}
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          data-testid="search-input"
        />
      </div>

      {data && (
        <div className="workbench-meta">
          {t("workbench.pageOf", { page: data.page, total: data.total })}
        </div>
      )}

      {loading && <div className="muted">…</div>}
      {data && data.items.length === 0 && !loading && (
        <div className="muted" data-testid="workbench-empty">{t("workbench.empty")}</div>
      )}

      <div className="gallery" data-testid="gallery">
        {data?.items.map((im) => (
          <GalleryCard key={im.image_id} im={im} onOpen={onOpen} />
        ))}
      </div>

      {data && data.total > data.page_size && (
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>←</button>
          <span>{page}</span>
          <button
            disabled={page * data.page_size >= data.total}
            onClick={() => setPage((p) => p + 1)}
          >→</button>
        </div>
      )}
    </div>
  );
}

function GalleryCard({ im, onOpen }: { im: ImageSummary; onOpen: (id: string) => void }) {
  const pred = im.prediction;
  return (
    <button className="card" onClick={() => onOpen(im.image_id)} data-testid={`card-${im.image_id}`}>
      <div className="card-thumb">
        <img src={thumbnailUrl(im.image_id)} alt={im.image_id} loading="lazy" />
        {im.review_priority_rank != null && (
          <span className="card-rank" title={t("workbench.rank")}>#{im.review_priority_rank}</span>
        )}
        <span className={`card-status status-${im.review_state.status}`}>
          {t(`status.${im.review_state.status}` as const)}
        </span>
      </div>
      <div className="card-body">
        <div className="card-id">{im.image_id}</div>
        {pred && (
          <>
            <ClassChip cls={pred.predicted_class} />
            <div className="card-margin">
              {t("patch.margin")}: {pred.top_two_margin.toFixed(3)}
            </div>
          </>
        )}
        <QcBadges qc={im.qc} />
      </div>
    </button>
  );
}
