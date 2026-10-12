import { useEffect, useState } from "react";
import { getAttributionMeta } from "../api";
import type { AttributionMeta, CanonicalClass, ImageDetail, Meta } from "../types";
import { t } from "../strings";
import { ClassChip, ScoreBars } from "./Shared";
import { ImageViewer } from "./ImageViewer";
import { Analysis } from "./Analysis";
type LoadState = "idle" | "loading" | "ready" | "error";

interface Props {
  image: ImageDetail;
}

export function AnalysisPanel({ image }: Props) {
  const [attrib, setAttrib] = useState<AttributionMeta | null>(null);
  const [attribErr, setAttribErr] = useState(false);
  const [pair, setPair] = useState<{ a: CanonicalClass; b: CanonicalClass } | null>(null);
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

  const overlaySrcY = pair
    ? `/v1/images/${encodeURIComponent(image.image_id)}/attribution?target_a=${pair.a}&target_b=${pair.b}&format=png`
    : "";

  useEffect(() => {
    if (pair && showOverlay) setImgState("loading");
  }, [pair, showOverlay, image.image_id]);

  const predY = image.prediction;
  const sortedY = predY
    ? Object.entries(predY.scores)
        .map(([k, v]) => [k, v] as const)
        .sort(([, a], [, b]) => b - a)
    : [];

  const topY = sortedY[0];
  const secondY = sortedY[1];
  const topClassY = topY?.[0] as CanonicalClass | undefined;
  const runnerUpY = secondY?.[0] as CanonicalClass | undefined;

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

  const samePairY = (p: { a: CanonicalClass; b: CanonicalClass }, a: CanonicalClass, b: CanonicalClass) =>
    p.a === a && p.b === b;

  const marginRowsY = predY && (
    <div className="analysis-margin" data-testid="analysis-margin">
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topClass")}</span>
        <span>
          {topClassY ? (
            <ClassChip cls={topClassY} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{topY?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.secondClass")}</span>
        <span>
          {runnerUpY ? (
            <ClassChip cls={runnerUpY} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{secondY?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topTwoMargin")}</span>
        <span className="small">{predY.top_two_margin.toFixed(4)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.uncertainty")}</span>
        <span className="small">{predY.normalized_entropy.toFixed(4)}</span>
        <span className="badge badge-uncal">{t("patch.uncalibrated")}</span>
      </div>
    </div>
  );

  const selectOptionsY = attrib.pairs.map((p) => (
    <option key={`${p.a}|${p.b}`} value={`${p.a}|${p.b}`}>
      {t(`class.${p.a}` as const)} {t("attribution.vs")} {t(`class.${p.b}` as const)}
      {samePairY(attrib.default_pair, p.a, p.b) ? "  ★" : ""}
    </option>
  ));

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

  const overlaySrcC = pair
    ? `/v1/images/${encodeURIComponent(image.image_id)}/attribution?target_a=${pair.a}&target_b=${pair.b}&format=png`
    : "";

  useEffect(() => {
    if (pair && showOverlay) setImgState("loading");
  }, [pair, showOverlay, image.image_id]);

  const predC = image.prediction;
  const sortedC = predC
    ? Object.entries(predC.scores)
        .map(([k, v]) => [k, v] as const)
        .sort(([, a], [, b]) => b - a)
    : [];

  const topC = sortedC[0];
  const secondC = sortedC[1];
  const topClassC = topC?.[0] as CanonicalClass | undefined;
  const runnerUpC = secondC?.[0] as CanonicalClass | undefined;

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

  const samePairC = (p: { a: CanonicalClass; b: CanonicalClass }, a: CanonicalClass, b: CanonicalClass) =>
    p.a === a && p.b === b;

  const marginRowsC = predC && (
    <div className="analysis-margin" data-testid="analysis-margin">
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topClass")}</span>
        <span>
          {topClassC ? (
            <ClassChip cls={topClassC} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{topC?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.secondClass")}</span>
        <span>
          {runnerUpC ? (
            <ClassChip cls={runnerUpC} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{secondC?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topTwoMargin")}</span>
        <span className="small">{predC.top_two_margin.toFixed(4)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.uncertainty")}</span>
        <span className="small">{predC.normalized_entropy.toFixed(4)}</span>
        <span className="badge badge-uncal">{t("patch.uncalibrated")}</span>
      </div>
    </div>
  );

  const selectOptionsC = attrib.pairs.map((p) => (
    <option key={`${p.a}|${p.b}`} value={`${p.a}|${p.b}`}>
      {t(`class.${p.a}` as const)} {t("attribution.vs")} {t(`class.${p.b}` as const)}
      {samePairC(attrib.default_pair, p.a, p.b) ? "  ★" : ""}
    </option>
  ));

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

  const overlaySrcA = pair
    ? `/v1/images/${encodeURIComponent(image.image_id)}/attribution?target_a=${pair.a}&target_b=${pair.b}&format=png`
    : "";

  useEffect(() => {
    if (pair && showOverlay) setImgState("loading");
  }, [pair, showOverlay, image.image_id]);

  const predA = image.prediction;
  const sortedA = predA
    ? Object.entries(predA.scores)
        .map(([k, v]) => [k, v] as const)
        .sort(([, a], [, b]) => b - a)
    : [];

  const topA = sortedA[0];
  const secondA = sortedA[1];
  const topClassA = topA?.[0] as CanonicalClass | undefined;
  const runnerUpA = secondA?.[0] as CanonicalClass | undefined;

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

  const samePairA = (p: { a: CanonicalClass; b: CanonicalClass }, a: CanonicalClass, b: CanonicalClass) =>
    p.a === a && p.b === b;

  const marginRowsA = predA && (
    <div className="analysis-margin" data-testid="analysis-margin">
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topClass")}</span>
        <span>
          {topClassA ? (
            <ClassChip cls={topClassA} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{topA?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.secondClass")}</span>
        <span>
          {runnerUpA ? (
            <ClassChip cls={runnerUpA} />
          ) : (
            <span className="muted">{t("metric.notAvailable")}</span>
          )}
        </span>
        <span>{secondA?.[1].toFixed(3)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.topTwoMargin")}</span>
        <span className="small">{predA.top_two_margin.toFixed(4)}</span>
      </div>
      <div className="analysis-row">
        <span className="muted small">{t("analysis.uncertainty")}</span>
        <span className="small">{predA.normalized_entropy.toFixed(4)}</span>
        <span className="badge badge-uncal">{t("patch.uncalibrated")}</span>
      </div>
    </div>
  );

  const selectOptionsA = attrib.pairs.map((p) => (
    <option key={`${p.a}|${p.b}`} value={`${p.a}|${p.b}`}>
      {t(`class.${p.a}` as const)} {t("attribution.vs")} {t(`class.${p.b}` as const)}
      {samePairA(attrib.default_pair, p.a, p.b) ? "  ★" : ""}
    </option>
  ));

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

  const overlaySrc = pair
    ? `/v1/images/${encodeURIComponent(image.image_id)}/attribution?target_a=${pair.a}&target_b=${pair.b}&format=png`
    : "";

  useEffect(() => {
    if (pair && showOverlay) setImgState("loading");
  }, [pair, showOverlay, image.image_id]);

  const pred = image.prediction;
  const sorted = pred
    ? Object.entries(pred.scores)
        .map(([k, v]) => [k, v] as const)
        .sort(([, a], [, b]) => b - a)
    : [];

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

  const samePair = (p: { a: CanonicalClass; b: CanonicalClass }, a: CanonicalClass, b: CanonicalClass) =>
    p.a === a && p.b === b;

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

  const selectOptions = attrib.pairs.map((p) => (
    <option key={`${p.a}|${p.b}`} value={`${p.a}|${p.b}`}>
      {t(`class.${p.a}` as const)} {t("attribution.vs")} {t(`class.${p.b}` as const)}
      {samePair(attrib.default_pair, p.a, p.b) ? "  ★" : ""}
    </option>
  ));

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
              {selectOptions}
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
          <AttributionImage
            src={`/v1/images/${encodeURIComponent(image.image_id)}/full`}
            alt={`${t("analysis.originalImage")} ${image.image_id}`}
            base
          />
          {showOverlay && imgState !== "error" && (
            <AttributionImage
              src={overlaySrc}
              alt={`attribution ${pair.a} vs ${pair.b}`}
              overlay
              opacity={opacity}
              display={imgState === "ready" ? "block" : "none"}
              onReady={() => setImgState("ready")}
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

function AttributionImage({
  src,
  alt,
  base,
  overlay,
  opacity,
  display,
  onReady,
  onError,
}: {
  src: string;
  alt: string;
  base?: boolean;
  overlay?: boolean;
  opacity?: number;
  display?: string;
  onReady?: () => void;
  onError?: () => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const u = await authenticatedImageUrl(src);
        if (active) setUrl(u);
      } catch {
        if (active) setFailed(true);
      }
    }

    load();
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [src]);

  if (failed) {
    if (onError) onError();
    return null;
  }

  if (!url) return null;

  const img = (
    <img
      className={base ? "attrib-base" : "attrib-overlay"}
      src={url}
      alt={alt}
      draggable={false}
      style={overlay ? { opacity: opacity ?? 1, display: display ?? "block" } : undefined}
      onLoad={() => { if (onReady) onReady(); }}
      onError={() => { if (onError) onError(); }}
    />
  );

  return base ? <div className="attrib-base">{img}</div> : img;
}

async function authenticatedImageUrl(path: string): Promise<string> {
  const res = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(typeof window !== "undefined" && window.osteopatch_auth ? { Authorization: `Bearer ${window.osteopatch_auth}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status}: ${path}`);
  return URL.createObjectURL(await res.blob());
}
