/**
 * U005 - light and dark themes with safe local preferences.
 *
 * A theme preference is a display setting and nothing else: it carries no
 * clinical or reviewer data, it never leaves the browser, and it must not be
 * able to change a pixel of the histology, the thumbnails or the attribution
 * overlay. Those are decided by tokens.css, not by anything in this file.
 *
 * Two rules shape the design here:
 *
 *  1. Nothing in this module may throw. It runs before the first render (see
 *     main.tsx) and inside a control a reviewer can poke at any time, so a
 *     blocked localStorage - private browsing, cookies disabled, a quota - ends
 *     up as a *reported* condition ("this session only") rather than a crash or
 *     a silent lie that the choice was saved.
 *  2. Storage holds one bare literal. No JSON, no free text, nothing that could
 *     later be mistaken for a review, a project or a patient.
 */

import { useCallback, useEffect, useState } from "react";

export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

/** The one key this feature owns. Version suffix so a future change can migrate. */
export const THEME_STORAGE_KEY = "osteopatch:theme:v1";

/** The OS query that "system" follows. */
export const DARK_QUERY = "(prefers-color-scheme: dark)";

export const THEME_PREFERENCES: readonly ThemePreference[] = ["system", "light", "dark"];

export type StorageFailure = "unavailable" | "write-failed";

export interface StorageResult {
  saved: boolean;
  reason: StorageFailure | null;
}

export interface AppliedTheme {
  /** What the reviewer chose. "system" means "follow the OS". */
  preference: ThemePreference;
  /** The theme actually on screen right now. */
  resolved: ResolvedTheme;
  systemDark: boolean;
  /** True only when the running preference is verifiably in the store. */
  persisted: boolean;
  /** Non-null when the preference could not be persisted this session. */
  storageError: string | null;
}

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

export function resolvePreference(preference: ThemePreference, systemDark: boolean): ResolvedTheme {
  if (preference === "system") return systemDark ? "dark" : "light";
  return preference;
}

/**
 * The store, or null. Touching `window.localStorage` is itself the thing that
 * throws in a cookie-blocked window, so even the lookup is guarded.
 */
function storage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

function readRaw(): { value: string | null; error: string | null } {
  const store = storage();
  if (!store) return { value: null, error: "localStorage is unavailable in this browser context" };
  try {
    return { value: store.getItem(THEME_STORAGE_KEY), error: null };
  } catch (error) {
    return { value: null, error: `localStorage read failed: ${describe(error)}` };
  }
}

/** The stored preference, or "system" when absent, unreadable or not a literal. */
export function readPreference(): ThemePreference {
  const { value } = readRaw();
  return isThemePreference(value) ? value : "system";
}

export function writePreference(preference: ThemePreference): StorageResult {
  const store = storage();
  if (!store) return { saved: false, reason: "unavailable" };
  try {
    store.setItem(THEME_STORAGE_KEY, preference);
    return { saved: true, reason: null };
  } catch {
    return { saved: false, reason: "write-failed" };
  }
}

function describe(error: unknown): string {
  return error instanceof Error ? error.name : typeof error;
}

/** Whether the OS asks for a dark UI. False when the query is not available. */
export function systemPrefersDark(): boolean {
  try {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
    return window.matchMedia(DARK_QUERY).matches;
  } catch {
    return false;
  }
}

/**
 * Paint the theme onto <html>. The attribute is the whole hook: tokens.css keys
 * the dark palette off it, and the media-query path covers the window before
 * this ever runs.
 */
function paint(resolved: ResolvedTheme, preference: ThemePreference): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (!root) return;
  root.dataset.theme = resolved;
  root.dataset.themePreference = preference;
  // No colour-scheme write here: tokens.css owns it, so there is one source.
}

/** Apply a preference, persisting it unless told otherwise. */
export function applyPreference(
  preference: ThemePreference,
  options: { persist?: boolean } = {},
): AppliedTheme {
  const { persist = true } = options;
  const systemDark = systemPrefersDark();
  const resolved = resolvePreference(preference, systemDark);
  let storageError: string | null = null;

  if (persist) {
    const write = writePreference(preference);
    if (!write.saved) {
      storageError =
        write.reason === "unavailable"
          ? "localStorage is unavailable in this browser context"
          : "localStorage refused the write";
    }
  } else {
    const read = readRaw();
    if (read.error) storageError = read.error;
  }

  // Read back rather than trusting the write: `persisted` has to mean the value
  // is really in the store, not that we asked nicely.
  const persisted = readRaw().value === preference;
  if (persist && !persisted && storageError === null) {
    storageError = "localStorage did not retain the preference";
  }

  paint(resolved, preference);
  return { preference, resolved, systemDark, persisted, storageError };
}

/** Cold start: read whatever was stored and paint it. Never writes. */
export function applyStoredPreference(): AppliedTheme {
  const preference = readPreference();
  const systemDark = systemPrefersDark();
  const resolved = resolvePreference(preference, systemDark);
  const { value, error } = readRaw();
  paint(resolved, preference);
  return {
    preference,
    resolved,
    systemDark,
    persisted: value === preference,
    storageError: error,
  };
}

/**
 * Watch the OS preference. Returns an unsubscribe that removes the listener, so
 * an unmounted control leaves nothing behind.
 */
export function subscribeToSystemTheme(onChange: (systemDark: boolean) => void): () => void {
  let mql: MediaQueryList | null = null;
  try {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
    mql = window.matchMedia(DARK_QUERY);
  } catch {
    return () => {};
  }
  const handler = (event: MediaQueryListEvent) => onChange(event.matches);
  if (typeof mql.addEventListener === "function") {
    mql.addEventListener("change", handler);
    return () => mql?.removeEventListener("change", handler);
  }
  // Safari < 14 and a few embedded views only have the deprecated pair.
  const legacy = mql as unknown as {
    addListener: (cb: (e: MediaQueryListEvent) => void) => void;
    removeListener: (cb: (e: MediaQueryListEvent) => void) => void;
  };
  legacy.addListener(handler);
  return () => legacy.removeListener?.(handler);
}

export interface ThemeState extends AppliedTheme {
  setPreference: (next: ThemePreference) => void;
}

/**
 * The control's view of the theme.
 *
 * The initial state paints the stored preference, so a control mounted anywhere
 * in the tree is enough to apply the theme; main.tsx does the same thing earlier
 * so the very first paint is already correct. An OS change re-resolves without
 * rewriting storage, because "the OS changed" is not a new reviewer preference.
 */
export function useTheme(): ThemeState {
  const [state, setState] = useState<AppliedTheme>(() => applyStoredPreference());

  useEffect(
    () =>
      subscribeToSystemTheme(() => {
        setState((previous) => applyPreference(previous.preference, { persist: false }));
      }),
    [],
  );

  const setPreference = useCallback((next: ThemePreference) => {
    setState(applyPreference(next));
  }, []);

  return { ...state, setPreference };
}
