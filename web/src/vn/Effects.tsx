import { useMemo } from "react";

/** Weather and atmosphere over the backdrop — sparse, slow, CSS-only; off with reduced motion or effects off. */
export function Weather({ weather, night, indoor, on }: { weather: string | null; night: boolean; indoor: boolean; on: boolean }) {
  const kind = !on ? null : weather === "rain" && !indoor ? "rain" : weather === "snow" && !indoor ? "snow" : weather === "fog" ? "fog" : night && !indoor ? "stars" : indoor ? "dust" : null;
  const bits = useMemo(() => Array.from({ length: kind === "rain" ? 90 : kind === "snow" ? 60 : kind === "stars" ? 70 : 26 }, (_, i) => rnd(i + 1)), [kind]);
  if (!kind) return null;
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-[6] overflow-hidden">
      {kind === "rain" && (
        <>
          <div className="absolute inset-0 bg-[#0b1626]/35" />
          <div className="absolute inset-x-[-30%] bottom-0 h-1/3 bg-[radial-gradient(ellipse_at_center,#9fb4cc33,transparent_65%)]" style={{ animation: "vn-drift 30s ease-in-out infinite alternate" }} />
          {bits.map((r, i) => (
            <span
              key={i}
              className="absolute top-0 block w-px bg-gradient-to-b from-transparent to-[#bcd4f0]"
              style={{ left: `${r * 112}%`, height: `${8 + (r * 1000) % 10}vh`, opacity: 0.35 + ((r * 77) % 0.4), animation: `vn-rain ${0.55 + ((r * 13) % 0.5)}s linear ${-r * 3}s infinite` }}
            />
          ))}
        </>
      )}
      {kind === "snow" &&
        bits.map((r, i) => (
          <span key={i} className="absolute top-0 block rounded-full bg-white" style={{ left: `${r * 100}%`, width: 2 + ((r * 50) % 4), height: 2 + ((r * 50) % 4), opacity: 0.5 + ((r * 7) % 0.5), animation: `vn-snow ${7 + ((r * 31) % 8)}s linear ${-r * 12}s infinite` }} />
        ))}
      {kind === "fog" && (
        <>
          <div className="absolute inset-x-[-40%] bottom-0 h-2/3 bg-[radial-gradient(ellipse_at_center,#c9d2de55,transparent_65%)]" style={{ animation: "vn-drift 38s ease-in-out infinite alternate" }} />
          <div className="absolute inset-x-[-40%] bottom-[10%] h-1/2 bg-[radial-gradient(ellipse_at_center,#aab5c444,transparent_60%)]" style={{ animation: "vn-drift 52s ease-in-out -20s infinite alternate-reverse" }} />
        </>
      )}
      {kind === "stars" &&
        bits.map((r, i) => (
          <span key={i} className="absolute block rounded-full bg-[#f3e6cf]" style={{ left: `${r * 100}%`, top: `${((r * 997) % 1) * 38}%`, width: 2, height: 2, animation: `vn-twinkle ${2.5 + ((r * 19) % 4)}s ease-in-out ${-r * 6}s infinite` }} />
        ))}
      {kind === "dust" &&
        bits.map((r, i) => (
          <span key={i} className="absolute block rounded-full bg-[#ffe3b0]" style={{ left: `${r * 100}%`, top: `${40 + ((r * 991) % 1) * 55}%`, width: 3, height: 3, filter: "blur(.5px)", animation: `vn-dust ${9 + ((r * 23) % 9)}s ease-in-out ${-r * 14}s infinite` }} />
        ))}
    </div>
  );
}

/** Golden motes drifting up through stage light — the theatre's dust in the footlights. */
export function Motes({ on, count = 18 }: { on: boolean; count?: number }) {
  const bits = useMemo(() => Array.from({ length: count }, (_, i) => rnd(i + 101)), [count]);
  if (!on) return null;
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-[25] overflow-hidden">
      {bits.map((r, i) => {
        const size = 2 + ((r * 97) % 3);
        return (
          <span
            key={i}
            className="absolute block rounded-full"
            style={{
              left: `${4 + r * 92}%`,
              bottom: `${-4 + ((r * 7919) % 1) * 30}%`,
              width: size,
              height: size,
              background: "radial-gradient(circle, #fff1cc 0%, #f0c983 45%, transparent 70%)",
              boxShadow: "0 0 8px 2px #f0c98355",
              ["--dx" as string]: `${-30 + ((r * 613) % 1) * 60}px`,
              animation: `vn-mote ${12 + ((r * 37) % 10)}s ease-in-out ${-r * 22}s infinite`,
              willChange: "transform, opacity",
            }}
          />
        );
      })}
    </div>
  );
}

/** Kept for older callers. */
export const Petals = Motes;

/** Deterministic pseudo-random 0..1, so particles don't jump between renders. */
function rnd(i: number) {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}
