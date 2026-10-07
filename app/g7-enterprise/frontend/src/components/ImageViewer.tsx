import { useRef, useState, useCallback, useEffect } from "react";
import { authenticatedImageUrl, fullUrl } from "../api";
import { t } from "../strings";

export function ImageViewer({ imageId }: { imageId: string }) {
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const [loadedImage, setLoadedImage] = useState<{ imageId: string; src: string } | null>(null);
  const [failedImageId, setFailedImageId] = useState<string | null>(null);
  const dragging = useRef<{ x: number; y: number } | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let current = true;
    let objectUrl: string | null = null;
    setLoadedImage(null);
    setFailedImageId(null);
    dragging.current = null;
    setScale(1);
    setTx(0);
    setTy(0);
    authenticatedImageUrl(fullUrl(imageId))
      .then((url) => {
        objectUrl = url;
        if (!current) URL.revokeObjectURL(url);
        else setLoadedImage({ imageId, src: url });
      })
      .catch(() => { if (current) setFailedImageId(imageId); });
    return () => {
      current = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageId, retry]);

  const reset = useCallback(() => {
    setScale(1);
    setTx(0);
    setTy(0);
  }, []);

  const zoom = useCallback((factor: number) => {
    setScale((s) => Math.min(8, Math.max(0.5, +(s * factor).toFixed(3))));
  }, []);

  useEffect(() => {
    const element = stage.current;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15);
    };
    element?.addEventListener("wheel", wheel, { passive: false });
    return () => element?.removeEventListener("wheel", wheel);
  }, [zoom]);

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("button")) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dragging.current = { x: e.clientX - tx, y: e.clientY - ty };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    setTx(e.clientX - dragging.current.x);
    setTy(e.clientY - dragging.current.y);
  };
  const onPointerUp = () => {
    dragging.current = null;
  };

  return (
    <div className="viewer" data-testid="image-viewer">
      <div className="viewer-toolbar">
        <button onClick={() => zoom(1.25)} aria-label={t("viewer.zoomIn")}>+</button>
        <button onClick={() => zoom(1 / 1.25)} aria-label={t("viewer.zoomOut")}>-</button>
        <button onClick={reset} aria-label={t("viewer.reset")}>{t("viewer.reset")}</button>
        <span className="viewer-scale">{Math.round(scale * 100)}%</span>
      </div>
      <div
        className="viewer-stage"
        ref={stage}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onLostPointerCapture={onPointerUp}
      >
        {loadedImage?.imageId === imageId ? (
          <img
            src={loadedImage.src}
            alt={imageId}
            draggable={false}
            style={{ transform: `translate(${tx}px, ${ty}px) scale(${scale})` }}
            onError={() => {
              URL.revokeObjectURL(loadedImage.src);
              setLoadedImage(null);
              setFailedImageId(imageId);
            }}
          />
        ) : failedImageId === imageId ? (
          <div className="img-missing">
            <span className="img-missing-tag">no pixels</span>
            <span>{t("patch.loadError")}</span>
            <button type="button" className="btn" onClick={() => setRetry(n => n + 1)}>Retry image</button>
          </div>
        ) : (
          <div className="img-loading" role="status">Loading image…</div>
        )}
      </div>
    </div>
  );
}
