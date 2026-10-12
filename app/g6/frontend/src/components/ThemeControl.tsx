import { useRef } from "react";
import { t } from "../strings";
import { THEME_PREFERENCES, useTheme, type ThemePreference } from "../theme";

/**
 * U005 - the theme selector, in the header actions beside the export links.
 *
 * It is a radiogroup, not a second navigation system: three mutually exclusive
 * display options, one tab stop, arrow keys to move (the WAI-ARIA pattern), and
 * every option named in text. Nothing here is colour-only, and the resolved
 * theme is spelled out in the group label so a screen-reader user knows whether
 * "Auto" currently means light or dark.
 *
 * A browser that refuses localStorage still themes the session; it just says so
 * instead of pretending the choice was saved.
 */
export function ThemeControl() {
  const { preference, resolved, persisted, storageError, setPreference } = useTheme();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const choose = (next: ThemePreference) => setPreference(next);

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    const current = THEME_PREFERENCES.indexOf(preference);
    let next = -1;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      next = (current + 1) % THEME_PREFERENCES.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      next = (current - 1 + THEME_PREFERENCES.length) % THEME_PREFERENCES.length;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = THEME_PREFERENCES.length - 1;
    }
    if (next < 0) return;
    event.preventDefault();
    choose(THEME_PREFERENCES[next]);
    // Roving tabindex: focus follows the selection so the arrow run continues.
    buttons.current[next]?.focus();
  };

  return (
    <div className="theme-control">
      <div
        className="theme-options"
        role="radiogroup"
        aria-label={`${t("theme.label")}: ${t(`theme.${preference}`)} (${t(`theme.${resolved}`)})`}
        data-testid="theme-control"
        data-theme-resolved={resolved}
      >
        {THEME_PREFERENCES.map((option, index) => {
          const checked = option === preference;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              className={checked ? "theme-opt active" : "theme-opt"}
              aria-checked={checked}
              tabIndex={checked ? 0 : -1}
              data-testid={`theme-${option}`}
              ref={(node) => {
                buttons.current[index] = node;
              }}
              onClick={() => choose(option)}
              onKeyDown={onKeyDown}
            >
              {t(`theme.${option}`)}
            </button>
          );
        })}
      </div>
      {storageError && !persisted ? (
        <span className="theme-note" role="status" data-testid="theme-storage-note">
          {t("theme.storageBlocked")}
        </span>
      ) : null}
    </div>
  );
}
