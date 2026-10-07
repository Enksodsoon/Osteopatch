import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { PointerEvent } from "react";
import type OpenSeadragon from "openseadragon";
import * as api from "../api";
import type { LivePrediction, LiveTile } from "../types";

export type ViewerAnnotation = api.SlideRegion & { id: string };
export type DeepZoomViewerHandle = {
  zoom: (factor: number) => void;
  fit: () => void;
  focus: (region: api.SlideRegion) => void;
  fullscreen: () => void;
};

type Props = {
  slide: api.SlideMeta;
  mode: "pan" | "annotate";
  annotations: ViewerAnnotation[];
  selected: string | null;
  analysisTiles: LiveTile[];
  analysisRegion: api.SlideRegion | null;
  prediction: LivePrediction | null;
  showAnalysisMap: boolean;
  onViewChange: (view: api.SlideRegion) => void;
  onAddAnnotation: (region: api.SlideRegion) => void;
};

function tileClass(tile: LiveTile) {
  return tile.decode_error || tile.confidence === "indeterminate" || !tile.predicted_class
    ? "uncertain" : `cl-${tile.predicted_class}`;
}

function niceDistance(raw: number) {
  if (!Number.isFinite(raw) || raw <= 0) return 1;
  const unit = 10 ** Math.floor(Math.log10(raw));
  const ratio = raw / unit;
  return (ratio >= 5 ? 5 : ratio >= 2 ? 2 : 1) * unit;
}

export const DeepZoomViewer = forwardRef<DeepZoomViewerHandle, Props>(function DeepZoomViewer({
  slide, mode, annotations, selected, analysisTiles, analysisRegion, prediction,
  showAnalysisMap, onViewChange, onAddAnnotation,
}, forwardedRef) {
  const host = useRef<HTMLDivElement>(null);
  const overlay = useRef<SVGSVGElement>(null);
  const viewer = useRef<OpenSeadragon.Viewer | null>(null);
  const osdLibrary = useRef<typeof OpenSeadragon | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [viewport, setViewport] = useState<api.SlideRegion>({ x: 0, y: 0, width: slide.width, height: slide.height });
  const [ready, setReady] = useState(false);
  const [tileError, setTileError] = useState<string | null>(null);
  const [draft, setDraft] = useState<api.SlideRegion | null>(null);
  const onViewChangeRef = useRef(onViewChange);
  const onAddAnnotationRef = useRef(onAddAnnotation);

  useEffect(() => { onViewChangeRef.current = onViewChange; }, [onViewChange]);
  useEffect(() => { onAddAnnotationRef.current = onAddAnnotation; }, [onAddAnnotation]);

  useEffect(() => {
    if (!host.current) return;
    let stopped = false;
    let frame = 0;
    let observer: ResizeObserver | null = null;
    let instance: OpenSeadragon.Viewer | null = null;
    void import("openseadragon").then(({ default: OpenSeadragon }) => {
      if (stopped || !host.current) return;
      osdLibrary.current = OpenSeadragon;
      instance = OpenSeadragon({
      element: host.current,
      showNavigationControl: false,
      showNavigator: true,
      navigatorPosition: "TOP_RIGHT",
      navigatorSizeRatio: 0.16,
      navigatorAutoFade: false,
      navigatorBorderColor: "#dbc9b9",
      navigatorDisplayRegionColor: "#b85134",
      navigatorBackground: "#211b18",
      loadTilesWithAjax: true,
      ajaxHeaders: api.slideTileHeaders(),
      tileRetryMax: 2,
      tileRetryDelay: 400,
      animationTime: 0.22,
      blendTime: 0.08,
      maxZoomPixelRatio: 2,
      minZoomImageRatio: 0.7,
      visibilityRatio: 1,
      gestureSettingsMouse: { clickToZoom: false, dblClickToZoom: true, dragToPan: true, scrollToZoom: false },
      });
      viewer.current = instance;
      const updateViewport = (current = true) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const item = instance?.world.getItemAt(0);
        if (!item || !instance?.isOpen()) return;
        const bounds = item.viewportToImageRectangle(instance.viewport.getBounds(current));
        const x = Math.max(0, Math.floor(bounds.x));
        const y = Math.max(0, Math.floor(bounds.y));
        const right = Math.min(slide.width, Math.ceil(bounds.x + bounds.width));
        const bottom = Math.min(slide.height, Math.ceil(bounds.y + bounds.height));
        if (right > x && bottom > y) {
          const next = { x, y, width: right - x, height: bottom - y };
          setViewport(next);
          onViewChangeRef.current(next);
        }
        setCanvasSize({ width: instance.container.clientWidth, height: instance.container.clientHeight });
      });
      };
      instance.addHandler("open", () => { setReady(true); setTileError(null); updateViewport(); });
      instance.addHandler("viewport-change", () => updateViewport());
      instance.addHandler("resize", () => updateViewport());
      instance.addHandler("canvas-scroll", event => {
        event.preventDefaultAction = true;
        instance?.viewport.zoomBy(Math.pow(1.2, event.scroll));
        instance?.viewport.applyConstraints();
        if (frame) { cancelAnimationFrame(frame); frame = 0; }
        updateViewport(false);
      });
      instance.addHandler("tile-load-failed", () => setTileError("Some slide tiles could not be loaded. Check the connection, then retry."));
      instance.addHandler("open-failed", () => setTileError("The slide could not be opened. Try refreshing the slide library."));
      observer = new ResizeObserver(() => instance?.forceResize());
      observer.observe(host.current);
      instance.open({
      tileSource: {
        width: slide.width,
        height: slide.height,
        tileSize: slide.tile_size || 256,
        tileOverlap: 0,
        minLevel: 0,
        maxLevel: Math.ceil(Math.log2(Math.max(slide.width, slide.height))),
        getTileUrl: (level: number, x: number, y: number) => api.slideTilePath(slide.slide_id, level, x, y),
      },
      });
    }).catch(() => setTileError("The slide viewer could not start. Reload the page and try again."));
    return () => {
      stopped = true;
      observer?.disconnect();
      if (frame) cancelAnimationFrame(frame);
      instance?.destroy();
      viewer.current = null;
      osdLibrary.current = null;
    };
  }, [slide.slide_id, slide.width, slide.height, slide.tile_size]);

  useEffect(() => { viewer.current?.setMouseNavEnabled(mode === "pan"); }, [mode]);

  useImperativeHandle(forwardedRef, () => ({
    zoom: factor => { viewer.current?.viewport.zoomBy(factor); viewer.current?.viewport.applyConstraints(); },
    fit: () => viewer.current?.viewport.goHome(),
    focus: region => {
      const item = viewer.current?.world.getItemAt(0);
      if (!item) return;
      const bounds = item.imageToViewportRectangle(region.x, region.y, region.width, region.height);
      viewer.current?.viewport.fitBounds(bounds);
    },
    fullscreen: () => viewer.current?.setFullScreen(!viewer.current?.isFullScreen()),
  }), []);

  function imagePoint(event: PointerEvent<SVGSVGElement>) {
    const instance = viewer.current;
    if (!instance) return { x: 0, y: 0 };
    const rect = event.currentTarget.getBoundingClientRect();
    const Point = osdLibrary.current?.Point;
    if (!Point) return { x: 0, y: 0 };
    const point = instance.viewport.pointFromPixel(new Point(event.clientX - rect.left, event.clientY - rect.top), true);
    const image = instance.world.getItemAt(0)?.viewportToImageCoordinates(point);
    return { x: Math.max(0, Math.min(slide.width, image?.x ?? 0)), y: Math.max(0, Math.min(slide.height, image?.y ?? 0)) };
  }

  function rectangle(end: { x: number; y: number }) {
    const origin = start.current!;
    return {
      x: Math.round(Math.min(origin.x, end.x)), y: Math.round(Math.min(origin.y, end.y)),
      width: Math.round(Math.abs(end.x - origin.x)), height: Math.round(Math.abs(end.y - origin.y)),
    };
  }

  function screenRect(region: api.SlideRegion) {
    const item = viewer.current?.world.getItemAt(0);
    if (!item) return null;
    const Point = osdLibrary.current?.Point;
    if (!Point) return null;
    const topLeft = item.imageToViewerElementCoordinates(new Point(region.x, region.y));
    const bottomRight = item.imageToViewerElementCoordinates(new Point(region.x + region.width, region.y + region.height));
    return { x: topLeft.x, y: topLeft.y, width: bottomRight.x - topLeft.x, height: bottomRight.y - topLeft.y };
  }

  const pixelsPerImagePixel = canvasSize.width / Math.max(1, viewport.width);
  const scalePixels = niceDistance(84 / Math.max(0.000001, pixelsPerImagePixel));
  const scaleLength = scalePixels * pixelsPerImagePixel;
  const physicalScale = slide.mpp_x ? scalePixels * slide.mpp_x : null;
  const scaleLabel = physicalScale === null ? `${Math.round(scalePixels).toLocaleString()} px`
    : physicalScale >= 1000 ? `${(physicalScale / 1000).toPrecision(2)} mm` : `${Math.round(physicalScale)} µm`;

  return <div className={`wsi-viewport mode-${mode}`} data-testid="slide-canvas" data-ready={ready}>
    <div ref={host} className="openseadragon-host" role="img" aria-label={`Tiled whole-slide viewer for ${slide.filename}. Scroll or pinch to zoom; drag to pan; use the navigator to move across the slide.`} />
    <svg ref={overlay} className="wsi-overlay" viewBox={`0 0 ${canvasSize.width} ${canvasSize.height}`} preserveAspectRatio="none"
      role="img" aria-label="Slide annotations and analyzed regions" tabIndex={mode === "annotate" ? 0 : -1}
      onPointerDown={event => {
        if (mode !== "annotate" || event.button !== 0) return;
        start.current = imagePoint(event); setDraft({ ...start.current, width: 0, height: 0 });
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={event => { if (start.current && mode === "annotate") setDraft(rectangle(imagePoint(event))); }}
      onPointerUp={event => {
        if (!start.current) return;
        const region = rectangle(imagePoint(event));
        if (region.width > 2 && region.height > 2) onAddAnnotationRef.current(region);
        start.current = null; setDraft(null);
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={() => { start.current = null; setDraft(null); }}>
      {showAnalysisMap && analysisTiles.map(tile => {
        const box = screenRect(tile);
        return box && <rect key={`tile-${tile.tile_index}`} {...box} className={`analysis-tile ${tileClass(tile)}`} data-testid="analysis-tile" aria-hidden="true" />;
      })}
      {showAnalysisMap && analysisRegion && prediction && (() => {
        const box = screenRect(analysisRegion);
        return box && <rect {...box} className={`analysis-region ${prediction.confidence === "indeterminate" ? "uncertain" : `cl-${prediction.predicted_class}`}`} data-testid="analysis-region" aria-hidden="true" />;
      })()}
      {annotations.map(annotation => {
        const box = screenRect(annotation);
        return box && <rect key={annotation.id} {...box} className={selected === annotation.id ? "annotation selected" : "annotation"} vectorEffect="non-scaling-stroke" />;
      })}
      {draft && (() => { const box = screenRect(draft); return box && <rect {...box} className="annotation selected" vectorEffect="non-scaling-stroke" />; })()}
    </svg>
    {!ready && <div className="wsi-loading" role="status">Loading slide tiles…</div>}
    {tileError && <div className="wsi-error" role="alert"><span>{tileError}</span><button onClick={() => { setTileError(null); viewer.current?.forceResize(); viewer.current?.viewport.applyConstraints(); }}>Retry</button></div>}
    {canvasSize.width > 0 && <div className="wsi-scale" aria-label={`Scale bar: ${scaleLabel}`}>
      <span className="wsi-scale-line" style={{ width: Math.max(28, Math.min(150, scaleLength)) }} />
      <span>{scaleLabel}</span>
    </div>}
  </div>;
});
