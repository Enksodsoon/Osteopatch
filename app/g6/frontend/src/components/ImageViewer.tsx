import { useRef, useState, useCallback, useEffect } from "react";
import { fullUrl } from "../api";
import { t } from "../strings";

// Large histology image with zoom (wheel + buttons) and pan (drag). The full
// image is loaded only when a patch is selected (this component mounts).
export function ImageViewer({ imageId }: { imageId: string }) {
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const dragging = useRef<{ x: number; y: number } | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    setScale(1);
    setTx(0);
    setTy(0);
    setLoaded(false);
    setFailed(false);
    dragging.current = null;
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
        <button onClick={() => zoom(1.25)} aria-label={t("viewer.zoomIn")}>＋</button>
        <button onClick={() => zoom(1 / 1.25)} aria-label={t("viewer.zoomOut")}>－</button>
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
        {!loaded && !failed && <div className="img-loading" role="status">Loading image…</div>}
        {failed ? <div className="img-missing" role="alert"><span className="img-missing-tag">no pixels</span>{t("patch.loadError")}<button type="button" onClick={() => setRetry(n => n + 1)}>Retry image</button></div> : <img
          key={`${imageId}-${retry}`}
          src={fullUrl(imageId)}
          alt={imageId}
          draggable={false}
          style={{ transform: `translate(${tx}px, ${ty}px) scale(${scale})`, visibility: loaded ? "visible" : "hidden" }}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />}
      </div>
    </div>
  );
}
