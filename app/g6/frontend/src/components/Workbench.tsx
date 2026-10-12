import { useEffect, useRef, useState } from "react";
import { listImages, thumbnailUrl } from "../api";
import type { ImageList, ImageSummary } from "../types";
import { t } from "../strings";
import { ClassChip, QcBadges } from "./Shared";
// U003: one read-state vocabulary. The previous `data`/`loading`/`failed`
// booleans could not say "refreshing" or "offline", which is how the previous
// query's cards ended up being presented as the current query's results.
import {
  AsyncStatus,
  beginFetch,
  dataOf,
  isStale,
  rejectFetch,
  resolveFetch,
  type AsyncState,
} from "./AsyncState";
// U001 integration hook: the queue vocabulary now lives with the route parser, so the
// URL validator and these controls cannot drift apart.
import { DEFAULT_CONTEXT, VALID_FILTERS as FILTERS, VALID_SORTS as SORTS, type QueueContext } from "../navigation";

export interface WorkbenchProps {
  onOpen: (imageId: string) => void;
  /** Restored from the URL on a deep link or Back. Omitted = today's defaults. */
  context?: QueueContext;
  /** Reports control edits so the caller can keep the URL in step. */
  onContextChange?: (context: QueueContext) => void;
}

export function Workbench({ onOpen, context, onContextChange }: WorkbenchProps) {
  const [sort, setSort] = useState<string>(context?.sort ?? DEFAULT_CONTEXT.sort);
  const [filter, setFilter] = useState<string>(context?.filter ?? DEFAULT_CONTEXT.filter);
  const [q, setQ] = useState(context?.q ?? DEFAULT_CONTEXT.q);
  const [page, setPage] = useState(context?.page ?? DEFAULT_CONTEXT.page);
  const [state, setState] = useState<AsyncState<ImageList>>({ kind: "idle" });
  const [reloadKey, setReloadKey] = useState(0);
  /** Consecutive retries spent on the CURRENT query; reset when the query changes. */
  const [attempts, setAttempts] = useState<{ key: string; n: number }>({ key: "", n: 0 });
  /** One request at a time, so the retry control can never start a second. */
  const inflight = useRef(false);
  const queryKey = `${sort}|${filter}|${q}|${page}`;
  const tries = attempts.key === queryKey ? attempts.n : 0;
  const list = dataOf(state);

  // The caller re-creates this callback every render, so it is read through a ref:
  // depending on it directly would loop (report -> setState -> new callback -> ...).
  const report = useRef(onContextChange);
  const reported = useRef(false);
  useEffect(() => {
    report.current = onContextChange;
  }, [onContextChange]);
  useEffect(() => {
    if (!report.current) return;
    if (!reported.current) {
      reported.current = true; // don't echo the context we were just handed
      return;
    }
    report.current({ sort, filter, q, page });
  }, [sort, filter, q, page]);

  useEffect(() => {
    // A real abort, not just an ignore flag: a superseded query stops consuming
    // the connection and its response can never overwrite the newer one.
    const controller = new AbortController();
    inflight.current = true;
    setState((prev) => beginFetch(prev));
    const filtered = filter !== "all" || q.trim() !== "";
    listImages({ sort, filter, q, page, page_size: 60 }, { signal: controller.signal })
      .then((d) => {
        if (controller.signal.aborted) return;
        inflight.current = false;
        setState((prev) => resolveFetch(prev, d, { filtered }));
        setAttempts({ key: queryKey, n: 0 });
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        inflight.current = false;
        // Previous rows are kept and marked stale rather than thrown away, and an
        // abort of our own making leaves the state alone.
        setState((prev) => rejectFetch(prev, err));
      });
    return () => {
      controller.abort();
    };
  }, [sort, filter, q, page, reloadKey]);

  const retry = () => {
    if (inflight.current) return;
    setAttempts({ key: queryKey, n: tries + 1 });
    setReloadKey((v) => v + 1);
  };

  return (
    <div className="workbench" data-testid="workbench" data-async-state={state.kind}>
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

        {list && (
          <div className="workbench-meta">
            <span className="result-dot" aria-hidden="true" />
            {t("workbench.pageOf", { page: list.page, total: list.total })}
          </div>
        )}
      </section>

      <AsyncStatus state={state} onRetry={retry} attempts={tries} inFlight={inflight.current} />

      <div className="gallery" data-testid="gallery" data-stale={isStale(state)}>
        {list?.items.map((im) => (
          <GalleryCard key={im.image_id} im={im} onOpen={onOpen} />
        ))}
      </div>

      {list && list.total > list.page_size && (
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">←</button>
          <span>{page}</span>
          <button
            disabled={page * list.page_size >= list.total}
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
