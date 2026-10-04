import { useEffect, useMemo, useState } from "react";
import { attributionUrl, getAttributionMeta, fullUrl } from "../api";
import type { AttributionMeta, AttributionPair, CanonicalClass } from "../types";
import { t } from "../strings";

type LoadState = "idle" | "loading" | "ready" | "error";

/**
 * Image-scoped contrastive attribution panel.
 *
 * Honest by construction:
 *  - the overlay <img> only renders on a successful (onLoad) load; onError flips
 *    to an explicit error state and shows NO heatmap (never a fabricated one);
 *  - the recovery disclosure + "not segmentation" disclaimer are always visible,
 *    not hidden behind a toggle;
 *  - the contrastive hint names the exact A-vs-B comparison currently shown.
 */
export function AttributionPanel({ imageId }: { imageId: string }) {
  const [meta, setMeta] = useState<AttributionMeta | null>(null);
  const [metaErr, setMetaErr] = useState(false);
  const [pair, setPair] = useState<AttributionPair | null>(null);
  const [showOverlay, setShowOverlay] = useState(true);
  const [opacity, setOpacity] = useState(0.55);
  const [imgState, setImgState] = useState<LoadState>("idle");

  // reset when the patch changes
  useEffect(() => {
    setMeta(null);
    setMetaErr(false);
    setPair(null);
    setImgState("idle");
    getAttributionMeta(imageId)
      .then((m) => {
        setMeta(m);
        setPair(m.default_pair);
      })
      .catch(() => setMetaErr(true));
  }, [imageId]);

  const overlaySrc = useMemo(
    () => (pair ? attributionUrl(imageId, pair.a, pair.b) : ""),
    [imageId, pair],
  );

  // begin loading whenever the pair changes and overlay is on
  useEffect(() => {
    if (pair && showOverlay) setImgState("loading");
  }, [pair, showOverlay, imageId]);

  if (metaErr) {
    return (
      <div className="attrib-panel" data-testid="attribution-panel">
        <h4>{t("attribution.heading")}</h4>
        <p className="attrib-error" role="alert" data-testid="attribution-error">
          {t("attribution.error")}
        </p>
        <p className="muted small" data-testid="attribution-recovery-disclosure">
          {t("attribution.recoveryDisclosure")}
        </p>
      </div>
    );
  }

  if (!meta || !pair) {
    return (
      <div className="attrib-panel" data-testid="attribution-panel">
        <h4>{t("attribution.heading")}</h4>
        <p className="muted" data-testid="attribution-loading">{t("attribution.loading")}</p>
      </div>
    );
  }

  const samePair = (p: AttributionPair, a: string, b: string) => p.a === a && p.b === b;

  return (
    <div className="attrib-panel" data-testid="attribution-panel">
      <h4>{t("attribution.heading")}</h4>

      {/* contrastive comparison selector — 6 ordered pairs */}
      <div className="attrib-controls">
        <label className="attrib-compare">
          {t("attribution.compareLabel")}
          <select
            data-testid="attribution-pair"
            value={`${pair.a}|${pair.b}`}
            onChange={(e) => {
              const [a, b] = e.target.value.split("|") as [CanonicalClass, CanonicalClass];
              setPair({ a, b });
            }}
          >
            {meta.pairs.map((p) => (
              <option key={`${p.a}|${p.b}`} value={`${p.a}|${p.b}`}>
                {t(`class.${p.a}` as const)} {t("attribution.vs")} {t(`class.${p.b}` as const)}
                {samePair(meta.default_pair, p.a, p.b) ? "  ★" : ""}
              </option>
            ))}
          </select>
        </label>

        <label className="attrib-toggle">
          <input
            type="checkbox"
            data-testid="attribution-overlay-toggle"
            checked={showOverlay}
            onChange={(e) => setShowOverlay(e.target.checked)}
          />
          {t("attribution.showOverlay")}
        </label>

        <label className="attrib-opacity">
          {t("attribution.opacity")}
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={opacity}
            data-testid="attribution-opacity"
            disabled={!showOverlay}
            onChange={(e) => setOpacity(Number(e.target.value))}
          />
          <span className="mono">{Math.round(opacity * 100)}%</span>
        </label>
      </div>

      {/* contrastive hint naming the exact A-vs-B shown */}
      <p className="attrib-hint" data-testid="attribution-hint">
        {t("attribution.contrastHint", {
          a: t(`class.${pair.a}` as const),
          b: t(`class.${pair.b}` as const),
        })}
      </p>

      {/* image stack: original + optional overlay. Overlay only shows on load. */}
      <div className="attrib-stage" data-testid="attribution-stage">
        <img
          className="attrib-base"
          src={fullUrl(imageId)}
          alt={`${t("attribution.originalView")} ${imageId}`}
          draggable={false}
        />
        {showOverlay && imgState !== "error" && (
          <img
            className="attrib-overlay"
            src={overlaySrc}
            alt={`attribution ${pair.a} vs ${pair.b}`}
            draggable={false}
            style={{ opacity, display: imgState === "ready" ? "block" : "none" }}
            data-testid="attribution-overlay-img"
            onLoad={() => setImgState("ready")}
            onError={() => setImgState("error")}
          />
        )}
        {showOverlay && imgState === "loading" && (
          <div className="attrib-loading" data-testid="attribution-loading">
            {t("attribution.loading")}
          </div>
        )}
        {showOverlay && imgState === "error" && (
          <div className="attrib-error" role="alert" data-testid="attribution-error">
            {t("attribution.error")}
          </div>
        )}
      </div>

      {/* always-visible disclaimers + recovery disclosure */}
      <p className="muted small" data-testid="attribution-default-note">
        {t("attribution.defaultNote")}
      </p>
      <p className="muted small" data-testid="attribution-not-segmentation">
        {t("attribution.notSegmentation")}
      </p>
      <p className="attrib-disclosure small" data-testid="attribution-recovery-disclosure">
        {t("attribution.recoveryDisclosure")}
      </p>
      <p className="muted small">
        {t("attribution.method")} · {meta.recovered_model_id} · {meta.attribution_target}
      </p>
    </div>
  );
}
