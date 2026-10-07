import type { LivePrediction, LiveRun } from "../../types";
import { CLASS_LABELS, CLASS_NAMES, SUPPORT_FLAG_LABELS } from "../../types";
import { ScoreReadout } from "./ScoreReadout";

/**
 * The answer to "what did the model say about my patch".
 *
 * The headline is deliberately NOT a class name when the call is
 * indeterminate. A large, colourful word reads as a conclusion no matter what
 * the footnote says, so when the top two classes are not distinguishable the
 * headline says so instead — the honest state gets the visual weight, not the
 * uncertain one.
 */
export function VerdictCard({
  run,
  prediction,
  sourceLabel,
}: {
  run: LiveRun;
  prediction: LivePrediction;
  sourceLabel?: string;
}) {
  const { confidence, caveat } = prediction;
  const decided = confidence !== "indeterminate";

  return (
    <article className={`verdict v-${confidence}`} aria-live="polite">
      <header className="verdict-head">
        <div className="verdict-file">
          <span className="verdict-name">{sourceLabel ?? run.source_name}</span>
          {!sourceLabel && <span className="mono subtle">{run.source_sha256.slice(0, 16)}…</span>}
        </div>
        <span className="live-tag">live inference · not a corpus prediction</span>
      </header>

      <div className="verdict-main">
        <div className="verdict-hero">
          {decided ? (
            <>
              <span className="hero-label">Predicted class</span>
              <h3 className={`hero-class cl-${prediction.predicted_class}`}>
                {CLASS_NAMES[prediction.predicted_class]}
              </h3>
              <p className="hero-sub">{CLASS_LABELS[prediction.predicted_class]}</p>
            </>
          ) : (
            <>
              <span className="hero-label">Result</span>
              <h3 className="hero-class hero-undecided">
                <span className="hatch" aria-hidden="true" />
                Not determined
              </h3>
              <p className="hero-sub">
                The top two scores differ by less than 0.05. No class is being
                asserted for this patch.
              </p>
            </>
          )}
        </div>

        <div className="verdict-scores">
          <ScoreReadout
            scores={prediction.scores}
            predictedClass={prediction.predicted_class}
            margin={prediction.top_two_margin}
            confidence={confidence}
            scoreLabel={prediction.score_label}
          />
        </div>
      </div>

      {(caveat || (prediction.support_flags?.length ?? 0) > 0) && (
        <div className="caveats" role="note">
          {caveat && <p className="caveat-line">{caveat}</p>}
          {prediction.support_flags?.map((f) => (
            <p className="flag-line" key={f}>
              <span className="flag-tag">input caveat</span>
              {SUPPORT_FLAG_LABELS[f] ?? f}
            </p>
          ))}
        </div>
      )}
    </article>
  );
}
