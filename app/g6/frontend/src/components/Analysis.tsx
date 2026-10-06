import { useEffect, useMemo, useState } from "react";
import { attributionUrl, getAttributionMeta, fullUrl } from "../api";
import type { AttributionMeta, AttributionPair, CanonicalClass, ImageDetail } from "../types";
import type { Meta } from "../types";
import { t } from "../strings";
import { ClassChip, ScoreBars } from "./Shared";

type LoadState = "idle" | "loading" | "ready" | "error";

interface Props {
  image: ImageDetail;
  meta: Meta;
}

export function Analysis({ image }: Props) {
  const [attrib, setAttrib] = useState<AttributionMeta | null>(null);
  const [attribErr, setAttribErr] = useState(false);
  const [pair, setPair] = useState<AttributionPair | null>(null);
  const [showOverlay, setShowOverlay] = useState(true);
  const [opacity, setOpacity] = useState(0.55);
  const [imgState, setImgState] = useState<LoadState>("idle");

  useEffect(() => {
    setAttrib(null);
    setAttribErr(false);
    setPair(null);
    setImgState("idle");
    getAttributionMeta(image.image_id)
      .then((m) => {
        setAttrib(m);
        setPair(m.default_pair);
      })
      .catch(() => setAttribErr(true));
  }, [image.image_id]);

  const overlaySrc = useMemo(
    () => (pair ? attributionUrl(image.image_id, pair.a, pair.b) : ""),
    [image.image_id, pair],
  );

  useEffect(() => {
    if (pair && showOverlay) setImgState("loading");
  }, [pair, showOverlay, image.image_id]);

  const pred = image.prediction;
  const sorted = useMemo(() => {
    if (!pred) return [];
    return Object.entries(pred.scores)
      .map(([k, v]) => [k, v] as const)
      .sort(([, a], [, b]) => b - a);
  }, [pred]);

  const top = sorted[0];
  const second = sorted[1];
  const topClass = top?.[0] as CanonicalClass | undefined;
  const runnerUp = second?.[0] as CanonicalClass | undefined;

  if (attribErr) {
    return (
      <section className="analysis" data-testid="analysis">
        <h3>{t("analysis.title")}</h3>
        <div className="analysis-error" data-testid="analysis-error">
          <p className="muted">{t("analysis.disclosure")}</p>
          <p className="muted small" data-testid="analysis-recovery-disclosure">
            {t("attribution.recoveryDisclosure")}
          </p>
        </div>
      </section>
    );
  }

  if (!attrib || !pair) {
    return (
      <section className="analysis" data-testid="analysis">
        <h3>{t("analysis.title")}</h3>
        <p className="muted" data-testid="analysis-loading">{t("attribution.loading")}</p>
      </section>
    );
  }

  const samePair = (p: AttributionPair, a: string, b: string) => p.a === a && p.b === b;

  const marginRows = pred && (
    <div className="analysis-margin" data-testid="analysis-margin">
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topClass")}</span>
        <span>
          {topClass ? (
            <ClassChip cls={topClass} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{top?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.secondClass")}</span>
        <span>
          {runnerUp ? (
            <ClassChip cls={runnerUp} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{second?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topTwoMargin")}</span>
        <span className="small">{pred.top_two_margin.toFixed(4)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.uncertainty")}</span>
        <span className="small">{pred.normalized_entropy.toFixed(4)}</span>
        <span className="badge badge-uncal">{t("patch.uncalibrated")}</span>
      </div>
    </div>
  );

  return (
    <section className="analysis" data-testid="analysis">
      <h3>{t("analysis.title")}</h3>

      <div className="analysis-context" data-testid="analysis-context">
        <div className="analysis-row">
          <span className="muted small">{t("analysis.sourceGroup")}</span>
          <span>{image.source_group}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.qc")}</span>
          <span>{image.qc.primary_qc_status}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.datasetLabel")}</span>
          <span>{image.qc.original_label ?? "—"}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.trainingEligible")}</span>
          <span>{image.qc.training_eligible ? "yes" : "no"}</span>
        </div>
        <div className="analysis-three-class" data-testid="analysis-three-class">
          <span className="muted small">{t("analysis.threeClassLabel")}</span>
          <span className="small">{t("analysis.threeClassNote")}</span>
        </div>
      </div>

      {pred && (
        <div className="analysis-scores" data-testid="analysis-scores">
          <h4>{t("analysis.scoreReadout")}</h4>
          <ScoreBars pred={pred} />
        </div>
      )}

      <div className="analysis-margin" data-testid="analysis-margin">
        <div className="analysis-row">
          <span className="muted small">{t("analysis.topClass")}</span>
          <span>
            {topClass ? (
              <ClassChip cls={topClass} />
            ) : (
              <span className="muted">{t("metric.notAvailable")}</span>
            )}
          </span>
          <span>{top?.[1].toFixed(3)}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.secondClass")}</span>
          <span>
            {runnerUp ? (
              <ClassChip cls={runnerUp} />
            ) : (
              <span className="muted">{t("metric.notAvailable")}</span>
            )}
          </span>
          <span>{second?.[1].toFixed(3)}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.topTwoMargin")}</span>
          <span className="small">{pred?.top_two_margin.toFixed(4)}</span>
        </div>
        <div className="analysis-row">
          <span className="muted small">{t("analysis.uncertainty")}</span>
          <span className="small">{pred?.normalized_entropy.toFixed(4)}</span>
          <span className="badge badge-uncal">{t("patch.uncalibrated")}</span>
        </div>
      </div>

      {marginRows}

      <div className="analysis-attribution">
        <h4>{t("analysis.suggestedVsRunnerUp")}</h4>

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
              {attrib.pairs.map((p) => (
                <option key={`${p.a}|${p.b}`} value={`${p.a}|${p.b}`}>
                  {t(`class.${p.a}` as const)} {t("attribution.vs")} {t(`class.${p.b}` as const)}
                  {samePair(attrib.default_pair, p.a, p.b) ? "  ★" : ""}
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

        <p className="attrib-hint" data-testid="attribution-hint">
          {t("attribution.contrastHint", {
            a: t(`class.${pair.a}` as const),
            b: t(`class.${pair.b}` as const),
          })}
        </p>

        <div className="attrib-stage" data-testid="attribution-stage">
          <img
            className="attrib-base"
            src={fullUrl(image.image_id)}
            alt={`${t("analysis.originalImage")} ${image.image_id}`}
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
          {t("attribution.method")} · {attrib.recovered_model_id} · {attrib.attribution_target}
        </p>
      </div>
    </section>
  );
}
