import { useState } from "react";
import { newIdempotencyKey, submitReview } from "../api";
import type { CanonicalClass, ImageDetail, Meta, ReviewAction } from "../types";
import { t, type StringKey } from "../strings";
import { ClassChip } from "./Shared";

const CLASSES: CanonicalClass[] = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"];

export function ReviewPanel({
  image,
  meta,
  onReviewed,
}: {
  image: ImageDetail;
  meta: Meta;
  onReviewed: () => void;
}) {
  const [action, setAction] = useState<ReviewAction>("ACCEPT");
  const [selected, setSelected] = useState<CanonicalClass | "">("");
  const [reason, setReason] = useState<string>("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const pred = image.prediction;
  if (!pred) return null;

  const canSave =
    action === "ACCEPT" ||
    (action === "CORRECT" && selected !== "") ||
    action === "DEFER";

  async function save() {
    setBusy(true);
    setMsg(null);
    const res = await submitReview(image.image_id, {
      prediction_id: pred!.prediction_id,
      action,
      selected_label: action === "CORRECT" ? (selected as string) : null,
      reason: action === "DEFER" ? reason || "other" : null,
      note: note || null,
      expected_revision: image.review_state.revision,
      idempotency_key: newIdempotencyKey(),
    });
    setBusy(false);
    if (res.conflict) {
      setMsg(t("review.conflict"));
      onReviewed(); // reload latest state
      return;
    }
    setMsg(t("review.saved"));
    setNote("");
    onReviewed();
  }

  return (
    <div className="review-panel" data-testid="review-panel">
      <h3>{t("review.title")}</h3>

      <div className="review-actions" role="radiogroup" aria-label={t("review.title")}>
        {(["ACCEPT", "CORRECT", "DEFER"] as ReviewAction[]).map((a) => (
          <button
            key={a}
            role="radio"
            aria-checked={action === a}
            className={`review-action ${action === a ? "active" : ""}`}
            onClick={() => setAction(a)}
            data-testid={`action-${a}`}
          >
            {t(`review.${a.toLowerCase()}` as StringKey)}
          </button>
        ))}
      </div>

      {action === "ACCEPT" && (
        <p className="review-hint">
          {t("patch.suggested")}: <ClassChip cls={pred.predicted_class} />
        </p>
      )}

      {action === "CORRECT" && (
        <div className="review-field">
          <label>{t("review.pickClass")}</label>
          <div className="class-picker">
            {CLASSES.map((c) => (
              <button
                key={c}
                className={`class-opt ${selected === c ? "active" : ""}`}
                onClick={() => setSelected(c)}
                data-testid={`class-${c}`}
                aria-pressed={selected === c}
              >
                <ClassChip cls={c} selected={selected === c} />
              </button>
            ))}
          </div>
        </div>
      )}

      {action === "DEFER" && (
        <div className="review-field">
          <label htmlFor="defer-reason">{t("review.deferReason")}</label>
          <select
            id="defer-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="defer-reason"
          >
            <option value="">—</option>
            {meta.defer_reasons.map((r) => (
              <option key={r} value={r}>
                {t(`defer.${r}` as StringKey)}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="review-field">
        <label htmlFor="review-note">{t("review.note")}</label>
        <textarea
          id="review-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          data-testid="review-note"
        />
      </div>

      <button
        className="btn-primary"
        disabled={!canSave || busy}
        onClick={save}
        data-testid="save-review"
      >
        {t("review.save")}
      </button>
      {msg && <span className="review-msg" data-testid="review-msg">{msg}</span>}
    </div>
  );
}

export function ReviewHistory({ image }: { image: ImageDetail }) {
  return (
    <div className="review-history" data-testid="review-history">
      <h3>{t("review.history")}</h3>
      {image.history.length === 0 ? (
        <p className="muted">{t("review.noHistory")}</p>
      ) : (
        <ol>
          {image.history.map((e) => (
            <li key={e.review_event_id} data-testid={`history-rev-${e.revision_number}`}>
              <span className="hist-rev">#{e.revision_number}</span>{" "}
              <strong>{e.action}</strong>
              {e.selected_class ? ` → ${e.selected_class}` : ""}
              {e.reason ? ` (${e.reason})` : ""}
              {e.note ? ` — ${e.note}` : ""}
              <span className="hist-time">{e.created_at}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
