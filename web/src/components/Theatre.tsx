import type { CSSProperties, ReactNode } from "react";
import { Link, NavLink } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { cx } from "./ui";
import { StatusChip } from "./StatusChip";

/** Optional theatre art imported from NOCTURNE (`babel theme import`). Everything has a CSS fallback. */
export function useThemeArt() {
  const q = useQuery({
    queryKey: ["theme"],
    queryFn: async () => {
      const r = await fetch("/api/theme");
      if (!r.ok) return { files: [] as string[], base: "/api/theme/files/" };
      return (await r.json()) as { files: string[]; base: string };
    },
    staleTime: Infinity,
  });
  const files = new Set(q.data?.files ?? []);
  const url = (name: string) => (files.has(name) ? `${q.data!.base}${name}` : null);
  return { ready: q.isFetched, url, has: (name: string) => files.has(name) };
}

/** The brass bar across the top of every page, after NOCTURNE's HUD. */
export function HudBar({ children }: { children?: ReactNode }) {
  return (
    <header className="hud-bar sticky top-0 z-30">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link to="/" className="brand" aria-label="BABEL home">
          BABEL
        </Link>
        <nav className="hidden items-center gap-5 sm:flex">
          <NavLink to="/" end className={({ isActive }) => cx("plaque !text-[#efe6da] opacity-70 transition-opacity hover:opacity-100", isActive && "!text-[#e9c98d] opacity-100")}>
            Repertoire
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <StatusChip />
          {children}
        </div>
      </div>
    </header>
  );
}

const FRAMES = 8; // the NOCTURNE curtain sheets: 8 frames, closed → gathered
const GATHERED = 6;
const EASE = "cubic-bezier(.76,0,.24,1)"; // a heavy curtain: slow start, slow stop

/**
 * The proscenium: valance across the top, two curtains, footlights along the bottom.
 *
 * Everything moves with GPU transforms (no stepped sprite frames), so it glides at the display's frame rate.
 * ``rest`` is where the curtains go when open: "gathered" (tied back at the sides, the lobby) or
 * "away" (off-stage entirely, with the valance and footlights withdrawn: the visual novel plays full-bleed).
 */
export function Proscenium({ open, children, className, footlights = true, duration = 1300, rest = "gathered" }: { open: boolean; children?: ReactNode; className?: string; footlights?: boolean; duration?: number; rest?: "gathered" | "away" }) {
  const art = useThemeArt();
  const left = art.url("curtain-left.webp");
  const right = art.url("curtain-right.webp");
  const valance = art.url("valance.webp");
  const lights = art.url("footlights.webp");
  const away = rest === "away";
  const frame = (src: string, n: number): CSSProperties => ({
    backgroundImage: `url(${src})`,
    backgroundSize: `${FRAMES * 100}% 100%`,
    backgroundRepeat: "no-repeat",
    backgroundPositionX: `${(n / (FRAMES - 1)) * 100}%`,
  });
  const t = (ms: number, delay = 0) => `transform ${ms}ms ${EASE} ${delay}ms, opacity ${Math.round(ms * 0.6)}ms ease ${delay + (open ? Math.round(ms * 0.35) : 0)}ms`;
  const curtain = (side: "left" | "right", src: string | null) => {
    const sign = side === "left" ? -1 : 1;
    // the closed drape slides out and gathers toward its edge…
    const closed: CSSProperties = {
      ...(src ? frame(src, 0) : velvet(side)),
      transformOrigin: side === "left" ? "0 50%" : "100% 50%",
      transform: open ? (away ? `translate3d(${sign * 101}%,0,0) scaleX(.7)` : `translate3d(${sign * 18}%,0,0) scaleX(.35)`) : "none",
      opacity: open && !away ? 0 : 1,
      transition: t(duration),
    };
    // …and in the lobby the tied-back drape fades in where it lands
    const gathered: CSSProperties | null =
      !away && src
        ? { ...frame(src, GATHERED), transform: open ? "none" : `translate3d(${-sign * 6}%,0,0)`, opacity: open ? 1 : 0, transition: `transform ${duration}ms ${EASE}, opacity ${Math.round(duration * 0.5)}ms ease ${open ? Math.round(duration * 0.45) : 0}ms` }
        : null;
    return (
      <div aria-hidden className={cx("pointer-events-none absolute inset-y-0 z-20 w-1/2", side === "left" ? "left-0" : "right-0")}>
        {gathered && <div className="vn-layer absolute inset-0" style={gathered} />}
        <div className="vn-layer absolute inset-0" style={closed} />
      </div>
    );
  };
  const chromeAway = open && away;
  return (
    <div className={cx("relative isolate overflow-hidden bg-black", className)}>
      {children}
      {curtain("left", left)}
      {curtain("right", right)}
      {/* valance */}
      <div
        aria-hidden
        className="vn-layer pointer-events-none absolute inset-x-0 top-0 z-30 h-[clamp(36px,9%,96px)]"
        style={{
          ...(valance
            ? { backgroundImage: `url(${valance})`, backgroundSize: "100% 100%", filter: "drop-shadow(0 6px 10px #000a)" }
            : { background: "linear-gradient(180deg,#1e5a55 0%,#14403c 70%,#c9954d 70%,#8a5a2b 100%)", boxShadow: "0 6px 14px #000a" }),
          transform: chromeAway ? "translate3d(0,-110%,0)" : "none",
          transition: `transform ${duration}ms ${EASE} ${chromeAway ? 250 : 0}ms`,
        }}
      />
      {footlights && (
        <div aria-hidden className="vn-layer pointer-events-none absolute inset-x-0 bottom-0 z-30 h-[clamp(10px,2.4%,22px)]" style={{ transform: chromeAway ? "translate3d(0,110%,0)" : "none", transition: `transform ${duration}ms ${EASE} ${chromeAway ? 250 : 0}ms` }}>
          <div
            className="h-full w-full"
            style={lights ? { backgroundImage: `url(${lights})`, backgroundSize: "300% 100%", backgroundPositionX: "100%" } : { background: "radial-gradient(circle at 50% 100%,#ffd38a 0 18%,transparent 60%) 0 0/48px 100% repeat-x" }}
          />
          <div className="absolute inset-x-0 -top-24 h-24 bg-[radial-gradient(ellipse_at_50%_100%,#ffcf8a22,transparent_70%)]" />
        </div>
      )}
    </div>
  );
}

/** CSS velvet when the curtain art isn't imported. */
function velvet(side: "left" | "right"): CSSProperties {
  return {
    background: "repeating-linear-gradient(90deg,#123f3b 0 14px,#1d5c55 14px 26px,#0f3431 26px 40px)",
    boxShadow: side === "left" ? "inset -10px 0 18px #0009" : "inset 10px 0 18px #0009",
    borderBottom: "6px solid #c9954d",
  };
}
