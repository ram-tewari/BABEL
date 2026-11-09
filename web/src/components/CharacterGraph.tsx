import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Network } from "lucide-react";
import { api, type Entity, type Graph } from "../lib/api";
import { cssColor } from "../lib/colors";
import { Empty, Modal, Spinner, cx } from "./ui";
import { CharacterPanel, useCast } from "./CastEditor";

interface P {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

/** Deterministic force layout (precomputed, no animation library). */
export function layout(g: Graph, w = 800, h = 560): Map<number, { x: number; y: number }> {
  const n = g.nodes.length;
  const pos = new Map<number, P>();
  g.nodes.forEach((node, i) => {
    const a = (i / Math.max(1, n)) * Math.PI * 2;
    pos.set(node.id, { x: w / 2 + Math.cos(a) * w * 0.3, y: h / 2 + Math.sin(a) * h * 0.3, vx: 0, vy: 0 });
  });
  const maxW = Math.max(1, ...g.edges.map((e) => e.weight));
  for (let it = 0; it < 300; it++) {
    const t = 1 - it / 300;
    for (const a of g.nodes) {
      const pa = pos.get(a.id)!;
      for (const b of g.nodes) {
        if (a.id >= b.id) continue;
        const pb = pos.get(b.id)!;
        let dx = pa.x - pb.x, dy = pa.y - pb.y;
        const d2 = Math.max(dx * dx + dy * dy, 25);
        const f = 4000 / d2;
        const d = Math.sqrt(d2);
        dx /= d; dy /= d;
        pa.vx += dx * f; pa.vy += dy * f; pb.vx -= dx * f; pb.vy -= dy * f;
      }
    }
    for (const e of g.edges) {
      const pa = pos.get(e.source), pb = pos.get(e.target);
      if (!pa || !pb) continue;
      const dx = pb.x - pa.x, dy = pb.y - pa.y;
      const d = Math.max(1, Math.hypot(dx, dy));
      const f = (d - 90) * 0.02 * (0.4 + e.weight / maxW);
      pa.vx += (dx / d) * f; pa.vy += (dy / d) * f; pb.vx -= (dx / d) * f; pb.vy -= (dy / d) * f;
    }
    for (const p of pos.values()) {
      p.vx += (w / 2 - p.x) * 0.01;
      p.vy += (h / 2 - p.y) * 0.01;
      p.x = Math.min(w - 30, Math.max(30, p.x + p.vx * t));
      p.y = Math.min(h - 30, Math.max(30, p.y + p.vy * t));
      p.vx *= 0.5;
      p.vy *= 0.5;
    }
  }
  return new Map([...pos].map(([id, p]) => [id, { x: p.x, y: p.y }]));
}

export function CharacterGraph({ novelId }: { novelId: number }) {
  const [minWeight, setMinWeight] = useState(2);
  const graph = useQuery({ queryKey: ["graph", novelId, minWeight], queryFn: () => api.graph(novelId, minWeight) });
  const cast = useCast(novelId);
  const [hover, setHover] = useState<number | null>(null);
  const [open, setOpen] = useState<Entity | null>(null);
  const pos = useMemo(() => (graph.data ? layout(graph.data) : new Map()), [graph.data]);
  const factions = useMemo(() => new Map((graph.data?.factions ?? []).map((f) => [f.id, f])), [graph.data]);

  if (graph.isLoading) return <Spinner />;
  const g = graph.data!;
  if (!g.nodes.length)
    return (
      <Empty icon={<Network size={40} />} title="No relationships yet">
        The graph links characters who talk in the same scenes. Transform a few chapters first.
      </Empty>
    );
  const maxLines = Math.max(1, ...g.nodes.map((n) => n.lines));
  const maxW = Math.max(1, ...g.edges.map((e) => e.weight));
  const linked = (id: number) => hover === null || hover === id || g.edges.some((e) => (e.source === hover && e.target === id) || (e.target === hover && e.source === id));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm text-muted">
        <span>Characters who speak in the same scenes. Bigger = more lines.</span>
        <label className="ml-auto flex items-center gap-2">
          min. shared scenes
          <input type="range" min={1} max={10} value={minWeight} onChange={(e) => setMinWeight(Number(e.target.value))} className="accent-[var(--accent)]" />
          <span className="w-4 tabular-nums">{minWeight}</span>
        </label>
      </div>
      <svg viewBox="0 0 800 560" className="w-full rounded-xl border border-line bg-surface" role="img" aria-label="Character relationship graph">
        {g.edges.map((e) => {
          const a = pos.get(e.source), b = pos.get(e.target);
          if (!a || !b) return null;
          const on = hover === null || hover === e.source || hover === e.target;
          return <line key={`${e.source}-${e.target}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--muted)" strokeOpacity={on ? 0.15 + (0.55 * e.weight) / maxW : 0.04} strokeWidth={1 + (3 * e.weight) / maxW} />;
        })}
        {g.nodes.map((n) => {
          const p = pos.get(n.id);
          if (!p) return null;
          const r = 8 + 18 * Math.sqrt(n.lines / maxLines);
          const faction = n.faction_id ? factions.get(n.faction_id) : undefined;
          return (
            <g
              key={n.id}
              transform={`translate(${p.x},${p.y})`}
              className={cx("cursor-pointer transition-opacity", !linked(n.id) && "opacity-25")}
              onMouseEnter={() => setHover(n.id)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(n.id)}
              onBlur={() => setHover(null)}
              onClick={() => setOpen(n)}
              onKeyDown={(e) => e.key === "Enter" && setOpen(n)}
              tabIndex={0}
              role="button"
              aria-label={`${n.name}, ${n.lines} lines`}
            >
              {faction && <circle r={r + 4} fill="none" stroke={cssColor(faction.color)} strokeWidth={2.5} />}
              <circle r={r} fill={cssColor(n.color)} stroke="var(--surface)" strokeWidth={2} />
              <text y={r + 14} textAnchor="middle" fontSize={12} fill="var(--text)" style={{ paintOrder: "stroke", stroke: "var(--surface)", strokeWidth: 3 }}>
                {n.name}
              </text>
              <title>{`${n.name}${n.note ? ` — ${n.note}` : ""}${faction ? ` (${faction.name})` : ""}`}</title>
            </g>
          );
        })}
      </svg>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open?.name ?? ""}>
        {open && <CharacterPanel character={cast.data?.find((c) => c.id === open.id) ?? open} novelId={novelId} cast={cast.data ?? []} onDone={() => setOpen(null)} />}
      </Modal>
    </div>
  );
}
