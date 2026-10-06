import { useEffect, useState } from "react";
import { listImages, thumbnailUrl } from "../api";
import type { ImageList, ImageSummary } from "../types";
import { t } from "../strings";
import { ImageViewer } from "./ImageViewer";

interface Props {
  onOpen: (imageId: string) => void;
}

export function Library({ onOpen }: Props) {
  void onOpen;
  const [data, setData] = useState<ImageList | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFailed(false);
    listImages({ sort: "image_id", filter: "all", page: 1, page_size: 240 })
      .then((d) => {
        if (active) setData(d);
        if (active) setLoading(false);
      })
      .catch(() => {
        if (active) setFailed(true);
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedImg = data?.items.find((im) => im.image_id === selected);

  return (
    <div className="library" data-testid="library">
      <div className="library-toolbar">
        <div className="panel-heading">
          <span className="eyebrow">{t("library.title")}</span>
          <h2>{t("library.title")}</h2>
        </div>
        {data && (
          <div className="workbench-meta">
            <span className="result-dot" aria-hidden="true" />
            {t("workbench.pageOf", { page: 1, total: data.total })}
          </div>
        )}
      </div>

      {loading && <div className="gallery-skeleton" aria-label="Loading library" />}

      {failed && !loading && (
        <div className="inline-error" role="alert">
          <span>{t("workbench.loadError")}</span>
          <button type="button" className="btn-link" onClick={() => window.location.reload()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {data && data.items.length === 0 && !loading && (
        <div className="empty-state" data-testid="library-empty">
          <strong>{t("library.empty")}</strong>
        </div>
      )}

      <div className="library-grid" data-testid="library-grid">
        {data?.items.map((im) => (
          <LibraryCard
            key={im.image_id}
            im={im}
            selected={selected === im.image_id}
            onClick={() => setSelected(im.image_id)}
          />
        ))}
      </div>

      {selectedImg && (
        <div className="library-viewer" data-testid="library-viewer">
          <div className="library-viewer-head">
            <span className="eyebrow">{t("patch.viewerEyebrow")}</span>
            <div className="pr-image-id">{selectedImg.image_id}</div>
            <button
              type="button"
              className="btn-link"
              onClick={() => setSelected(null)}
              data-testid="library-viewer-close"
            >
              ✕
            </button>
          </div>
          <ImageViewer imageId={selectedImg.image_id} />
        </div>
      )}
    </div>
  );
}

function LibraryCard({ im, selected, onClick }: { im: ImageSummary; selected: boolean; onClick: () => void }) {
  return (
    <button
      className={`card library-card${selected ? " selected" : ""}`}
      onClick={onClick}
      data-testid={`library-card-${im.image_id}`}
    >
      <div className="card-thumb">
        <img src={thumbnailUrl(im.image_id)} alt={`Histology patch ${im.image_id}`} loading="lazy" />
      </div>
      <div className="card-body">
        <div className="card-id">{im.image_id}</div>
        {im.prediction && (
          <div className="card-prediction">
            <span className="muted small">{t("patch.suggested")}</span>
            <span className="mono small">{im.prediction.predicted_class}</span>
          </div>
        )}
      </div>
    </button>
  );
}
