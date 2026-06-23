/**
 * CharacterGraph Page
 *
 * Interactive character relationship network built from the transformed
 * chapters. Nodes are characters (size ∝ how much they speak, colour by
 * faction or stable name hash); edges are chapter co-appearances (thickness ∝
 * weight). Click a node to inspect a character; the graph is spoiler-safe via
 * the optional `?upTo=` chapter limit.
 */

import { useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, type GraphNode } from '@/lib/api';
import { getCharacterColor } from '@/lib/style';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

const WIDTH = 900;
const HEIGHT = 640;
const CX = WIDTH / 2;
const CY = HEIGHT / 2;

function nodeColor(n: GraphNode): string {
  return n.color || getCharacterColor(n.name);
}

export function CharacterGraph() {
  const { novelId: novelIdParam } = useParams<{ novelId?: string }>();
  const [searchParams] = useSearchParams();
  const novelId = novelIdParam ? Number(novelIdParam) : undefined;
  const upTo = searchParams.get('upTo') ? Number(searchParams.get('upTo')) : undefined;

  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['character-graph', novelId, upTo],
    queryFn: () => api.getCharacterGraph(novelId, upTo),
  });

  // Lay characters out on a circle, biggest speakers first (most central arc).
  const layout = useMemo(() => {
    if (!data) return { positions: {} as Record<string, { x: number; y: number }>, maxLines: 1, maxWeight: 1 };
    const nodes = [...data.nodes].sort((a, b) => b.line_count - a.line_count);
    const positions: Record<string, { x: number; y: number }> = {};
    const n = Math.max(nodes.length, 1);
    const radius = Math.min(WIDTH, HEIGHT) / 2 - 70;
    nodes.forEach((node, i) => {
      const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
      positions[node.id] = {
        x: CX + radius * Math.cos(angle),
        y: CY + radius * Math.sin(angle),
      };
    });
    const maxLines = Math.max(1, ...nodes.map((d) => d.line_count));
    const maxWeight = Math.max(1, ...data.edges.map((e) => e.weight));
    return { positions, maxLines, maxWeight };
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8 text-center text-[var(--text-dim)]">
        Could not load the character graph.
      </div>
    );
  }

  if (data.nodes.length === 0) {
    return (
      <div className="p-8 text-center text-[var(--text-dim)]">
        No characters found yet. Process some chapters first.
      </div>
    );
  }

  const selectedNode = data.nodes.find((n) => n.id === selected) || null;
  const activeName = hovered || selected;
  const connected = new Set<string>();
  if (activeName) {
    for (const e of data.edges) {
      if (e.source === activeName) connected.add(e.target);
      if (e.target === activeName) connected.add(e.source);
    }
  }

  const isDim = (name: string) =>
    activeName != null && name !== activeName && !connected.has(name);

  return (
    <div className="mx-auto max-w-6xl p-4">
      <div className="mb-4 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Character Map</h1>
        <span className="text-sm text-[var(--text-dim)]">
          {data.nodes.length} characters · {data.edges.length} links ·{' '}
          {data.chapters_scanned} chapters scanned
          {upTo != null && ' (spoiler-safe)'}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]">
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-auto w-full">
            {/* Edges */}
            {data.edges.map((e, i) => {
              const a = layout.positions[e.source];
              const b = layout.positions[e.target];
              if (!a || !b) return null;
              const active =
                activeName != null && (e.source === activeName || e.target === activeName);
              return (
                <line
                  key={i}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={active ? 'var(--accent, #4f8cff)' : 'var(--border)'}
                  strokeOpacity={activeName == null ? 0.35 : active ? 0.9 : 0.06}
                  strokeWidth={1 + (e.weight / layout.maxWeight) * 5}
                />
              );
            })}

            {/* Nodes */}
            {data.nodes.map((node) => {
              const p = layout.positions[node.id];
              if (!p) return null;
              const r = 6 + (node.line_count / layout.maxLines) * 22;
              const dim = isDim(node.name);
              return (
                <g
                  key={node.id}
                  transform={`translate(${p.x}, ${p.y})`}
                  className="cursor-pointer"
                  opacity={dim ? 0.25 : 1}
                  onMouseEnter={() => setHovered(node.name)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setSelected((s) => (s === node.id ? null : node.id))}
                >
                  <circle
                    r={r}
                    fill={nodeColor(node)}
                    stroke={selected === node.id ? 'var(--text-primary)' : 'transparent'}
                    strokeWidth={2}
                  />
                  <text
                    y={-r - 4}
                    textAnchor="middle"
                    className="select-none text-[11px]"
                    fill="var(--text-secondary)"
                  >
                    {node.name}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Detail panel */}
        <aside className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
          {selectedNode ? (
            <div>
              <div
                className="text-lg font-bold"
                style={{ color: nodeColor(selectedNode) }}
              >
                {selectedNode.name}
              </div>
              {selectedNode.faction && (
                <div className="mt-0.5 text-sm font-medium text-[var(--text-dim)]">
                  {selectedNode.faction}
                </div>
              )}
              {selectedNode.description && (
                <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
                  {selectedNode.description}
                </p>
              )}
              <dl className="mt-3 space-y-1 text-sm text-[var(--text-secondary)]">
                <div className="flex justify-between">
                  <dt className="text-[var(--text-dim)]">Lines spoken</dt>
                  <dd>{selectedNode.line_count}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--text-dim)]">First seen</dt>
                  <dd>Chapter {selectedNode.first_chapter + 1}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--text-dim)]">Connections</dt>
                  <dd>{connected.size}</dd>
                </div>
              </dl>
              {selectedNode.aliases?.length > 0 && (
                <div className="mt-2 text-xs uppercase tracking-wide text-[var(--text-dim)]">
                  aka {selectedNode.aliases.join(', ')}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-dim)]">
              Hover to highlight a character's relationships. Click a node to pin its details here.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}

export default CharacterGraph;
