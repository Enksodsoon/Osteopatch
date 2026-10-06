import type { Confidence, Scores } from "../../types";
import { CLASS_LABELS, CLASSES } from "../../types";

/** Band edges. Mirrors LIVE_MARGIN_INDETERMINATE / LIVE_MARGIN_LOW in G6 config. */
export const MARGIN_INDETERMINATE = 0.05;
export const MARGIN_LOW = 0.2;

export const CONFIDENCE_COPY: Record<Confidence, string> = {
  clear: "Top two classes are separated.",
  low: "Top two classes are close — treat this as a weak call, not a verdict.",
  indeterminate: "Top two classes are not distinguishable. No call is being made.",
};

/**
 * The three scores, and — more importantly — how far apart the top two are.
 *
 * Bars alone invite the reader to treat the numbers as probabilities, so the
 * margin ribbon underneath is the correction: it says out loud whether the top
 * two classes were distinguishable at all, and it draws the band edges so the
 * reader can see where the thresholds actually sit rather than trusting a word.
 */
export function ScoreReadout({
  scores,
  predictedClass,
  margin,
  confidence,
  scoreLabel,
}: {
  scores: Scores;
  predictedClass: keyof Scores;
  margin: number;
  confidence: Confidence;
  scoreLabel: string;
}) {
  const top = Math.max(...CLASSES.map((c) => scores[c]));
  return (
    <div className="readout">
      <div className="bars">
        {CLASSES.map((c, i) => {
          const v = scores[c];
          const isTop = c === predictedClass;
          return (
            <div className={`bar-row${isTop ? " top" : ""}`} key={c}>
              <span className="bar-label">{CLASS_LABELS[c]}</span>
              <div className="bar-track">
                <div
                  className={`bar-fill cl-${c}`}
                  style={{ width: `${Math.max(v * 100, 0.8)}%`, animationDelay: `${i * 90}ms` }}
                />
              </div>
              <span className="bar-val">{v.toFixed(3)}</span>
            </div>
          );
        })}
      </div>

      <div className="ribbon" role="img"
           aria-label={`Separation between the top two scores is ${margin.toFixed(3)}: ${CONFIDENCE_COPY[confidence]}`}>
        <div className="ribbon-track">
          <div className="ribbon-fill" style={{ width: `${Math.min(margin * 100, 100)}%` }} />
          <div className="ribbon-edge" style={{ left: `${MARGIN_INDETERMINATE * 100}%` }} />
          <div className="ribbon-edge" style={{ left: `${MARGIN_LOW * 100}%` }} />
        </div>
        <div className="ribbon-scale">
          <span>0</span>
          <span style={{ left: `${MARGIN_INDETERMINATE * 100}%` }}>0.05</span>
          <span style={{ left: `${MARGIN_LOW * 100}%` }}>0.20</span>
          <span className="ribbon-max">1.0</span>
        </div>
      </div>

      <p className={`conf conf-${confidence}`}>
        <b>separation {margin.toFixed(3)}</b> — {CONFIDENCE_COPY[confidence]}
      </p>
      <p className="calib">
        <span className="calib-tag">{scoreLabel}</span>
        <span className="calib-note">
          Highest score {top.toFixed(3)} is a class score, not a probability. The model has not
          been calibrated, so it cannot tell you how likely anything is.
        </span>
      </p>
    </div>
  );
}