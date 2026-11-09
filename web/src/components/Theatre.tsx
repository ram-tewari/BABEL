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
        <Link to="/" className="font-[family-name:var(--font-tiny)] text-[17px] tracking-[0.32em] text-[#f3e6cf] drop-shadow-[0_1px_0_#000]" aria-label="BABEL home">
          BABEL
        </Link>
        <nav className="hidden items-center gap-5 sm:flex">
          <NavLink to="/" end className={({ isActive }) => cx("plaque !font-normal opacity-80 hover:opacity-100", isActive && "opacity-100 underline decoration-[#dfb56f] underline-offset-[6px]")}>
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

/**
 * The proscenium: valance across the top, two curtains, footlights along the bottom.
 * ``open`` is 0 (closed) … 1 (open); curtains step through the sprite frames like a real pull.
 */
export function Proscenium({ open, children, className, footlights = true, duration = 1100 }: { open: number; children?: ReactNode; className?: string; footlights?: boolean; duration?: number }) {
  const art = useThemeArt();
  const left = art.url("curtain-left.webp");
  const right = art.url("curtain-right.webp");
  const valance = art.url("valance.webp");
  const lights = art.url("footlights.webp");
  const frame = Math.round(Math.max(0, Math.min(1, open)) * (FRAMES - 1));
  const sprite = (src: string): CSSProperties => ({
    backgroundImage: `url(${src})`,
    backgroundSize: `${FRAMES * 100}% 100%`,
    backgroundRepeat: "no-repeat",
    backgroundPositionX: `${(frame / (FRAMES - 1)) * 100}%`,
    transition: `background-position ${duration}ms steps(${FRAMES - 1}, jump-none)`,
    imageRendering: "pixelated",
  });
  return (
    <div className={cx("relative isolate overflow-hidden bg-black", className)}>
      {children}
      {/* curtains */}
      <div aria-hidden className="pointer-events-none absolute inset-y-0 left-0 z-20 w-1/2" style={left ? sprite(left) : velvet(open, "left", duration)} />
      <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 z-20 w-1/2" style={right ? sprite(right) : velvet(open, "right", duration)} />
      {/* valance */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 z-30 h-[clamp(36px,9%,96px)]"
        style={
          valance
            ? { backgroundImage: `url(${valance})`, backgroundSize: "100% 100%", imageRendering: "pixelated", filter: "drop-shadow(0 6px 10px #000a)" }
            : { background: "linear-gradient(180deg,#1e5a55 0%,#14403c 70%,#c9954d 70%,#8a5a2b 100%)", boxShadow: "0 6px 14px #000a", clipPath: "polygon(0 0,100% 0,100% 72%,95% 100%,90% 72%,85% 100%,80% 72%,75% 100%,70% 72%,65% 100%,60% 72%,55% 100%,50% 72%,45% 100%,40% 72%,35% 100%,30% 72%,25% 100%,20% 72%,15% 100%,10% 72%,5% 100%,0 72%)" }
        }
      />
      {footlights && (
        <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 z-30 h-[clamp(10px,2.4%,22px)]">
          <div
            className="h-full w-full"
            style={lights ? { backgroundImage: `url(${lights})`, backgroundSize: "300% 100%", backgroundPositionX: "100%", imageRendering: "pixelated" } : { background: "radial-gradient(circle at 50% 100%,#ffd38a 0 18%,transparent 60%) 0 0/48px 100% repeat-x" }}
          />
          <div className="absolute inset-x-0 -top-24 h-24 bg-[radial-gradient(ellipse_at_50%_100%,#ffcf8a22,transparent_70%)]" />
        </div>
      )}
    </div>
  );
}

/** CSS velvet when the curtain art isn't imported: gathers toward the edge as it opens. */
function velvet(open: number, side: "left" | "right", duration: number): CSSProperties {
  const w = 100 - Math.max(0, Math.min(1, open)) * 88; // % of its half
  return {
    width: `${w / 2}%`,
    [side]: 0,
    background: "repeating-linear-gradient(90deg,#123f3b 0 14px,#1d5c55 14px 26px,#0f3431 26px 40px)",
    boxShadow: side === "left" ? "inset -10px 0 18px #0009" : "inset 10px 0 18px #0009",
    borderBottom: "6px solid #c9954d",
    transition: `width ${duration}ms var(--ease-out)`,
  } as CSSProperties;
}
