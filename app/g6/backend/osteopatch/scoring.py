"""Pure, torch-free scoring and review-priority math.

These functions operate on the three model class scores already stored in the
prediction row. Keeping them torch-free means the server, the tests, and the UI
contract all agree on exactly ONE definition, and the browser never waits on
PyTorch.

Definitions (frozen):
  * ``top1`` = max score; ``predicted_class`` = argmax in canonical order.
  * ``top_two_margin`` = (largest - second largest) score. Smaller = the model's
    top two guesses are closer together.
  * ``normalized_entropy`` = Shannon entropy of the 3 scores / log(3), in [0, 1].
    Higher = flatter / more diffuse score distribution.

Review priority is a DETERMINISTIC RANKING, not calibrated uncertainty and not a
probability of error. Order: (1) smallest top_two_margin, (2) then highest
normalized_entropy, (3) then stable image_id. Raw values are exposed in the UI;
we never translate them into a confidence claim.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .config import CANONICAL_CLASSES


def top1_index(scores: list[float]) -> int:
    """Argmax; ties broken by lowest index (canonical order) for determinism.

    Raises ValueError on an empty score vector rather than IndexError, so a
    malformed prediction surfaces as a clear contract violation.
    """
    if not scores:
        raise ValueError("top1_index requires at least one score")
    best_i, best_v = 0, scores[0]
    for i in range(1, len(scores)):
        if scores[i] > best_v:
            best_i, best_v = i, scores[i]
    return best_i


def top_two_margin(scores: list[float]) -> float:
    """Largest minus second-largest score. Always >= 0.

    Requires at least two scores; a single-element vector has no second-largest
    and raises ValueError instead of IndexError.
    """
    if len(scores) < 2:
        raise ValueError("top_two_margin requires at least two scores")
    ordered = sorted(scores, reverse=True)
    return float(ordered[0] - ordered[1])


def normalized_entropy(scores: list[float]) -> float:
    """Shannon entropy / log(n), clamped to [0, 1].

    Treats the scores as a distribution (they sum to ~1 after softmax). Zero
    scores contribute nothing (0*log0 := 0).

    Edge cases handled explicitly (defensive — the stored G6 scores are a valid
    3-class softmax, but this is also used on ad-hoc inputs):
      * n < 2        -> 0.0 (entropy is undefined / log(1)=0 would divide by zero).
      * total <= 0   -> 0.0 (no valid mass to form a distribution).
      * negative s   -> clamped to 0 (a negative "probability" is not a valid
                        distribution component; raw logits are never passed here).
    """
    n = len(scores)
    if n < 2:
        return 0.0
    # Clamp negatives to 0 before forming the distribution; a stray negative
    # score would otherwise corrupt the normalization and the entropy sum.
    clamped = [s if s > 0 else 0.0 for s in scores]
    total = sum(clamped)
    if total <= 0:
        return 0.0
    h = 0.0
    for s in clamped:
        p = s / total
        if p > 0:
            h -= p * math.log(p)
    norm = h / math.log(n)
    # Clamp against tiny floating-point overshoot.
    return max(0.0, min(1.0, float(norm)))


@dataclass(frozen=True)
class ScoreSummary:
    predicted_class: str
    scores: dict[str, float]
    top1_score: float
    top_two_margin: float
    normalized_entropy: float


def summarize(scores: list[float]) -> ScoreSummary:
    """Derive every stored prediction metric from the 3 raw class scores.

    Validates arity AND finiteness: a NaN/inf score would otherwise propagate
    into predicted_class/margin/entropy and be stored as a silent garbage
    prediction, so it is rejected here at the single choke point.
    """
    if len(scores) != len(CANONICAL_CLASSES):
        raise ValueError(
            f"expected {len(CANONICAL_CLASSES)} scores, got {len(scores)}"
        )
    if not all(math.isfinite(s) for s in scores):
        raise ValueError(f"scores must all be finite, got {scores}")
    idx = top1_index(scores)
    return ScoreSummary(
        predicted_class=CANONICAL_CLASSES[idx],
        scores={CANONICAL_CLASSES[i]: float(scores[i]) for i in range(len(scores))},
        top1_score=float(scores[idx]),
        top_two_margin=top_two_margin(scores),
        normalized_entropy=normalized_entropy(scores),
    )


def review_priority_key(margin: float, entropy: float, image_id: str) -> tuple:
    """Deterministic sort key: ambiguous (small margin) first, then diffuse
    (high entropy) first, then stable image_id. Negate entropy so that a plain
    ascending sort puts highest entropy first within equal margins.
    """
    return (round(margin, 9), -round(entropy, 9), image_id)
