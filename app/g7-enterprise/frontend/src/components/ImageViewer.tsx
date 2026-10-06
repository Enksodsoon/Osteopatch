import { useRef, useState, useCallback, useEffect } from "react";
import { fullUrl } from "../api";
import { t } from "../strings";

export function ImageViewer({ imageId }: { imageId: string }) {
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const dragging = useRef<{ x: number; y: number } | null>(null);

  const loadImage = useCallback(async () => {
    try {
      const { authenticatedImageUrl } = await import("../api");
      const url = await authenticatedImageUrl(fullUrl(imageId));
      setImgSrc(url);
    } catch {
      setImgSrc(null);
    }
  }, [imageId]);

  useEffect(() => {
    loadImage();
    return () => { if (imgSrc) URL.revokeObjectURL(imgSrc); };
  }, [loadImage, imgSrc]);

  const reset = useCallback(() => {
    setScale(1);
    setTx(0);
    setTy(0);
  }, []);

  const zoom = useCallback((factor: number) => {
    setScale((s) => Math.min(8, Math.max(0.5, +(s * factor).toFixed(3))));
  }, []);

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15);
  };

  const onPointerDown = (e: React.PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
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
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {imgSrc ? (
          <img
            src={imgSrc}
            alt={imageId}
            draggable={false}
            style={{ transform: `translate(${tx}px, ${ty}px) scale(${scale})` }}
          />
        ) : (
          <div className="img-missing">
            <span className="img-missing-tag">no pixels</span>
            <span>{t("patch.loadError")}</span>
          </div>
        )}
      </div>
    </div>
  );
}
