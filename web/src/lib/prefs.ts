import { useSyncExternalStore } from "react";

export type Theme = "dark" | "light" | "sepia" | "system";

export interface Prefs {
  theme: Theme;
  fontSize: number; // px
  width: "narrow" | "medium" | "wide";
  showTags: boolean;
  showAvatars: boolean;
  view: "scenario" | "original";
}

const DEFAULTS: Prefs = { theme: "dark", fontSize: 18, width: "medium", showTags: true, showAvatars: true, view: "scenario" };
const KEY = "babel.prefs.v2";

function load(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

let current = load();
const listeners = new Set<() => void>();

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

export function setPrefs(patch: Partial<Prefs>) {
  current = { ...current, ...patch };
  try {
    localStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    /* storage unavailable: keep in memory */
  }
  if (patch.theme) applyTheme(patch.theme);
  listeners.forEach((l) => l());
}

export function usePrefs(): Prefs {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => current,
  );
}

export const WIDTHS: Record<Prefs["width"], string> = { narrow: "36rem", medium: "44rem", wide: "56rem" };

applyTheme(current.theme);
