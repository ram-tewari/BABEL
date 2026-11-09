import { useEffect, useState } from "react";

/** Player preferences, per browser (a convenience: everything works with the defaults). */
export interface VnSettings {
  textSpeed: number; // characters per second; 0 = instant
  autoDelay: number; // multiplier on the auto-play pause after a line
  effects: boolean; // weather, screen shake, character reactions
}

const KEY = "babel.vn.settings";
const DEFAULTS: VnSettings = { textSpeed: 55, autoDelay: 1, effects: true };

function load(): VnSettings {
  try {
    return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<VnSettings>) };
  } catch {
    return DEFAULTS;
  }
}

export function useVnSettings(): [VnSettings, (patch: Partial<VnSettings>) => void] {
  const [s, setS] = useState<VnSettings>(load);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(s));
    } catch {
      /* private mode: keep in memory */
    }
  }, [s]);
  return [s, (patch) => setS((x) => ({ ...x, ...patch }))];
}

export const reducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
